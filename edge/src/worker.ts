/**
 * Landing Optimizer — edge ingestion Worker (Cloudflare).
 *
 * Production front for the public snippet endpoints. It performs cheap, fast
 * validation and load-shedding at the edge, attaches a coarse (non-identifying)
 * country only where legally safe, and forwards event batches to the control
 * plane. Config reads are cached at the edge. The Worker holds NO database
 * credentials and never stores PII.
 *
 * Requires @cloudflare/workers-types for full typing; kept dependency-free here.
 */

export interface Env {
  API_ORIGIN: string; // e.g. https://api.landingoptimizer.io
  ALLOWED_COUNTRIES?: string; // optional CSV; empty => omit country entirely
}

const MAX_BODY_BYTES = 32 * 1024;

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === 'POST' && url.pathname === '/v1/events') {
      return handleEvents(request, env, ctx);
    }
    if (request.method === 'GET' && url.pathname.startsWith('/v1/config/')) {
      return handleConfig(request, env, ctx);
    }
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }
    return new Response('Not found', { status: 404 });
  },
};

async function handleEvents(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const cl = Number(request.headers.get('content-length') ?? '0');
  if (cl > MAX_BODY_BYTES) {
    return json({ error: { code: 'validation_error', message: 'body too large' } }, 400, request);
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json({ error: { code: 'validation_error', message: 'invalid json' } }, 400, request);
  }
  if (!isEnvelopeLike(body)) {
    return json({ error: { code: 'validation_error', message: 'invalid envelope' } }, 400, request);
  }

  // Attach coarse country only when explicitly allowed for the region.
  const cf = (request as unknown as { cf?: { country?: string } }).cf;
  const allowed = (env.ALLOWED_COUNTRIES ?? '').split(',').map((s) => s.trim()).filter(Boolean);
  const country = cf?.country && allowed.includes(cf.country) ? cf.country : '';

  // Fire-and-forget forward to the control plane; respond fast (202).
  const forward = fetch(`${env.API_ORIGIN}/v1/events`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Forwarded-Origin': request.headers.get('origin') ?? '',
      'X-Geo-Country': country,
    },
    body: JSON.stringify(body),
  }).catch(() => undefined);
  ctx.waitUntil(forward);

  return new Response(null, { status: 202, headers: corsHeaders(request) });
}

async function handleConfig(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const cache = (caches as unknown as { default: Cache }).default;
  const cacheKey = new Request(request.url, request);
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const url = new URL(request.url);
  const upstream = await fetch(`${env.API_ORIGIN}${url.pathname}`, { method: 'GET' });
  const res = new Response(upstream.body, upstream);
  res.headers.set('Cache-Control', 'public, max-age=30, stale-while-revalidate=300');
  applyCors(res, request);
  if (upstream.ok) ctx.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}

function isEnvelopeLike(v: unknown): boolean {
  if (!v || typeof v !== 'object') return false;
  const e = v as Record<string, unknown>;
  return e['v'] === 1 && typeof e['siteId'] === 'string' && Array.isArray(e['events']);
}

function corsHeaders(request: Request): Record<string, string> {
  const origin = request.headers.get('origin') ?? '*';
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}

function applyCors(res: Response, request: Request): void {
  for (const [k, v] of Object.entries(corsHeaders(request))) res.headers.set(k, v);
}

function json(body: unknown, status: number, request: Request): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(request) },
  });
}
