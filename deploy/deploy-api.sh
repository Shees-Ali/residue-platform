#!/usr/bin/env bash
# Deploy the API to Cloud Run. Needs: gcloud logged in, PROJECT_ID set.
# API_PUBLIC=true (default): reachable by browsers; auth is enforced in the app (Firebase / Google ID tokens).
# API_PUBLIC=false: IAM-only; only service accounts with run.invoker can call it.
set -euo pipefail
cd "$(dirname "$0")/.."
. deploy/env.sh

AUTH_FLAG="--allow-unauthenticated"
[ "${API_PUBLIC:-true}" = "false" ] && AUTH_FLAG="--no-allow-unauthenticated"

gcloud run deploy "$API_SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" \
  --source api \
  --service-account "$API_SA" \
  --min-instances 0 --max-instances 2 \
  $AUTH_FLAG \
  --update-env-vars "FIREBASE_PROJECT_ID=$PROJECT_ID,VOICE_SERVICE_ACCOUNT=$VOICE_SA"
# --update (not --set) keeps the Telnyx settings deploy-voice.sh adds for F4 dial-out.

# Only the voice service account may invoke the API through IAM.
gcloud run services add-iam-policy-binding "$API_SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:$VOICE_SA" --role roles/run.invoker
