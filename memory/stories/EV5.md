# EV5. Safe and honest delivery

**Status:** built 2026-10-16 (API, Firestore, web and browser tests; live Firebase project not tried)

## Spec
Events reach only the right people, never block a request, never duplicate, and tell the truth about their state.

**Build:** `deploy/firestore.rules`, deterministic inbox doc ids, `delivered_at`, sweeper, 30-day TTL.

## Acceptance criteria
- Done when: Rules tests deny every cross-user read and every client write; a Firestore outage leaves requests succeeding and the retry delivers each notification once.

## Validation
Constraints and messages: `../validation-rules.md`, section "Events and notifications".

## Tests to write first
- Catalog table tests, event sequence, emulator fan-out, rules, Playwright e2e (see the plan milestones).

## Built so far
- 2026-10-16: Firestore: `deploy/firestore.rules` (only the owner reads `users/{uid}/inbox`, no client writes, everything else closed), TTL on `expires_at` (30 days). API: `app/services/inbox.py` (deterministic doc id, `delivered_at`, `sweep`, never fails a request); the dispatch tick and loop retry what failed. Tests: `test_inbox_delivery.py` (fake), `test_inbox_emulator.py` (real emulator), `web/tests/rules/inbox.rules.test.ts` (9 rule tests), `web/e2e/isolation.spec.ts` (Firestore answers 403 to another user, to nobody, and to every client write).

## Decisions
- Per-person Firestore inbox (`users/{uid}/inbox`), Postgres is the truth, in-app channel only. See `../decisions.md`, 2026-10-16 "Events, notifications and the Firestore inbox".

## Open
- SMS/WhatsApp for phone-only farmers and transporters (`TODO(EV-SMS)`), browser push, email, Urdu text, mute preferences, arrival alerts.
