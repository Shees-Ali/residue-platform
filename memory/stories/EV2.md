# EV2. Be told when it is my turn

**Status:** built 2026-10-16 (API, Firestore, web and browser tests; live Firebase project not tried)

## Spec
As a farmer, factory, transporter, buyer or admin, I get a short message when something happens that I need to know or act on (lot, offer, job, escalation, ledger, order and account events).

**Build:** `notifications` table, `app/services/notify.py` (catalog, recipients, text, `emit`), `test_event_sequence.py`.

## Acceptance criteria
- Done when: After each step of the end-to-end flow, each person's inbox holds exactly the messages the catalog lists for them, and nobody else's.

## Validation
Constraints and messages: `../validation-rules.md`, section "Events and notifications".

## Tests to write first
- Catalog table tests, event sequence, emulator fan-out, rules, Playwright e2e (see the plan milestones).

## Built so far
- 2026-10-16: API: `app/services/notify_catalog.py` (31 event types, who hears what, the text, what to refresh), `app/services/notify.py` (`emit`: event plus one notification per person, inside the caller's transaction; the actor is not told of their own act unless the message is a money or matching result), emit calls in the services (funding, dispatch, delivery, settlement, escalations, assignment) and routers (lots, orders, users, transporters, signup). Tests: `test_notify_catalog.py` (every type complete, every message within 80/240 characters, no phone or email possible, web list equals catalog), `test_event_sequence.py` (what each person holds after every step), `test_event_flows.py` (unmatched, ladder, decline, accounts, orders, low stock, edits, escalation, ledger alert, refused steps leave nothing).

## Decisions
- Per-person Firestore inbox (`users/{uid}/inbox`), Postgres is the truth, in-app channel only. See `../decisions.md`, 2026-10-16 "Events, notifications and the Firestore inbox".

## Open
- SMS/WhatsApp for phone-only farmers and transporters (`TODO(EV-SMS)`), browser push, email, Urdu text, mute preferences, arrival alerts.
