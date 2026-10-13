# Source this file: `. deploy/env.sh`. Override via environment before sourcing.
export PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
export REGION="${REGION:-asia-south1}"
export API_SERVICE="${API_SERVICE:-residue-api}"
export VOICE_SERVICE="${VOICE_SERVICE:-residue-voice}"
export API_SA="residue-api@${PROJECT_ID}.iam.gserviceaccount.com"
export VOICE_SA="residue-voice@${PROJECT_ID}.iam.gserviceaccount.com"
