# Event Schema — Landing Optimizer

> Status: Living document. Last updated: 2026-07-02.
> The wire contract between the snippet SDK and the ingestion edge. Designed for
> **privacy by construction**: fields that could carry PII are absent by design.

## 1. Envelope

The SDK batches events and POSTs them to `POST /v1/events` on the edge.

```jsonc
{
  "v": 1,                       // schema version
  "siteId": "uuid",             // public site id
  "ik": "ingest_key",           // public write key (rate-limited, origin-checked)
  "sid": "s_9f3...",            // short-lived, daily-salted session id (opaque)
  "sentAt": 1719900000000,      // client epoch ms (server overrides with authoritative time)
  "ctx": {                      // coarse, derived, non-identifying context
    "path": "/pricing",         // pathname only; query string stripped client-side
    "ref": "google.com",        // referrer HOST only
    "dev": "mobile",            // device category
    "br": "chromium",           // browser category
    "vp": [390, 844],           // viewport bucketed
    "lang": "en"                // 2-letter language, no locale specifics
  },
  "events": [ /* Event[] see below */ ]
}
```

The **edge** derives `country` (coarse, only where legally safe), sets the
authoritative `event_time`, computes `is_bot`, and strips any unexpected fields
before enqueueing. The edge never trusts client `sentAt` for storage ordering.

## 2. Event object

```jsonc
{
  "n": "cta_click",             // event name (enum below)
  "t": 1420,                    // ms since page nav start (relative)
  "sec": "hero",                // section id from page map (optional)
  "sel": "#cta-primary",        // sanitized selector (optional)
  "sd": 75,                     // scroll depth bucket 0..100 (optional)
  "dw": 5300,                   // dwell ms (optional)
  "exp": "uuid",                // experiment id if exposed (optional)
  "var": "uuid",                // variant id if exposed (optional)
  "goal": "signup",             // conversion goal name (conversion only)
  "val": 1,                     // numeric value (optional)
  "p": { "safe": "props" }      // sanitized props, size-capped, PII-scrubbed
}
```

## 3. Event name enum

| name | trigger | notes |
| --- | --- | --- |
| `page_view` | page load | one per navigation |
| `scroll_depth` | scroll milestones | buckets 25/50/75/100 |
| `cta_click` | click on detected CTA | selector recorded |
| `dead_click` | click with no effect | heuristic |
| `rage_click` | >=3 rapid clicks same area | heuristic |
| `form_start` | first focus in a form | never captures values |
| `form_submit` | form submit | never captures values |
| `section_view` | section enters viewport | via IntersectionObserver |
| `dwell` | periodic/sectional dwell | ms |
| `dropoff` | section left / exit intent | aggregate |
| `exposure` | experiment variant applied | for stats |
| `conversion` | `conversion()` API / goal match | value optional |
| `page_map` | structural snapshot | sanitized map in `p` |

## 4. Validation rules (edge + consumer)

- `v`, `siteId`, `ik`, `events[]` required. Batch max 50 events, body max 32 KB.
- `n` MUST be in the enum; unknown names dropped.
- `sel` MUST match a safe selector allowlist (no attribute selectors that could
  leak values; no `[value=...]`).
- `p` MUST pass the PII scrubber: reject/drop keys matching email/phone/cc/ssn
  patterns; truncate strings > 256 chars; max 20 keys.
- `path` MUST NOT contain `?`/`#` (stripped client-side, re-checked at edge).
- Origin header MUST match the site's origin allowlist.

## 5. PII scrubbing (defense in depth)

Client SDK never reads form field values, `input[type=password]`, or elements
marked `data-lo-ignore`. The edge runs a second scrubber:

```
EMAIL   = /[^\s@]+@[^\s@]+\.[^\s@]+/
PHONE   = /(\+?\d[\d\s().-]{7,}\d)/
CC      = /\b(?:\d[ -]*?){13,16}\b/
SSN     = /\b\d{3}-\d{2}-\d{4}\b/
```
Any matching value is dropped (not masked-then-stored). Whole event rejected if
a scrubbed value appeared in a non-`p` field.

## 6. Response contract

`202 Accepted` with empty body on success (fast, fire-and-forget). `400` for
malformed batch (SDK does not retry 4xx). `429` for rate limit (SDK backs off).
Any 5xx: SDK drops the batch silently (never blocks the page).

## 7. Config fetch (SDK → edge/CDN)

`GET /v1/config/:siteId` returns signed config:
```jsonc
{
  "siteId": "uuid",
  "version": 42,
  "sampling": 1.0,
  "experiments": [
    {
      "id": "uuid",
      "allocation": 0.5,
      "targeting": { "device": ["mobile"], "query": { "utm_source": "ads" } },
      "variants": [
        { "id": "uuid", "weight": 0.5, "isControl": true, "changes": [] },
        { "id": "uuid", "weight": 0.5, "isControl": false, "changes": [
          { "selector": "#hero h1", "op": "set_text", "value": "New headline" }
        ] }
      ]
    }
  ],
  "sig": "base64-ed25519-signature"   // over canonical JSON minus sig
}
```
The SDK verifies `sig` with the public key embedded in the loader before
applying any change. See [API_CONTRACTS.md](./API_CONTRACTS.md).
