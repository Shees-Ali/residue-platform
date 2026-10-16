# EV3. See changes live

**Status:** built 2026-10-16 (API, Firestore, web and browser tests; live Firebase project not tried)

## Spec
As any signed-in person, my open screens update within about 2 seconds of a change, without refreshing.

**Build:** Firestore inbox listener (`LiveProvider`), `refresh` hints that invalidate TanStack Query keys, polling slowed to a safety net.

## Acceptance criteria
- Done when: In a browser, the factory funds and the transporter's offers board shows the new offer with no reload and no polling tick.

## Validation
Constraints and messages: `../validation-rules.md`, section "Events and notifications".

## Tests to write first
- Catalog table tests, event sequence, emulator fan-out, rules, Playwright e2e (see the plan milestones).

## Built so far
- 2026-10-16: Web: `live/LiveProvider.tsx` listens to `users/{uid}/inbox` (newest 20): the first server snapshot catches up silently, new docs toast and refetch the Query keys they name, `usePoll` slows every screen to a 60 s safety net while live and 30 s while paused. `GET /api/me` says whether the API mirrors (`live_updates`), so a screen never slows its polling for a mirror that is off. Tests: `web/src/live/live.test.tsx`, `web/e2e/full-flow.spec.ts` (five browsers, no reloads: the offer appears on the transporter's board the moment the factory funds).

## Decisions
- Per-person Firestore inbox (`users/{uid}/inbox`), Postgres is the truth, in-app channel only. See `../decisions.md`, 2026-10-16 "Events, notifications and the Firestore inbox".

## Open
- SMS/WhatsApp for phone-only farmers and transporters (`TODO(EV-SMS)`), browser push, email, Urdu text, mute preferences, arrival alerts.
