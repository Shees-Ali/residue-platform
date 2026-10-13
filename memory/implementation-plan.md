# Technical Implementation Plan

Oct 13, 2026 · @Shees ali

React on Firebase Hosting, a FastAPI backend and an ADK voice agent on Cloud Run, and Firestore as the database. The demo takes a real phone call and runs on free tiers and trial credit, with simulated payments.

## Stack

Use React with TypeScript and Vite for the web app, one FastAPI backend in Python for the API, and a separate ADK voice agent in Python for phone calls. The API and the voice agent are two Cloud Run services built from one repo, so the voice agent can act only through the API and never touches the database. Everything except the web app is Python, so Pydantic models generate an OpenAPI spec and a typed React client, and pytest drives the test-first work. .NET and Node.js are not needed.

## Components

Eight parts, each with one job.

| Component | Tech | Runs on | Job |
| --- | --- | --- | --- |
| Web app | React, Vite, Tailwind, Leaflet | Firebase Hosting | One app with role routes: admin, transporter, factory, marketplace, and a browser call widget as a fallback |
| API | FastAPI, Pydantic, pytest | Cloud Run | Jobs, factory assignment, offer ladder, escrow ledger, revenue-share calculator, photo grading, and a small agent-only endpoint group |
| Voice agent | Google ADK, FastAPI WebSocket, Gemini Live | Cloud Run | Answers calls, talks to the farmer, and uses tools that call the API |
| Telephony | Twilio (trial) | Twilio | Receives the farmer's call and streams the audio to the voice agent |
| Database | Firestore | Firebase | Lots, jobs, offers, ledger and users, with live listeners that update the dashboards |
| Auth | Firebase Authentication, Google ID tokens | Firebase, Google Cloud | Email or Google sign-in for dashboards, and signed tokens between the voice agent and the API |
| Photo storage | Cloud Storage | Google Cloud | Lot and weighbridge photos |
| Scheduler | Cloud Scheduler | Google Cloud | One job that calls the API's tick endpoint to expire unanswered offers |

## Data and flows

Firestore holds ten collections: users, farmers, transporters, factories, lots, jobs, offers, ledger, products and orders. Five flows connect them.

1. **Intake.** The farmer calls the Twilio number. Twilio hits the voice agent's webhook and streams the call audio, and the voice agent passes it to Gemini Live through ADK. Tools call the API to create the lot and link the caller's phone number to a farmer record. The browser call widget uses the same agent as a fallback.
2. **Assignment.** The API scores factories by residue type accepted, distance (haversine in code) and price, then creates the job and an escrow-in ledger entry.
3. **Dispatch.** Offers go to ranked transporters one at a time, each with an expiry. The tick endpoint, or a demo fast-forward button, expires an offer and moves to the next transporter.
4. **Delivery.** The transporter uploads a photo and weight. The API's grading endpoint returns a structured grade (type, moisture band, contamination flags, confidence), and the factory confirms weight and grade.
5. **Settlement.** The API writes ledger entries that release the farmer, transporter and platform fee. The revenue-share calculator is a pure function with unit tests.

Rules for the voice agent: it reaches the API only through four tools (create lot, get quote, escalate, record confirmation), using a Google ID token plus the call ID. The API takes the farmer's identity from the call record, not from anything the model says, requires an idempotency key on writes, and decides whether money moves. The webhook verifies Twilio's signature, and the media stream carries a one-time token.

## User stories

Thirteen stories across five roles. The happy path runs F1, F2, A1, FA1, T1, T2, FA2, F4, A3, FA3, B1. F3 and A2 are the side paths. Each job moves through these states: created, funded, offered, accepted, picked up, delivered, confirmed, verified, settled. Side states are expired offer, rejected lot and disputed.

### Farmer

- **F1. Report residue by call.** As a farmer, I describe my residue by phone in Urdu so someone comes to collect it. *Build:* the call reaches the ADK voice agent through Twilio, or through the browser widget as a fallback. The agent calls a create\_lot tool (residue type, quantity, pickup window, and village and district matched to coordinates from a seeded list), and the API saves the lot. *Done when:* a spoken call produces a complete lot in Firestore and the agent reads the details back.
- **F2. Hear the price and terms.** As a farmer, I hear the price per tonne, when I get paid and my revenue share, so I can decide. *Build:* a quote\_price tool reads the assigned factory's delivered price and the stored split formula, and the agent says it in plain words. *Done when:* the quote on the call matches the ledger entries created later.
- **F3. Reach a person when stuck.** As a farmer, I can ask for a person when the agent can't help. *Build:* an escalate\_to\_human tool saves the transcript and a summary to an escalations collection, which shows in the admin queue. *Done when:* an unclear or upset call appears in the queue within seconds.
- **F4. Confirm delivery and payment.** As a farmer, I confirm the weight and the amount I will receive, so I know I was paid fairly. *Build:* after the factory confirms, the agent places a verification call through Twilio (in the demo, a button starts it) and records a yes or a dispute. *Done when:* a yes completes verification and releases the payout, and a dispute freezes it and alerts the admin.

### Transporter

- **T1. Find and accept a job.** As a transporter, I see jobs offered to me with pickup place, estimated weight, destination and pay, and accept before the offer expires. *Build:* each offer has an expiry. The dashboard listens to offers addressed to me, shows pickup and factory pins on a Leaflet map, and accepting runs as a Firestore transaction so only one transporter wins. *Done when:* two simultaneous accepts produce one winner and the other sees the offer withdrawn.
- **T2. Prove delivery and get paid.** As a transporter, I upload a photo and weight at pickup and delivery so my payout is clear. *Build:* photos go to Cloud Storage and the job moves from accepted to picked up to delivered. The payout view reads the ledger. *Done when:* the payout shows as pending until the factory confirms, then as released.

### Factory

- **FA1. Fund escrow for assigned lots.** As a factory, I see lots assigned to me and fund escrow so dispatch can start. *Build:* the dashboard lists jobs by state, and "fund escrow" writes an escrow-in ledger entry (simulated in the demo). *Done when:* a job cannot be offered to transporters until it is funded.
- **FA2. Confirm weight and grade.** As a factory, I weigh the lot at the gate and accept or reject it, with an AI grade to help. *Build:* the API's grade endpoint takes the photos and returns a structured grade (residue type, moisture band, contamination flags, confidence), labeled a visual estimate. The factory enters the weighbridge weight and confirms or rejects with a reason. *Done when:* confirmation sets the final weight and moves the job on, and a rejection records the reason and applies the pre-agreed cost rule.
- **FA3. List products and see the split.** As a factory, I list finished products for sale and see how each sale is split. *Build:* products and orders collections, and the revenue-share calculator that splits each sale among farmer, factory, NGO and platform. *Done when:* a test sale shows the four-way split adding to 100%.

### Admin

- **A1. Assign the factory.** As an admin, I want each lot matched to the best factory automatically, with the option to override. *Build:* the API scores factories by residue type accepted, distance (haversine in code) and price. The admin screen shows the ranked list, and overrides are logged. *Done when:* every new lot gets a ranked list and a chosen factory within seconds.
- **A2. Watch jobs and handle escalations.** As an admin, I follow every job live, handle escalations and approve transporters. *Build:* Firestore listeners drive the job list and escalation queue. Approving a transporter sets a tier that controls job size. The tick endpoint, or a demo fast-forward button, expires unanswered offers and moves to the next transporter. *Done when:* an unanswered offer moves to the next transporter without anyone clicking.
- **A3. Run the ledger and impact numbers.** As an admin, I see every payout and the tonnes kept out of burning. *Build:* ledger entries for escrow in, release to farmer, release to transporter, platform fee and refund, plus a check that escrow in equals everything released plus fees and refunds. An impact counter and a per-lot record (farmer, place, date, weight) give traceability. *Done when:* the check passes in unit tests and on screen, and the counter rises at settlement.

### Buyer

- **B1. Browse and order products.** As a buyer, I browse factory products and place an order. *Build:* a marketplace route reads products and writes orders. Payment is simulated, and export enquiries stay a roadmap item. *Done when:* an order reduces stock and creates the sale record that feeds the split.

Write tests first for the A3 ledger check, the FA3 split, the A2 offer expiry and the A1 scoring. Skip tests-first for the UI and the voice agent, which change too fast.

## Running free

Most of it can run free, with two exceptions: phone calls run on Twilio trial credit, and real payments need a licensed partner. Cloud Run and Cloud Storage need a billing account on file even within the free quota, so set a budget alert, keep max instances at 1 or 2 and min instances at 0. Free-tier limits change, so confirm each one on its pricing page before relying on it.

| Piece | Free path | Caveat |
| --- | --- | --- |
| Front end | Firebase Hosting | Static files only |
| API and voice agent | Cloud Run with scale to zero | Limited free quota, billing account required, cold starts delay the first request, and an open call keeps an instance running |
| Agent framework | ADK (open source) | None |
| Database | Firestore | Daily read and write quotas, so avoid chatty listeners |
| AI models | Gemini API key from AI Studio | Rate limits apply. Check that the Live API is on the free tier. Free-tier prompts may be used to improve Google products, so use synthetic data |
| Maps | Leaflet with OpenStreetMap tiles | Light demo use only. Skip Google Maps APIs |
| Phone calls | Twilio trial credit | Trial numbers accept calls only from verified caller IDs, and Pakistani number availability is unconfirmed. A call-back flow is the alternative |
| Payments | Simulated ledger | Real wallets and escrow need a licensed partner |

## Build order

Five days, riskiest piece first, assuming a submission on Oct 18 (the deadline is unconfirmed).

1. **Day 1.** Scaffold the repo with the prompt below. Set up the Firebase project and deploy empty web, API and voice services. Get a real phone call to greet you and answer back through Twilio, ADK and Gemini Live. Test Urdu, latency and interruptions. Fallback: the browser call widget.
2. **Day 2.** Add the agent tools and the API's agent endpoints so a call creates a lot, with the caller linked to a farmer. Covers F1 to F3.
3. **Day 3.** Build assignment, the offer ladder and the transporter board with live updates, including one transporter who does not respond. Covers A1, A2, FA1, T1 and T2.
4. **Day 4.** Build the factory dashboard, grading, the escrow ledger and the settlement screen with tonnes kept out of burning, plus the call-back verification call. Covers FA2, F4, A3, FA3 and B1.
5. **Day 5.** Polish the UI, write the demo script, record the three-minute video including the phone call, and write the proposal PDF. Keep half a day as buffer.

## Risks and fallbacks

The phone call is the riskiest part, so plan a fallback for it.

- **Phone leg fails or is too slow.** Fall back to the browser call widget, or record a real call early and show the tool calls on screen.
- **No Pakistani number.** Use a foreign number with your phone as a verified caller ID, or use the call-back flow.
- **Live voice is flaky or rate-limited.** Fall back to push-to-talk with speech-to-text, Gemini text and text-to-speech.
- **Language coverage.** Only Urdu is confirmed. Show other languages as roadmap unless you have tested them.
- **Photo grading overclaims.** Label it a visual estimate and require weighbridge confirmation.
- **Cost surprises.** Use a budget alert, max instances and no always-on instances.
- **Demo data.** Use synthetic data only.

## Scaffold prompt

Paste this into a coding agent in an empty folder. It creates the monorepo with stubs, tests and config only, and no business logic.

```
Create a monorepo named residue-platform with three projects and shared tooling.

web/ (React front end)
- React 18, TypeScript, Vite, Tailwind, React Router, Vitest.
- Routes: /admin, /transporter, /factory, /market, /call (browser call widget used as a fallback).
- Firebase Auth (email or Google) with role claims, Firestore live listeners for dashboards, Leaflet with OpenStreetMap for maps.
- Generate a typed API client from the API's OpenAPI spec with openapi-typescript.

api/ (FastAPI backend)
- Python 3.12, FastAPI, Pydantic v2, google-cloud-firestore AsyncClient, pytest, pytest-asyncio, ruff.
- Folders: app/routers, app/services, app/models, app/auth, tests.
- Routers: lots, jobs, offers, ledger, products, orders, dispatch (tick endpoint), agent.
- Services as pure, testable modules: assignment, dispatch, ledger, revenue_share, grading (Gemini vision).
- Auth: verify Firebase ID tokens for dashboard users, and verify Google ID tokens from the voice service for /api/agent/* routes.
- The agent routes allow only: create lot, get quote, escalate, record confirmation. Require an Idempotency-Key header on writes. Take the farmer's identity from the call record, never from request fields the model controls.
- Write failing tests first for revenue_share (splits always sum to 100%), the ledger check (escrow in equals releases plus fees plus refunds), offer expiry, and factory scoring. Add stubs only.
- Dockerfile for Cloud Run.

voice/ (ADK voice agent)
- Python 3.12, FastAPI, google-adk with bidirectional streaming (Gemini Live), httpx, pytest.
- Routes: POST /twilio/voice (validate the Twilio signature, return TwiML that opens a media stream), WS /twilio/media (Twilio Media Streams: convert 8 kHz mu-law to 16 kHz PCM for input, and 24 kHz PCM back to 8 kHz mu-law for output), WS /browser (browser mic fallback).
- One ADK agent named intake_agent with Urdu-first instructions and four tools: create_lot, get_quote, escalate_to_human, record_confirmation. Each tool is a plain function that calls the API over HTTPS with a Google ID token.
- Do not import Firestore or any database client in this project. Add a CI check that fails if it does.
- Dockerfile for Cloud Run.

Shared
- deploy/: firebase.json for web Hosting, and gcloud run deploy scripts for api and voice with max-instances 2 and min-instances 0. The voice service account gets run.invoker on the API only.
- seed/: a script that creates synthetic farmers, transporters and factories. No real data.
- Each project gets .env.example, a health route or page, and a README section. Root Makefile with dev, test and deploy targets. A GitHub Actions workflow that runs tests for all three projects.
- Root README lists user stories F1 to F4, T1, T2, FA1 to FA3, A1 to A3 and B1. Leave TODO comments that reference the story IDs.
- Create stubs, tests and config only. Do not implement business logic yet. Commit in small steps.
```

Run it on day 1, then follow the build order above.
