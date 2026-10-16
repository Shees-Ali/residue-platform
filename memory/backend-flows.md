# Backend flows spec (stories A1, FA1, A2, T1, T2, FA2, F2, F3, F4, A3, FA3, B1)

Written 2026-10-14, after F1. Source of truth for the order of work. Per-story status stays in `stories/`.
Assumptions marked **(assumed)** were not specified by the plan; they are logged in `decisions.md` and are constants in `app/config.py` so they are easy to change.

## Money model (assumed)
All integers, minor units (paisa). Shares are basis points summing to 10000.
- `gross = round(weight_kg * quoted_price_per_tonne / 1000)`. At funding the weight is `est_weight_kg`; at settlement it is `final_weight_kg`.
- Shares of gross: **farmer 7000, transporter 2000, platform 1000** (config `SHARE_*_BPS`; farmer gets the remainder). Parts come from `revenue_share.split` (largest remainder), so they sum to gross exactly.
- Escrow: factory funds `gross(est)` (`escrow_in`). At settlement, if `gross(final)` is higher the difference is topped up (`escrow_in`), if lower it is returned (`refund`). Then `release_farmer`, `release_transporter`, `platform_fee` equal `gross(final)`; the ledger check (`escrow_in == releases + fees + refunds`) holds.
- Rejection by the factory (pre-agreed cost rule): transporter is paid their estimated share (`release_transporter`), the rest of escrow is refunded (`refund`), farmer gets nothing, lot becomes `rejected`.
- Dispute by the farmer: payout is frozen (no ledger rows), job state `disputed`, admin alerted. Resolution flow is roadmap.
- Offer `payout_amount` = transporter share of the estimated gross (an estimate; final pay follows the final weight).

## Job state machine (pure, `app/services/job_states.py`)
`created -> funded -> offered -> accepted -> picked_up -> delivered -> confirmed -> settled`
Side: `offered -> funded` (ladder exhausted, needs a person), `delivered -> rejected`, `confirmed -> disputed`.
`verified` is stamped (`verified_at`) in the same transaction that settles; the state goes `confirmed -> settled`. Every transition is guarded in SQL (`UPDATE ... WHERE state = :expected`), zero rows means someone else got there first (409).

## Dispatch (assumed)
- Eligible transporter: `approved_at` set and `max_tonnes >= lot tonnes`. Ranked by haversine distance to pickup. Tier sets `max_tonnes`: tier 1 = 3 t, tier 2 = 7 t, tier 3 = 15 t.
- One offer at a time, `OFFER_TTL_SECONDS` (default 120). `POST /api/dispatch/tick` expires pending offers past `expires_at` and offers the next untried transporter; admin may pass `force=true` (demo fast-forward) to expire all pending now. Ladder exhausted: job returns to `funded`, an event is published, admin sees `offers_exhausted`.
- Accept is an atomic `UPDATE offers ... WHERE status='pending' AND expires_at > now()`; the job moves only if still `offered`.

## Auth for dashboards (assumed)
Firebase ID token verified with `google.oauth2.id_token.verify_firebase_token`; uid looked up in `users` (role from the table, not custom claims). `AUTH_DISABLED=true` (never on Cloud Run) lets tests pick an identity with `X-Dev-Uid`, default a seeded admin. Ownership: transporter routes use `transporters.user_uid`, factory routes use `factories.user_uid`.

## Slices, endpoints and done-when
1. **Pure modules (tests exist, remove `tdd` marker):** A1 `score_factory/rank_factories/haversine_km`, A2 `is_offer_expired/tick/next_transporter`, A3 `escrow_balanced`, FA3 `split`. Add `rank_transporters` and `job_states` with tests.
2. **Dashboard auth:** `current_user` / `require_role`, seed users, `X-Dev-Uid` in bypass mode.
3. **A1 assignment:** `services/assignment_store.py` runs after a lot is created (same transaction): writes `factory_candidates` (ranked), creates the `job` (`created`) with quoted price, `farmer_share_bps`, `est_weight_kg`; no eligible factory leaves the lot `open`. `GET /api/lots`, `/{id}`, `/{id}/ranking`, `POST /{id}/override` (admin, reason required, logged on the candidate row).
4. **FA1 funding:** `GET /api/jobs` (role-scoped), `GET /{id}`, `POST /api/jobs/{id}/fund` (owning factory): `escrow_in`, `funded`, then starts dispatch. Done when an unfunded job cannot get offers.
5. **A2/T1 dispatch:** `POST /api/dispatch/tick`, `GET /api/offers` (own), `POST /api/offers/{id}/accept`. Done when an expired offer moves to the next transporter and two concurrent accepts give one winner.
6. **T2 delivery:** `POST /api/jobs/{id}/photos/upload-url` (signed URL, fake in dev), `POST /{id}/pickup`, `POST /{id}/deliver` (transporter; photo path + weight), `GET /api/ledger/mine` (payout pending until settled, then released).
7. **FA2 weigh and confirm:** `POST /api/jobs/{id}/grade` (Gemini behind an interface, labeled estimate, stored in `grades`), `POST /{id}/confirm` (factory: final weight + accept, or reject with reason + cost rule).
8. **F4 verification and settlement:** `/api/agent/confirmations` (yes -> settle, no -> disputed), `POST /api/jobs/{id}/verification-call` (admin demo button: creates a `verification` call row; Twilio dial is voice-plan work), `services/settlement.py`.
9. **F2 quote:** `/api/agent/quote` returns price per tonne, shares, payment timing, computed with the same functions settlement uses so quote and ledger agree.
10. **F3 escalations:** `/api/agent/escalations`, `GET /api/escalations`, `POST /{id}/resolve` (admin).
11. **A3 ledger and impact:** `GET /api/ledger` (admin), `/check` (per-job and global), `GET /api/impact` (tonnes of settled jobs).
12. **FA3/B1 market:** `GET/POST /api/products`, `PATCH`, `POST /api/orders` (atomic stock decrement, `sale_splits` via `split`, ledger `order` entries), `GET /api/orders/{id}/split`.

## Not in this spec
Twilio outbound dialing, Cloud Storage client, real payments, dispute resolution, web UI, deploy.

## Status (2026-10-14)
Slices 1 to 12 are built on the API with tests (167 API tests, 14 voice tool tests). Deviations from the spec above: the transporter is paid at factory confirmation, not at settlement (see decisions); `GET /api/ledger/mine` serves transporters only; added `POST /api/jobs/{id}/redispatch`, transporter approve/revoke, and tick dispatch of waiting jobs; `verified` state unused.
Not verified against real services: Firebase ID tokens, Cloud Scheduler OIDC, Cloud Storage signed URLs, Gemini grading, the Firestore events writer (`FIRESTORE_EVENTS=1`). Not built: web UIs, Twilio webhook and outbound verification dial, deploy changes (new env vars are in `api/.env.example`), admin resolution of disputes.

## Events, notifications and live updates (EV1 to EV7)
Every business change calls `notify.emit(db, type, ...)` inside its transaction: one `events` row (the fact) and one `notifications` row per person the catalog (`app/services/notify_catalog.py`) says should hear about it. The actor is not told of their own act, except for money and matching results. After the commit, `inbox.commit_and_deliver` mirrors each new notification to Firestore `users/{uid}/inbox`; a failed mirror leaves `delivered_at` empty and the request still succeeds. `POST /api/dispatch/tick` (Cloud Scheduler, or `DISPATCH_LOOP_SECONDS` locally) retries the failed ones and checks the ledger (`ledger.unbalanced`). Switch the mirror on with `FIRESTORE_EVENTS=1`; `GET /api/me` tells the web (`live_updates`). Routes: `GET /api/notifications`, `/unread-count`, `POST /{id}/read`, `/read-all`, `GET /api/jobs/{id}/events`.
Tests: `pytest` (545, no Firestore), `firebase emulators:exec --only firestore ... "pytest -m emulator"` (real Firestore emulator), `npm run test:rules`, `npm run e2e` (real browsers).
