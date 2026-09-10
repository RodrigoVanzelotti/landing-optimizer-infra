# Roadmap — Landing Optimizer

> Status: Living document. Last updated: 2026-09-09.
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

## Phase 1.5 — DOM-to-database completion + behavior heatmap (current)
Closes the gaps between "the SDK observes it" and "the database stores it",
and ships the first visual analytics feature.

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | Store element selectors + goal names in ClickHouse (`selector`/`goal` columns; previously validated then discarded) | 🟡 |
| 2 | Persist `page_map` events to Postgres (upsert per site+path; unblocks AI context) | 🟡 |
| 3 | Hover ("attention") tracking in the SDK — sampled 1 Hz, element-anchored, aggregated before send, coordinates never leave the browser | 🟡 |
| 4 | Operator-triggered page snapshot capture (`lo-capture.js`, lazy-loaded via `?lo_capture=1`; screenshot + element geometry) | 🟡 |
| 5 | Snapshot storage + control-plane API (`POST /v1/snapshots`, list/get/image/delete, retention) | 🟡 |
| 6 | Heatmap analytics endpoint (`GET /v1/analytics/heatmap`) | 🟡 |
| 7 | Dashboard **Heatmap** page: screenshot overlay with toggleable layers — clicks (fill), hover (ring), frustration (badge), scroll depth (rules) — plus legend, tooltip, and table fallback | 🟡 |

## Phase 1.9 — MVP hardening (required before calling MVP done)
1. Run the full local stack (`make up`), apply Postgres + ClickHouse migrations,
   seed, and execute an end-to-end smoke: install snippet → events + hover in
   ClickHouse → page map in Postgres → capture snapshot → heatmap renders →
   approve/start a copy experiment → verify overlay + results → rollback.
2. Emit RLS `CREATE POLICY` statements as a Prisma migration + tenant-isolation
   integration test.
3. Split ingestion into edge Worker → queue → standalone consumer (today the
   Worker forwards straight to the API).
4. Dashboard component tests + API integration tests against live datastores.
5. A shared site selector in the dashboard (pages currently pin `sites[0]`).
6. Server/edge attribution for `url` and `form_submit` conversion goals;
   filter experiment results by the experiment's primary goal.

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
