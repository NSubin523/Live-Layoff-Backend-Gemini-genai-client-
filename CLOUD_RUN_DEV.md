# Cloud Run development container

Prepared service name: `layoff-chat-dev`. Runtime project from signup:
`project-66f10582-7e37-4d2a-915`. Firebase project: `live-layoffs-tracker`.
Deployed October 13, 2026, in `us-east4`:
`https://layoff-chat-dev-241672723896.us-east4.run.app`.
Public `/health` returns 200, notifications return 404, and chat/history require
Firebase authentication. Logged-in Android chat generation still needs testing.
The service scales from zero to one instance and uses request-based CPU allocation.

GitHub is connected through Cloud Build connection `layoff-dev-github` in
`us-east4`. Trigger `layoff-chat-dev-main` watches exactly `^main$` in
`NSubin523/Live-Layoff-Backend-Gemini-genai-client-`.

Work goes into `develop`; pushes there do not deploy. Merge or push to `main` to
build the Dockerfile and deploy Python to the development URL automatically.
The pipeline preserves existing runtime settings and secrets, tags the image
with the Git commit SHA, and checks public `/health` after deployment. Production
is not configured. Check status under Google Cloud Console → Cloud Build →
Triggers / History in `us-east4`.

To deliberately deploy current local code manually:

```bash
bash scripts/deploy-dev.sh
```

The script preserves existing secrets and runtime configuration. If the CLI is
not on PATH, use `GCLOUD_BIN=/tmp/layoff-cloud-tools/google-cloud-sdk/bin/gcloud`
and `CLOUDSDK_CONFIG=/tmp/layoff-cloud-tools/config` from this chat, or install and
authenticate the official Google Cloud CLI. Temporary files may be removed by the
operating system. Manual deployment uses the local checkout regardless of its
branch, so it bypasses the usual `main` deployment workflow.

The Dockerfile runs Uvicorn on `0.0.0.0:$PORT` as a non-root user. Docker and
Google Cloud source upload ignore files exclude local secrets and virtualenvs.

Set `FIREBASE_PROJECT_ID=live-layoffs-tracker` and leave
`GOOGLE_APPLICATION_CREDENTIALS` unset on Cloud Run. Firebase then uses the
attached runtime service account. Grant that account the necessary Firestore
permissions in the existing Firebase project. Local development still accepts the
existing credentials file through `GOOGLE_APPLICATION_CREDENTIALS`.

Provide `GEMINI_API_KEY` from a dev Secret Manager secret. Chat uses the Gemini
Developer API client unless explicitly configured otherwise. The currently
registered Python routes do not use PostgreSQL; telemetry is owned by Spring.

`ENABLE_NOTIFICATION_SEND=false` is the container default. It removes the
unauthenticated `/api/v1/notifications/send` route while retaining chat and health
routes. Local execution defaults to enabling that route. Keep it disabled for an
internet-accessible deployment until an authorized sender mechanism is added.
FCM device tokens and topics identify message recipients, not authorized callers.

After deployment, verify `/health`, verify notification sending returns 404, and
test chat and history with a Firebase ID token from `live-layoffs-tracker`.
Using this Firebase project shares its existing data and users.

The full infrastructure checklist is in `CLOUD_RUN_DEV.md` in the Spring project.
