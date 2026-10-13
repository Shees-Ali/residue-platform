# AGENTS.md - web

Read `../AGENTS.md` first, then `../memory/implementation-plan.md` and the story file you are working on.

## Commands
- `npm install`; `npm run dev` (port 5173, proxies /api to :8000)
- `npm test`; `npm run lint`; `npm run build`
- `npm run gen:api` regenerates `src/api/schema.d.ts` from `openapi.json` (export with `python -m scripts.export_openapi ../web/openapi.json` in `api/`).

## Rules
- Routes: /admin, /transporter, /factory, /market, /call (+ /health). Roles come from Firebase ID token claims.
- Use the generated API client; do not hand-write request types.
- Keep Firestore listeners narrow (free-tier quotas). Maps: Leaflet + OpenStreetMap only.
- UI is not test-first; keep smoke tests green.
- Update the story file and `../memory/decisions.md` in the same commit.
