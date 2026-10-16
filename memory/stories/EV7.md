# EV7. End-to-end proof

**Status:** built 2026-10-16 (API, Firestore, web and browser tests; live Firebase project not tried)

## Spec
As the team, one command proves the whole story from lot to settled, with events, notifications and live updates for every role.

**Build:** Playwright specs in `web/e2e/`, emulator tests (`pytest -m emulator`), rules tests (`npm run test:rules`).

## Acceptance criteria
- Done when: `npm run e2e` is green on the emulators, and the API-level event-sequence test is green in `pytest`.

## Validation
Constraints and messages: `../validation-rules.md`, section "Events and notifications".

## Tests to write first
- Catalog table tests, event sequence, emulator fan-out, rules, Playwright e2e (see the plan milestones).

## Built so far
- 2026-10-16: `cd web && npm run e2e` (11 browser tests on the Auth and Firestore emulators and a throwaway `residue_e2e` database: five browsers through a whole lot, isolation, dispute, fallback, signup resume), `npm run test:rules`, `firebase emulators:exec ... pytest -m emulator`, and `pytest` (545 tests). `scripts/with-emulators.mjs` stops the emulators afterwards (on Windows they otherwise keep running and block the next run).

## Decisions
- Per-person Firestore inbox (`users/{uid}/inbox`), Postgres is the truth, in-app channel only. See `../decisions.md`, 2026-10-16 "Events, notifications and the Firestore inbox".

## Open
- SMS/WhatsApp for phone-only farmers and transporters (`TODO(EV-SMS)`), browser push, email, Urdu text, mute preferences, arrival alerts.
