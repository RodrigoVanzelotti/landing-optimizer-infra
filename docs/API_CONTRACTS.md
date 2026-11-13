# API Contracts — Landing Optimizer

> Status: Living document. Last updated: 2026-09-09.
> Two API surfaces: the **public edge** (snippet-facing, unauthenticated but
> origin/key gated) and the **control-plane API** (dashboard/operator, JWT
> authenticated). All request/response bodies are validated with Zod (edge) or
> class-validator/Zod DTOs (NestJS). All list endpoints are tenant-scoped.

## Conventions
- Base path: `/v1`.
- Auth (control plane): `Authorization: Bearer <access_jwt>` (short-lived, 15m)
  + refresh cookie (httpOnly, secure, sameSite=strict).
- Content type: `application/json`.
- Errors: RFC 7807-ish `{ "error": { "code", "message", "details?" } }`.
- Idempotency: mutating snippet-config publishes accept `Idempotency-Key`.
- Pagination: `?limit=&cursor=`; responses include `{ data, nextCursor }`.

---

## A. Public edge API (snippet-facing)

### `GET /v1/config/:siteId`
Returns signed site config (see EVENT_SCHEMA §7). Cached at CDN.
- 200 → signed config JSON.
- 404 → unknown/paused site.
- Headers: `Cache-Control: public, max-age=30, stale-while-revalidate=300`.

### `POST /v1/events`
Ingest a batch of events. Origin + `ik` (ingest key) validated.
- Body: event envelope (EVENT_SCHEMA §1).
- 202 → accepted (empty body).
- 400 → malformed. 401/403 → bad key/origin. 429 → rate limited.
- `page_map` events are split off and upserted into Postgres `page_map`
  (one row per site + path); all other events land in ClickHouse.

---

## B. Control-plane API (dashboard/operator)

### Auth
| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/v1/auth/register` | `{ token, name, email, password }`; invitation required | `{ accessToken, user }` + refresh cookie |
| POST | `/v1/auth/login` | `{ email, password, rememberMe? }` | `{ accessToken, user }` + refresh cookie |
| POST | `/v1/auth/refresh` | (cookie) | `{ accessToken }` |
| POST | `/v1/auth/logout` | — | 204; revokes all account sessions |
| POST | `/v1/auth/reset-password` | `{ token, password }` | 204; revokes account sessions |
| GET | `/v1/auth/me` | — | `{ id, name, email, tenantId, role, platformOwner }` |

### Platform tenant administration (platform owner only)
| Method | Path | Notes |
| --- | --- | --- |
| POST/GET | `/v1/platform/tenants` | provision with first-administrator invitation / list |
| GET | `/v1/platform/tenants/:id` | details, members and pending invitations |
| POST | `/v1/platform/tenants/:id/archive` | exact name confirmation; revokes member sessions |
| POST | `/v1/platform/tenants/:id/restore` | restores access; requires a fresh login |
| POST | `/v1/platform/tenants/:id/users/:userId/password-reset` | issue a one-use reset link |

### Sites
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/v1/sites` | `{ name, primaryDomain }` → generates keys + `ingestKey` |
| GET | `/v1/sites` | list tenant sites |
| GET | `/v1/sites/:id` | |
| PATCH | `/v1/sites/:id` | update settings/sampling/status |
| GET | `/v1/sites/:id/snippet` | returns install snippet + GTM variant |
| GET | `/v1/sites/:id/origins` / POST / DELETE | manage origin allowlist |
| POST | `/v1/sites/:id/config/publish` | recompile + sign + cache; no CDN purge is performed |

### Conversion goals
| Method | Path |
| --- | --- |
| POST/GET/PATCH/DELETE | `/v1/sites/:id/goals[/:goalId]` |

### Page snapshots (behavior heatmap)

`lo-capture.js` downloads a file. A logged-in editor uploads it here; site ownership
is checked server-side. The public ingest key cannot authorize this operation.

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/v1/snapshots` | editor; base64 image ≤ 3 MB, decoded dimensions ≤ 24 million pixels; 201 `{ "saved": true }` |
| GET | `/v1/sites/:id/snapshots` | list snapshot metadata (newest first) |
| GET | `/v1/sites/:id/snapshots/:snapshotId` | metadata + element geometry (`nodes`) |
| GET | `/v1/sites/:id/snapshots/:snapshotId/image` | image bytes; `Cache-Control: no-store` |
| DELETE | `/v1/sites/:id/snapshots/:snapshotId` | editor; audited; 204 |

### Experiments
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/v1/experiments` | create (status `draft`) with variants + changes |
| GET | `/v1/experiments?siteId=&status=` | list |
| GET | `/v1/experiments/:id` | detail incl. variants/changes/approval |
| PATCH | `/v1/experiments/:id` | edit while `draft`/`ai_suggested` |
| POST | `/v1/experiments/:id/submit` | → `pending_review` |
| POST | `/v1/experiments/:id/approve` | reviewer → `approved` (records approval) |
| POST | `/v1/experiments/:id/reject` | reviewer → `rejected` |
| POST | `/v1/experiments/:id/schedule` | `{ startAt }` → `scheduled` |
| POST | `/v1/experiments/:id/start` | → `running` (publishes config) |
| POST | `/v1/experiments/:id/pause` | → `paused` |
| POST | `/v1/experiments/:id/complete` | → `completed` (`{ winnerVariantId? }`) |
| POST | `/v1/experiments/:id/rollback` | → `rolled_back` (restores original) |
| POST | `/v1/experiments/:id/kill` | emergency kill switch (immediate) |

State transitions are enforced server-side by a guarded state machine; invalid
transitions return `409 Conflict`.

### Approvals
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/v1/approvals?status=pending` | review queue |
| GET | `/v1/approvals/:id` | full context (original/proposed/risk/checklist) |

### AI suggestions
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/v1/sites/:id/ai/analyze` | trigger AI analysis (async job) |
| GET | `/v1/sites/:id/ai/suggestions` | list suggestions |
| POST | `/v1/ai/suggestions/:id/materialize` | convert suggestion → `ai_suggested` experiment |

Internal API → AI service:
| Method | Path | Notes |
| --- | --- | --- |
| POST | `(ai) /internal/analyze` | `{ pageMap, metrics, guardrails }` → structured suggestions (JWT/mTLS) |
| POST | `(ai) /internal/score` | `{ pageMap, metrics }` → `{ score, factors }` |

### Analytics (read, from ClickHouse)
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/v1/analytics/overview?siteId=&from=&to=` | KPIs (views, conversions, rate) |
| GET | `/v1/analytics/funnel?siteId=` | event funnel |
| GET | `/v1/analytics/sections?siteId=` | section performance (heat-style) |
| GET | `/v1/analytics/heatmap?siteId=&path=&from=&to=` | per-selector clicks/hover/frustration + scroll-depth distribution for one page path (defaults: `path=/`, last 30 days) |
| GET | `/v1/analytics/experiments/:id/results` | exposures/conversions + significance |

### Brand guardrails
| Method | Path |
| --- | --- |
| GET/PUT | `/v1/sites/:id/guardrails` |

### Audit log
| Method | Path |
| --- | --- |
| GET | `/v1/audit?from=&to=&action=` |

### Team
| Method | Path |
| --- | --- |
| GET/POST/PATCH/DELETE | `/v1/team/members[/:userId]` (role management) |

---

## C. Standard error codes
`unauthenticated`, `forbidden`, `not_found`, `validation_error`,
`invalid_state_transition`, `rate_limited`, `conflict`, `internal_error`.

## D. Example: create experiment
```jsonc
// POST /v1/experiments
{
  "siteId": "…",
  "name": "Hero headline test",
  "hypothesis": "A benefit-led headline lifts signups",
  "type": "headline",
  "primaryGoalId": "…",
  "allocation": 0.5,
  "targeting": { "device": ["desktop"] },
  "variants": [
    { "name": "control", "isControl": true, "weight": 0.5, "changes": [] },
    { "name": "v1", "isControl": false, "weight": 0.5, "changes": [
      { "selector": "#hero h1", "op": "set_text",
        "originalValue": "Welcome", "proposedValue": "Ship faster today" }
    ] }
  ]
}
// 201 → { "id": "…", "status": "draft", ... }
```
