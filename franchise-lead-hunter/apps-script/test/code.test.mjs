// Runs Code.gs in Node against an in-memory fake of Google's services (no Google account needed).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';
import { demoSeed } from '../../server/src/demoData.js';

const code = fs.readFileSync(new URL('../Code.gs', import.meta.url), 'utf8') + '\n' + fs.readFileSync(new URL('../Social.gs', import.meta.url), 'utf8');
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

function boot({ searchItems = [], fetchHandler = null } = {}) {
  const sheets = {};
  const seed = demoSeed();
  for (const [tab, { headers, rows }] of Object.entries(seed)) sheets[tab] = makeSheet([headers, ...rows.map((r) => headers.map((h) => r[h] ?? ''))]);
  const store = {}, cache = {};
  const fetches = [];
  const fetchLog = [];
  const sandbox = {
    console,
    Utilities: {
      computeHmacSha256Signature: (v, k) => signed(crypto.createHmac('sha256', toBuf(k)).update(toBuf(v)).digest()),
      base64EncodeWebSafe: (v) => (typeof v === 'string' ? Buffer.from(v) : toBuf(v)).toString('base64url') + '',
      base64DecodeWebSafe: (s) => signed(Buffer.from(s, 'base64url')),
      newBlob: (bytes) => ({ getDataAsString: () => toBuf(bytes).toString('utf8') }),
      getUuid: () => crypto.randomUUID(),
      computeDigest: (alg, v) => signed(crypto.createHash('md5').update(v).digest()),
      DigestAlgorithm: { MD5: 'MD5' },
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
    UrlFetchApp: { fetch: (url, opts) => { fetches.push(url); fetchLog.push({ url, opts }); if (fetchHandler) return fetchHandler(url, opts); return { getResponseCode: () => 200, getContentText: () => JSON.stringify({ items: searchItems }) }; } },
    ScriptApp: {},
    HtmlService: { XFrameOptionsMode: { ALLOWALL: 1 }, createHtmlOutputFromFile: (n) => ({ file: n, setTitle() { return this; }, addMetaTag() { return this; }, setXFrameOptionsMode() { return this; }, getContent() { return '<html>' + n + '</html>'; } }) },
  };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox);
  vm.runInContext("saveUser_('admin@example.com', 'Admin', 'admin', 'test-only-password-1')", sandbox);
  const call = (action, extra = {}) => JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify({ action, ...extra }) } }).getContent());
  const login = () => call('login', { email: 'admin@example.com', password: 'test-only-password-1' }).data.token;
  return { call, login, sheets, fetches, fetchLog, sandbox };
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
  assert.equal(JSON.parse(t.sandbox.doGet({ parameter: { health: '1' } }).getContent()).ok, true);
  assert.equal(t.sandbox.doGet({ parameter: {} }).file, 'Index'); // opening the address serves the app page
  assert.equal(JSON.parse(t.sandbox.api(JSON.stringify({ action: 'health' }))).status, 200);
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

test('budget parser reads Indian formats and never guesses', () => {
  const t = boot(); const p = (x) => t.sandbox.parseBudgetCr_(x);
  assert.equal(p('Rs 50 lakh'), 0.5); assert.equal(p('25_50_lakh'), 0.25); assert.equal(p('1-2 crore'), 1);
  assert.equal(p('\u20b91 crore+'), 1); assert.equal(p('1.5 Cr'), 1.5); assert.equal(p('5000000'), 0.5);
  assert.equal(p('Below 25 lakh'), 0.25); assert.equal(p('50'), null); assert.equal(p(''), null); assert.equal(p('not sure'), null);
});

const fbReply = (obj, code = 200) => ({ getResponseCode: () => code, getContentText: () => JSON.stringify(obj) });
function fbServer(leads) {
  return (url) => {
    if (url.includes('/leadgen_forms')) return fbReply({ data: [{ id: 'F1', name: 'Franchise Enquiry', status: 'ACTIVE' }, { id: 'F2', name: 'Old', status: 'ARCHIVED' }] });
    if (url.includes('/F1/leads')) return fbReply({ data: leads });
    return fbReply({ error: { message: 'Unknown path' } }, 400);
  };
}
const FB_LEADS = [
  { id: '111', created_time: '2026-11-13T09:15:00+0000', ad_name: 'HNI cafe ad', field_data: [
    { name: 'full_name', values: ['Rohit Mehra'] }, { name: 'email', values: ['rohit@example.com'] }, { name: 'phone_number', values: ['+919800000001'] },
    { name: 'city', values: ['Pune'] }, { name: 'job_title', values: ['Director'] }, { name: 'company_name', values: ['Mehra Group'] },
    { name: 'investment_budget', values: ['1_2_crore'] }, { name: 'interested_brand', values: ['Cafe / F&B'] }, { name: 'timeline', values: ['Within 3 months'] }] },
  { id: '112', created_time: '2026-11-13T09:20:00+0000', field_data: [{ name: 'full_name', values: ['Asha K'] }, { name: 'email', values: ['asha@example.com'] }, { name: 'investment_budget', values: ['below_25_lakh'] }] },
];

test('facebook import: maps fields, marks HNI B2B, keeps the token out of web addresses, never imports twice', () => {
  const t = boot({ fetchHandler: fbServer(FB_LEADS) }); vm_run(t);
  t.sandbox.props_().setProperties({ FB_PAGE_ID: 'P1', FB_TOKEN: 'SECRET-TOKEN' });
  const r1 = t.sandbox.runFacebookImport_('facebook-manual');
  assert.equal(r1.saved, 2); assert.equal(r1.errors, 0);
  const leads = t.call('leads', { token: t.login(), args: { all: true } }).data.items;
  const a = leads.find((l) => l.sourceUrl === 'fb-lead:111'), b = leads.find((l) => l.sourceUrl === 'fb-lead:112');
  assert.equal(a.name, 'Rohit Mehra'); assert.equal(a.phone, '+919800000001'); assert.equal(a.email, 'rohit@example.com');
  assert.equal(a.city, 'Pune'); assert.equal(a.profession, 'Director, Mehra Group'); assert.equal(a.budgetCr, 1);
  assert.equal(a.segment, 'HNI B2B'); assert.equal(a.quality, 'Warm'); assert.equal(a.brand, 'Cafe / F&B'); assert.equal(a.status, 'New');
  assert.match(a.notes, /Within 3 months/); assert.match(a.source, /Facebook Lead Ad/);
  assert.equal(b.segment, 'Other'); assert.equal(b.budgetCr, 0.25);
  assert.ok(t.fetchLog.every((f) => !f.url.includes('SECRET-TOKEN') && f.opts.headers.Authorization === 'Bearer SECRET-TOKEN'));
  assert.equal(t.sandbox.props_().getProperty('FB_SINCE_F1'), String(Math.floor(Date.parse('2026-11-13T09:20:00Z') / 1000)));
  const r2 = t.sandbox.runFacebookImport_('facebook-manual');
  assert.equal(r2.saved, 0); assert.equal(r2.duplicates, 2);
  assert.ok(t.call('runs', { token: t.login() }).data.items.some((x) => x.trigger === 'facebook-manual'));
});

test('facebook import: errors are logged without leaking the token; no token means a clear note', () => {
  const t = boot({ fetchHandler: () => fbReply({ error: { message: 'Error validating access token' } }, 400) }); vm_run(t);
  assert.match(t.sandbox.runFacebookImport_('facebook-manual').notes, /not connected/);
  t.sandbox.props_().setProperties({ FB_PAGE_ID: 'P1', FB_TOKEN: 'SECRET-TOKEN' });
  const r = t.sandbox.runFacebookImport_('facebook-manual');
  assert.equal(r.saved, 0); assert.equal(r.errors, 1); assert.match(r.notes, /Facebook said: Error validating access token/);
  assert.ok(!r.notes.includes('SECRET-TOKEN'));
});

test('linkedin import: reads the pasted CSV rows, marks them imported, skips duplicates', () => {
  const t = boot(); vm_run(t);
  const sh = t.sandbox.ensureLinkedInTab_();
  const grid = sh.getRange(1, 1, 1, 1) && null; // tab exists with headers
  const tab = t.sheets['Import_LinkedIn'];
  assert.ok(tab);
  const head = ['First Name', 'Last Name', 'Email', 'Phone Number', 'Company Name', 'Job Title', 'City', 'Budget', 'Form Name', 'Created Time', 'Imported'];
  tab.grid.push(['Neha', 'Singh', 'neha@example.com', '+919811111111', 'Singh Retail', 'Founder', 'Delhi', 'Rs 2 crore', 'Franchise Form', '2026-11-12T10:00:00Z', '']);
  tab.grid.push(['Neha', 'Singh', 'neha@example.com', '', '', '', '', '', 'Franchise Form', '', '']);   // same person again
  tab.grid.push(['Vik', 'Rao', 'vik@example.com', '', '', 'Analyst', 'Pune', '20 lakh', 'Franchise Form', '', '']);
  const r1 = t.sandbox.runLinkedInImport_();
  assert.equal(r1.saved, 2); assert.equal(r1.duplicates, 1); assert.equal(r1.errors, 0);
  const leads = t.call('leads', { token: t.login(), args: { all: true } }).data.items;
  const n = leads.find((l) => l.email === 'neha@example.com');
  assert.equal(n.name, 'Neha Singh'); assert.equal(n.profession, 'Founder, Singh Retail'); assert.equal(n.budgetCr, 2); assert.equal(n.segment, 'HNI B2B');
  assert.match(n.source, /LinkedIn Lead Gen Form/); assert.equal(n.dateReceived, '12 Nov 2026');
  assert.ok(tab.grid.slice(1).every((row) => String(row[head.indexOf('Imported')]).length > 0));
  const r2 = t.sandbox.runLinkedInImport_();
  assert.equal(r2.found, 0); assert.equal(r2.saved, 0);
  // a different export layout (columns in another order, other names) still maps
  tab.grid[0].splice(10, 1); tab.grid.length = 1;
  tab.grid[0].push('Full Name', 'Work Email', 'Mobile', 'Imported');
  tab.grid.push(['A. Kumar', 'ak@example.com', '+919822222222', '']);
  const r3 = t.sandbox.runLinkedInImport_();
  assert.equal(r3.saved, 1);
});
