# Implementation Status — Landing Optimizer

> **Honest, living status.** Nothing is marked done unless it exists in code and
> has been validated (typecheck / tests / build). Last updated: 2026-09-09.

Legend: ✅ done & validated · 🟡 partial · ⛔ blocked · ⬜ missing

## Validation summary (this run)
| Repo | Typecheck | Tests | Build |
| --- | --- | --- | --- |
| snippet | ✅ `tsc --noEmit` clean | ✅ 15 pass (vitest) | ✅ `lo.js` 15.9 KB + `loader.js` 984 B |
| api | ✅ `tsc --noEmit` clean | ✅ 6 pass (vitest) | ✅ Prisma client generated |
| ai | ruff clean | ✅ 3 pass (pytest) | n/a |
| dashboard | ✅ `tsc --noEmit` clean | ⬜ (no unit tests yet) | ✅ `next build` 18 routes |
| infra | n/a | n/a | ✅ `docker compose config` valid |

> 2026-08-05 update: added the Conversion Goals and Brand Guardrails
> control-plane endpoints, `primaryGoalId` ownership validation, and
> `goals`/`guardrails` unit tests. New code typechecks clean in-editor; the
> vitest suite was **not executed this session** (no datastores were started),
> so the counts above are unchanged pending a local `npm test` run.
>
> Follow-up (same session): the dashboard **Brand guardrails** page is now a
> real editor (site selector + tone/banned-words/max-length/must-keep-claims,
> `GET`/`PUT`), and the site detail page manages **Conversion goals**
> (create/list/delete). Hardening: the global exception filter now maps Prisma
> `P2002`/`P2025`/`P2003` to `409`/`404`/`400` (no more 500 on a name-collision
> race), and `PUT` was added to the API CORS allowlist.
>
> Logging update (same date): API control-plane mutations and all exceptions now
> produce concise, correlated logs; high-volume successful event ingestion is
> excluded, while ingestion rejections and dependency errors retain reasons.
> The AI service logs analyze/score successes, validation/HTTP/unhandled errors,
> and provider fallbacks with request IDs. Payloads and secrets are never logged.
> Added request-ID/log-sanitization tests, syntax/type checked in-editor only.
>
> JSON logging follow-up: every API and AI process log is now one JSON object.
> Business fields (`event`, `request_id`, `status`, `site_id`, duration, tenant,
> actor, dependency) are top-level and queryable. API bootstrap/dependency/
> migration output and Uvicorn startup/error output use the same JSON envelope.
> Formatter regression tests were added; not executed in this session.
>
> AI logger API refactor: application modules now instantiate the cached,
> thread-safe `Logger(__name__)` facade once and call `logger.info()`,
> `logger.warn()`, `logger.error()`, or `logger.exception()` directly. The
> previous numeric-level `log_event` helper was removed; JSON output is unchanged.
>
> API logger API refactor: all API modules now declare one cached
> `Logger('Context')` instance near the top of the file and use direct structured
> methods (`info`, `warn`, `error`, `exception`, etc.). The facade remains a Nest
> `LoggerService` for framework output. The old `JsonLoggerService` was removed;
> singleton identity/direct-method regression tests were added but not executed.
>
> Dashboard/API request fix: the dashboard client no longer sends
> `Content-Type: application/json` on bodyless mutations (including **Run
> analysis**), preventing Fastify's empty-JSON rejection. Explicit falsy JSON
> bodies are now preserved. The API exception filter also respects Fastify HTTP
> status codes, so malformed JSON is reported as `400 validation_error`, not
> `500 internal_error`. Client regression tests added; not executed this session.
>
> Docker development update (2026-08-06): API, AI, dashboard, and snippet
> Dockerfiles now have explicit `development` targets with native watch/reload
> commands. Compose watch overlays synchronize source, restart on config edits,
> and rebuild on dependency/schema/Dockerfile changes; `make watch` starts the
> primary stack. YAML/Dockerfile editor validation completed; Compose was not
> executed in this session.

> **2026-09-09 update — DOM-to-database completion + behavior heatmap (Phase
> 1.5).** All code below is written but **not executed in this session** (no
> typecheck, tests, build, or datastores were run); validate locally before
> promoting anything to ✅.
>
> - **Snippet SDK**: new `hover` attention tracking (`src/hover.ts`) — 1 Hz
>   pointer sampling resolved to the nearest page-map element, aggregated
>   locally (noise floor 2 s, ≤20 selectors/flush), emitted as `hover` events
>   with `sel` + `dw`; raw coordinates never leave the browser. The tracker now
>   builds the page map **once** and shares it (previously walked the DOM
>   twice). New operator-only capture bundle (`src/capture.ts` → `lo-capture.js`,
>   third tsup entry): lazy-loaded by `lo.js` only when the page is opened with
>   `?lo_capture=1`; rasterizes the page via SVG foreignObject (computed styles
>   inlined, form values/password/hidden inputs and `[data-lo-ignore]` removed,
>   cross-origin images replaced with placeholders), collects document-space
>   rects for all page-map nodes, and POSTs to `/v1/snapshots`. `company_context`
>   added to the `EventName` union. New tests: `test/hover.test.ts`,
>   `test/capture.test.ts` (not run).
> - **API**: ClickHouse migration `0002_selector_goal.sql` adds `selector` +
>   `goal` columns — the SDK's `sel`/`goal` fields were previously validated
>   then silently discarded; they are now sanitized (server-side selector
>   allowlist, `sanitizeSelector`) and stored. `page_map` events are now split
>   from the behavioral stream and **upserted into Postgres `page_map`** (one
>   row per site+path, Redis rate-limited 30/h/site) — this table previously
>   had zero writers while the AI module read it. Site auth extracted to
>   `SiteAuthService` (shared by events + snapshots). New `snapshots` module:
>   public `POST /v1/snapshots` (ingest-key + origin + 10/h rate limit +
>   magic-byte content check + 3 MB cap, retention 3/path + 20/site) and
>   tenant-scoped list/get/image/delete under `/v1/sites/:id/snapshots`. New
>   `GET /v1/analytics/heatmap` (per-selector clicks/hover/frustration +
>   scroll-depth distribution for a path). Prisma: `PageSnapshot` model,
>   `@@unique([siteId, urlPath])` on `PageMap`, hand-written migration
>   `20260909120000_page_snapshots` (includes duplicate cleanup before the
>   unique index). Fastify `bodyLimit` raised 64 KB → 6 MB for snapshot uploads
>   (events remain schema-bounded; edge enforces 32 KB). New tests:
>   `test/event-scrub.test.ts`, `test/snapshots.test.ts` (not run).
> - **Edge Worker**: routes `POST /v1/snapshots` (5 MB cap, synchronous forward
>   so the capture UI gets a real status; events remain fire-and-forget).
> - **Dashboard**: new **Heatmap** page (`/heatmap`) — site + snapshot
>   selectors, four layer checkboxes (Clicks = sequential-blue zone fill,
>   Hover = orange ring thickness, Frustration = ⚠ badge with dead+rage count,
>   Scroll depth = dashed rules with "% of visitors" labels), legend, per-zone
>   tooltip, capture instructions when no snapshot exists, and a plain-table
>   fallback of all element metrics. New `Checkbox` primitive; `api.getBlob`
>   for the authenticated snapshot image. Layer encodings use distinct visual
>   channels so several layers combine without color blending.
> - **Known gaps in this batch**: SDK capture fidelity depends on same-origin/
>   CORS images and computed-style inlining (web fonts are not embedded);
>   hover is desktop-only by nature; the heatmap queries raw ClickHouse events
>   (no rollup MV yet — add one if query volume warrants); snapshot images
>   live in Postgres bytea per MVP decision, with S3 as the post-MVP swap.

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
- Conversion goals (`/v1/sites/:id/goals`): CRUD with per-kind matcher
  validation (`event`/`url`/`form_submit`), unique-name enforcement, a
  delete-guard that blocks removing a goal referenced by a non-terminal
  experiment, and audit logging. Experiment creation now validates that
  `primaryGoalId` exists and belongs to the same site.
- Brand guardrails (`/v1/sites/:id/guardrails`): GET/PUT with a strict rules
  schema + normalization (case-insensitive banned-word dedupe); the same rules
  the AI service enforces in `apply_guardrails`.
- Approvals + audit reads. Tenant isolation: guards + ownership checks +
  `withTenant` GUC helper for Postgres RLS. Tests: state machine, stats,
  signing, goal-matcher + guardrail-rules validation.
- Production JSON logging: request correlation, successful control-plane mutation
  summaries, global exception reasons, ingestion rejection/dependency failures;
  event bodies, credentials, visitor IDs, and secrets are excluded.

### AI service (`landing-optimizer-ai`)
- FastAPI app, bearer-token internal auth, `/internal/analyze`, `/internal/score`,
  `/health`.
- LLM **provider abstraction**: deterministic `stub` (default, no key) and
  `openai` (any OpenAI-compatible endpoint, strict JSON, graceful fallback).
- Brand-guardrail enforcement (banned words, max length). Tests: determinism +
  guardrails.
- Production JSON logging: correlated analyze/score success summaries, global
  validation/HTTP/unhandled exception handling, safe provider-fallback reasons,
  and duplicate Uvicorn access logs disabled.

### Dashboard (`landing-optimizer-dashboard`)
- Next.js 15 App Router, React 19, Tailwind, minimal shadcn-style primitives.
- Auth (login + token store), API client, sidebar shell.
- API-backed pages: overview, sites, site detail (snippet install + conversion
  goals), experiments, experiment detail (lifecycle actions), approvals,
  analytics, sections, AI insights, results, brand guardrails (editor), audit.
  Honest placeholders: settings, team, billing. `next build` compiles all 18
  routes.

### Infra (`landing-optimizer-infra`)
- Docker Compose full local stack (Postgres, ClickHouse, Redis, Redpanda, API,
  AI, dashboard) — `docker compose config` validated.
- Docker Compose watch workflows for API/AI/dashboard and snippet/demo, with
  production Docker stages kept unchanged.
- Cloudflare **edge Worker** (`edge/`), K8s base manifests, Terraform skeleton,
  GitHub Actions CI per repo, Makefile + seed script.

## Partially completed 🟡
- **Dashboard**: functional against the API but no unit/e2e tests; secondary
  pages are intentional placeholders (settings/team/billing).
- **Edge Worker**: implemented but not wired to a real queue (forwards to API
  ingestion in dev); production Kafka/SQS consumer path is a stub.
- **RLS**: `withTenant` GUC helper + policy design exist; the SQL `CREATE POLICY`
  statements are documented but not yet emitted as a Prisma migration.
- **Observability**: production-safe application logs now exist in API + AI;
  OTel/Prometheus/Sentry are designed/referenced but not yet instrumented.

## Missing ⬜
- Prisma migration files (`prisma migrate` needs a live Postgres; schema is
  authoritative and `prisma generate` succeeds).
- Real queue consumer (Redpanda/SQS) as a separate worker process.
- RLS policy migration SQL applied to the DB.
- Dashboard tests; API integration/e2e tests against live datastores.
- Billing, team RBAC UI, visual editor, GitHub integration,
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
- Conversion goals are defined for all three kinds, but only `event`-kind goals
  are auto-attributed today (the SDK `conversion(name)` emits the event). Server
  or edge-side attribution for `url`/`form_submit` goals is a follow-up; the
  `matcher` shapes are already validated and stored for it. Experiment results
  also count all conversions rather than filtering by the experiment's primary
  goal — to be refined alongside the attribution engine.

## Known risks
- Ed25519 Web Crypto verify is unavailable on older browsers → SDK safely skips
  experiments (analytics still runs). Acceptable fail-safe; monitor coverage.
- ClickHouse async-insert tuning needed under high load.
- Config signing key rotation strategy still to be finalized.
- Anti-flicker is bounded by a timeout; heavy SPAs may still show brief flicker.

## Next recommended tasks
1. Validate the 2026-09-09 batch: `tsc --noEmit` + `npm test` + build in
   snippet/api/dashboard, `prisma generate`, then `make up`, `prisma migrate
   deploy` + `clickhouse:migrate`, seed, and a full E2E smoke (install snippet →
   events + hover in ClickHouse → page map in Postgres → `?lo_capture=1`
   snapshot → heatmap page renders all four layers → approve/start a copy
   experiment → verify overlay + results → rollback).
2. Emit RLS `CREATE POLICY` statements as a Prisma migration + tenant-isolation
   integration test.
3. Split ingestion into edge Worker + queue + standalone consumer.
4. Add dashboard component/e2e tests and API integration tests.
5. Instrument OpenTelemetry + Prometheus + Sentry.
