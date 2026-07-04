/**
 * Seed a demo tenant + site against a running API and print the install snippet.
 * Usage: node scripts/seed.mjs [apiBaseUrl]
 * Default API base: http://localhost:3001/v1
 */
const API = process.argv[2] ?? 'http://localhost:3001/v1';

const rnd = Math.random().toString(36).slice(2, 8);
const email = `demo+${rnd}@example.com`;
const password = 'demo-password-1234';

async function main() {
  console.log(`Seeding against ${API}`);

  const register = await fetchJson('POST', '/auth/register', {
    email,
    password,
    tenantName: 'Demo Workspace',
  });
  const token = register.accessToken;
  console.log(`Created operator ${email}`);

  const site = await fetchJson(
    'POST',
    '/sites',
    { name: 'Demo Site', primaryDomain: 'demo.example.com' },
    token,
  );
  console.log(`Created site ${site.id}`);

  const snippet = await fetchJson('GET', `/sites/${site.id}/snippet`, null, token);
  console.log('\n--- Install snippet ---\n');
  console.log(snippet.html);
  console.log('\nLogin with:', email, '/', password);
}

async function fetchJson(method, path, body, token) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${method} ${path} -> ${res.status}: ${text}`);
  }
  return res.status === 204 ? null : res.json();
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
