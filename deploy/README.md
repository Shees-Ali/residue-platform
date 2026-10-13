# deploy

Prereqs: `gcloud` and `firebase` CLIs logged in; secrets `twilio-auth-token`, `gemini-api-key` in Secret Manager; service accounts `residue-api` and `residue-voice` created.

```
export PROJECT_ID=your-project
bash deploy/deploy-api.sh && bash deploy/deploy-voice.sh && bash deploy/deploy-web.sh   # from repo root; or run any one
```

- Cloud Run: `--min-instances 0 --max-instances 2` for both services (free-tier safety). Set a budget alert.
- The voice service account gets `roles/run.invoker` on the API service only.
- API ingress is public by default (browser dashboards); see the open decision in `memory/decisions.md`.
