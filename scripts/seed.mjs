/**
 * Create a demo site for an existing, provisioned account and print the install snippet.
 * Usage: node scripts/seed.mjs [apiBaseUrl]
 * Default API base: http://localhost:3001/v1
 */
const API = process.argv[2] ?? 'http://localhost:3001/v1';

const email = process.env.DEMO_EMAIL;
const password = process.env.DEMO_PASSWORD;

async function main() {
  if (!email || !password) throw new Error('Set DEMO_EMAIL and DEMO_PASSWORD for a provisioned admin/editor account. Create tenants using npm run tenant:create in the API first.');
  console.log(`Seeding against ${API}`);

  const auth = await fetchJson('POST', '/auth/login', {
    email,
    password,
  });
  const token = auth.accessToken;
  console.log(`Signed in as ${email}`);

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
  console.log('\nAccount:', email);
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
