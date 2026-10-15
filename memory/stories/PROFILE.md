# PROFILE - Edit my details; admin edits

**Why:** after signup a factory or transporter could change nothing, and the admin had no edit screen.

**Scope (confirmed 2026-10-16):** a Settings page for every role; edits apply at once (no re-approval, no pause switch); admin edits anyone's details, transporter tier and max load, and lot details until escrow is funded. Not included: revenue split settings, reference data, farmers editing lots.

**Endpoints:** `GET/PATCH /api/me/profile`, `GET/PATCH /api/users/{uid}/profile` (admin), `GET /api/users?q=`, `PATCH /api/lots/{id}` (admin). Rules: `validation-rules.md`, section "Edit my details, and admin edits".

**Data:** migration 0011 adds `district`, `village`, `updated_at` to `factories` and `transporters`.

**Done when:** a factory's new price and residues are used by the next lot's ranking while assigned jobs keep their locked price; a transporter's new base changes who is nearest; the admin can change a tier and re-rank an unfunded lot.

## Built
- 2026-10-16 API: migration 0011 (district, village, updated_at on factories and transporters; signup now stores them), `GET/PATCH /api/me/profile` (own row, any status except suspended can edit), `GET/PATCH /api/users/{uid}/profile` (admin; tier and max load), `GET /api/users?q=`, `PATCH /api/lots/{id}` (admin, until funded; re-ranks in place with `assignment_store.reassign_lot`, reports a dropped override). Unknown districts at signup now say "District must be one of ...". Tests: `api/tests/test_profile_edit.py` (43), role matrix updated.
- 2026-10-16 web: `/settings` page (My details in the nav for every role, links on the factory and transporter dashboards, an edit dialog on the pending page), shared `ProfileForm` (sends only changed fields, Reset, spinner), admin `People` section (search, role and status filters, edit dialog with tier and max load), admin lot `Edit` button and `LotEditDialog` (locked after funding). Tests: `web/src/components/live/profile.test.tsx` (24).

## Decided
- Edits apply at once: job price is locked at assignment, so edits only affect future lots and offers.
- No audit table; one log line per edit.

## Open
- Rows created before migration 0011 show the district and village as Not set until the person picks them once.
- Vehicle details, pause switch, revenue split settings, reference data editing.
