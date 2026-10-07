# API data inventory and AI research boundaries

Reviewed: 2026-10-06. Scope: current working-tree Prisma schema, SQL migrations, API persistence paths, SDK and edge forwarding. **Repository-defined schema; deployed migrations, row counts and data completeness were not verified.**

## Storage format

| Store | Format | Data |
| --- | --- | --- |
| PostgreSQL | Relational tables via Prisma; structured `JSONB`; binary `BYTEA` | Accounts, sites, experiment configuration, approvals, AI suggestions, page structure, screenshots and audit records |
| ClickHouse | Typed event rows inserted using `JSONEachRow`; `MergeTree` plus `SummingMergeTree` materialized views | Pseudonymous visitor behavior and aggregate experiment/funnel/section metrics |
| Redis | Expiring string keys containing JSON or integer counters | Signed configuration cache, site authentication cache and rate limits; not an analytical system of record |

HTTP uses JSON with camelCase fields; SQL uses snake_case. Snapshot uploads encode images as base64; PostgreSQL stores decoded bytes. ClickHouse `props` is JSON serialized into a `String`, not a native JSON column.

## Is `DATABASE_SCHEMA.md` current?

**Partially. Table coverage and ClickHouse event types are largely current; several PostgreSQL types and enforcement claims are incorrect.**

| Document claim / omission | Current implementation |
| --- | --- |
| PostgreSQL IDs and references are `uuid` | All are `TEXT`; application-generated primary IDs contain UUID v7 strings. ClickHouse IDs are native `UUID`. |
| PostgreSQL timestamps are `timestamptz` | All are `TIMESTAMP(3)` without time zone. Application code uses UTC dates; SQL type itself carries no zone. |
| `tenant.slug` and `user.email` are `citext` | Both are unique `TEXT`; no database-level case-insensitive type. |
| Categorical fields are `text` | Native PostgreSQL enums; values listed below. |
| Fractions are unspecified `numeric` | `sampling_rate`, `allocation`, `weight`: `DECIMAL(4,3)`. API validation supplies 0–1 bounds; migrations do not add range checks. |
| Missing fields | `user.password_hash TEXT NULL`, `site.config_version INTEGER NOT NULL DEFAULT 0`, `api_key.created_at TIMESTAMP(3) NOT NULL`. |
| Every scoped table has `tenant_id` and active RLS | Several child tables scope through parent relationships. Checked-in migrations contain no RLS policies; `withTenant()` exists but has no callers in API source. Current isolation uses application checks/filters. |
| User references are enforced FKs | `experiment.created_by`, `approval.approver_user_id`, `audit_log.actor_user_id` have no FKs. Neither do `experiment.winner_variant_id` nor `ai_suggestion.site_id`. |
| No PII in either store | PostgreSQL explicitly stores operator email/name and password hashes. Visitor collection applies heuristic scrubbing; it is not proof that every arbitrary string or uploaded screenshot is PII-free. |
| Country populated by edge | Edge sends `X-Geo-Country`, but API ingestion writes `country = ''`; `is_bot = 0` is also hardcoded. |

## PostgreSQL tables

Physical SQL column names below. `?` means nullable. All 16 tables have `id TEXT PRIMARY KEY`. `created_at` is non-null `TIMESTAMP(3)` with a database `CURRENT_TIMESTAMP` default wherever present; `updated_at` is non-null `TIMESTAMP(3)` maintained by Prisma, not a database update trigger. `captured_at` also defaults to `CURRENT_TIMESTAMP`.

| Table / grain | Columns and SQL types, excluding common `id` | Meaning |
| --- | --- | --- |
| `tenant` / account | `name TEXT`; `slug TEXT UNIQUE`; `plan Plan`; `data_region TEXT`; `created_at`, `updated_at` | Customer/organization boundary; subscription tier and region label. |
| `user` / operator | `email TEXT UNIQUE`; `name TEXT?`; `password_hash TEXT?`; `created_at`, `updated_at` | Dashboard login identity; not a visitor identity. |
| `user_membership` / tenant–operator pair | `tenant_id TEXT FK`; `user_id TEXT FK`; `role Role`; `created_at` | Access role. Unique `(tenant_id, user_id)`. |
| `api_key` / service credential | `tenant_id TEXT FK`; `name TEXT`; `hashed_key TEXT`; `scopes TEXT[]`; `last_used_at TIMESTAMP(3)?`; `revoked_at TIMESTAMP(3)?`; `created_at` | Programmatic access metadata. Migration permits SQL NULL for `scopes`, although Prisma declares a required string list. No key-management write path found in API modules. |
| `site` / website | `tenant_id TEXT FK`; `name TEXT`; `primary_domain TEXT`; `public_key TEXT`; `private_key_enc BYTEA`; `ingest_key TEXT UNIQUE`; `sampling_rate DECIMAL(4,3)`; `status SiteStatus`; `settings JSONB`; `config_version INTEGER`; `created_at`, `updated_at` | Domain/configuration; base64 Ed25519 public key, AES-256-GCM encrypted private key, public ingestion credential and config revision. |
| `site_origin` / allowed site origin | `site_id TEXT FK`; `origin TEXT`; `created_at` | Exact normalized origin allowlist. Unique `(site_id, origin)`. |
| `conversion_goal` / named site goal | `site_id TEXT FK`; `name TEXT`; `kind GoalKind`; `matcher JSONB`; `created_at` | Intended conversion definition. Unique `(site_id, name)`; not a measured conversion record. |
| `experiment` / experiment definition | `tenant_id TEXT FK`; `site_id TEXT FK`; `name TEXT`; `hypothesis TEXT?`; `status ExperimentStatus`; `type ExperimentType`; `targeting JSONB`; `allocation DECIMAL(4,3)`; `primary_goal_id TEXT? FK`; `risk_score INTEGER`; `winner_variant_id TEXT?`; `created_by TEXT?`; `created_at`, `updated_at`; `started_at TIMESTAMP(3)?`; `ended_at TIMESTAMP(3)?` | Hypothesis, lifecycle, eligibility, traffic fraction, intended outcome, risk and manually recorded winner. Statistical results are computed from ClickHouse. |
| `variant` / experiment arm | `experiment_id TEXT FK`; `name TEXT`; `is_control BOOLEAN`; `weight DECIMAL(4,3)`; `created_at` | Control/treatment flag and traffic split within an experiment. |
| `variant_change` / DOM mutation | `variant_id TEXT FK`; `selector TEXT`; `op ChangeOp`; `original_value TEXT?`; `proposed_value TEXT?`; `attr_name TEXT?`; `created_at` | Target element, operation, previous/new content or attribute/class value. |
| `approval` / review record | `experiment_id TEXT FK`; `status ApprovalStatus`; `reason TEXT?`; `risk_score INTEGER`; `checklist JSONB`; `screenshot_url TEXT?`; `approver_user_id TEXT?`; `decided_at TIMESTAMP(3)?`; `created_at` | Human review decision, checklist, risk snapshot and optional evidence URL. |
| `ai_suggestion` / individual generated suggestion | `tenant_id TEXT FK`; `site_id TEXT`; `kind SuggestionKind`; `payload JSONB`; `model TEXT`; `expected_impact TEXT?`; `risk_level RiskLevel`; `experiment_id TEXT? FK`; `created_at` | Generated recommendation and provenance. Impact is descriptive text, not measured lift. No analysis-run/input-version ID. |
| `brand_guardrail` / site rules | `site_id TEXT UNIQUE FK`; `rules JSONB`; `created_at`, `updated_at` | Tone and copy constraints consumed by AI. |
| `page_map` / latest site–path structure | `site_id TEXT FK`; `url_path TEXT`; `map JSONB`; `captured_at TIMESTAMP(3)` | Sanitized structural nodes and short copy; unique `(site_id, url_path)`, overwritten by ingestion. No historical map versions. |
| `page_snapshot` / captured screenshot | `site_id TEXT FK`; `url_path TEXT`; `width INTEGER`; `height INTEGER`; `content_type TEXT`; `image BYTEA`; `nodes JSONB`; `captured_at TIMESTAMP(3)` | Operator-triggered page image plus capture-time document geometry. Index `(site_id, url_path, captured_at)`. |
| `audit_log` / application action | `tenant_id TEXT FK`; `actor_user_id TEXT?`; `action TEXT`; `target_type TEXT`; `target_id TEXT`; `metadata JSONB`; `ip_hash TEXT?`; `created_at` | Action provenance and caller-supplied metadata; nullable actor for system actions. Append-only by application convention. |

### PostgreSQL enum domains

| SQL type | Values |
| --- | --- |
| `Plan` | `free`, `pro`, `enterprise` |
| `SiteStatus` | `active`, `paused` |
| `Role` | `owner`, `admin`, `editor`, `viewer` |
| `GoalKind` | `event`, `url`, `form_submit` |
| `ExperimentType` | `copy`, `cta`, `headline`, `subheadline`, `button_style`, `section_order`, `section_visibility`, `layout_class` |
| `ExperimentStatus` | `draft`, `ai_suggested`, `pending_review`, `approved`, `scheduled`, `running`, `paused`, `completed`, `rejected`, `rolled_back` |
| `ChangeOp` | `set_text`, `set_html_safe`, `set_attr`, `add_class`, `remove_class`, `hide`, `show`, `reorder` |
| `ApprovalStatus` | `pending`, `approved`, `rejected` |
| `SuggestionKind` | `hypothesis`, `headline`, `cta`, `friction`, `section`, `score`, `plan` |
| `RiskLevel` | `low`, `medium`, `high` |

### Structured JSON and binary payloads

| Column | Persisted shape / semantics |
| --- | --- |
| `site.settings` | Arbitrary JSON object accepted by API; not a fixed feature schema. |
| `conversion_goal.matcher` | `event`: `{}` (goal name is the identifier); `url`: `{op: exact\|prefix\|contains\|regex, path: string}`; `form_submit`: `{selector?: string}`. Definition alone does not establish measured outcome attribution. |
| `experiment.targeting` | `{device?: (mobile\|tablet\|desktop)[], query?: Record<string,string>}`; eligibility rules, not collected visitor query parameters. |
| `approval.checklist` | `Record<string,boolean>` supplied by reviewer. |
| `brand_guardrail.rules` | `{tone?: string, bannedWords?: string[], maxLength?: integer, mustKeepClaims?: string[]}`. |
| `ai_suggestion.payload` | `{kind, title, detail, riskLevel, selector?, proposedValue?, originalValue?, expectedImpact?}`; text strings except enum fields. Stored as returned by AI; database JSONB does not enforce this shape. |
| `page_map.map` | `{path: string, counts: Record<string,integer>, nodes: [{role, selector, tag, text?, textHash?}]}`. API accepts ≤60 nodes, text ≤120 characters; current SDK sends ≤60 nodes with text ≤80 characters. `textHash` is an unsigned 32-bit noncryptographic hash emitted as a JSON integer; not recoverable full text. |
| `page_snapshot.nodes` | `[{selector: string, role: string, rect: [x,y,width,height]}]`; ≤150 nodes; nonnegative integer document coordinates and positive dimensions in CSS pixels. |
| `page_snapshot.image` | WebP/PNG/JPEG bytes, ≤3 MiB per upload; declared width 200–4000 and height 200–40000. SDK strips form values/ignored elements before rasterizing. Retention pruning is best-effort: newest 3 per path and 20 per site. |
| `audit_log.metadata` | Action-specific JSON object; includes AI analysis score/count for `ai.analyzed`. Not a dedicated model evaluation dataset. |

## ClickHouse tables

### `events`: one accepted behavioral/context event

| Column | Physical type | Meaning / current population |
| --- | --- | --- |
| `event_date` | `Date` | Derived from `event_time`; retention date. |
| `event_time` | `DateTime64(3)` | API ingestion time with millisecond precision; every event in a batch receives the same timestamp. |
| `tenant_id`, `site_id` | `UUID` | Organization and website resolved by API. |
| `session_id` | `String` | 32-character SHA-256-derived pseudonym of SDK session, site and deterministic daily salt; not an account/customer ID. |
| `event_name` | `LowCardinality(String)` | Accepted event category; API enum below, SQL itself permits strings. |
| `page_path` | `String` | Path ≤512 characters, query/hash removed. |
| `referrer_host` | `LowCardinality(String)` | Referring host; API truncates to 255 characters. |
| `device_category` | `LowCardinality(String)` | `mobile`, `tablet`, `desktop`; coarse client classification. |
| `browser_category` | `LowCardinality(String)` | `chromium`, `firefox`, `safari`, `edge`, `other`. |
| `country` | `LowCardinality(String)` | Currently empty in API inserts, including edge-forwarded batches. |
| `is_bot` | `UInt8` | Currently always `0`; no observed bot classification. |
| `experiment_id`, `variant_id` | `UUID` | Event-supplied assignment; nil UUID when absent. No cross-store FK. |
| `section_id` | `LowCardinality(String)` | Optional ≤64-character section label. SDK section views use semantic roles, not unique DOM section IDs. |
| `selector` | `String` | Sanitized CSS selector ≤256 characters, or empty. Element join key for heatmaps. |
| `goal` | `LowCardinality(String)` | Optional conversion goal name ≤64 characters; not a goal-table FK. |
| `scroll_depth` | `UInt8` | 0–100 percent; SDK emits reached buckets; `0` when absent. |
| `dwell_ms` | `UInt32` | Event-specific duration/attention in milliseconds, API cap 86,400,000; `0` when absent. |
| `value` | `Float64` | Finite generic numeric value; SDK `conversion()` defaults to `1`, API absence defaults to `0`. No currency/unit column; not fixed-precision money. |
| `props` | `String` | Sanitized JSON or empty string; ≤20 keys, keys ≤64 characters, strings ≤256, arrays ≤10 items; serialized payload >4096 characters becomes empty. Object-valued properties are dropped. |

API event names: `page_view`, `scroll_depth`, `cta_click`, `dead_click`, `rage_click`, `form_start`, `form_submit`, `section_view`, `hover`, `dwell`, `dropoff`, `exposure`, `conversion`, `company_context`. `page_map` is accepted on the wire but routed to PostgreSQL, not this table. Arbitrary custom event names sent through SDK `track()` fail API validation.

Engine: `MergeTree`; partition `(toYYYYMMDD(event_time), tenant_id)`; sort `(tenant_id, site_id, event_name, event_time)`; raw TTL **180 days**, with asynchronous expiry. No event ID, deduplication key or exact-once guarantee; failed inserts can drop acknowledged batches.

**Current working-tree ingestion blockers:** `EventsService.ingest()` passes `envelope.sid` (SDK session ID) to site authorization instead of `envelope.siteId`; normal SDK batches therefore fail site lookup. The edge forwards `X-Forwarded-Origin`, but current event/snapshot controllers read `Origin`/`Referer`, so origin validation can also reject forwarded uploads. These paths have pre-existing local edits; the inventory describes expected stored rows, not evidence that collection currently succeeds.

### Materialized aggregate tables

These views own stored `SummingMergeTree` data. Query using `sum(...) GROUP BY` because background merges need not be complete. No TTL is declared for them.

| Table | Grain and dimension types | Metric types and meaning |
| --- | --- | --- |
| `mv_daily_funnel` | `event_date Date`, `tenant_id UUID`, `site_id UUID`, `event_name LowCardinality(String)` | `events UInt64`: event count; not an ordered/deduplicated session funnel. |
| `mv_section_performance` | `event_date Date`, `tenant_id UUID`, `site_id UUID`, `section_id LowCardinality(String)` | `views UInt64`, `dead_clicks UInt64`, `rage_clicks UInt64`, `dwell_ms_total UInt64`: conditional event counts and sum of `dwell_ms` for rows with nonempty section. |
| `mv_experiment_stats` | `event_date Date`, `tenant_id UUID`, `site_id UUID`, `experiment_id UUID`, `variant_id UUID` | `exposures UInt64`, `conversions UInt64`, `conversion_value Float64`: event counts and summed conversion value; only non-nil experiment rows. |

Aggregate types above follow the migration SELECT expressions (`count`, `countIf`, `sum(UInt32)`, `sumIf(Float64)`); confirm via deployed `DESCRIBE TABLE` if consuming live data.

## What the AI layer currently receives

`AiService.analyze()` sends JSON `{siteId, pageMap, metrics: {overview, sections}, guardrails}`:

| Input | Scope / shape |
| --- | --- |
| `pageMap` | Single most recently captured map across the site; `{nodes: []}` fallback. Other paths/maps are not included. |
| `metrics.overview` | Last 30 days, entire site: numeric `pageViews`, `conversions`, `conversionRate`, `ctaClicks`, `formSubmits`. Rate = conversion events / page-view events. |
| `metrics.sections` | All retained section rollups, entire site: `[{section, views, deadClicks, rageClicks, dwellMs}]`; no matching 30-day filter and no path dimension. |
| `guardrails` | Site rule object, or `{}`. |

Raw events, screenshot bytes/geometry, element heatmaps, device/referrer cohorts, company context, experiment results and previous suggestions **exist as potential inputs but are not included in this call**. Suggestions are persisted individually; overall score is returned and recorded in audit metadata, without a versioned input snapshot.

## AI research implications

| Research task | Data support / limitation |
| --- | --- |
| Copy/CTA/structure recommendations | Available short snippets, roles, selectors and brand rules. Full HTML/CSS, complete copy, product positioning and business objectives are not guaranteed inputs. |
| Visual/layout analysis | Stored screenshots and element rectangles support multimodal research after extending AI input retrieval. Captures are sparse, operator-triggered and pruned; no stable historical design corpus. |
| Friction/attention analysis | Raw selectors support click/hover/scroll aggregation by page. Hover is aggregated pointer attention, not gaze or raw cursor trajectories. Click coordinates are not stored. |
| Section-level performance | Current SDK emits clicks/hover/dwell without `sec`; section views use role labels. Section rollups therefore cannot reliably attach frustration/dwell to individual sections, and merge roles across paths. |
| Segmentation | Device/browser/referrer and optional primitive `company_context.props` are available in raw events. Country and bot columns currently provide no variation; no explicit campaign/UTM, viewport or language columns. |
| Session funnels / time-to-conversion | Same-site/day session grouping is possible. Client `t`, `sentAt`, viewport and language are discarded; ingestion timestamps tie within batches, preventing exact event order/timing reconstruction. No durable cross-day visitor/customer identity. |
| Experiment lift / causal evaluation | Exposure events carry experiment/variant IDs, but current SDK `conversion()` does not; no API attribution enrichment. Default conversion rows have nil IDs and are excluded from experiment rollups. Attribution and deduplication must be established before treating results as reliable treatment outcomes. Rollups also omit goal, page and cohort dimensions. |
| Revenue/LTV/churn/personalization | Optional numeric conversion value is not a transaction ledger. No currency, order/customer IDs, longitudinal customer history or churn labels; these tasks require additional data. |
| Supervised model training | Suggestions, approvals, changes and event outcomes provide potential source material. No curated labels, reproducible analysis input versions, run IDs or direct suggestion-to-measured-lift dataset; qualitative `expected_impact` is not ground truth. |

## Source files

- [Prisma schema](../../landing-optimizer-api/prisma/schema.prisma) and [PostgreSQL migrations](../../landing-optimizer-api/prisma/migrations/).
- [ClickHouse migrations](../../landing-optimizer-api/clickhouse/migrations/).
- [Ingestion mapping](../../landing-optimizer-api/src/modules/events/events.service.ts), [validation/scrubbing](../../landing-optimizer-api/src/modules/events/event-scrub.ts), [session pseudonymization](../../landing-optimizer-api/src/modules/events/site-auth.service.ts).
- [Snapshots](../../landing-optimizer-api/src/modules/snapshots/snapshots.service.ts), [snapshot validation](../../landing-optimizer-api/src/modules/snapshots/snapshots.dto.ts).
- [AI input/persistence](../../landing-optimizer-api/src/modules/ai/ai.service.ts), [analytics queries](../../landing-optimizer-api/src/modules/analytics/analytics.service.ts), [SDK tracker](../../landing-optimizer-snippet/src/tracker.ts), [edge worker](../edge/src/worker.ts).
