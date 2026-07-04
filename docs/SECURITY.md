# Security Model — Landing Optimizer

> Status: Living document. Last updated: 2026-07-02.
> Security is a first-class requirement. This document maps each control to its
> implementation location and to the OWASP Top 10.

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
