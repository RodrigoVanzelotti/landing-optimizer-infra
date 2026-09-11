# Roadmap — Landing Optimizer

> Status: Living document. Last updated: 2026-09-10.
> Legend: ✅ code complete (validated per IMPLEMENTATION_STATUS) · 🟡 code
> written, pending a validation run · ⬜ not started.
> Honest per-item status lives in [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md);
> this file is the ordered plan.

## Phase 0 — Foundations (design) ✅
- [x] Product requirements, architecture, schema, contracts, security, deployment docs.
- [x] Repo scaffolds for all five services.

## Phase 1 — MVP core loop
Goal: end-to-end loop from install to a running approved copy experiment.

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | Tenant/site creation (API + Postgres) | ✅ |
| 2 | Script generation (per-site snippet + GTM variant) | ✅ |
| 3 | Async snippet loader + core SDK | ✅ |
| 4 | Basic event tracking: page_view, click, scroll, dwell | ✅ |
| 5 | Event ingestion (edge fallback in API) → ClickHouse | ✅ |
| 6 | ClickHouse event storage + rollups | ✅ |
| 7 | Dashboard overview (KPIs) | ✅ |
| 8 | AI insight stub (deterministic placeholder + provider abstraction) | ✅ |
| 9 | Manual experiment creation (draft → approve) | ✅ |
| 10 | Approved copy replacement via DOM selector (overlay) | ✅ |
| 11 | Basic A/B allocation (weighted, sticky by session) | ✅ |
| 12 | Experiment results page (exposures/conversions/significance) | ✅ |
| 13 | Rollback + kill switch | ✅ |

## Phase 1.5 — DOM-to-database completion + behavior heatmap ✅
Closed the gaps between "the SDK observes it" and "the database stores it",
and shipped the first visual analytics feature. Validated locally 2026-09-10
(typecheck/tests/builds + Docker E2E incl. heatmap).

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | Store element selectors + goal names in ClickHouse (`selector`/`goal` columns; previously validated then discarded) | ✅ |
| 2 | Persist `page_map` events to Postgres (upsert per site+path; unblocks AI context) | ✅ |
| 3 | Hover ("attention") tracking in the SDK — sampled 1 Hz, element-anchored, aggregated before send, coordinates never leave the browser | ✅ |
| 4 | Operator-triggered page snapshot capture (`lo-capture.js`, lazy-loaded via `?lo_capture=1`; screenshot + element geometry) | ✅ |
| 5 | Snapshot storage + control-plane API (`POST /v1/snapshots`, list/get/image/delete, retention) | ✅ |
| 6 | Heatmap analytics endpoint (`GET /v1/analytics/heatmap`) | ✅ |
| 7 | Dashboard **Heatmap** page: screenshot overlay with toggleable layers — clicks (fill), hover (ring), frustration (badge), scroll depth (rules) — plus legend, tooltip, and table fallback | ✅ |

## Phase 1.6 — Ingestion reliability + launch observability (current)
Triggered by a field incident: ingestion silently stopped after a period of
use. Root-caused and fixed; observability contract formalized for launch.

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | Rate limiter made atomic + self-healing (Lua INCR+EXPIRE; a counter that lost its TTL previously rate-limited a site **permanently**) | 🟡 |
| 2 | ClickHouse insert failures surfaced (`wait_for_async_insert: 1`) — silent data loss is no longer possible; drops are logged once with reason + request_id | 🟡 |
| 3 | Boot-time ClickHouse schema guard (`clickhouse_schema_outdated` error log when the live table is missing columns the code writes) | 🟡 |
| 4 | SDK clamps `t`/`dw` to the 24 h wire ceiling (tabs open >24 h no longer get every batch rejected) | 🟡 |
| 5 | Single-record error rule: one log per incident; `DependencyUnavailableException` carries dependency facts to the global filter (AI path no longer double-logs) | 🟡 |
| 6 | Cross-service trace: edge Worker mints/propagates `X-Request-ID` + JSON logs; dashboard log-relay (`/api/client-log`) forwards browser errors with the failed request's id | 🟡 |
| 7 | Logging & error-tracing contract documented (DEPLOYMENT §8) | ✅ |

## Phase 1.7 — Activation & product-led growth (current)
A naive-user review found the tool didn't guide, explain, or reward: users
landed on empty KPIs with 13 flat nav links and dead-end empty states. This
phase makes the product speak for itself (PRODUCT_REQUIREMENTS §5.8).

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | `GET /v1/sites/:id/journey` — server-computed activation milestones with live progress (thresholds in one tunable const) | 🟡 |
| 2 | Getting-started journey panel on Overview: next action always highlighted, progress bars, "Live — receiving events" pill | 🟡 |
| 3 | Progressive unlocks with visible progress: AI insights (500 views), heatmap warm-up (200 interactions), results significance countdown (60 exposures = the z-test floor) | 🟡 |
| 4 | Self-explaining KPIs: definition + "what to expect" tooltip on every metric; funnel event explanations; significance explainer | 🟡 |
| 5 | Global site selector (sidebar) shared by all pages via SiteProvider — replaces the hidden `sites[0]` pinning (was Phase 1.9 item 5) | 🟡 |
| 6 | Sidebar grouped by intent: Measure / Optimize / Configure | 🟡 |
| 7 | Empty states rewritten as anticipation: what the feature will show + the action that unlocks it | 🟡 |

## Phase 1.9 — MVP hardening (required before calling MVP done)
1. ~~Full local stack E2E smoke~~ — done 2026-09-10 (also surfaced the
   ingestion-stop incident that became Phase 1.6). Re-run after Phase 1.6
   validation.
2. Emit RLS `CREATE POLICY` statements as a Prisma migration + tenant-isolation
   integration test.
3. Split ingestion into edge Worker → queue → standalone consumer (today the
   Worker forwards straight to the API).
4. Dashboard component tests + API integration tests against live datastores.
5. ~~A shared site selector in the dashboard~~ — moved to Phase 1.7 (item 5).
6. Server/edge attribution for `url` and `form_submit` conversion goals;
   filter experiment results by the experiment's primary goal.
7. PLG follow-ups: milestone-completion celebrations (toast), weekly email
   digest ("your page score moved"), in-product changelog/what's-next teaser.

## Phase 2 — Post-MVP
- AI-generated variants (headlines, CTAs, friction analysis) — suggestions
  generated offline against a curated dataset, then imported (per product
  decision 2026-09; the live-LLM path stays behind the provider abstraction).
- Advanced statistics (Bayesian + sequential testing).
- Server-side snapshot capture (headless browser) as an upgrade over the
  operator-triggered SDK capture; object storage (S3) for snapshot images.
- Visual editor for selecting elements + previewing variants.
- OpenTelemetry + Prometheus + Sentry instrumentation.
- Billing (metered by events/experiments), team permissions (fine-grained roles).
- Multi-region deployment + data residency.
- GitHub integration (optional export of approved copy).

## Phase 3 — Scale & polish
- Automatic winner detection + auto-pause losers (still no auto-publish).
- Multi-armed bandit allocation (opt-in).
- SDK plugins, server-side experiments, feature-flag bridge.
- SOC 2 controls, pen-test, DPA automation.

## Guiding principles
- Privacy-first; no PII ever. Heatmaps are element-anchored aggregates — raw
  pointer coordinates never leave the visitor's browser.
- Human approval before any live change.
- Fail silent in the browser; never break a customer page.
- Honest status tracking in IMPLEMENTATION_STATUS.md.
