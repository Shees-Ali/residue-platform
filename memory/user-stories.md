# User stories

Source: [implementation-plan.md](implementation-plan.md). Per-story detail and status live in `stories/`.

Happy path: F1, F2, A1, FA1, T1, T2, FA2, F4, A3, FA3, B1. Side paths: F3, A2.
Job states: created, funded, offered, accepted, picked up, delivered, confirmed, verified, settled. Side states: expired offer, rejected lot, disputed.

| ID | Title | Status | Done when |
|---|---|---|---|
| [F1](stories/F1.md) | Report residue by call | in progress (API + tools done, audio/Twilio left) | a spoken call produces a complete lot in the database and the agent reads the details back. |
| [F2](stories/F2.md) | Hear the price and terms | backend and voice tool done | the quote on the call matches the ledger entries created later. |
| [F3](stories/F3.md) | Reach a person when stuck | backend and voice tool done | an unclear or upset call appears in the queue within seconds. |
| [F4](stories/F4.md) | Confirm delivery and payment | backend and voice tool done | a yes completes verification and releases the payout, and a dispute freezes it and alerts the admin. |
| [T1](stories/T1.md) | Find and accept a job | backend done | two simultaneous accepts produce one winner and the other sees the offer withdrawn. |
| [T2](stories/T2.md) | Prove delivery and get paid | backend done | the payout shows as pending until the factory confirms, then as released. |
| [FA1](stories/FA1.md) | Fund escrow for assigned lots | backend done | a job cannot be offered to transporters until it is funded. |
| [FA2](stories/FA2.md) | Confirm weight and grade | backend done | confirmation sets the final weight and moves the job on, and a rejection records the reason and applies the pre-agreed cost rule. |
| [FA3](stories/FA3.md) | List products and see the split | backend done | a test sale shows the four-way split adding to 100%. |
| [A1](stories/A1.md) | Assign the factory | backend done | every new lot gets a ranked list and a chosen factory within seconds. |
| [A2](stories/A2.md) | Watch jobs and handle escalations | backend done | an unanswered offer moves to the next transporter without anyone clicking. |
| [A3](stories/A3.md) | Run the ledger and impact numbers | backend done | the check passes in unit tests and on screen, and the counter rises at settlement. |
| [B1](stories/B1.md) | Browse and order products | backend done | an order reduces stock and creates the sale record that feeds the split. |
