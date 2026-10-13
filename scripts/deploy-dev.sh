#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT=project-66f10582-7e37-4d2a-915
"${GCLOUD_BIN:-gcloud}" run deploy layoff-chat-dev \
  --project="$PROJECT" --region=us-east4 --source=. \
  --build-service-account="projects/$PROJECT/serviceAccounts/layoff-dev-builder@$PROJECT.iam.gserviceaccount.com" \
  --quiet
