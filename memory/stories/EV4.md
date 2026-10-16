# EV4. A notification center

**Status:** built 2026-10-16 (API, Firestore, web and browser tests; live Firebase project not tried)

## Spec
As any person, I see a bell with an unread count, a list (newest first, unread marked), can open the related screen, mark one or all as read, and page back through history.

**Build:** `GET /api/notifications`, `/unread-count`, `POST /{id}/read`, `/read-all`, `NotificationBell`.

## Acceptance criteria
- Done when: Counts and read state agree across two browser tabs and survive a reload.

## Validation
Constraints and messages: `../validation-rules.md`, section "Events and notifications".

## Tests to write first
- Catalog table tests, event sequence, emulator fan-out, rules, Playwright e2e (see the plan milestones).

## Built so far
- 2026-10-16: API: `GET /api/notifications` (keyset paging, `unread_only`), `/unread-count`, `POST /{id}/read`, `/read-all`; someone else's id is a plain 404. Web: `NotificationBell` in the header (badge, list, Load older, mark one or all read, route per type via `lib/notifications.ts`). Tests: `api/tests/test_notifications_api.py`, `web/src/components/live/bell.test.tsx`, e2e step 6 (read state follows the person across tabs).

## Decisions
- Per-person Firestore inbox (`users/{uid}/inbox`), Postgres is the truth, in-app channel only. See `../decisions.md`, 2026-10-16 "Events, notifications and the Firestore inbox".

## Open
- SMS/WhatsApp for phone-only farmers and transporters (`TODO(EV-SMS)`), browser push, email, Urdu text, mute preferences, arrival alerts.
