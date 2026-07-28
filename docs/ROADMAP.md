# Roadmap — Landing Optimizer

> Status: Living document. Last updated: 2026-07-22.

## Phase 0 — Foundations (design)
- [x] Product requirements, architecture, schema, contracts, security, deployment docs.
- [x] Repo scaffolds for all five services.

## Phase 1 — MVP (implement first)
Goal: end-to-end loop from install to a running approved copy experiment.
1. Tenant/site creation (API + Postgres).
2. Script generation (per-site snippet + GTM variant).
3. Async snippet loader + core SDK.
4. Basic event tracking: page_view, click, scroll, dwell.
5. Event ingestion (edge) → queue → consumer.
6. ClickHouse event storage + rollups.
7. Dashboard overview (KPIs).
8. AI insight stub (deterministic placeholder + provider abstraction).
9. Manual experiment creation (draft → approve).
10. Approved **copy replacement** via DOM selector (overlay).
11. Basic A/B allocation (weighted, sticky by session).
12. Experiment results page (exposures/conversions/significance).
13. Rollback + kill switch.

## Phase 2 — Post-MVP
- AI-generated variants (headlines, CTAs, friction analysis).
- Brand guardrails enforcement in AI + validation.
- Advanced statistics (Bayesian + sequential testing).
- Heatmap-like section analytics.
- GitHub integration (optional export of approved copy).
- Visual editor for selecting elements + previewing variants.
- Billing (metered by events/experiments).
- Team permissions (fine-grained roles).
- Multi-region deployment + data residency.

## Phase 3 — Scale & polish
- Automatic winner detection + auto-pause losers (still no auto-publish).
- Multi-armed bandit allocation (opt-in).
- SDK plugins, server-side experiments, feature-flag bridge.
- SOC 2 controls, pen-test, DPA automation.

## Guiding principles
- Privacy-first; no PII ever.
- Human approval before any live change.
- Fail silent in the browser; never break a customer page.
- Honest status tracking in IMPLEMENTATION_STATUS.md.
