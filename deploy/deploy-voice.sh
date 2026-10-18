#!/usr/bin/env bash
# Deploy the voice service to Cloud Run. Telnyx must reach it, so it is public;
# /telnyx/webhook verifies Telnyx's Ed25519 signature; /telnyx/media verifies our stream-URL HMAC.
# The voice SA gets run.invoker on the API only.
# WEB_ORIGIN=https://<project>.web.app is the page allowed to open the browser call (/phone).
# TELNYX_ENABLED=true also wires the paid phone line (secrets telnyx-api-key, telnyx-public-key,
# stream-secret); without it only the browser line runs and only gemini-api-key is needed.
set -euo pipefail
cd "$(dirname "$0")/.."
. deploy/env.sh

SECRETS="GEMINI_API_KEY=gemini-api-key:latest"
if [ "${TELNYX_ENABLED:-false}" = "true" ]; then
  SECRETS="$SECRETS,TELNYX_API_KEY=telnyx-api-key:latest,TELNYX_PUBLIC_KEY=telnyx-public-key:latest,STREAM_SECRET=stream-secret:latest"
fi

API_URL="$(gcloud run services describe "$API_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"

gcloud run deploy "$VOICE_SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" \
  --source voice \
  --service-account "$VOICE_SA" \
  --min-instances 0 --max-instances 2 \
  --allow-unauthenticated \
  --timeout 3600 \
  --update-env-vars "API_BASE_URL=$API_URL,BROWSER_CALLS_ENABLED=true,BROWSER_ALLOWED_ORIGINS=${WEB_ORIGIN:?set WEB_ORIGIN to the hosted web URL}" \
  --set-secrets "${SECRETS}"

# The service's own URL (Telnyx streams calls to <it>/telnyx/media) only exists after the first
# deploy, so it is set afterwards, every time (cheap, and correct on the very first deploy).
VOICE_URL="$(gcloud run services describe "$VOICE_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
if [[ -z "$VOICE_URL" ]]; then
  echo "error: could not read the voice service URL" >&2
  exit 1
fi
gcloud run services update "$VOICE_SERVICE" --project "$PROJECT_ID" --region "$REGION"   --update-env-vars "PUBLIC_BASE_URL=$VOICE_URL"
# F4 verification calls: the API dials through Telnyx and streams to this service.
# Set TELNYX_CONNECTION_ID and TELNYX_FROM_NUMBER (the Call Control app and its number) to enable.
if [[ -n "${TELNYX_CONNECTION_ID:-}" && -n "${TELNYX_FROM_NUMBER:-}" ]]; then
  gcloud run services update "$API_SERVICE" --project "$PROJECT_ID" --region "$REGION"     --update-env-vars "VOICE_STREAM_URL=${VOICE_URL/https:/wss:}/telnyx/media,TELNYX_CONNECTION_ID=$TELNYX_CONNECTION_ID,TELNYX_FROM_NUMBER=$TELNYX_FROM_NUMBER"     --update-secrets "TELNYX_API_KEY=telnyx-api-key:latest,STREAM_SECRET=stream-secret:latest"
fi
echo "Voice service: $VOICE_URL"
echo "Point the Telnyx Call Control app's webhook at: $VOICE_URL/telnyx/webhook"
