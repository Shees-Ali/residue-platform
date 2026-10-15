# Demo script: one load from the farmer to settled, then a marketplace sale

Everything below runs on real data (Postgres, Firebase sign-in). Nothing is mocked in the browser.

## One-time setup
1. Firebase console: enable Google, Email/Password and Phone sign-in; add a phone **test number** (for example `+923001234567` with code `123456`). Add `localhost` under Authorized domains.
2. `api/.env`: `FIREBASE_PROJECT_ID`, `BOOTSTRAP_ADMIN_EMAILS` (your Google email), `AUTH_DISABLED=false`, and for demos `DISPATCH_LOOP_SECONDS=5` (offers move on without a Scheduler) and `OFFER_TTL_SECONDS=300` (five minutes to answer an offer). `web/.env`: the `VITE_FIREBASE_*` values.
3. `cd api && alembic upgrade head && python ../seed/seed.py` (villages, residues, seed factories). Run the API (`python start.py`) and the web app (`npm run dev`).

## The accounts (use different browser profiles, or sign out between steps)
| Role | Sign up with | What they need |
|---|---|---|
| Admin | Google, the email in `BOOTSTRAP_ADMIN_EMAILS` | nothing: admin at first sign-in |
| Factory | any email | Factory name, price, **rice straw** ticked, district and village (for example Lahore, Raiwind). Needs admin approval |
| Transporter | any email | phone, district and village near the farm. Needs admin approval |
| Farmer | any email | the phone **test number**, verified by the SMS code (`123456`) |
| Buyer | any email | name only |

## The walkthrough
1. **Admin** opens `/admin`: "Waiting for approval" lists the new factory and transporter. Approve both (transporter at tier 2 so it can carry 2.5 t).
2. **Farmer** at `/farmer`: Report residue (rice straw, 2.5 t, tomorrow, morning, Raiwind, Lahore). The request shows "Matched to <your factory>" and the expected payout.
3. **Factory** at `/factory`: "Awaiting escrow" shows the load. Fund escrow (confirm the amount). The nearest approved transporter is offered the load.
4. **Transporter** at `/transporter`: the offer appears with a countdown. Accept. (Pass sends it to the next transporter; if nobody answers, the loop moves it on.) Allow location when asked.
5. **Transporter**: Record pickup (photo, weight 2450, location is read from the phone), then drive on: the page shares your position every 15 s. Record delivery (photo, weight 2440).
6. **Admin** `/admin` "Live map" and **factory** "Track this load": the farm, the factory and the truck path on the map, with distance and arrival estimate.
7. **Factory** "At the weighbridge": look at the photos, optionally "Estimate grade" (needs a Gemini key, otherwise it says so), then Confirm weight (2480 kg).
8. **Farmer**: "Confirm your weight and payment" shows the final weight and what they will be paid. Yes, pay me. The job is settled.
9. **Everyone**: the transporter sees "Paid"; the factory opens Money for the load; the admin sees the ledger balanced and the tonnes counter up.
10. **Dispute path** (second load): the farmer presses Dispute with a reason. The money stays frozen, the admin sees it under "Needs a person" and resolves it.
11. **Marketplace**: the factory lists a product (My products). The buyer opens `/market`, adds it to the cart, places the order and sees the four-way split (farmer 50, factory 30, NGO 5, platform 15). The admin ledger still balances.

## If something does not move
- No offer appears for the transporter: the transporter is not approved, is too far, or the tier is too small for the load. Admin: Dispatch, "Send out again" after approving.
- Offers do not advance on their own: `DISPATCH_LOOP_SECONDS` is not set (or use "Move pending offers on now").
- Photo upload fails: the API must be running with no `STORAGE_BUCKET` (local disk store) and the file must be JPEG, PNG or WebP up to 5 MB.
- "Allow location access": the browser blocked location; allow it for localhost and try again.
- "Invalid token ... clock is behind": turn on automatic time in the operating system.

## Not covered here
The phone call (Twilio, Gemini Live): the same lot and the same confirmation can be made by voice later, through `/api/agent/*`, and land on these same screens.
