// Local stand-in for the deployed Apps Script web app, for trying the app in a browser without Google.
// Usage: node test/dev-server.mjs [open|login]   -> http://localhost:8200/exec  (login: admin@example.com / dev-password-12345)
import fs from 'node:fs';
import vm from 'node:vm';
import http from 'node:http';
import crypto from 'node:crypto';
import { demoSeed } from '../../server/src/demoData.js';

const mode = process.argv[2] || 'open';
const code = fs.readFileSync(new URL('../Code.gs', import.meta.url), 'utf8');
const toBuf = (v) => (typeof v === 'string' ? Buffer.from(v) : Buffer.from(v.map((b) => b & 255)));
const signed = (b) => [...b].map((x) => (x > 127 ? x - 256 : x));
const makeSheet = (grid) => {
  const lastCol = () => Math.max(1, ...grid.map((r) => r.length));
  const rng = (r, c, nr = 1, nc = 1) => ({
    getValues: () => Array.from({ length: nr }, (_, i) => Array.from({ length: nc }, (_, j) => grid[r - 1 + i]?.[c - 1 + j] ?? '')),
    setValues: (v) => v.forEach((row, i) => row.forEach((x, j) => { (grid[r - 1 + i] ||= [])[c - 1 + j] = x; })),
    setValue: (x) => { (grid[r - 1] ||= [])[c - 1] = x; }, setNumberFormat: () => {},
  });
  return { getLastColumn: lastCol, getLastRow: () => grid.length, getRange: rng,
    getDataRange: () => ({ getValues: () => grid.map((row) => Array.from({ length: lastCol() }, (_, j) => row[j] ?? '')) }) };
};
const sheets = {};
for (const [tab, { headers, rows }] of Object.entries(demoSeed())) sheets[tab] = makeSheet([headers, ...rows.map((r) => headers.map((h) => r[h] ?? ''))]);
const store = {}, cache = {};
const ctx = {
  console,
  Utilities: {
    computeHmacSha256Signature: (v, k) => signed(crypto.createHmac('sha256', toBuf(k)).update(toBuf(v)).digest()),
    base64EncodeWebSafe: (v) => (typeof v === 'string' ? Buffer.from(v) : toBuf(v)).toString('base64url'),
    base64DecodeWebSafe: (s) => signed(Buffer.from(s, 'base64url')),
    newBlob: (bytes) => ({ getDataAsString: () => toBuf(bytes).toString('utf8') }), getUuid: () => crypto.randomUUID(),
  },
  PropertiesService: { getScriptProperties: () => ({ getProperty: (k) => store[k] ?? null, setProperty: (k, v) => { store[k] = v; }, setProperties: (o) => Object.assign(store, o), deleteProperty: (k) => { delete store[k]; } }) },
  CacheService: { getScriptCache: () => ({ get: (k) => cache[k] ?? null, put: (k, v) => { cache[k] = v; }, remove: (k) => { delete cache[k]; } }) },
  LockService: { getScriptLock: () => ({ tryLock: () => true, releaseLock: () => {} }) },
  ContentService: { MimeType: { JSON: 'application/json', JAVASCRIPT: 'application/javascript' },
    createTextOutput: (t) => ({ t, setMimeType(m) { this.m = m; return this; }, getContent() { return this.t; } }) },
  SpreadsheetApp: { getActive: () => ({ getSheetByName: (n) => sheets[n] || null, insertSheet: (n) => (sheets[n] = makeSheet([[]])) }) },
  UrlFetchApp: { fetch: () => ({ getResponseCode: () => 500, getContentText: () => '{}' }) }, ScriptApp: {},
  HtmlService: {},
};
vm.createContext(ctx); vm.runInContext(code, ctx);
vm.runInContext("saveUser_('admin@example.com','Admin','admin','dev-password-12345'); sheet_('Leads', LEAD_FIELDS); sheet_('Agencies', AGENCY_FIELDS); sheet_('Runs', RUN_FIELDS); sheet_('Rules', RULE_FIELDS); backfill_();", ctx);
if (mode === 'open') store.OPEN_MODE = '1';

const SHIM = `<script>window.google={script:{run:{_s:null,_f:null,withSuccessHandler(f){const r=Object.create(this);r._s=f;return r},withFailureHandler(f){const r=Object.create(this);r._f=f;return r},api(x){fetch('/api',{method:'POST',body:x}).then(r=>r.text()).then(t=>this._s&&this._s(t)).catch(e=>this._f&&this._f(e))}}}};</script>`;
http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  if (u.pathname === '/' ) { res.writeHead(200, { 'Content-Type': 'text/html' }); return res.end(fs.readFileSync(new URL('../Index.html', import.meta.url), 'utf8').replace('<head>', '<head>' + SHIM)); }
  if (u.pathname === '/api' && req.method === 'POST') { let b = ''; req.on('data', (c) => (b += c)); return req.on('end', () => { res.writeHead(200, { 'Content-Type': 'text/plain' }); res.end(ctx.api(b)); }); }
  const send = (o) => { res.writeHead(200, { 'Content-Type': o.m || 'application/json' }); res.end(o.getContent()); }; // note: no CORS headers on purpose
  if (req.method === 'GET') return send(ctx.doGet({ parameter: Object.fromEntries(u.searchParams) }));
  let body = ''; req.on('data', (c) => (body += c)); req.on('end', () => send(ctx.doPost({ postData: { contents: body } })));
}).listen(8200, () => console.log(`fake Apps Script on http://localhost:8200/exec (${mode} mode)`));
