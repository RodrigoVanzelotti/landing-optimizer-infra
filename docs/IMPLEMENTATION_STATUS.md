# Implementation Status — Landing Optimizer

> **Honest, living status.** Nothing is marked done unless it exists in code and
> has been validated (typecheck / tests / build). Last updated: 2026-07-04.

Legend: ✅ done & validated · 🟡 partial · ⛔ blocked · ⬜ missing

## Validation summary (this run)
| Repo | Typecheck | Tests | Build |
| --- | --- | --- | --- |
| snippet | ✅ `tsc --noEmit` clean | ✅ 15 pass (vitest) | ✅ `lo.js` 15.9 KB + `loader.js` 984 B |
| api | ✅ `tsc --noEmit` clean | ✅ 6 pass (vitest) | ✅ Prisma client generated |
| ai | ruff clean | ✅ 3 pass (pytest) | n/a |
| dashboard | ✅ `tsc --noEmit` clean | ⬜ (no unit tests yet) | ✅ `next build` 18 routes |
| infra | n/a | n/a | ✅ `docker compose config` valid |

## Completed ✅

### Design docs (`landing-optimizer-infra/docs`)
PRODUCT_REQUIREMENTS, ARCHITECTURE, DATABASE_SCHEMA, EVENT_SCHEMA,
API_CONTRACTS, SECURITY, DEPLOYMENT, ROADMAP, this status file.

### Snippet SDK (`landing-optimizer-snippet`)
- Async, fail-silent loader + full SDK bundle (tsup/IIFE, ~15.9 KB minified).
- Public API: `track`, `identifyCompanyContext`, `conversion`, queue drain.
- Privacy: short-lived per-tab session id, PII scrubbing, selector allowlist,
  HTML sanitizer, path/referrer-host only, coarse device/browser buckets.
- Behavioral tracking: page_view, scroll depth, CTA/dead/rage clicks, form
  start/submit, section visibility, dwell, dropoff.
- Sanitized DOM page-map builder (hero/CTA/pricing/testimonials/FAQ/nav/footer).
- Experiment engine: signed-config fetch, **Ed25519 signature verification**,
  deterministic sticky allocation, safe DOM apply ops, anti-flicker via observer.
- Tests: sanitize + experiments (bucketing, canonical JSON, applyChange). GTM +
  CSP install templates.

### API (`landing-optimizer-api`)
- NestJS + Fastify bootstrap, Helmet, CORS, global validation + exception filter.
- Prisma schema for all DATABASE_SCHEMA entities with `@@map` + indexes.
- Auth: register/login/refresh/logout/me, Argon2id, short-lived JWT, refresh
  cookie (`__Host-`, httpOnly, secure, sameSite=strict), global JWT + roles guards.
- Sites: create (Ed25519 keygen + AES-256-GCM private-key encryption + ingest
  key), CRUD, origins, snippet + GTM + CSP response; signed config publisher
  (canonical JSON identical to snippet) + Redis cache.
- Experiments: full lifecycle **state machine**, approvals gating, rollback,
  kill switch, risk scoring; publishes signed config on state changes.
- Events ingestion (dev/edge-fallback): key + origin allowlist, Redis rate
  limit, server-side PII scrub, daily-salted session pseudonym, ClickHouse write;
  public signed `GET /config/:siteId`.
- Analytics: ClickHouse client + async inserts, migration runner + `0001_init`
  (events + 3 rollup MVs), overview/funnel/sections, experiment results with a
  **two-proportion z-test**.
- AI orchestration: client to FastAPI, suggestion persistence + materialization
  into an `ai_suggested` experiment (never auto-published).
- Approvals + audit reads. Tenant isolation: guards + ownership checks +
  `withTenant` GUC helper for Postgres RLS. Tests: state machine, stats, signing.

### AI service (`landing-optimizer-ai`)
- FastAPI app, bearer-token internal auth, `/internal/analyze`, `/internal/score`,
  `/health`.
- LLM **provider abstraction**: deterministic `stub` (default, no key) and
  `openai` (any OpenAI-compatible endpoint, strict JSON, graceful fallback).
- Brand-guardrail enforcement (banned words, max length). Tests: determinism +
  guardrails.

### Dashboard (`landing-optimizer-dashboard`)
- Next.js 15 App Router, React 19, Tailwind, minimal shadcn-style primitives.
- Auth (login + token store), API client, sidebar shell.
- API-backed pages: overview, sites, site detail (snippet install), experiments,
  experiment detail (lifecycle actions), approvals, analytics, sections, AI
  insights, results, audit. Honest placeholders: guardrails, settings, team,
  billing. `next build` compiles all 18 routes.

### Infra (`landing-optimizer-infra`)
- Docker Compose full local stack (Postgres, ClickHouse, Redis, Redpanda, API,
  AI, dashboard) — `docker compose config` validated.
- Cloudflare **edge Worker** (`edge/`), K8s base manifests, Terraform skeleton,
  GitHub Actions CI per repo, Makefile + seed script.

## Partially completed 🟡
- **Dashboard**: functional against the API but no unit/e2e tests; secondary
  pages are intentional placeholders (guardrails/settings/team/billing).
- **Edge Worker**: implemented but not wired to a real queue (forwards to API
  ingestion in dev); production Kafka/SQS consumer path is a stub.
- **RLS**: `withTenant` GUC helper + policy design exist; the SQL `CREATE POLICY`
  statements are documented but not yet emitted as a Prisma migration.
- **Observability**: OTel/Prometheus/Sentry are designed/referenced in infra but
  not yet instrumented in code.

## Missing ⬜
- Prisma migration files (`prisma migrate` needs a live Postgres; schema is
  authoritative and `prisma generate` succeeds).
- Real queue consumer (Redpanda/SQS) as a separate worker process.
- RLS policy migration SQL applied to the DB.
- Dashboard tests; API integration/e2e tests against live datastores.
- Billing, team RBAC UI, guardrail editor UI, visual editor, GitHub integration,
  multi-region (all post-MVP per ROADMAP).
- Automated CDN publishing pipeline for versioned SDK releases.

## Blocked ⛔
- **Live DB migrations & full E2E run** require running datastores. Docker images
  were not pulled in this environment, so `prisma migrate`, ClickHouse migrate,
  and an end-to-end smoke test were not executed. Unblock with `make up` in
  `landing-optimizer-infra/docker` locally.
- Prisma engine download initially failed on a corporate TLS root; resolved by
  running Node with `--use-system-ca`.

## Technical debt
- Events ingestion lives in the API for dev convenience; production should route
  through the edge Worker + queue + a dedicated consumer.
- Significance is a frequentist z-test MVP (ROADMAP tracks Bayesian/sequential).
- Some list endpoints lack cursor pagination (noted in API_CONTRACTS).
- Dashboard fetching is client-side only; could adopt RSC/server actions.

## Known risks
- Ed25519 Web Crypto verify is unavailable on older browsers → SDK safely skips
  experiments (analytics still runs). Acceptable fail-safe; monitor coverage.
- ClickHouse async-insert tuning needed under high load.
- Config signing key rotation strategy still to be finalized.
- Anti-flicker is bounded by a timeout; heavy SPAs may still show brief flicker.

## Next recommended tasks
1. `make up` locally, run `prisma migrate dev` + `clickhouse:migrate`, seed, and
   run a full E2E smoke (install snippet → events in ClickHouse → approve/start a
   copy experiment → verify overlay + results).
2. Emit RLS `CREATE POLICY` statements as a Prisma migration + tenant-isolation
   integration test.
3. Split ingestion into edge Worker + queue + standalone consumer.
4. Add dashboard component/e2e tests and API integration tests.
5. Instrument OpenTelemetry + Prometheus + Sentry.
