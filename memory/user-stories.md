# User stories

Source: [implementation-plan.md](implementation-plan.md). Per-story detail and status live in `stories/`.

Happy path: F1, F2, A1, FA1, T1, T2, FA2, F4, A3, FA3, B1. Side paths: F3, A2.
Job states: created, funded, offered, accepted, picked up, delivered, confirmed, verified, settled. Side states: expired offer, rejected lot, disputed.

| ID | Title | Status | Done when |
|---|---|---|---|
| [F1](stories/F1.md) | Report residue by call | built (API, tools, web form, `/phone` browser line; tried live on `/phone` 2026-10-16; Telnyx works but is not the demo line) | a spoken call produces a complete lot in the database and the agent reads the details back. |
| [F2](stories/F2.md) | Hear the price and terms | built (API, voice tool, web; tried live on `/phone` 2026-10-16) | the quote on the call matches the ledger entries created later. |
| [F3](stories/F3.md) | Reach a person when stuck | built (API, voice tool, web admin queue; tried live on `/phone` 2026-10-16) | an unclear or upset call appears in the queue within seconds. |
| [F4](stories/F4.md) | Confirm delivery and payment | built for the web (farmer confirms on the site); the phone verification call is not demoed (needs a paid Telnyx line) | a yes completes verification and releases the payout, and a dispute freezes it and alerts the admin. |
| [F5](stories/F5.md) | Check on my requests by phone | built (API route, voice tool, call-screen card); tests pass; a live /phone call pending | a caller asking about an earlier request hears its current stage, matching their web page. |
| [T1](stories/T1.md) | Find and accept a job | built (API and web) | two simultaneous accepts produce one winner and the other sees the offer withdrawn. |
| [T2](stories/T2.md) | Prove delivery and get paid | built (API and web) | the payout shows as pending until the factory confirms, then as released. |
| [FA1](stories/FA1.md) | Fund escrow for assigned lots | built (API and web) | a job cannot be offered to transporters until it is funded. |
| [FA2](stories/FA2.md) | Confirm weight and grade | built (API and web) | confirmation sets the final weight and moves the job on, and a rejection records the reason and applies the pre-agreed cost rule. |
| [FA3](stories/FA3.md) | List products and see the split | built (API and web) | a test sale shows the four-way split adding to 100%. |
| [A1](stories/A1.md) | Assign the factory | built (API and web) | every new lot gets a ranked list and a chosen factory within seconds. |
| [A2](stories/A2.md) | Watch jobs and handle escalations | built (API and web) | an unanswered offer moves to the next transporter without anyone clicking. |
| [A3](stories/A3.md) | Run the ledger and impact numbers | built (API and web) | the check passes in unit tests and on screen, and the counter rises at settlement. |
| [B1](stories/B1.md) | Browse and order products | built (API and web) | an order reduces stock and creates the sale record that feeds the split. |
| [AUTH](stories/AUTH.md) | Sign in with the right role | built (needs a live Firebase check) | a new transporter waits for approval, a buyer cannot open admin pages, and every API route rejects the wrong role. |
| [PROFILE](stories/PROFILE.md) | Edit my details; admin edits | built (API and web) | a factory's new price and residues rank the next lot, and the admin can edit anyone, tiers and unfunded lots. |
| [EV1](stories/EV1.md) | Record every business fact | built (API, Firestore rules, web, browser tests) | a job's timeline lists every step with time and actor, with no phone or email. |
| [EV2](stories/EV2.md) | Be told when it is my turn | built (API, Firestore rules, web, browser tests) | each role's inbox holds exactly the catalog messages after each step. |
| [EV3](stories/EV3.md) | See changes live | built (API, Firestore rules, web, browser tests) | a funded job appears on the transporter's board with no reload and no polling tick. |
| [EV4](stories/EV4.md) | A notification center | built (API, Firestore rules, web, browser tests) | bell, unread count, read and read-all agree across tabs and survive a reload. |
| [EV5](stories/EV5.md) | Safe and honest delivery | built (API, Firestore rules, web, browser tests) | rules deny cross-user reads and client writes; an outage loses nothing and delivers once. |
| [EV6](stories/EV6.md) | Know when live updates are down | built (API, Firestore rules, web, browser tests) | a paused chip shows and screens still refresh; admin sees the undelivered count. |
| [EV7](stories/EV7.md) | End-to-end proof | built (API, Firestore rules, web, browser tests) | `npm run e2e` and the event-sequence test are green. |
