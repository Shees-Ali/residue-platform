#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd web && npm ci && npm run build)
firebase deploy --only hosting --config deploy/firebase.json --project "${PROJECT_ID:?set PROJECT_ID}"
