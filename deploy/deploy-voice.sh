#!/usr/bin/env bash
# Deploy the voice service to Cloud Run. Twilio must reach it, so it is public;
# /twilio/voice validates Twilio's signature. The voice SA gets run.invoker on the API only.
set -euo pipefail
cd "$(dirname "$0")/.."
. deploy/env.sh

API_URL="$(gcloud run services describe "$API_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"

gcloud run deploy "$VOICE_SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" \
  --source voice \
  --service-account "$VOICE_SA" \
  --min-instances 0 --max-instances 2 \
  --allow-unauthenticated \
  --timeout 3600 \
  --set-env-vars "API_BASE_URL=$API_URL" \
  --set-secrets "TWILIO_AUTH_TOKEN=twilio-auth-token:latest,GEMINI_API_KEY=gemini-api-key:latest"
