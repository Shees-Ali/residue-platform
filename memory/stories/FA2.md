# FA2. Confirm weight and grade

**Status:** backend done (factory UI todo)

## Spec
As a factory, I weigh the lot at the gate and accept or reject it, with an AI grade to help.

**Build:** the API's grade endpoint takes the photos and returns a structured grade (residue type, moisture band, contamination flags, confidence), labeled a visual estimate. The factory enters the weighbridge weight and confirms or rejects with a reason.

## Acceptance criteria
- Done when: confirmation sets the final weight and moves the job on, and a rejection records the reason and applies the pre-agreed cost rule.

## Tests to write first
- Not test-first (UI / voice agent change too fast); add tests once the shape settles.

## Code TODO markers
- Search the repo for `TODO(FA2)`.

## Built so far

- 2026-10-14 backend: `POST /api/jobs/{id}/grade` (Gemini vision behind a `Grader` interface; stored in `grades`; always labelled a visual estimate), `POST /{id}/confirm` (accept with the weighbridge weight, or reject with a reason). Accept adjusts escrow to the final weight (top-up or refund) and pays the transporter; reject pays the transporter their estimated share, refunds the rest, marks the lot rejected.

- 2026-10-13 scaffold: services/grading.py grade_photos stub (Gemini vision) and jobs confirm/grade route stubs.
- 2026-10-13 scaffold: /factory page placeholder.

## Decisions
- None yet. Log repo-wide decisions in `../decisions.md`.

## Open
- `GeminiGrader` is not exercised against the live API (needs a key and real photos). Factory UI.

- 2026-10-16 end-to-end: web: weighbridge cards with the transporter photos, optional AI grade estimate, confirm weight and reject with a reason. Tests: `api/tests/test_e2e_flow.py` and the web panel tests.

- 2026-10-16 (EV stories): events: `job.confirmed` and `job.rejected` (farmer, transporter, admin). See `EV2.md`.
