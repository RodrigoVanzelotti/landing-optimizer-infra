# Landing Optimizer V1 deployment

AI, API and dashboard releases are automated on successful merges to `main` through
GitHub Actions and Terraform. See [CI/CD operation and recovery](CI_CD.md).
The local deployment scripts below are retained for administrator bootstrap/recovery.

One Cloud Run service serves the existing Nest API and the built snippet SDK.
Another Cloud Run service serves the Next.js dashboard and proxies its `/api`
requests to the API so HTTP-only refresh cookies work on the dashboard's domain.
One PostgreSQL 16 Cloud SQL instance stores app data, events, page maps and shared
rate limits. Set `ANALYTICS_BACKEND=postgres` and omit `REDIS_URL`; caches become
cache misses and rate limits use atomic database counters. The existing ClickHouse
and Redis paths remain available for development and a future higher-volume release.

Project: `landing-optimizer-landing-page`, region: `southamerica-east1`.
Account: `rodrigovanzelotti@gmail.com`.
The existing landing-page Cloud Run service is outside this state and is unchanged.

## Infrastructure source

`vendor/modules` copies the Cloud Run, Secret Manager and Artifact Registry modules
from `C:/Users/Vanzelotti/Desktop/dev/personal-cloud-infrastructure/terraform/modules`
as read on 2026-11-10. The upstream repository has no HEAD commit yet. The only
module extension adds optional Cloud SQL socket mounts to Cloud Run. `main.tf`
composes these modules with Cloud SQL, the migration job and a dedicated runtime
identity. Provider versions and checksums come from the upstream lock file.

The original IaC directory is outside this session's writable roots. This folder
is a separately applied V1 stack; central YAML registration remains disabled.
Do not enable a second central stack managing these same resources without
migrating state. GCS state lives in
`gs://landing-optimizer-v1-tfstate-505424813528/landing-optimizer/v1`, with versioning
and public access prevention. Terraform rejects destructive changes in `deploy.py`.

## Deploy

Requires Python 3.12+, Terraform 1.16.6, gcloud and credentials for the account above.
No local Docker daemon is required. From this folder:

```powershell
python deploy.py
python deploy_dashboard.py
python onboard.py --smoke
python smoke_dashboard.py
# For another website:
python onboard.py --domain example.com
```

First-time project bootstrap (already performed for this deployment): enable
`run.googleapis.com`, `sqladmin.googleapis.com`, `artifactregistry.googleapis.com`,
`secretmanager.googleapis.com` and `cloudbuild.googleapis.com`. Create the state
bucket with uniform bucket-level access, public access prevention and versioning.
The build identity must be able to build, write images and write build logs.

The deployment builds a source allowlist from the two sibling repositories, runs
their type checks and full tests in Cloud Build, pins the resulting image digest,
runs Prisma migrations as a Cloud Run job, then updates the public API service.
Targeted Terraform applies establish infrastructure and run migrations before
the final complete apply. Re-running preserves secret version 1 and existing sites.
`release.auto.tfvars.json` records the current image and is ignored by Git.

On this Windows sandbox, provider installation cannot copy/link its downloaded
files. `tools/terraform.rc` selects the official 7.46.2 provider binary directly;
both Terraform and provider ZIPs were checked against HashiCorp SHA256SUMS.
This ignored workaround is local only. Normal machines use standard `terraform init`.

## Generate and install a snippet

The default hostname is the existing landing page's generated Google Cloud domain.
`onboard.py` logs in as the operator (registers on first run), reuses/creates the site
for the requested hostname and saves `install.html`. Paste its contents before
`</head>` on the target page. Nothing captures real visitor traffic until installed.
The site allows the HTTPS origin for that hostname. Add other origins with the
authenticated `POST /v1/sites/:id/origins` endpoint before installing there.

The operator password is in Secret Manager `lo-v1-operator-password`, version 1.
Database credentials, JWT secret and the site-signing encryption key also live in
Secret Manager; secret values are absent from Terraform state and the source bundle.
The runtime cannot read the operator-password secret. `install.html` contains only
the public ingest key and public signing key. Treat operator credentials as private.

`--smoke` checks all three SDK files, signed config, successful ingestion, persisted
analytics/heatmap reads and rejected origins. It deliberately stores synthetic
events at `/__deployment_smoke`; they appear in aggregate metrics. Results are saved
in ignored `smoke-result.json`, with no operator password or JWT.

## V1 limits and operations

- Cloud Run scales from zero to two instances, each with three database connections.
- Cloud SQL is a small zonal `db-f1-micro`, 10 GB SSD with automatic growth capped
  at 20 GB, daily backups, seven-day point-in-time recovery and deletion protection.
  It bills continuously and has no shared-core availability SLA. Upgrade the database
  before sustained traffic or production availability requirements.
- PostgreSQL analytics use ordinary indexed tables and views. Monitor database CPU,
  disk, latency and ingestion failures; move analytics to ClickHouse when needed.
- Event retention is currently manual: periodically run
  `DELETE FROM events WHERE event_time < now() - interval '180 days';` with an
  authorized SQL connection. Schedule maintenance before expanding traffic. Full
  disk can stop ingestion; storage failures return HTTP 503.
- No AI service, custom domain, CDN or new GitHub release automation is
  deployed. AI routes still require a separately configured AI service.
- Existing API dependencies have npm security advisories, including critical
  reports. This deployment does not upgrade the framework; resolve them before
  broader production rollout. Cloud Build runs tests but is not a security audit.
- The SDK uses best-effort sends without retry or durable buffering; visitors with
  blockers and transient failures may not be counted.

Roll back application code by setting `image` in `release.auto.tfvars.json` to a
previous tested digest, then applying a reviewed Terraform plan. Database migrations
are forward-only; inspect compatibility before rolling back. Never remove or rotate
`lo-v1-config-key` without a plan for existing encrypted signing keys.

## Verified deployment, 2026-11-10

- API: https://landing-optimizer-api-505424813528.southamerica-east1.run.app
- SDK: https://landing-optimizer-api-505424813528.southamerica-east1.run.app/v1/sdk/v0.1.0/lo.js
- Cloud Build: `3666d0dd-e28f-4af5-a43c-e31bfbea9110`, successful; snippet 42 tests,
  API 62 tests, both type checks and production builds passed.
- All three Prisma migrations applied successfully by execution
  `landing-optimizer-migrate-v1-8qk49`.
- Live smoke passed: SDK assets, signed config, persisted events, funnel, overview,
  sections, heatmap, CORS, rejected origins/keys, 32 KB event limit and SDK file allowlist.
- Final full Terraform plan: no changes. Existing landing-page revision remains
  `landing-optimizer-landing-page-00014-hp4`.
- Site: `01a1c67b-3f0c-7e50-8104-ae57bb0d2ab0`. `install.html` targets the existing
  landing page's Google-generated domain; onboarding allows both Cloud Run aliases.
  The snippet has not been installed into that website by this deployment.

Google references: [Cloud Run PostgreSQL connections](https://docs.cloud.google.com/sql/docs/postgres/connect-run)
and [Cloud SQL pricing and shared-core limits](https://cloud.google.com/sql/pricing?hl=en).

The dashboard is deployed at
https://landing-optimizer-dashboard-505424813528.southamerica-east1.run.app/login.
Build `2e6cf573-e597-4732-a0d0-f21e7d0247f3` passed 8 tests and the Next.js production
build. Live HTTP and headless browser checks passed login, refresh, overview and
sites. Sign in with `rodrigovanzelotti@gmail.com` and the application password from
Secret Manager `lo-v1-operator-password` version 1. The dedicated dashboard runtime
has no secret access or Cloud SQL connection. Its limits are 1 vCPU, 512 MiB,
0–2 instances and concurrency 20. Complete inventory and deployment records:
[GOOGLE_CLOUD_DEPLOYMENTS.md](../../GOOGLE_CLOUD_DEPLOYMENTS.md).
