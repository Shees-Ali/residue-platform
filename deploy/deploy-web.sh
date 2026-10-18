#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd web && npm ci && npm run build)
# Hosting config is the root firebase.json (the CLI needs the public folder inside the config's directory).
firebase deploy --only hosting --project "${PROJECT_ID:?set PROJECT_ID}"
