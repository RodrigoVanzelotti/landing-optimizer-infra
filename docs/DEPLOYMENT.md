# Deployment Model — Landing Optimizer

> Status: Living document. Last updated: 2026-07-02.

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

## 8. Observability & alerting
- OpenTelemetry → collector → traces/metrics.
- Prometheus + Grafana dashboards (RED metrics, ingestion lag, error budget).
- Sentry for API/dashboard/SDK errors (SDK errors sampled, scrubbed).
- Alerts: ingestion lag, 5xx rate, config publish failures, queue depth,
  ClickHouse insert failures, AI provider errors.

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
