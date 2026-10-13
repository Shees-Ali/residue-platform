# FA2. Confirm weight and grade

**Status:** todo

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

- 2026-10-13 scaffold: services/grading.py grade_photos stub (Gemini vision) and jobs confirm/grade route stubs.
- 2026-10-13 scaffold: /factory page placeholder.

## Decisions
- None yet. Log repo-wide decisions in `../decisions.md`.

## Open
- None yet.
