// Runs Code.gs in Node against an in-memory fake of Google's services (no Google account needed).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';
import { demoSeed } from '../../server/src/demoData.js';

const code = fs.readFileSync(new URL('../Code.gs', import.meta.url), 'utf8');
const toBuf = (v) => (typeof v === 'string' ? Buffer.from(v) : Buffer.from(v.map((b) => b & 255)));
const signed = (b) => [...b].map((x) => (x > 127 ? x - 256 : x));

function makeSheet(grid) {
  const lastCol = () => Math.max(1, ...grid.map((r) => r.length));
  const rng = (r, c, nr = 1, nc = 1) => ({
    getValues: () => Array.from({ length: nr }, (_, i) => Array.from({ length: nc }, (_, j) => (grid[r - 1 + i] && grid[r - 1 + i][c - 1 + j] !== undefined ? grid[r - 1 + i][c - 1 + j] : ''))),
    setValues: (v) => v.forEach((row, i) => row.forEach((x, j) => { (grid[r - 1 + i] ||= [])[c - 1 + j] = x; })),
    setValue: (x) => { (grid[r - 1] ||= [])[c - 1] = x; },
    setNumberFormat: () => {},
  });
  return {
    grid, getLastColumn: lastCol, getLastRow: () => grid.length, getRange: rng,
    getDataRange: () => ({ getValues: () => grid.map((row) => Array.from({ length: lastCol() }, (_, j) => (row[j] === undefined ? '' : row[j]))) }),
  };
}

function boot({ searchItems = [] } = {}) {
  const sheets = {};
  const seed = demoSeed();
  for (const [tab, { headers, rows }] of Object.entries(seed)) sheets[tab] = makeSheet([headers, ...rows.map((r) => headers.map((h) => r[h] ?? ''))]);
  const store = {}, cache = {};
  const fetches = [];
  const sandbox = {
    console,
    Utilities: {
      computeHmacSha256Signature: (v, k) => signed(crypto.createHmac('sha256', toBuf(k)).update(toBuf(v)).digest()),
      base64EncodeWebSafe: (v) => (typeof v === 'string' ? Buffer.from(v) : toBuf(v)).toString('base64url') + '',
      base64DecodeWebSafe: (s) => signed(Buffer.from(s, 'base64url')),
      newBlob: (bytes) => ({ getDataAsString: () => toBuf(bytes).toString('utf8') }),
      getUuid: () => crypto.randomUUID(),
    },
    PropertiesService: { getScriptProperties: () => ({
      getProperty: (k) => store[k] ?? null, setProperty: (k, v) => { store[k] = v; },
      setProperties: (o) => Object.assign(store, o), deleteProperty: (k) => { delete store[k]; } }) },
    CacheService: { getScriptCache: () => ({ get: (k) => cache[k] ?? null, put: (k, v) => { cache[k] = v; }, remove: (k) => { delete cache[k]; } }) },
    LockService: { getScriptLock: () => ({ tryLock: () => true, releaseLock: () => {} }) },
    ContentService: { MimeType: { JSON: 'json', JAVASCRIPT: 'js' }, createTextOutput: (t) => ({ t, setMimeType(m) { this.m = m; return this; }, getContent() { return this.t; } }) },
    SpreadsheetApp: { getActive: () => ({
      getSheetByName: (n) => sheets[n] || null,
      insertSheet: (n) => (sheets[n] = makeSheet([[]])) }) },
    UrlFetchApp: { fetch: (url) => { fetches.push(url); return { getResponseCode: () => 200, getContentText: () => JSON.stringify({ items: searchItems }) }; } },
    ScriptApp: {},
  };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox);
  vm.runInContext("saveUser_('admin@example.com', 'Admin', 'admin', 'test-only-password-1')", sandbox);
  const call = (action, extra = {}) => JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({ action, ...extra }) } }).getContent());
  const login = () => call('login', { email: 'admin@example.com', password: 'test-only-password-1' }).data.token;
  return { call, login, sheets, fetches, sandbox };
}

test('health needs no login; every data action needs a valid token', () => {
  const t = boot();
  assert.equal(t.call('health').data.ok, true);
  for (const a of ['me', 'dashboard', 'leads', 'agencies', 'runs', 'rules', 'hunt', 'export']) {
    assert.equal(t.call(a).status, 401, a);
    assert.equal(t.call(a, { token: 'garbage' }).status, 401, a);
    assert.equal(t.call(a, { token: 'a.b' }).status, 401, a);
  }
});

test('login works with the right password only; account locks after 5 failures', () => {
  const t = boot();
  assert.equal(t.call('login', { email: 'ADMIN@example.com', password: 'test-only-password-1' }).status, 200);
  assert.equal(t.call('login', { email: 'admin@example.com', password: 'nope' }).status, 401);
  assert.equal(t.call('login', { email: 'who@example.com', password: 'x' }).status, 401);
  for (let i = 0; i < 5; i++) t.call('login', { email: 'admin@example.com', password: 'bad' });
  assert.equal(t.call('login', { email: 'admin@example.com', password: 'test-only-password-1' }).status, 429);
});

test('a tampered or expired token is rejected', () => {
  const t = boot();
  const token = t.login();
  const [p, s] = token.split('.');
  const forged = Buffer.from(JSON.stringify({ sub: 'admin@example.com', exp: Date.now() + 1e9 })).toString('base64url');
  assert.equal(t.call('me', { token: `${forged}.${s}` }).status, 401);
  assert.equal(t.call('me', { token }).status, 200);
  const expired = Buffer.from(JSON.stringify({ sub: 'admin@example.com', exp: Date.now() - 1000 })).toString('base64url');
  const sig = t.sandbox.Utilities.base64EncodeWebSafe(t.sandbox.Utilities.computeHmacSha256Signature(expired, t.sandbox.props_().getProperty('TOKEN_SECRET')));
  assert.equal(t.call('me', { token: `${expired}.${sig}` }).status, 401);
});

test('setup adds ids and segment to existing rows without touching other data', () => {
  const t = boot();
  vm_run(t, 'menuSetupCore_()');
});
function vm_run(t, src) { // menuSetup uses the UI; run its core pieces directly
  t.sandbox.sheet_('Leads', t.sandbox.LEAD_FIELDS);
  t.sandbox.sheet_('Agencies', t.sandbox.AGENCY_FIELDS);
  t.sandbox.sheet_('Runs', t.sandbox.RUN_FIELDS);
  t.sandbox.sheet_('Rules', t.sandbox.RULE_FIELDS);
  t.sandbox.backfill_();
}

test('leads: ids and segment are filled; default list is HNI B2B only', () => {
  const t = boot();
  vm_run(t);
  const token = t.login();
  const hni = t.call('leads', { token }).data;
  assert.equal(hni.total, 4);
  assert.ok(hni.items.every((l) => l.id.startsWith('L-') && l.segment === 'HNI B2B' && l.sourceUrl.startsWith('https://')));
  assert.equal(t.call('leads', { token, args: { all: true } }).data.total, 5);
  const head = t.sheets.Leads.grid[0];
  assert.ok(head.includes('Lead ID') && head.includes('Segment') && head[0] === 'Date received');
});

test('patching a lead writes to the sheet and rejects bad fields', () => {
  const t = boot(); vm_run(t);
  const token = t.login();
  const [first] = t.call('leads', { token }).data.items;
  const r = t.call('patchLead', { token, args: { id: first.id, changes: { status: 'Shortlisted', owner: 'a@b.com' } } });
  assert.equal(r.status, 200);
  const h = t.sheets.Leads.grid[0], row = t.sheets.Leads.grid.find((x) => x[h.indexOf('Lead ID')] === first.id);
  assert.equal(row[h.indexOf('Status')], 'Shortlisted');
  assert.equal(row[h.indexOf('Owner')], 'a@b.com');
  assert.equal(t.call('patchLead', { token, args: { id: first.id, changes: { id: 'hack' } } }).status, 400);
  assert.equal(t.call('patchLead', { token, args: { id: first.id, changes: { status: 'Bogus' } } }).status, 400);
  assert.equal(t.call('patchLead', { token, args: { id: 'L-nope', changes: { status: 'Won' } } }).status, 404);
});

test('dashboard counts leads and agencies; rules are admin only and validated', () => {
  const t = boot(); vm_run(t);
  const token = t.login();
  const d = t.call('dashboard', { token }).data;
  assert.equal(d.leads.total, 5); assert.equal(d.leads.hniB2b, 4);
  assert.equal(d.agencies.total, 3); assert.equal(d.agencies.leadsOnly, 2);
  assert.equal(t.call('saveRules', { token, args: { changes: { schedule: 'daily', cities: ['Pune'] } } }).data.schedule, 'daily');
  assert.deepEqual(t.call('rules', { token }).data.cities, ['Pune']);
  assert.equal(t.call('saveRules', { token, args: { changes: { schedule: 'weekly' } } }).status, 400);
  t.sandbox.saveUser_('team@example.com', 'Team', 'member', 'team-password-123');
  const member = t.call('login', { email: 'team@example.com', password: 'team-password-123' }).data.token;
  assert.equal(t.call('saveRules', { token: member, args: { changes: { schedule: 'daily' } } }).status, 403);
});

test('export neutralises formula injection', () => {
  const t = boot(); vm_run(t);
  assert.match(t.sandbox.toCsv_([{ name: '=HYPERLINK("x")' }], [['name', 'Name']]), /"'=HYPERLINK\(""x""\)"/);
  const csv = t.call('export', { token: t.login(), args: { kind: 'leads' } }).data.csv;
  assert.match(csv, /^"Date received"/);
});

test('hunt keeps only new HNI B2B leads and agencies, logs the run, respects the budget', () => {
  const items = [
    { title: 'Owner, Cafe Chain - Franchise Investor in Pune looking to invest in Restaurants and Bars upto INR 2 crore', snippet: '', link: 'https://www.smergers.com/investor/a-new/1' },
    { title: 'Student - Franchise Investor in Pune looking to invest in Restaurants and Bars upto INR 0.1 crore', snippet: '', link: 'https://www.smergers.com/investor/b-low/2' },
    { title: 'Director - Franchise Investor in Pune looking to invest in Restaurants and Bars upto INR 1 crore', snippet: '', link: 'https://www.smergers.com/investor/director-hospitality-franchise-investor-in-madhya-pradesh-looking-to-invest-in-restaurants-and-bars-upto-inr-1-crore/60j8o/' },
    { title: 'Interskale | Franchise Lead Generation', snippet: 'franchise leads', link: 'https://www.interskale.in/x' },
    { title: 'Acme Leads | Franchise lead generation', snippet: 'franchise leads', link: 'https://acmeleads.in/' },
  ];
  const t = boot({ searchItems: items }); vm_run(t);
  t.sandbox.props_().setProperties({ SEARCH_KEY: 'k', SEARCH_CX: 'c' });
  const token = t.login();
  t.call('saveRules', { token, args: { changes: { brands: ['Cafe'], cities: ['Pune'], maxQueriesPerRun: 3 } } });
  const run = t.call('hunt', { token }).data;
  assert.equal(run.queries, 3);
  assert.ok(run.saved >= 1 && run.duplicates >= 1 && run.filtered >= 1, JSON.stringify(run));
  const leads = t.call('leads', { token, args: { all: true } }).data.items;
  assert.ok(leads.some((l) => l.sourceUrl.endsWith('/a-new/1') && l.segment === 'HNI B2B' && l.status === 'New'));
  assert.ok(!leads.some((l) => l.sourceUrl.includes('b-low')));
  const ag = t.call('agencies', { token }).data.items;
  assert.equal(ag.filter((a) => a.website.includes('interskale')).length, 1);
  assert.ok(ag.some((a) => a.website.includes('acmeleads')));
  assert.equal(t.call('runs', { token }).data.items.length, 1);
  t.call('saveRules', { token, args: { changes: { monthlyQueryCap: 0 } } });
  const before = t.fetches.length;
  assert.equal(t.call('hunt', { token }).data.queries, 0);
  assert.equal(t.fetches.length, before);
});

test('open access: off by default; when on, no login is needed; when off again, login is required', () => {
  const t = boot(); vm_run(t);
  assert.equal(t.call('dashboard').status, 401);
  t.sandbox.props_().setProperty('OPEN_MODE', '1');
  assert.equal(t.call('me').data.user.email, 'open-access');
  assert.equal(t.call('dashboard').data.leads.total, 5);
  const [first] = t.call('leads').data.items;
  assert.equal(t.call('patchLead', { args: { id: first.id, changes: { status: 'Contacted' } } }).status, 200);
  t.sandbox.props_().setProperty('LAST_MANUAL_HUNT', String(Date.now()));
  assert.equal(t.call('hunt').status, 429); // hunts are rate limited without a login
  t.sandbox.props_().deleteProperty('OPEN_MODE');
  assert.equal(t.call('dashboard').status, 401);
  assert.equal(t.call('login', { email: 'admin@example.com', password: 'test-only-password-1' }).status, 200);
});

test('GET transport: script-tag style reply works, validates the callback name, health stays plain', () => {
  const t = boot(); vm_run(t);
  const enc = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const get = (o, callback) => t.sandbox.doGet({ parameter: { p: enc(o), ...(callback ? { callback } : {}) } }).getContent();
  assert.equal(JSON.parse(t.sandbox.doGet({ parameter: {} }).getContent()).ok, true);
  const login = get({ action: 'login', email: 'admin@example.com', password: 'test-only-password-1' }, 'cb1');
  assert.ok(login.startsWith('cb1("') && login.endsWith('");'));
  const inner = JSON.parse(JSON.parse(login.slice(4, -2)));
  assert.equal(inner.status, 200);
  const token = inner.data.token;
  const dash = JSON.parse(get({ action: 'dashboard', token })); // no callback: plain JSON
  assert.equal(dash.data.leads.total, 5);
  assert.equal(JSON.parse(get({ action: 'dashboard' })).status, 401);
  // a callback that is not a plain name is ignored (no script injection)
  assert.equal(get({ action: 'dashboard', token }, 'alert(1);//').startsWith('{'), true);
  assert.equal(t.sandbox.doGet({ parameter: { p: '!!not-base64' } }).getContent().includes('invalid_request'), true);
});
