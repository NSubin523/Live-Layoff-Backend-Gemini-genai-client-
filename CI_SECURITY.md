# CI and branch policy

Use feature branches for changes, open a PR into `develop`, then promote tested
changes from `develop` to `main` through a PR. A merge to `main` deploys the dev
Cloud Run service. `develop` never deploys. Production is not configured.

The CI workflow runs on PRs targeting `develop` or `main`, pushes to either branch,
manual dispatch, and a weekly scan. Its required status check is `CI gate`.
The gate fails when any job fails, is skipped, or is cancelled:

- Unit tests on Python 3.12 (the container runtime) and 3.14 (local development),
  plus `pip check`. Firebase and Gemini are mocked; CI needs no live credentials.
- Runtime Docker build and an import check ensuring chat/health exist and public
  notification sending stays disabled. Trivy scans runtime dependencies and OS
  packages. Fixable HIGH/CRITICAL vulnerabilities block merging; the full report
  includes lower-severity and unfixed findings for review.
- Gitleaks scans committed history for credentials.
- CodeQL security-extended analysis, with a SARIF gate that blocks security
  severity 7.0 or greater. Analysis failure or missing reports also blocks.

GitHub Actions are pinned to commit SHAs and default to a read-only token. CodeQL
alone gets permission to publish code-scanning results. Vulnerability reports
expire after seven days. No cloud runtime secrets are exposed to CI.

Dependabot proposes weekly pip, Docker, and GitHub Actions updates into `develop`;
updates still need to pass CI and be merged explicitly. Test-only dependencies
are listed in `requirements-test.txt` and are not installed in the runtime image.

Branch protection should require PRs, zero approving reviews, `CI gate`, an
up-to-date branch, and resolved review conversations. Apply it to admins as well,
and block force pushes and branch deletion. You can review and merge your own PR
after the checks pass; GitHub cannot count a self-approval as an approving review.

GitHub Actions CI is distinct from Cloud Build deployment checks. Requiring a
post-merge deployment as a pre-merge check would create a deadlock. Do not add
Cloud Build deployment statuses to the required branch checks.
