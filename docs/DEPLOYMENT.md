# Deployment Model — Landing Optimizer

> Status: Living document. Last updated: 2026-09-10.

## 1. Environments

| Env | Purpose | Infra |
| --- | --- | --- |
| **local** | Development | Docker Compose (Postgres, ClickHouse, Redis, Redpanda, API, AI, dashboard). |
| **staging** | Pre-prod validation | K8s/ECS namespace `staging`, separate DBs, synthetic traffic. |
| **production** | Live | K8s/ECS `prod`, multi-AZ, autoscaled, CDN for snippet+config. |

## 2. Local development (Docker Compose)

`landing-optimizer-infra/docker/docker-compose.yml` brings up the full stack:
- `postgres:16`, `clickhouse/clickhouse-server`, `redis:7`,
  `redpandadata/redpanda`, plus the API, AI, and dashboard services.
- Seed script creates a demo tenant + site + sample events.
- `make up` / `make down` / `make seed` wrappers.

For active development (Docker Compose 2.23+), `make watch` layers
`docker/docker-compose.watch.yml` over the base stack. API, AI, and dashboard
use Dockerfile `development` targets plus native framework reloaders. Compose
syncs source edits, restarts on configuration changes, and rebuilds on
dependency manifests or Dockerfile changes. API migration changes synchronize,
restart, and run idempotent Postgres/ClickHouse deploy commands. The snippet repo
has its own `docker-compose.watch.yml` for `tsup --watch` and demo-page sync.

## 3. Build & release

| Artifact | Pipeline |
| --- | --- |
| **Snippet SDK** | tsup build → versioned bundle → upload to CDN (`/sdk/vX.Y.Z/lo.js`) + `latest` channel; publish SRI hash. |
| **API** | Docker image → registry → deploy (rolling). Prisma migrate on release job. |
| **AI service** | Docker image → registry → deploy. |
| **Dashboard** | Next.js build → container or Vercel; env-scoped. |

Semantic versioning; snippet is **immutable per version** and pinned by
customers; `latest` is opt-in.

## 4. CI/CD (GitHub Actions)
- PR: lint, typecheck, unit tests, `npm audit`/`pip-audit`, build.
- main: build + push images, run migrations (guarded), deploy to staging,
  smoke tests, manual gate → production.
- OIDC to cloud (no static credentials). Signed artifacts.

## 5. Database migrations
- Postgres: `prisma migrate deploy` in a pre-deploy job; expand/contract pattern
  for zero-downtime (add columns before code, drop after).
- ClickHouse: idempotent SQL migration runner; additive changes preferred.

## 6. Deploy strategy
- **Rolling** for API/dashboard (readiness/liveness probes).
- **Blue/green** option for risky releases (traffic shift via LB/ingress).
- Snippet: additive CDN versions; never mutate a published version.

## 7. CDN for snippet & config
- Loader `lo.js` served from CDN with long cache + SRI.
- `GET /v1/config/:siteId` cached at edge (short TTL + stale-while-revalidate);
  invalidated on `config/publish`.

## 8. Observability — logging & error-tracing contract

All services ship logs to **one sink** (CloudWatch/Loki/Elastic/Datadog — any
JSON-lines collector). The contract below is what makes a failure traceable
across services; changes to it are breaking changes and belong in this doc.

### 8.1 Envelope (every line, every service)
One JSON object per line with the shared fields `timestamp`, `level`,
`service`, `logger`, and `event` (or `message` for framework output).
Emitters: `landing-optimizer-api` (Nest logger), `landing-optimizer-ai`
(JsonFormatter), `landing-optimizer-dashboard` (server + `/api/client-log`
relay for browser errors), `landing-optimizer-edge` (Worker `logEvent`, via
wrangler tail / Logpush). Business fields (`request_id`, `site_id`,
`tenant_id`, `status`, `duration_ms`, `dependency`, `reason`) are top-level
and queryable. Payloads, credentials, visitor IDs, and secrets are never
logged; untrusted values are control-char-stripped and length-capped.

### 8.2 Request-ID correlation (the trace)
One `X-Request-ID` follows a request through every hop:
1. **Edge Worker** accepts a safe incoming id or mints one, forwards it to the
   API, and echoes it on the response.
2. **API** (`requestIdOf`) reuses a safe incoming id or mints one, stamps it on
   every log line and the response header, and forwards it to the **AI
   service** (`AiClient` → `X-Request-ID` header).
3. **AI** middleware adopts it (`normalize_request_id`), logs with it, echoes
   it back.
4. **Dashboard** browser reports 5xx/network failures to `/api/client-log`
   carrying the `X-Request-ID` from the failed response.
Filtering the sink by one `request_id` therefore reconstructs the full
cross-service story of a failed request. (OpenTelemetry traces remain a
post-launch upgrade; the id-based trace is the launch mechanism.)

### 8.3 Single-record rule (no duplicate errors)
Exactly **one error/warn record per incident**, owned by a defined layer:
- **Global catchers own request-level failures.** API: `AllExceptionsFilter`
  logs one `request_failed` per failed request (`warn` <500, `error` ≥500).
  AI: FastAPI validation/HTTP/unhandled handlers do the same. Dashboard:
  window `error`/`unhandledrejection` listeners + the API-client hook relay
  browser errors. Edge: each handler logs its own rejection/forward failure.
- **Inner layers never log an error they rethrow.** If a layer has facts the
  filter can't see, it attaches them to the exception instead —
  `DependencyUnavailableException` carries `dependency`/`operation`/`reason`/
  `upstream_status`, and the filter merges them into its single record.
  (`AiClient` throws it; it does not log.)
- **Inner layers log only failures they swallow** (fail-soft paths where no
  exception propagates): `event_batch_dropped` / `page_map_dropped`
  (ingestion continues), `ingest_rejected` / `snapshot_rejected` (status
  mutated, not thrown), provider-fallback warns in the AI service, and
  connection-level `dependency_error` from the Redis client.
- `transaction_succeeded` is logged for control-plane mutations only;
  successful event ingestion is excluded to control volume.

### 8.4 Error-event vocabulary (alert on these)
`request_failed` (api/ai) · `event_batch_dropped`, `page_map_dropped`,
`ingest_rejected`, `snapshot_rejected`, `clickhouse_schema_outdated` (api) ·
`forward_failed`, `forward_rejected` (edge) · `api_request_failed`,
`api_unreachable`, `unhandled_error`, `unhandled_rejection` (dashboard relay)
· `dependency_error` (connection-level, api).

### 8.5 Metrics & alerting (next phase)
- OpenTelemetry → collector → traces/metrics; Prometheus + Grafana (RED
  metrics, ingestion lag, error budget); Sentry optional on top.
- Alerts: ingestion lag, 5xx rate, `event_batch_dropped` rate, config publish
  failures, queue depth, `clickhouse_schema_outdated`, AI provider errors.

## 9. Reliability
- SLOs: ingestion p99 < 50 ms; config availability 99.95%; dashboard 99.9%.
- Error budgets tracked; releases paused if budget exhausted.
- Backups: Postgres PITR (WAL) daily + retention; ClickHouse periodic backups
  of rollups; config regenerable from Postgres.
- DR: infra reproducible via Terraform; RPO ≤ 15 min, RTO ≤ 1 h.

## 10. Rollback
- App: redeploy previous image tag.
- DB: expand/contract makes forward-only safe; reversible migrations where
  feasible.
- Experiments: kill switch + `rollback` endpoint restores original DOM values.

## 11. Infra as code
- Terraform modules per environment in `landing-optimizer-infra/terraform`.
- K8s manifests / Helm in `landing-optimizer-infra/k8s`.
- Secrets via AWS Secrets Manager / Vault / Doppler (never in code).
