# EV1. Record every business fact

**Status:** built 2026-10-16 (API, Firestore, web and browser tests; live Firebase project not tried)

## Spec
As an admin (and the parties of a job, within what they may see), I see a timeline of what happened to a job and who did it.

**Build:** `events` table (migration 0012), `GET /api/jobs/{id}/events`, an Activity panel on admin and factory job cards.

## Acceptance criteria
- Done when: `GET /api/jobs/{id}/events` returns the ordered facts of a full run, each with time, actor role and a readable line, and none of them contains a phone number or email.

## Validation
Constraints and messages: `../validation-rules.md`, section "Events and notifications".

## Tests to write first
- Catalog table tests, event sequence, emulator fan-out, rules, Playwright e2e (see the plan milestones).

## Built so far
- 2026-10-16: API: `events` table (migration 0012, one immutable row per business fact, written in the same transaction as the change), `GET /api/jobs/{id}/events` (admin, owning factory, assigned transporter, the lot's farmer; each sees only events marked visible to their role; reads by the lot so the lot's own events come first). Web: an Activity button (`JobActivityButton`) on factory job cards and the admin lots table. Tests: `api/tests/test_event_sequence.py`, `test_event_flows.py`, `web/src/components/live/bell.test.tsx`, `web/e2e/full-flow.spec.ts` step 7.

## Decisions
- Per-person Firestore inbox (`users/{uid}/inbox`), Postgres is the truth, in-app channel only. See `../decisions.md`, 2026-10-16 "Events, notifications and the Firestore inbox".

## Open
- SMS/WhatsApp for phone-only farmers and transporters (`TODO(EV-SMS)`), browser push, email, Urdu text, mute preferences, arrival alerts.
