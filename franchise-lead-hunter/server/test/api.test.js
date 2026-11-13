import test from 'node:test';
import assert from 'node:assert/strict';
import { loadConfig } from '../src/config.js';
import { hashPassword } from '../src/auth.js';
import { MemoryStore } from '../src/sheets/memoryStore.js';
import { createRepos } from '../src/repo.js';
import { Hunter } from '../src/hunt/hunt.js';
import { createApp } from '../src/app.js';
import { demoSeed } from '../src/demoData.js';
import { parseInvestor, parseAgency } from '../src/hunt/parse.js';
import { toCsv } from '../src/util.js';

const PW = 'test-only-password-1';
const cfg = loadConfig({
  STORE: 'memory', JWT_SECRET: 'x'.repeat(40), ADMIN_EMAIL: 'admin@example.com',
  ADMIN_PASSWORD_HASH: hashPassword(PW), USERS_FILE: '/nonexistent/users.json',
});

async function boot({ searchResults = [] } = {}) {
  const store = new MemoryStore(demoSeed());
  const repos = await createRepos(store);
  const search = { configured: true, calls: 0, async search() { this.calls += 1; return searchResults; } };
  const hunter = new Hunter({ repos, search });
  const server = createApp({ cfg, repos, hunter }).listen(0);
  const base = `http://127.0.0.1:${server.address().port}`;
  const call = async (path, { method = 'GET', body, token } = {}) => {
    const res = await fetch(base + path, {
      method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    let json = null; try { json = JSON.parse(text); } catch { /* csv */ }
    return { status: res.status, json, text };
  };
  const login = async () => (await call('/api/auth/login', { method: 'POST', body: { email: 'admin@example.com', password: PW } })).json.token;
  return { call, login, store, search, close: () => { server.closeAllConnections(); server.close(); } };
}

test('every data endpoint rejects requests without a valid token', async () => {
  const t = await boot();
  for (const p of ['/api/leads', '/api/agencies', '/api/dashboard', '/api/runs', '/api/rules', '/api/export/leads.csv', '/api/auth/me']) {
    assert.equal((await t.call(p)).status, 401, p);
    assert.equal((await t.call(p, { token: 'garbage' })).status, 401, p);
  }
  assert.equal((await t.call('/health')).status, 200);
  t.close();
});

test('login: right password works, wrong password and unknown user do not', async () => {
  const t = await boot();
  const ok = await t.call('/api/auth/login', { method: 'POST', body: { email: 'ADMIN@example.com', password: PW } });
  assert.equal(ok.status, 200);
  assert.ok(ok.json.token);
  assert.equal((await t.call('/api/auth/login', { method: 'POST', body: { email: 'admin@example.com', password: 'nope' } })).status, 401);
  assert.equal((await t.call('/api/auth/login', { method: 'POST', body: { email: 'who@example.com', password: PW } })).status, 401);
  t.close();
});

test('account locks after 5 failed logins', async () => {
  const t = await boot();
  for (let i = 0; i < 5; i += 1) await t.call('/api/auth/login', { method: 'POST', body: { email: 'admin@example.com', password: 'bad' } });
  const r = await t.call('/api/auth/login', { method: 'POST', body: { email: 'admin@example.com', password: PW } });
  assert.equal(r.status, 429);
  t.close();
});

test('startup backfills ids and segment; default list is HNI B2B only', async () => {
  const t = await boot();
  const token = await t.login();
  const hni = await t.call('/api/leads', { token });
  assert.equal(hni.json.total, 4); // the 0.2 cr student is excluded
  assert.ok(hni.json.items.every((l) => l.id.startsWith('L-') && l.segment === 'HNI B2B' && l.sourceUrl.startsWith('https://')));
  const all = await t.call('/api/leads?segment=all', { token });
  assert.equal(all.json.total, 5);
  assert.equal((await t.call('/api/leads?quality=Hot', { token })).json.total, 0);
  t.close();
});

test('patching a lead writes to the sheet; unknown fields are rejected', async () => {
  const t = await boot();
  const token = await t.login();
  const [first] = (await t.call('/api/leads', { token })).json.items;
  const r = await t.call(`/api/leads/${first.id}`, { method: 'PATCH', token, body: { status: 'Shortlisted', owner: 'a@b.com' } });
  assert.equal(r.status, 200);
  const row = (await t.store.readRows('Leads')).rows.find((x) => x.values['Lead ID'] === first.id);
  assert.equal(row.values.Status, 'Shortlisted');
  assert.equal(row.values.Owner, 'a@b.com');
  assert.equal((await t.call(`/api/leads/${first.id}`, { method: 'PATCH', token, body: { id: 'hack' } })).status, 400);
  assert.equal((await t.call(`/api/leads/${first.id}`, { method: 'PATCH', token, body: { status: 'Bogus' } })).status, 400);
  assert.equal((await t.call('/api/leads/L-nope', { method: 'PATCH', token, body: { status: 'Won' } })).status, 404);
  t.close();
});

test('dashboard summarises leads and agencies', async () => {
  const t = await boot();
  const d = (await t.call('/api/dashboard', { token: await t.login() })).json;
  assert.equal(d.leads.total, 5);
  assert.equal(d.leads.hniB2b, 4);
  assert.equal(d.agencies.total, 3);
  assert.equal(d.agencies.leadsOnly, 2);
  assert.ok(d.leads.pipelineValueCr > 10);
  t.close();
});

test('only admins can change rules', async () => {
  const t = await boot();
  const token = await t.login();
  const r = await t.call('/api/rules', { method: 'PUT', token, body: { schedule: 'daily', cities: ['Pune'] } });
  assert.equal(r.status, 200);
  assert.equal(r.json.schedule, 'daily');
  assert.deepEqual((await t.call('/api/rules', { token })).json.cities, ['Pune']);
  assert.equal((await t.call('/api/rules', { method: 'PUT', token, body: { schedule: 'weekly' } })).status, 400);
  t.close();
});

test('CSV export neutralises formula injection', async () => {
  const csv = toCsv([{ name: '=HYPERLINK("x")', city: 'Pune' }], [['name', 'Name'], ['city', 'City']]);
  assert.match(csv, /"'=HYPERLINK\(""x""\)"/);
  const t = await boot();
  const r = await t.call('/api/export/leads.csv', { token: await t.login() });
  assert.equal(r.status, 200);
  assert.match(r.text, /^"Date received"/);
  t.close();
});

test('parsers read investor and agency results', () => {
  const p = parseInvestor({
    title: 'Owner, Cafe Chain - Franchise Investor in Pune looking to invest in Restaurants and Bars upto INR 2 crore',
    snippet: '', link: 'https://www.smergers.com/investor/owner-cafe-chain-franchise-investor-in-pune-looking-to-invest-in-restaurants-and-bars-upto-inr-2-crore/abc/',
  });
  assert.equal(p.budgetCr, 2);
  assert.equal(p.city, 'Pune');
  const slug = parseInvestor({ title: 'Investor profile', snippet: '', link: 'https://www.smergers.com/investor/director-hospitality-franchise-investor-in-madhya-pradesh-looking-to-invest-in-restaurants-and-bars-upto-inr-1-crore/60j8o/' });
  assert.equal(slug.budgetCr, 1);
  assert.equal(slug.profession, 'Director Hospitality');
  assert.equal(parseInvestor({ title: 'Random blog post', snippet: '', link: 'https://example.com/x' }), null);
  const a = parseAgency({ title: 'Interskale | Franchise Lead Generation', snippet: 'Paid-ad franchise leads. From Rs 1 lakh.', link: 'https://www.interskale.in/x' });
  assert.equal(a.name, 'Interskale');
  assert.equal(a.leadsOnly, 'Yes');
});

test('hunt keeps only new HNI B2B leads and new agencies, logs the run, respects the budget', async () => {
  const results = [
    { title: 'Owner, Cafe Chain - Franchise Investor in Pune looking to invest in Restaurants and Bars upto INR 2 crore', snippet: '', link: 'https://www.smergers.com/investor/a-new/1' },
    { title: 'Student - Franchise Investor in Pune looking to invest in Restaurants and Bars upto INR 0.1 crore', snippet: '', link: 'https://www.smergers.com/investor/b-low/2' },
    { title: 'Director - Franchise Investor in Pune looking to invest in Restaurants and Bars upto INR 1 crore', snippet: '', link: 'https://www.smergers.com/investor/director-hospitality-franchise-investor-in-madhya-pradesh-looking-to-invest-in-restaurants-and-bars-upto-inr-1-crore/60j8o/' },
    { title: 'Interskale | Franchise Lead Generation', snippet: 'franchise leads', link: 'https://www.interskale.in/x' },
    { title: 'Acme Leads | Franchise lead generation', snippet: 'franchise leads', link: 'https://acmeleads.in/' },
  ];
  const t = await boot({ searchResults: results });
  const token = await t.login();
  await t.call('/api/rules', { method: 'PUT', token, body: { brands: ['Cafe'], cities: ['Pune'], maxQueriesPerRun: 3 } });
  const run = (await t.call('/api/hunt/run', { method: 'POST', token })).json;
  assert.equal(run.queries, 3);
  assert.ok(run.saved >= 1 && run.duplicates >= 1 && run.filtered >= 1, JSON.stringify(run));
  const leads = (await t.call('/api/leads?segment=all', { token })).json.items;
  assert.ok(leads.some((l) => l.sourceUrl === 'https://www.smergers.com/investor/a-new/1' && l.segment === 'HNI B2B' && l.status === 'New'));
  assert.ok(!leads.some((l) => l.sourceUrl.includes('b-low')));
  const agencies = (await t.call('/api/agencies', { token })).json.items;
  assert.equal(agencies.filter((a) => a.website.includes('interskale')).length, 1); // not duplicated
  assert.ok(agencies.some((a) => a.website.includes('acmeleads')));
  assert.equal((await t.call('/api/runs', { token })).json.items.length, 1);
  // monthly budget: a cap of 0 stops searching
  await t.call('/api/rules', { method: 'PUT', token, body: { monthlyQueryCap: 0 } });
  const before = t.search.calls;
  const blocked = (await t.call('/api/hunt/run', { method: 'POST', token })).json;
  assert.equal(blocked.queries, 0);
  assert.equal(t.search.calls, before);
  t.close();
});
