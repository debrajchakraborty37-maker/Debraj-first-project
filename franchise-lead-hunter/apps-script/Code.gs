/**
 * Franchise Lead Hunter: the Google Sheet is the server.
 * This script lives inside the Sheet (Extensions > Apps Script). It
 *  - serves the app's API as a web app (every call except "health" needs a login token),
 *  - reads and writes the Leads, Agencies, Runs and Rules tabs,
 *  - runs the hourly hunt with a time trigger, using Google Programmable Search.
 * Passwords are never stored: only a salted hash is kept in Script Properties.
 */

// ---------- schema: field key -> column header (first columns match your existing tabs) ----------
var LEAD_FIELDS = [
  ['dateReceived', 'Date received'], ['source', 'Source'], ['brand', 'Brand interested'], ['name', 'Name'],
  ['phone', 'Phone'], ['email', 'Email'], ['city', 'City'], ['profession', 'Profession'],
  ['budgetCr', 'Stated budget (Rs crore)'], ['quality', 'Lead quality'], ['status', 'Status'],
  ['nextFollowUp', 'Next follow-up'], ['notes', 'Notes'],
  ['id', 'Lead ID'], ['owner', 'Owner'], ['sourceUrl', 'Source URL'], ['segment', 'Segment']];
var AGENCY_FIELDS = [
  ['dateAdded', 'Date added'], ['name', 'Agency name'], ['type', 'Type'], ['website', 'Website'],
  ['phone', 'Public phone'], ['email', 'Public email'], ['city', 'City'], ['leadsOnly', 'Leads only?'],
  ['services', 'Services and claims'], ['pricing', 'Pricing signals'], ['sourceUrl', 'Source URL'],
  ['status', 'Status'], ['notes', 'Notes'], ['linkedin', 'LinkedIn Profile'], ['id', 'Agency ID'], ['owner', 'Owner']];
var RUN_FIELDS = [
  ['id', 'Run ID'], ['startedAt', 'Started'], ['finishedAt', 'Finished'], ['trigger', 'Trigger'], ['by', 'By'],
  ['queries', 'Queries'], ['found', 'Found'], ['saved', 'Saved'], ['duplicates', 'Duplicates'],
  ['filtered', 'Filtered out'], ['errors', 'Errors'], ['notes', 'Notes']];
var RULE_FIELDS = [['key', 'Key'], ['value', 'Value']];

var STATUSES = ['New', 'Shortlisted', 'Contacted', 'Meeting', 'Negotiation', 'Won', 'Lost', 'Skipped'];
var QUALITIES = ['Hot', 'Warm', 'Cold'];
var DEFAULT_RULES = {
  brands: ['Cafe / F&B', 'Beauty and wellness', 'Gyms'], cities: ['Delhi', 'Bangalore', 'Mumbai'],
  hniMinCr: 1, maxBudgetCr: 25, schedule: 'hourly', maxQueriesPerRun: 12, monthlyQueryCap: 2000 };
var LEAD_PATCH = ['status', 'nextFollowUp', 'notes', 'owner', 'quality', 'phone', 'email'];
var AGENCY_PATCH = ['status', 'notes', 'owner', 'phone', 'email', 'city'];
var OPEN_USER = { email: 'open-access', name: 'Team (no login)', role: 'admin' };
var TOKEN_HOURS = 12, HASH_ROUNDS = 3000, MAX_FAILS = 5, LOCK_SECONDS = 900;

// ---------- small helpers ----------
function props_() { return PropertiesService.getScriptProperties(); }
function openMode_() { return props_().getProperty('OPEN_MODE') === '1'; } // temporary: no login needed
function fail_(status, error) { var e = new Error(error); e.status = status; return e; }
function pad2_(n) { return (n < 10 ? '0' : '') + n; }
var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function fmtDate_(d) { return pad2_(d.getUTCDate()) + ' ' + MONTHS[d.getUTCMonth()] + ' ' + d.getUTCFullYear(); }
function parseDate_(s) {
  var m = /^(\d{1,2}) ([A-Za-z]{3}) (\d{4})/.exec(String(s || '').trim());
  if (!m) return null;
  var i = MONTHS.map(function (x) { return x.toLowerCase(); }).indexOf(m[2].toLowerCase());
  return i < 0 ? null : new Date(Date.UTC(Number(m[3]), i, Number(m[1])));
}
function newId_(prefix) { return prefix + '-' + Utilities.getUuid().replace(/-/g, '').slice(0, 10); }
function extractUrl_(t) { var m = /https?:\/\/[^\s"'<>)]+/i.exec(String(t || '')); return m ? m[0] : ''; }
function domainOf_(u) {
  var m = /^(?:https?:\/\/)?(?:www\.)?([^\/?#:]+)/i.exec(String(u || '').trim());
  return m ? m[1].toLowerCase() : '';
}
function safeCell_(v) { var s = String(v == null ? '' : v); return /^[=+\-@\t\r]/.test(s) ? "'" + s : s; }
function titleCase_(s) { return s.replace(/\b[a-z]/g, function (c) { return c.toUpperCase(); }); }

// ---------- B2B HNI rule ----------
var B2B_TITLE = /\b(owner|proprietor|founder|co-?founder|director|managing|md|ceo|cfo|coo|cxo|chairman|promoter|partner|president|entrepreneur|businessman|business ?man|industrialist|investor|general manager|senior manager|vice president|vp|head)\b/i;
function segmentOf_(o, hniMin) {
  return B2B_TITLE.test(String(o.profession || '')) && Number(o.budgetCr) >= hniMin ? 'HNI B2B' : 'Other';
}
function qualityOf_(b) { b = Number(b); return b >= 1.5 ? 'Hot' : b >= 1 ? 'Warm' : 'Cold'; }

// ---------- sheet access ----------
function sheet_(tab, fields) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(tab) || ss.insertSheet(tab);
  var last = Math.max(sh.getLastColumn(), 1);
  var headers = sh.getRange(1, 1, 1, last).getValues()[0].map(String);
  var missing = fields.map(function (f) { return f[1]; }).filter(function (h) { return headers.indexOf(h) < 0; });
  if (missing.length) {
    var start = headers.filter(function (h) { return h !== ''; }).length;
    sh.getRange(1, start + 1, 1, missing.length).setValues([missing]);
  }
  return sh;
}
function headers_(sh) { return sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), 1)).getValues()[0].map(String); }
function cellOut_(key, v) {
  if (v instanceof Date) return fmtDate_(new Date(Date.UTC(v.getFullYear(), v.getMonth(), v.getDate())));
  if (key === 'budgetCr') { var n = parseFloat(v); return isFinite(n) ? n : null; }
  return v == null ? '' : v;
}
function readAll_(tab, fields) {
  var sh = sheet_(tab, fields), data = sh.getDataRange().getValues();
  var h = data[0].map(String), idx = {};
  fields.forEach(function (f) { idx[f[0]] = h.indexOf(f[1]); });
  var rows = [];
  for (var r = 1; r < data.length; r++) {
    var o = { _row: r + 1 };
    fields.forEach(function (f) { o[f[0]] = idx[f[0]] < 0 ? '' : cellOut_(f[0], data[r][idx[f[0]]]); });
    rows.push(o);
  }
  return rows;
}
function writeCells_(tab, fields, row, values) {
  var sh = sheet_(tab, fields), h = headers_(sh);
  fields.forEach(function (f) {
    if (!(f[0] in values)) return;
    var c = h.indexOf(f[1]);
    if (c < 0) return;
    var cell = sh.getRange(row, c + 1), v = values[f[0]];
    if (typeof v === 'number') cell.setValue(v); else { cell.setNumberFormat('@'); cell.setValue(v == null ? '' : String(v)); }
  });
}
function appendRow_(tab, fields, obj) {
  var sh = sheet_(tab, fields), row = sh.getLastRow() + 1;
  writeCells_(tab, fields, row, obj);
  return row;
}
function publicRow_(o) { var c = {}; Object.keys(o).forEach(function (k) { if (k !== '_row') c[k] = o[k]; }); return c; }

function backfill_() { // one-time: ids and derived columns for rows that pre-date the app; only fills blanks
  var rules = getRules_();
  readAll_('Leads', LEAD_FIELDS).forEach(function (l) {
    if (!l.name) return;
    var ch = {};
    if (!l.id) ch.id = newId_('L');
    if (!l.sourceUrl && extractUrl_(l.notes)) ch.sourceUrl = extractUrl_(l.notes);
    var seg = segmentOf_(l, rules.hniMinCr);
    if (l.segment !== seg) ch.segment = seg;
    if (Object.keys(ch).length) writeCells_('Leads', LEAD_FIELDS, l._row, ch);
  });
  readAll_('Agencies', AGENCY_FIELDS).forEach(function (a) {
    if (a.name && !a.id) writeCells_('Agencies', AGENCY_FIELDS, a._row, { id: newId_('A') });
  });
  sheet_('Runs', RUN_FIELDS);
}

function getRules_() {
  var out = JSON.parse(JSON.stringify(DEFAULT_RULES));
  readAll_('Rules', RULE_FIELDS).forEach(function (r) {
    if (r.key in DEFAULT_RULES) { try { out[r.key] = JSON.parse(r.value); } catch (e) { /* keep default */ } }
  });
  return out;
}
function setRules_(partial) {
  var next = getRules_();
  Object.keys(partial).forEach(function (k) { next[k] = partial[k]; });
  var rows = readAll_('Rules', RULE_FIELDS);
  Object.keys(next).forEach(function (k) {
    var hit = rows.filter(function (r) { return r.key === k; })[0], v = JSON.stringify(next[k]);
    if (hit) writeCells_('Rules', RULE_FIELDS, hit._row, { value: v });
    else appendRow_('Rules', RULE_FIELDS, { key: k, value: v });
  });
  return next;
}

// ---------- passwords and tokens ----------
function bytesToHex_(b) { return b.map(function (x) { return ((x & 255) + 256).toString(16).slice(1); }).join(''); }
function hashPw_(password, salt) {
  var h = Utilities.computeHmacSha256Signature(salt + ':' + password, salt);
  for (var i = 0; i < HASH_ROUNDS; i++) h = Utilities.computeHmacSha256Signature(h, salt);
  return bytesToHex_(h);
}
function same_(a, b) { // constant-time string compare
  a = String(a); b = String(b);
  var d = a.length ^ b.length;
  for (var i = 0; i < Math.max(a.length, b.length); i++) d |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return d === 0;
}
function users_() {
  var p = props_(), list = [];
  if (p.getProperty('ADMIN_EMAIL')) list.push({ email: p.getProperty('ADMIN_EMAIL'), name: p.getProperty('ADMIN_NAME') || 'Admin', role: 'admin', salt: p.getProperty('ADMIN_SALT'), hash: p.getProperty('ADMIN_HASH') });
  try { JSON.parse(p.getProperty('USERS') || '[]').forEach(function (u) { list.push(u); }); } catch (e) { /* ignore */ }
  return list;
}
function findUser_(email) {
  email = String(email || '').trim().toLowerCase();
  return users_().filter(function (u) { return u.email === email; })[0] || null;
}
function secret_() {
  var p = props_(), s = p.getProperty('TOKEN_SECRET');
  if (!s) { s = Utilities.getUuid() + Utilities.getUuid() + Utilities.getUuid(); p.setProperty('TOKEN_SECRET', s); }
  return s;
}
function signToken_(user) {
  var payload = Utilities.base64EncodeWebSafe(JSON.stringify({ sub: user.email, exp: Date.now() + TOKEN_HOURS * 3600000 }));
  var sig = Utilities.base64EncodeWebSafe(Utilities.computeHmacSha256Signature(payload, secret_()));
  return payload + '.' + sig;
}
function verifyToken_(token) {
  var parts = String(token || '').split('.');
  if (parts.length !== 2) throw fail_(401, 'unauthorized');
  var want = Utilities.base64EncodeWebSafe(Utilities.computeHmacSha256Signature(parts[0], secret_()));
  if (!same_(parts[1], want)) throw fail_(401, 'unauthorized');
  var p;
  try { p = JSON.parse(Utilities.newBlob(Utilities.base64DecodeWebSafe(parts[0])).getDataAsString()); } catch (e) { throw fail_(401, 'unauthorized'); }
  if (!p.exp || p.exp < Date.now()) throw fail_(401, 'unauthorized');
  var u = findUser_(p.sub);
  if (!u) throw fail_(401, 'unauthorized'); // removed users lose access at once
  return { email: u.email, name: u.name, role: u.role };
}
function login_(email, password) {
  email = String(email || '').trim().toLowerCase();
  var cache = CacheService.getScriptCache(), key = 'fail:' + email, fails = Number(cache.get(key) || 0);
  if (fails >= MAX_FAILS) throw fail_(429, 'too_many_attempts');
  var u = findUser_(email);
  var ok = same_(hashPw_(String(password || ''), u ? u.salt : 'no-such-user'), u ? u.hash : 'x');
  if (!u || !ok) { cache.put(key, String(fails + 1), LOCK_SECONDS); throw fail_(401, 'invalid_credentials'); }
  cache.remove(key);
  return { token: signToken_(u), user: { email: u.email, name: u.name, role: u.role } };
}

// ---------- dashboard ----------
function count_(items, k) { var m = {}; items.forEach(function (i) { var v = i[k] || 'Not set'; m[v] = (m[v] || 0) + 1; }); return m; }
function top_(m, n) {
  return Object.keys(m).map(function (k) { return { name: k, count: m[k] }; }).sort(function (a, b) { return b.count - a.count; }).slice(0, n);
}
function queriesThisMonth_() {
  var now = new Date(), total = 0;
  readAll_('Runs', RUN_FIELDS).forEach(function (r) {
    var d = parseDate_(r.startedAt);
    if (d && d.getUTCFullYear() === now.getUTCFullYear() && d.getUTCMonth() === now.getUTCMonth()) total += Number(r.queries) || 0;
  });
  return total;
}
function dashboard_() {
  var leads = readAll_('Leads', LEAD_FIELDS).filter(function (l) { return l.name; });
  var agencies = readAll_('Agencies', AGENCY_FIELDS).filter(function (a) { return a.name; });
  var runs = readAll_('Runs', RUN_FIELDS).filter(function (r) { return r.id; }), rules = getRules_();
  var t = new Date(), today = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), t.getUTCDate()));
  var open = leads.filter(function (l) { return ['Won', 'Lost', 'Skipped'].indexOf(l.status) < 0; });
  var due = open.filter(function (l) { var d = parseDate_(l.nextFollowUp); return d && d <= today; });
  var hni = leads.filter(function (l) { return l.segment === 'HNI B2B'; });
  var pipe = hni.filter(function (l) { return ['Lost', 'Skipped'].indexOf(l.status) < 0; }).reduce(function (s, l) { return s + (l.budgetCr || 0); }, 0);
  var last = runs.length ? runs[runs.length - 1] : null;
  return {
    leads: { total: leads.length, hniB2b: hni.length, newCount: leads.filter(function (l) { return l.status === 'New'; }).length,
      hot: leads.filter(function (l) { return l.quality === 'Hot'; }).length, followUpsDue: due.length,
      pipelineValueCr: Math.round(pipe * 100) / 100, byQuality: count_(leads, 'quality'), byStatus: count_(leads, 'status'),
      topCities: top_(count_(leads, 'city'), 5), topBrands: top_(count_(leads, 'brand'), 5) },
    agencies: { total: agencies.length, leadsOnly: agencies.filter(function (a) { return a.leadsOnly === 'Yes'; }).length,
      newCount: agencies.filter(function (a) { return a.status === 'New'; }).length, byType: count_(agencies, 'type'), byStatus: count_(agencies, 'status') },
    hunt: { lastRun: last ? publicRow_(last) : null, schedule: rules.schedule, queriesUsedThisMonth: queriesThisMonth_(),
      monthlyQueryCap: rules.monthlyQueryCap, searchConfigured: !!(props_().getProperty('SEARCH_KEY') && props_().getProperty('SEARCH_CX')) } };
}

// ---------- hunt: Google search -> parse -> keep only HNI B2B -> save ----------
function parseInvestor_(r) {
  var slug = '';
  try { slug = decodeURIComponent((r.link || '').replace(/^https?:\/\/[^\/]+/i, '').split(/[?#]/)[0]).split('/').filter(Boolean).sort(function (a, b) { return b.length - a.length; })[0] || ''; } catch (e) { slug = ''; }
  slug = slug.replace(/-/g, ' ');
  var AMT = /(?:up ?to|upto|budget of|invest(?:ment)? of)?\s*(?:inr|rs\.?|₹)\s*([\d.,]+)\s*(crore|cr|lakh|lac)/i;
  var fromText = AMT.exec((r.title || '') + ' ' + (r.snippet || '')), amt = fromText || AMT.exec(slug);
  var title = String(r.title || '').replace(/\s+/g, ' ').replace(/\s+-\s+SMERGERS.*$/i, '').trim();
  var inv = /^(.*?)\s*(?:[-–|:,]\s*)?franchise investor in\s+(.+?)\s+looking to invest in\s+(.+?)\s*(?:up ?to|upto|\bfor\b|$)/i.exec(title) ||
    /^(.*?)\s+franchise investor in\s+(.+?)\s+looking to invest in\s+(.+?)\s+up ?to/i.exec(slug);
  if (!inv || !amt) return null;
  var n = parseFloat(amt[1].replace(/,/g, ''));
  if (!isFinite(n)) return null;
  var budget = /lakh|lac/i.test(amt[2]) ? n / 100 : n;
  var prof = titleCase_(inv[1].trim().replace(/^[-–|:,\s]+|[-–|:,\s]+$/g, '')) || 'Not shown';
  return { source: 'Google search (' + (domainOf_(r.link) || 'web') + ' investor profile)', brand: titleCase_(inv[3].trim()),
    name: 'Name not shown (' + prof + ')', city: titleCase_(inv[2].trim()), profession: prof, budgetCr: budget, sourceUrl: r.link,
    notes: 'Public profile, up to INR ' + budget + ' crore' + (fromText ? '' : ' (budget read from the URL, verify)') + '. Contact details appear only after connecting on the source site. ' + r.link };
}
function parseAgency_(r) {
  var web = domainOf_(r.link);
  if (!web) return null;
  var name = String(r.title || '').replace(/\s+/g, ' ').trim().split(/\s+[|–—-]\s+|\s*:\s+/)[0].trim() || web;
  var text = ((r.title || '') + ' ' + (r.snippet || '')).toLowerCase();
  var type = /portal|directory|listing/.test(text) ? 'Franchise portal' : /consult/.test(text) ? 'Franchise consultancy' : /lead generation|leads?\b/.test(text) ? 'Lead generation agency' : 'Marketing agency';
  var price = /(?:rs\.?|inr|₹)\s*[\d.,]+\s*(?:lakh|lac|k|crore)?/i.exec((r.title || '') + ' ' + (r.snippet || ''));
  return { type: type, website: 'https://' + web, name: name, leadsOnly: /lead generation|pay[- ]per[- ]lead|exclusive leads|franchise leads/.test(text) ? 'Yes' : 'Unclear',
    services: String(r.snippet || '').replace(/\s+/g, ' ').trim() || 'Not stated', pricing: price ? price[0] : 'Not public', sourceUrl: r.link,
    notes: "Claims are from the agency's own site or search snippet and are unverified." };
}
function search_(q) {
  var p = props_(), key = p.getProperty('SEARCH_KEY'), cx = p.getProperty('SEARCH_CX');
  var url = 'https://www.googleapis.com/customsearch/v1?key=' + encodeURIComponent(key) + '&cx=' + encodeURIComponent(cx) + '&num=10&gl=in&q=' + encodeURIComponent(q);
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error('Google Search failed (' + res.getResponseCode() + ')');
  return (JSON.parse(res.getContentText()).items || []).map(function (i) { return { title: i.title || '', snippet: i.snippet || '', link: i.link || '' }; });
}
function buildQueries_(rules) {
  var q = [], cities = rules.cities.length ? rules.cities : ['India'];
  rules.brands.forEach(function (b) { cities.forEach(function (c) { q.push({ kind: 'lead', text: 'franchise investor in ' + c + ' looking to invest in ' + b + ' upto INR crore site:smergers.com' }); }); });
  q.push({ kind: 'agency', text: 'franchise lead generation agency India investors' });
  q.push({ kind: 'agency', text: 'franchise lead generation company HNI investors pricing' });
  return q;
}
function runHunt_(trigger, by) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(2000)) return { skipped: 'A hunt is already running' };
  var started = new Date(), s = { queries: 0, found: 0, saved: 0, duplicates: 0, filtered: 0, errors: 0 }, notes = [];
  try {
    var rules = getRules_(), configured = !!(props_().getProperty('SEARCH_KEY') && props_().getProperty('SEARCH_CX'));
    var budget = Math.min(rules.maxQueriesPerRun, Math.max(0, rules.monthlyQueryCap - queriesThisMonth_()));
    if (!configured) { notes.push('Search API not configured'); budget = 0; } else if (budget === 0) notes.push('Monthly search budget used up');
    var seenUrls = {}, seenDomains = {}, today = fmtDate_(started);
    readAll_('Leads', LEAD_FIELDS).forEach(function (l) { if (l.sourceUrl) seenUrls[l.sourceUrl] = 1; });
    readAll_('Agencies', AGENCY_FIELDS).forEach(function (a) { var d = domainOf_(a.website); if (d) seenDomains[d] = 1; });
    var queries = buildQueries_(rules);
    for (var qi = 0; qi < queries.length; qi++) {
      var q = queries[qi];
      if (s.queries >= budget) { notes.push('Stopped at query limit'); break; }
      s.queries++;
      var results = [];
      try { results = search_(q.text); } catch (e) { s.errors++; notes.push(e.message); continue; }
      results.forEach(function (r) {
        s.found++;
        if (q.kind === 'lead') {
          var p = parseInvestor_(r);
          if (!p) { s.filtered++; return; }
          if (seenUrls[p.sourceUrl]) { s.duplicates++; return; }
          if (segmentOf_(p, rules.hniMinCr) !== 'HNI B2B' || p.budgetCr > rules.maxBudgetCr) { s.filtered++; return; }
          seenUrls[p.sourceUrl] = 1;
          p.id = newId_('L'); p.dateReceived = today; p.phone = ''; p.email = ''; p.quality = qualityOf_(p.budgetCr);
          p.status = 'New'; p.nextFollowUp = ''; p.owner = ''; p.segment = 'HNI B2B';
          appendRow_('Leads', LEAD_FIELDS, p); s.saved++;
        } else {
          var a = parseAgency_(r), dom = a && domainOf_(a.website);
          if (!a || !dom) { s.filtered++; return; }
          if (seenDomains[dom]) { s.duplicates++; return; }
          seenDomains[dom] = 1;
          a.id = newId_('A'); a.dateAdded = today; a.phone = ''; a.email = ''; a.city = ''; a.status = 'New'; a.linkedin = ''; a.owner = '';
          appendRow_('Agencies', AGENCY_FIELDS, a); s.saved++;
        }
      });
    }
  } catch (e) { s.errors++; notes.push('Run failed: ' + e.message); } finally { lock.releaseLock(); }
  var fin = new Date();
  var run = { id: newId_('R'), startedAt: fmtDate_(started) + ' ' + pad2_(started.getUTCHours()) + ':' + pad2_(started.getUTCMinutes()),
    finishedAt: fmtDate_(fin) + ' ' + pad2_(fin.getUTCHours()) + ':' + pad2_(fin.getUTCMinutes()), trigger: trigger, by: by,
    queries: s.queries, found: s.found, saved: s.saved, duplicates: s.duplicates, filtered: s.filtered, errors: s.errors, notes: notes.join('; ').slice(0, 500) };
  appendRow_('Runs', RUN_FIELDS, run);
  return run;
}
function scheduledHunt() { // called by the hourly time trigger
  var h = new Date().getUTCHours(), sch = getRules_().schedule;
  if (sch === 'hourly' || (sch === 'every3h' && h % 3 === 0) || (sch === 'daily' && h === 2)) runHunt_('schedule', 'apps-script');
}

// ---------- API ----------
function toCsv_(rows, fields) {
  var esc = function (v) { return '"' + safeCell_(v).replace(/"/g, '""') + '"'; };
  return [fields.map(function (f) { return esc(f[1]); }).join(',')].concat(rows.map(function (r) { return fields.map(function (f) { return esc(r[f[0]]); }).join(','); })).join('\r\n') + '\r\n';
}
function pick_(src, allowed) {
  var out = {};
  Object.keys(src || {}).forEach(function (k) { if (allowed.indexOf(k) < 0) throw fail_(400, 'invalid_request'); out[k] = src[k]; });
  return out;
}
function checkPatch_(c) {
  Object.keys(c).forEach(function (k) {
    var v = c[k];
    if (k === 'status' && STATUSES.indexOf(v) < 0) throw fail_(400, 'invalid_request');
    if (k === 'quality' && QUALITIES.indexOf(v) < 0) throw fail_(400, 'invalid_request');
    if (typeof v !== 'string' || v.length > 2000) throw fail_(400, 'invalid_request');
  });
  return c;
}
function patch_(tab, fields, allowed, id, changes) {
  var c = checkPatch_(pick_(changes, allowed));
  var row = readAll_(tab, fields).filter(function (o) { return o.id === id; })[0];
  if (!row) throw fail_(404, 'not_found');
  if (tab === 'Leads') { var merged = {}; Object.keys(row).forEach(function (k) { merged[k] = row[k]; }); Object.keys(c).forEach(function (k) { merged[k] = c[k]; }); c.segment = segmentOf_(merged, getRules_().hniMinCr); }
  writeCells_(tab, fields, row._row, c);
  var out = {}; Object.keys(row).forEach(function (k) { out[k] = row[k]; }); Object.keys(c).forEach(function (k) { out[k] = c[k]; });
  return publicRow_(out);
}
function validRules_(r) {
  var out = {}, num = function (k, lo, hi) { if (typeof r[k] !== 'number' || r[k] < lo || r[k] > hi) throw fail_(400, 'invalid_request'); out[k] = r[k]; };
  var list = function (k) { if (!Array.isArray(r[k]) || r[k].length > 30 || r[k].some(function (x) { return typeof x !== 'string' || x.length > 60; })) throw fail_(400, 'invalid_request'); out[k] = r[k]; };
  Object.keys(r || {}).forEach(function (k) {
    if (k === 'brands' || k === 'cities') list(k);
    else if (k === 'hniMinCr') num(k, 0, 100); else if (k === 'maxBudgetCr') num(k, 0, 1000);
    else if (k === 'maxQueriesPerRun') num(k, 1, 50); else if (k === 'monthlyQueryCap') num(k, 0, 100000);
    else if (k === 'schedule' && ['hourly', 'every3h', 'daily', 'off'].indexOf(r[k]) >= 0) out[k] = r[k];
    else throw fail_(400, 'invalid_request');
  });
  return out;
}

function handle_(req) {
  var action = String(req.action || '');
  if (action === 'health') return { ok: true };
  if (action === 'login') return login_(req.email, req.password);
  var user = openMode_() ? OPEN_USER : verifyToken_(req.token), a = req.args || {};
  switch (action) {
    case 'me': return { user: user };
    case 'dashboard': return dashboard_();
    case 'leads': {
      var all = readAll_('Leads', LEAD_FIELDS).filter(function (l) { return l.name; });
      var items = a.all ? all : all.filter(function (l) { return l.segment === 'HNI B2B'; });
      return { total: items.length, items: items.slice(0, 500).map(publicRow_) };
    }
    case 'patchLead': return patch_('Leads', LEAD_FIELDS, LEAD_PATCH, String(a.id), a.changes);
    case 'agencies': { var ag = readAll_('Agencies', AGENCY_FIELDS).filter(function (x) { return x.name; }); return { total: ag.length, items: ag.map(publicRow_) }; }
    case 'patchAgency': return patch_('Agencies', AGENCY_FIELDS, AGENCY_PATCH, String(a.id), a.changes);
    case 'runs': { var rs = readAll_('Runs', RUN_FIELDS).filter(function (r) { return r.id; }); return { items: rs.slice(-50).reverse().map(publicRow_) }; }
    case 'hunt': {
      if (openMode_()) { // without a login, limit how often search quota can be spent
        var last = Number(props_().getProperty('LAST_MANUAL_HUNT') || 0);
        if (Date.now() - last < 120000) throw fail_(429, 'too_many_attempts');
        props_().setProperty('LAST_MANUAL_HUNT', String(Date.now()));
      }
      return runHunt_('manual', user.email);
    }
    case 'rules': return getRules_();
    case 'saveRules': if (user.role !== 'admin') throw fail_(403, 'forbidden'); return setRules_(validRules_(a.changes));
    case 'export': {
      var kind = a.kind === 'agencies' ? [AGENCY_FIELDS, 'Agencies'] : [LEAD_FIELDS, 'Leads'];
      return { csv: toCsv_(readAll_(kind[1], kind[0]).filter(function (r) { return r.name; }), kind[0]) };
    }
    default: throw fail_(404, 'not_found');
  }
}

function out_(text, callback) {
  // With a callback name the reply is a script that calls it. Browsers can load that from any page without CORS.
  if (callback && /^[A-Za-z_][A-Za-z0-9_]{0,60}$/.test(callback)) {
    return ContentService.createTextOutput(callback + '(' + JSON.stringify(text) + ');').setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(text).setMimeType(ContentService.MimeType.JSON);
}
function run_(raw) {
  var req;
  try { req = JSON.parse(raw); } catch (e) { return { status: 400, error: 'invalid_request' }; }
  try { return { status: 200, data: handle_(req) }; }
  catch (err) {
    if (!err.status) console.error(err);
    return { status: err.status || 500, error: err.status ? err.message : 'server_error' };
  }
}
// GET: no parameters opens the app page; ?health=1 is a plain health check; ?p=<base64url JSON>&callback=<name> is the script-tag API.
function api(raw) { return JSON.stringify(run_(raw)); } // called by the app page (google.script.run)
function doGet(e) {
  var q = (e && e.parameter) || {};
  if (q.health) return out_(JSON.stringify({ ok: true }), '');
  if (!q.p) { // opening the web app address shows the app itself
    return HtmlService.createHtmlOutputFromFile('Index').setTitle('Franchise Lead Hunter')
      .addMetaTag('viewport', 'width=device-width, initial-scale=1').setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  }
  if (String(q.p).length > 7000) return out_(JSON.stringify({ status: 400, error: 'invalid_request' }), q.callback);
  var raw;
  try { raw = Utilities.newBlob(Utilities.base64DecodeWebSafe(q.p)).getDataAsString(); }
  catch (err) { return out_(JSON.stringify({ status: 400, error: 'invalid_request' }), q.callback); }
  return out_(JSON.stringify(run_(raw)), q.callback);
}
// POST: JSON body. Used by the phone apps and for large requests.
function doPost(e) {
  if (!e || !e.postData || e.postData.contents.length > 60000) return out_(JSON.stringify({ status: 400, error: 'invalid_request' }), '');
  return out_(JSON.stringify(run_(e.postData.contents)), '');
}

// ---------- one-time setup, from the Sheet's "Lead Hunter" menu ----------
function onOpen() {
  SpreadsheetApp.getUi().createMenu('Lead Hunter')
    .addItem('1. Set up tabs', 'menuSetup')
    .addItem('2. Set admin login', 'menuAdmin')
    .addItem('3. Set Google Search keys', 'menuSearch')
    .addItem('4. Start hourly hunt', 'menuTrigger')
    .addItem('Add team member', 'menuAddUser')
    .addSeparator()
    .addItem('Facebook: connect page', 'menuFbConnect')
    .addItem('Facebook: import leads now', 'menuFbImport')
    .addItem('Facebook: auto-import every 15 min', 'menuFbTrigger')
    .addItem('LinkedIn: set up import tab', 'menuLiSetup')
    .addItem('LinkedIn: import leads now', 'menuLiImport')
    .addSeparator()
    .addItem('Open access ON (no login)', 'menuOpenOn')
    .addItem('Open access OFF (login required)', 'menuOpenOff')
    .addItem('Show app address', 'menuUrl')
    .addToUi();
}
function ask_(title, text) {
  var ui = SpreadsheetApp.getUi(), r = ui.prompt(title, text, ui.ButtonSet.OK_CANCEL);
  return r.getSelectedButton() === ui.Button.OK ? r.getResponseText().trim() : null;
}
function menuSetup() {
  sheet_('Leads', LEAD_FIELDS); sheet_('Agencies', AGENCY_FIELDS); sheet_('Runs', RUN_FIELDS); sheet_('Rules', RULE_FIELDS);
  backfill_(); secret_();
  SpreadsheetApp.getUi().alert('Done. Tabs are ready. Your existing data was kept; ids were added to old rows.');
}
function saveUser_(email, name, role, password) {
  var salt = Utilities.getUuid(), rec = { email: email.toLowerCase(), name: name || email, role: role, salt: salt, hash: hashPw_(password, salt) };
  var p = props_();
  if (role === 'admin' && !p.getProperty('ADMIN_EMAIL')) {
    p.setProperties({ ADMIN_EMAIL: rec.email, ADMIN_NAME: rec.name, ADMIN_SALT: rec.salt, ADMIN_HASH: rec.hash });
  } else if (role === 'admin' && p.getProperty('ADMIN_EMAIL') === rec.email) {
    p.setProperties({ ADMIN_NAME: rec.name, ADMIN_SALT: rec.salt, ADMIN_HASH: rec.hash });
  } else {
    var list = [];
    try { list = JSON.parse(p.getProperty('USERS') || '[]'); } catch (e) { list = []; }
    list = list.filter(function (u) { return u.email !== rec.email; }); list.push(rec);
    p.setProperty('USERS', JSON.stringify(list));
  }
}
function menuAdmin() {
  var email = ask_('Admin login', 'Admin email:'); if (!email) return;
  var pw = ask_('Admin login', 'Choose a password (at least 10 characters). It is stored only as a hash.'); if (!pw) return;
  if (pw.length < 10) { SpreadsheetApp.getUi().alert('Use at least 10 characters.'); return; }
  var p = props_(); p.deleteProperty('ADMIN_EMAIL');
  saveUser_(email, 'Admin', 'admin', pw);
  SpreadsheetApp.getUi().alert('Admin login saved for ' + email + '.');
}
function menuAddUser() {
  var email = ask_('Add team member', 'Email:'); if (!email) return;
  var name = ask_('Add team member', 'Name:') || email;
  var pw = ask_('Add team member', 'Password (at least 10 characters):'); if (!pw || pw.length < 10) { SpreadsheetApp.getUi().alert('Use at least 10 characters.'); return; }
  saveUser_(email, name, 'member', pw);
  SpreadsheetApp.getUi().alert(email + ' added.');
}
function menuSearch() {
  var key = ask_('Google Search', 'API key (Custom Search API):'); if (!key) return;
  var cx = ask_('Google Search', 'Search engine ID (cx):'); if (!cx) return;
  props_().setProperties({ SEARCH_KEY: key, SEARCH_CX: cx });
  SpreadsheetApp.getUi().alert('Saved. Keys are kept in Script Properties, not in the Sheet.');
}
function menuTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'scheduledHunt') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('scheduledHunt').timeBased().everyHours(1).create();
  SpreadsheetApp.getUi().alert('The hunt now runs every hour. Change the schedule in the app (Hunt rules).');
}
function menuUrl() {
  var url = ScriptApp.getService().getUrl();
  SpreadsheetApp.getUi().alert(url ? 'App address:\n' + url : 'Not deployed yet. Deploy > New deployment > Web app.');
}

function menuOpenOn() {
  var ui = SpreadsheetApp.getUi();
  var r = ui.alert('Turn on open access?', 'Anyone who has your app address can then use the app and see and change your leads, without a login. Keep the address private, and turn this off when you are done testing.', ui.ButtonSet.YES_NO);
  if (r !== ui.Button.YES) return;
  props_().setProperty('OPEN_MODE', '1');
  ui.alert('Open access is ON. The app now opens without a login.');
}
function menuOpenOff() {
  props_().deleteProperty('OPEN_MODE');
  SpreadsheetApp.getUi().alert('Open access is OFF. The app asks for a login again.');
}
