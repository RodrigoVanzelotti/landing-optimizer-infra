# Product Requirements Document — Landing Optimizer

> Status: Living document. Last updated: 2026-07-02.

## 1. Summary

**Landing Optimizer** is an AI-powered, privacy-preserving landing page
optimization platform. Customers install a single asynchronous JavaScript
snippet on their landing pages. The snippet observes **aggregate** visitor
behavior, builds a lightweight structural map of the page, and streams
pseudonymous events to our ingestion edge. Our backend detects weak
copy/layout/CTA areas, an AI service generates conversion-rate-optimization
(CRO) experiment suggestions, a human approves them, and safe A/B tests are then
executed entirely through a **DOM overlay layer** — never by modifying the
customer's source code.

The product is inspired by the general category of autonomous CRO agents but is
an **original implementation**, not a clone of any specific vendor.

## 2. Goals & non-goals

### Goals
- One-line, async, non-blocking, fail-silent script install.
- Privacy-preserving analytics with **no PII** and **no cross-site identity**.
- AI-generated, human-approved experiments applied via DOM overlay.
- Multi-tenant SaaS with strict tenant isolation.
- Horizontally scalable event ingestion and analytics.
- A dashboard for insights, approvals, experiments, results, and rollback.

### Non-goals (initial)
- No individual user profiling or session replay of raw content.
- No auto-publishing of AI changes (human approval always required).
- No editing of the customer's source repository (overlay only).
- No collection of raw form values, emails, names, or payment data.

## 3. Personas

| Persona | Needs |
| --- | --- |
| **Growth marketer** | Fast wins on conversion without engineering. Clear suggestions, one-click approve, visible lift. |
| **Founder / SMB owner** | Simple install, trustworthy privacy story, ROI visibility. |
| **CRO specialist** | Statistical rigor, control of allocation, guardrails, rollback. |
| **Engineer / admin** | CSP-safe install, GTM support, security review, minimal performance cost. |
| **DPO / legal** | Proof of no-PII, data residency controls, audit log. |

## 4. Core constraints (privacy)

Tracking MUST be privacy-preserving:
- Do **not** build individual user profiles.
- Do **not** store PII.
- Use anonymous, **short-lived** session IDs only when technically necessary for
  aggregate funnel/session metrics (rotated, salted daily, never cross-site).
- Store behavioral data in **aggregated or pseudonymous** form.

### Never collected
Full IP addresses, names, emails, phone numbers, raw form input, password
fields, payment data, precise geolocation, long-term cross-site identifiers.

### Collected (aggregate / pseudonymous)
Page views, scroll depth, CTA clicks, form starts, form submits, rage clicks,
dead clicks, dwell time, section visibility, drop-off sections, conversion
goals, referrer/source (host only), device category, browser category,
country/region (only when legally safe), aggregate bot/AI-crawler detection.

## 5. Feature requirements

### 5.1 Script installation
- Generate one-line snippet per site (unique `siteId` + public key).
- Loads async via CDN; `defer`/async; never blocks render.
- Fails silently if backend unavailable (try/catch everywhere, timeouts).
- Window API:
  - `window.LandingOptimizer.track(eventName, payload)`
  - `window.LandingOptimizer.identifyCompanyContext(payload)` — non-PII B2B metadata only
  - `window.LandingOptimizer.conversion(goalName, payload)`
- GTM-compatible (custom HTML tag).
- CSP-safe deployment guidance (nonce/hash, connect-src allowlist).

### 5.2 Privacy-preserving analytics
See §4. All metrics aggregated in ClickHouse; no per-user tables.

### 5.3 DOM understanding
Snippet inspects structure safely and builds a **lightweight page map**:
headings, CTAs, forms, hero, pricing, testimonials, FAQ, navigation, footer.
Sends **sanitized structural metadata** (selectors, roles, text hashes/short
snippets), not full private page dumps unless explicitly configured per site.

### 5.4 Experiment engine
Variant types: copy, CTA text, headline, subheadline, button style classes,
section ordering (where safe), hide/show section (where approved), layout class
toggles. Targeting: query-param, device. Controls: traffic allocation,
control vs variant groups, automatic winner detection, manual approval before
activation, rollback, kill switch.

### 5.5 AI suggestion system
Generates: CRO hypotheses, headline rewrites, CTA alternatives, friction
analysis, section-level recommendations, landing page score, brand-safe copy
variants, experiment plans, expected impact, risk level, required approval
checklist. **AI never auto-publishes** — suggestions land in the dashboard.

### 5.6 Dashboard
Pages: Overview, Sites, Script installation, Analytics, Section performance
(heat-style), AI insights, Suggested experiments, Experiment review, Active
experiments, Results, Brand guardrails, Audit log, Settings, Team members,
Billing placeholder.

### 5.7 Approval workflow
Statuses: `draft`, `ai_suggested`, `pending_review`, `approved`, `scheduled`,
`running`, `paused`, `completed`, `rejected`, `rolled_back`.
Every change records: original content, proposed variant, screenshot / DOM
selector context, reason, risk score, approval user, timestamp, rollback data.

### 5.8 Activation & progressive disclosure (product-led growth)
The product must deliver visible value within minutes of signup and make every
future capability something the user anticipates, not discovers by accident:
- **Time-to-value**: after install, the dashboard confirms tracking with a
  live "receiving events" signal — the operator never wonders if it worked.
- **Guided path**: a getting-started journey (create site → install → traffic
  → goal → snapshot → heatmap → AI insights → experiment → verdict) with one
  obvious next action at all times.
- **Honest progressive unlocks**: data-hungry features (heatmap, AI insights,
  significance verdicts) present as locked-with-progress until they have
  enough data to be trustworthy — with a visible progress bar toward the
  threshold, what the feature will show, and the action that advances it.
  Thresholds exist because the feature genuinely needs the data (e.g. the
  results target equals the significance test's minimum sample), never as an
  artificial paywall.
- **Self-explaining KPIs**: every metric carries a plain-language definition
  and an expectation ("what's a normal number") one hover away.
- **Server-computed state**: journey/unlock state is derived from stored data
  via `GET /v1/sites/:id/journey` — it can never contradict reality.

## 6. Success metrics
- Snippet payload < 15 KB gzipped; TTI impact < 10 ms.
- Ingestion p99 < 50 ms at edge.
- Experiment apply flicker < 50 ms (anti-flicker cloak).
- Zero PII stored (verified by schema + tests + audits).
- Statistical significance calc correct vs reference implementation.

## 7. Compliance posture
GDPR/CCPA-aligned by design: data minimization, purpose limitation, no PII, DPA
support, configurable region storage, right-to-erasure trivially satisfied
(no personal data held).

## 8. MVP scope
See [ROADMAP.md](./ROADMAP.md) and [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md).
MVP: tenant/site creation, script generation, async snippet, basic event
tracking (click/scroll/dwell), ingestion, ClickHouse storage, dashboard
overview, AI insight stub, manual experiment creation, approved copy
replacement via DOM selector, basic A/B allocation, results page, rollback.
