# AUTH. Sign in with the right role

**Status:** built, needs a live Firebase check (tokens, Google popup, phone SMS were mocked in tests)

## Spec
As a farmer, buyer, transporter, factory or admin, I want to sign in and see only what my role may use, so that money flows and personal data stay with the right people.

**Build:** Firebase Auth (Google, email/password) proves identity. The API owns roles and approval in `users`. Self-signup picks farmer, buyer, transporter or factory; transporters and factories wait for an admin; admin is granted only to `BOOTSTRAP_ADMIN_EMAILS` (verified). The web app guards pages and filters navigation by role; the API enforces every route.

## Acceptance criteria
- Done when: a new transporter signs up, waits on the pending page, is approved by an admin and then sees offers; a buyer cannot open admin pages or call admin routes; every dashboard route rejects the wrong role.

## Tests
- `api/tests/test_dashboard_auth.py` (token, status), `test_signup_and_approval.py` (signup, approval, farmers), `test_role_matrix.py` (every route x every role, anonymous, pending, Firebase token on service routes).
- `web/src/auth/*.test.*`, `web/src/App.test.tsx`, `web/src/components/fasalloop/approvals.test.tsx`.

## Built
- 2026-10-15 API: migration 0005; `verified_claims` and status-aware `current_user`; `GET /api/me`, `POST /api/me/register`; `GET /api/users` and approve, reject, suspend, reactivate; farmer-scoped `GET /api/lots`, `/{id}`, `/api/ledger/mine`; CORS via `CORS_ORIGINS`; `BOOTSTRAP_ADMIN_EMAILS`; tightened impact, products, jobs and orders (see decisions).
- 2026-10-15 web: `AuthProvider`, token middleware, `/login`, `/signup` (account then role step, farmer phone SMS), `/pending`, route guards, role-filtered nav, user chip and sign-out (demo switcher removed), pending-approvals table on the admin dashboard.

- 2026-10-15 web: toasts for all auth and API errors, TanStack Query layer, page, panel and button loaders (see the web state decision). API: token rejections are logged with the reason and a 10 s clock-skew allowance was added.

- 2026-10-15 validation pass on every wired field, API and web, per `memory/validation-rules.md` (explicit per-field errors, inline messages, toasts, spinners; 238 API and 124 web tests).

- 2026-10-15 fix: bootstrap admin granted on `/api/me` and gated routes (no role screen); loaders cover the whole real request, Google popup gets an explicit Cancel.

## Decided
See `decisions.md` entries of 2026-10-15 (auth and roles, farmer phone, real Firebase login in web, role-matrix findings).

## Open
- Try it against a real Firebase project: enable Google, Email/Password and Phone providers, set `VITE_FIREBASE_*`, `FIREBASE_PROJECT_ID`, `BOOTSTRAP_ADMIN_EMAILS`, and add a phone test number.
- Email verification, password reset and a way for a farmer to add a phone later are not built.
- Dashboards still run on the in-browser demo engine; only the approvals table uses the API. Wiring each dashboard to its endpoints is the next task.
- The web has a fixed list of districts and residue codes (`src/lib/places.ts`) until the API exposes them.

- 2026-10-16 (EV stories): events: `account.pending` (admins), `account.approved`, `account.rejected`, `account.suspended`, `account.reactivated` (the person; their screen re-reads who they are). See `EV2.md`.
