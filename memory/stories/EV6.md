# EV6. Know when live updates are down

**Status:** built 2026-10-16 (API, Firestore, web and browser tests; live Firebase project not tried)

## Spec
As a person, I see when live updates are paused and that the page is refreshing every 30 s instead; as an admin, I see how many notifications are waiting to be delivered.

**Build:** `LiveProvider` health state, paused chip, `notifications_undelivered` in `GET /api/stats`.

## Acceptance criteria
- Done when: Blocking Firestore in the browser shows the chip and the screens still refresh; the admin stats show the undelivered count and it returns to 0.

## Validation
Constraints and messages: `../validation-rules.md`, section "Events and notifications".

## Tests to write first
- Catalog table tests, event sequence, emulator fan-out, rules, Playwright e2e (see the plan milestones).

## Built so far
- 2026-10-16: Web: a `Live updates paused` chip and a 30 s refresh when the listener is down, `<html data-live>` for inspection; admin overview shows how many notifications are waiting (`notifications_undelivered` in `GET /api/stats`). Tests: `live.test.tsx`, `bell.test.tsx`, `web/e2e/fallback.spec.ts` (Firestore blocked: chip shows, a new lot still appears within 30 s, unblocked: live again).

## Decisions
- Per-person Firestore inbox (`users/{uid}/inbox`), Postgres is the truth, in-app channel only. See `../decisions.md`, 2026-10-16 "Events, notifications and the Firestore inbox".

## Open
- SMS/WhatsApp for phone-only farmers and transporters (`TODO(EV-SMS)`), browser push, email, Urdu text, mute preferences, arrival alerts.
