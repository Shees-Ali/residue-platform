# residue-platform

Crop-residue marketplace demo. Farmers phone in (Urdu, Telnyx + Gemini Live; a browser call page is the fallback); the API assigns a factory, dispatches transporters, runs a simulated escrow ledger and splits revenue. Synthetic data only.

| Project | What | Runs on |
|---|---|---|
| [web/](web/) | React 18, Vite, Tailwind, Firebase, Leaflet | Firebase Hosting |
| [api/](api/) | FastAPI, Pydantic v2, PostgreSQL | Cloud Run |
| [voice/](voice/) | ADK voice agent: Telnyx phone line and browser mic fallback. No database access | Cloud Run |
| [deploy/](deploy/), [seed/](seed/), [scripts/](scripts/) | deploy scripts, synthetic data, CI checks | |
| [memory/](memory/) | project memory: plan, stories, decision log (source of truth) | |

## Quick start
```
# once per project
cd api   && pip install -e ".[dev]"
cd voice && pip install -e ".[dev]"
cd web   && npm install

# run (one terminal each)
cd api   && python start.py   # :8000
cd voice && python start.py   # :8001
cd web   && npm run dev       # :5173

# test
cd api   && pytest -m "not tdd"   # tdd-marked failing tests excluded; see below
cd voice && pytest
cd web   && npm test

# deploy (needs gcloud + firebase CLIs, PROJECT_ID set; bash or Git Bash)
bash deploy/deploy-api.sh && bash deploy/deploy-voice.sh && bash deploy/deploy-web.sh
```
Each project has `.env.example`, a health route (`/health`) and its own README, AGENTS.md and CLAUDE.md. Agents: read [AGENTS.md](AGENTS.md) and [memory/](memory/) first.

## Tests first
Failing-by-design tests (marker `tdd`) exist for the A3 ledger check, FA3 revenue split, A2 offer expiry and A1 factory scoring: `cd api && pytest -m tdd`. CI runs them as a non-blocking job.

## User stories
Details, status and decisions: [memory/user-stories.md](memory/user-stories.md). Code TODOs reference these IDs, e.g. `TODO(F1)`.

- **F1** Report residue by call. Done when: a spoken call produces a complete lot in the database and the agent reads the details back.
- **F2** Hear the price and terms. Done when: the quote on the call matches the ledger entries created later.
- **F3** Reach a person when stuck. Done when: an unclear or upset call appears in the queue within seconds.
- **F4** Confirm delivery and payment. Done when: a yes completes verification and releases the payout, and a dispute freezes it and alerts the admin.
- **T1** Find and accept a job. Done when: two simultaneous accepts produce one winner and the other sees the offer withdrawn.
- **T2** Prove delivery and get paid. Done when: the payout shows as pending until the factory confirms, then as released.
- **FA1** Fund escrow for assigned lots. Done when: a job cannot be offered to transporters until it is funded.
- **FA2** Confirm weight and grade. Done when: confirmation sets the final weight and moves the job on, and a rejection records the reason and applies the pre-agreed cost rule.
- **FA3** List products and see the split. Done when: a test sale shows the four-way split adding to 100%.
- **A1** Assign the factory. Done when: every new lot gets a ranked list and a chosen factory within seconds.
- **A2** Watch jobs and handle escalations. Done when: an unanswered offer moves to the next transporter without anyone clicking.
- **A3** Run the ledger and impact numbers. Done when: the check passes in unit tests and on screen, and the counter rises at settlement.
- **B1** Browse and order products. Done when: an order reduces stock and creates the sale record that feeds the split.
