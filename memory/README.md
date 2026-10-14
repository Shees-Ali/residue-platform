# Project memory

Long-term memory and source of truth for residue-platform. Read before starting work; update after finishing it.

- [implementation-plan.md](implementation-plan.md) - the Technical Implementation Plan (stack, flows, build order, risks).
- [user-stories.md](user-stories.md) - story index with status.
- [stories/](stories/) - one file per story (F1-F4, T1-T2, FA1-FA3, A1-A3, B1): spec, acceptance criteria, status, decisions, open items.
- [data-model.md](data-model.md) - PostgreSQL schema, conventions and the Firestore events feed.
- [decisions.md](decisions.md) - append-only decision log.

Rules
- Before a story: read `implementation-plan.md` and the story file.
- After finishing or changing anything: update the story file (built, decided and why, still open) and the index status.
- Before coding a future story: write its spec here first (endpoints, data fields, done-when check, tests to write first).
- Commit memory updates in the same commit as the code they describe.
- No secrets and no real farmer data. Synthetic data only.
