# AGENTS.md - web

Read `../AGENTS.md` first, then `../memory/implementation-plan.md` and the story file you are working on.

## Commands
- `npm install`; `npm run dev` (port 5173, proxies /api to :8000)
- `npm test`; `npm run lint`; `npm run build`
- `npm run gen:api` regenerates `src/api/schema.d.ts` from `openapi.json` (export with `python -m scripts.export_openapi ../web/openapi.json` in `api/`).

## Rules
- Routes: /admin, /transporter, /factory, /farmer, /market, /call (admin desk), and the public pages /phone (demo phone, no sign-in), /login, /signup, /pending, /health. Sign-in is Firebase Auth; the role and approval status come from `GET /api/me` (the `users` table), never from token claims. Pages are guarded with `canAccess` in `src/lib/auth.ts`; the API enforces the same rules.
- Use the generated API client; do not hand-write request types.
- Keep Firestore listeners narrow (free-tier quotas). Maps: Leaflet + OpenStreetMap only.
- UI is not test-first; keep smoke tests green.
- Update the story file and `../memory/decisions.md` in the same commit.
- Validation first (see ../AGENTS.md): mirror the API constraints from `../memory/validation-rules.md` in `src/lib/validation.ts`, show them inline with `<Field>`, toast the summary, and map API `errors` back onto the fields.
