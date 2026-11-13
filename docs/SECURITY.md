# Security Model — Landing Optimizer

> Implementation status reviewed: 2026-11-13. The design targets below are not
> evidence that each control is implemented or deployed. See
> [the security review](../../artifacts/security-review/REPORT.md) for findings,
> verification limits, rollout requirements and unresolved architectural decisions.

## Current implementation

- The API uses Argon2id passwords and invitation-based registration, not Auth.js
  or Clerk. Access tokens stay in dashboard memory; refresh tokens use HttpOnly,
  Secure, SameSite=Strict cookies. Refresh has a fixed deadline but is not backed
  by a rotating, replay-detecting session store. Logout advances the account session
  version and writes an audit record in a transaction, revoking all account sessions.
  Membership removal and tenant archival also advance account versions; restoration
  requires a fresh login and does not resurrect previously issued tokens.
- Global JWT and role guards protect control-plane endpoints. Roles, membership,
  account session version and tenant archive state are read from the database.
  Services enforce object ownership. There is no implemented TenantGuard,
  automatic Prisma tenant middleware, or RLS policy in the checked-in migrations.
- Shared Redis limits use atomic increment/expiry, with PostgreSQL fallback that
  does not silently allow traffic on dependency failure. Auth and control-plane
  limits now exist in code; deployed quotas and proxy behavior still need validation.
- Site signing keys use AES-256-GCM with an environment-supplied key; this is not
  direct KMS signing. Production validation rejects the development encryption
  fallback and weak/default service credentials. Secret Manager supplies the key
  in the GCP configuration. Rotation and re-encryption need an operator procedure.
- Events use a public ingest key and an origin allowlist. Empty allowlists deny
  ingestion. Origins are forgeable by non-browser clients: these controls do not
  establish operator identity. Snapshots require an authenticated dashboard editor
  and a tenant ownership check; the capture bundle downloads a file for upload.
- Public config reads no longer increment database versions. Publication is
  serialized and cached configs are checked against the database version.
  Live experiment changes invalidate that version in their transaction.
- Browser output uses React escaping; no dashboard raw HTML injection was found.
  The dashboard CSP restricts frames, plugins, base URLs and form actions. It does
  not yet restrict script execution with nonces/hashes.
- Collection attempts to minimize visitor PII. Pattern scrubbing cannot guarantee
  that paths, custom labels or screenshots contain none. Account emails and names
  are deliberately stored. Daily pseudonym salts now depend on a server secret.
- Audit writes accompany many mutations in their database transaction. Logs are
  not demonstrated to be immutable; OTel, Sentry, anomaly alerts, MFA, signed CI
  artifacts and comprehensive secret scanning are not established by this review.
- Framework and validation dependencies were upgraded in the security review.
  API and dashboard CI now reject high/critical dependency advisories rather than
  ignoring audit failures. See the review's dated audit artifacts for exact results.

## Historical design targets

The remaining sections describe the intended defense-in-depth model. Verify each
claim against code and deployment state before relying on it.

## 1. Threat model (STRIDE, abridged)

| Threat | Vector | Mitigation |
| --- | --- | --- |
| Spoofing | Forged events / fake site | Origin allowlist + public ingest key + rate limit; config signature verify. |
| Tampering | Modified experiment config in transit | Ed25519-signed config; SDK verifies before applying. |
| Repudiation | Who approved this change? | Immutable audit log with actor + timestamp. |
| Information disclosure | PII leakage | No-PII-by-design schema + dual scrubbing + no raw form reads. |
| Denial of service | Ingestion flood | Edge rate limiting, sampling, load shedding, queue buffering. |
| Elevation of privilege | Cross-tenant access | Tenant guard + Prisma middleware + Postgres RLS. |

## 2. Tenant isolation (defense in depth)

1. **AuthN**: short-lived JWT (15 min) with `sub`, `tenantId`, `role`.
2. **AuthZ guard**: NestJS `TenantGuard` + `RolesGuard` on every route.
3. **ORM middleware**: Prisma middleware injects `tenant_id` filter; rejects
   queries missing a tenant scope.
4. **Database RLS**: Postgres policies keyed on `current_setting('app.tenant_id')`
   set per request transaction — final backstop even if app logic is bypassed.
5. **Analytics**: ClickHouse queries always inject `tenant_id`/`site_id`
   server-side; client can never supply them directly.

## 3. Snippet / edge security

- **Origin allowlist** per site; `Origin`/`Referer` checked at edge.
- **Public ingest key** is write-only, rate-limited, and safe to expose (cannot
  read data, cannot mutate config).
- **Config signing**: config compiled server-side, signed with per-site Ed25519
  key; private key encrypted at rest (KMS/Vault). SDK verifies signature.
- **No secrets in the browser**: only `siteId`, ingest key, and a public key.
- **CSP-safe**: SDK works with strict CSP. Guidance: allow
  `script-src` for the CDN host (or nonce/hash the loader), `connect-src` for
  the ingestion + config hosts. SDK adds no inline event handlers.
- **DOM safety**: variant changes use a safe op allowlist. `set_html_safe`
  sanitizes with an allowlist sanitizer; selectors validated against an
  allowlist grammar (no `[value]`, no script injection). Never `eval`.

## 4. Application security (OWASP Top 10 mapping)

| OWASP | Control |
| --- | --- |
| A01 Broken Access Control | Tenant/roles guards + RLS + object-level checks. |
| A02 Cryptographic Failures | TLS 1.2+; Ed25519 config signing; Argon2id password/API-key hashing; KMS for keys at rest. |
| A03 Injection | Parameterized ClickHouse/SQL; Prisma; Zod validation; selector allowlist; HTML sanitizer. |
| A04 Insecure Design | Threat model, state machine, no-PII schema, human approval gate. |
| A05 Security Misconfiguration | Hardened Helmet headers, least-priv IAM, no default creds, infra as code. |
| A06 Vulnerable Components | Renovate/Dependabot, `npm audit`/`pip-audit` in CI, pinned versions. |
| A07 AuthN Failures | Short-lived JWT, rotating refresh, rate-limited login, MFA-ready. |
| A08 Data Integrity Failures | Signed config, signed CI artifacts, SRI on CDN loader. |
| A09 Logging/Monitoring | Structured audit + OTel + Sentry; alerting on anomalies. |
| A10 SSRF | AI service has no arbitrary URL fetch; egress allowlist. |

## 5. Secrets management
- No secrets in repos; `.env.example` only.
- Dev: Docker Compose env; Prod: AWS Secrets Manager / Vault / Doppler.
- Signing keys in KMS; app receives only decrypt grants (least privilege).

## 6. Data protection
- **No PII stored** (see PRODUCT_REQUIREMENTS §4, EVENT_SCHEMA §5).
- Encryption in transit (TLS) and at rest (DB volumes, KMS).
- `session_id` daily-salted, non-linkable, TTL'd.
- `ip_hash` in audit log is salted SHA-256, never raw IP.
- Configurable data region per tenant.

## 7. AuthN/Z details
- Dashboard users: Auth.js (or Clerk) → issues session; API mints short JWT.
- Service-to-service: signed JWT (aud-scoped) or mTLS on internal network.
- API keys: Argon2id-hashed, scoped, revocable, `last_used_at` tracked.
- Cookies: `httpOnly`, `secure`, `sameSite=strict`, `__Host-` prefix.

## 8. Rate limiting & abuse
- Edge: token-bucket per `siteId`+IP-hash in Redis.
- Control plane: per-user + per-IP limits; stricter on auth endpoints.
- Bot filtering at aggregate level (UA + heuristics), never per-user tracking.

## 9. Secure SDLC
- Zod/DTO validation at every boundary; output encoding in dashboard (React
  escapes by default; sanitize any `dangerouslySetInnerHTML`).
- SAST + dependency scanning + secret scanning in GitHub Actions.
- Signed, versioned SDK releases with SRI hashes published.
- Least-privilege CI credentials (OIDC to cloud, no long-lived keys).

## 10. Incident response
- Kill switch per experiment + global site pause.
- Rollback restores `original_value` from `variant_change`.
- Audit log supports forensic reconstruction (no PII involved).
