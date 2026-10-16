# deploy

Prereqs: `gcloud` and `firebase` CLIs logged in; secrets `twilio-auth-token`, `gemini-api-key` in Secret Manager; service accounts `residue-api` and `residue-voice` created.

```
export PROJECT_ID=your-project
bash deploy/deploy-api.sh && bash deploy/deploy-voice.sh && bash deploy/deploy-web.sh   # from repo root; or run any one
```

- Cloud Run: `--min-instances 0 --max-instances 2` for both services (free-tier safety). Set a budget alert.
- The voice service account gets `roles/run.invoker` on the API service only.
- API ingress is public by default (browser dashboards); see the open decision in `memory/decisions.md`.

## Firestore: the notification inbox (EV3, EV5)

Firestore holds only `users/{uid}/inbox/{notification id}`. The API writes it after each Postgres commit; the browser reads its own inbox (`deploy/firestore.rules`). Deploy the rules and the TTL policy with:

```
firebase deploy --only firestore --config deploy/firebase.json --project $PROJECT_ID
```

- Docs carry `expires_at` (30 days). `firestore.indexes.json` turns on the TTL policy for the `inbox` collection group; Firestore deletes expired docs on its own (free). Postgres keeps every notification.
- The API's service account (`residue-api`) needs `roles/datastore.user`. Set `FIRESTORE_EVENTS=1` on the API service to switch the mirror on.
- Cloud Scheduler already calls `POST /api/dispatch/tick`; that call also retries any notification whose mirror failed.
- Local tests and the browser end-to-end run against the emulators: `firebase emulators:exec --only firestore --config deploy/firebase.json --project demo-residue "..."` (needs Java; see `memory/demo-script.md`).
