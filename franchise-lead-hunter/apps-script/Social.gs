/**
 * Lead connectors: Facebook Lead Ads (live, every 15 minutes) and LinkedIn Lead Gen Forms (CSV import tab).
 * Both write into the same Leads tab as everything else, so the app shows them at once.
 * Tokens live in Script Properties (never in the Sheet, never in a web address).
 */
var FB_API = 'https://graph.facebook.com/v21.0';
var LI_TAB = 'Import_LinkedIn';

// ---------- shared helpers ----------
function normKey_(s) { return String(s || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }
function firstOf_(ans, keys) { for (var i = 0; i < keys.length; i++) { if (ans[keys[i]]) return ans[keys[i]]; } return ''; }
function containing_(ans, parts) {
  var ks = Object.keys(ans);
  for (var p = 0; p < parts.length; p++) for (var i = 0; i < ks.length; i++) if (ks[i].indexOf(parts[p]) >= 0 && ans[ks[i]]) return ans[ks[i]];
  return '';
}

/** "Rs 50 lakh", "25_50_lakh", "1-2 crore", "1 crore+", "5000000" -> Rs crore (lower end of a range). null when unknown. */
function parseBudgetCr_(text) {
  var t = String(text == null ? '' : text).toLowerCase().replace(/[_,₹]/g, ' ').replace(/\brs\.?|\binr\b/g, ' ').replace(/\s+/g, ' ').trim();
  if (!t) return null;
  var unit = /(crores?|cr)\b/.test(t) ? 'cr' : /(lakhs?|lacs?|lac)\b|\bl\b/.test(t) ? 'lakh' : '';
  var nums = t.match(/\d+(?:\.\d+)?/g);
  if (!nums) return null;
  var n = parseFloat(nums[0]);
  if (!isFinite(n)) return null;
  if (unit === 'cr') return n;
  if (unit === 'lakh') return n / 100;
  if (n >= 100000) return n / 10000000; // plain rupees
  return null; // a bare small number is ambiguous: do not guess
}

/** One normalised lead from a social form. o: {source, ext, created, rows:[[label,value]], formName} */
function buildSocialLead_(o, rules) {
  var a = {}, used = {};
  o.rows.forEach(function (r) { var k = normKey_(r[0]); if (k && r[1] !== '' && r[1] != null) a[k] = String(r[1]).trim(); });
  var first = firstOf_(a, ['firstname']), last = firstOf_(a, ['lastname']);
  var name = firstOf_(a, ['fullname', 'name']) || (first + ' ' + last).trim() || 'Name not shown';
  var title = firstOf_(a, ['jobtitle', 'title', 'profession', 'occupation', 'designation']);
  var company = firstOf_(a, ['companyname', 'company', 'organization', 'businessname']);
  var profession = [title, company].filter(Boolean).join(', ') || 'Not shown';
  var budget = parseBudgetCr_(containing_(a, ['budget', 'invest', 'capital']));
  var email = firstOf_(a, ['email', 'workemail']), phone = firstOf_(a, ['phonenumber', 'phone', 'workphonenumber', 'mobile', 'mobilenumber']);
  var city = firstOf_(a, ['city', 'town', 'location']);
  var brand = containing_(a, ['brand', 'interest', 'sector', 'industry']) || o.formName || '';
  ['firstname', 'lastname', 'fullname', 'name', 'jobtitle', 'title', 'companyname', 'company', 'email', 'workemail', 'phonenumber', 'phone', 'city'].forEach(function (k) { used[k] = 1; });
  var extra = o.rows.filter(function (r) { return !used[normKey_(r[0])] && r[1] !== '' && r[1] != null; })
    .map(function (r) { return r[0] + ': ' + r[1]; });
  var lead = {
    dateReceived: fmtDate_(o.created), source: o.source, brand: brand, name: name, phone: phone, email: email, city: city,
    profession: profession, budgetCr: budget, quality: budget == null ? 'Warm' : qualityOf_(budget), status: 'New', nextFollowUp: '',
    notes: ('Submitted through the ' + o.source + ' form (consent given by the lead). ' + extra.join(' | ')).trim(),
    id: newId_('L'), owner: '', sourceUrl: o.ext,
  };
  lead.segment = segmentOf_(lead, rules.hniMinCr);
  return lead;
}

function existingExt_() {
  var seen = {};
  readAll_('Leads', LEAD_FIELDS).forEach(function (l) { if (l.sourceUrl) seen[l.sourceUrl] = 1; });
  return seen;
}
function logRun_(trigger, by, s, notes, started) {
  var fin = new Date(), st = started || fin;
  appendRow_('Runs', RUN_FIELDS, {
    id: newId_('R'), startedAt: fmtDate_(st) + ' ' + pad2_(st.getUTCHours()) + ':' + pad2_(st.getUTCMinutes()),
    finishedAt: fmtDate_(fin) + ' ' + pad2_(fin.getUTCHours()) + ':' + pad2_(fin.getUTCMinutes()), trigger: trigger, by: by,
    queries: s.queries || 0, found: s.found, saved: s.saved, duplicates: s.duplicates, filtered: 0, errors: s.errors, notes: notes.join('; ').slice(0, 500) });
}

// ---------- Facebook Lead Ads ----------
function fbGet_(path) {
  var token = props_().getProperty('FB_TOKEN');
  if (!token) throw new Error('Facebook is not connected');
  var res = UrlFetchApp.fetch(FB_API + path, { headers: { Authorization: 'Bearer ' + token }, muteHttpExceptions: true }); // token goes in a header, not the address
  var code = res.getResponseCode(), j = {};
  try { j = JSON.parse(res.getContentText()); } catch (e) { j = {}; }
  if (code !== 200) throw new Error('Facebook said: ' + (j.error && j.error.message ? j.error.message : 'HTTP ' + code));
  return j;
}
function fbTime_(s) { return new Date(String(s).replace(/([+-]\d\d)(\d\d)$/, '$1:$2')); }

function runFacebookImport_(trigger) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(2000)) return { skipped: 'An import is already running' };
  var started = new Date(), s = { queries: 0, found: 0, saved: 0, duplicates: 0, errors: 0 }, notes = [];
  try {
    var page = props_().getProperty('FB_PAGE_ID');
    if (!page || !props_().getProperty('FB_TOKEN')) { notes.push('Facebook not connected'); s.errors++; }
    else {
      var rules = getRules_(), seen = existingExt_();
      s.queries++;
      var forms = fbGet_('/' + page + '/leadgen_forms?fields=id,name,status&limit=50').data || [];
      forms.forEach(function (form) {
        if (form.status === 'ARCHIVED') return;
        var key = 'FB_SINCE_' + form.id, since = Number(props_().getProperty(key) || 0), newest = since, after = '';
        for (var pageNo = 0; pageNo < 10; pageNo++) {
          var filt = since ? '&filtering=' + encodeURIComponent(JSON.stringify([{ field: 'time_created', operator: 'GREATER_THAN', value: since }])) : '';
          s.queries++;
          var r = fbGet_('/' + form.id + '/leads?fields=id,created_time,field_data,ad_name&limit=100' + filt + (after ? '&after=' + encodeURIComponent(after) : ''));
          (r.data || []).forEach(function (lead) {
            s.found++;
            var ext = 'fb-lead:' + lead.id, created = fbTime_(lead.created_time);
            newest = Math.max(newest, Math.floor(created.getTime() / 1000));
            if (seen[ext]) { s.duplicates++; return; }
            var rows = (lead.field_data || []).map(function (f) { return [f.name, (f.values || []).join(', ')]; });
            if (lead.ad_name) rows.push(['Ad', lead.ad_name]);
            appendRow_('Leads', LEAD_FIELDS, buildSocialLead_({ source: 'Facebook Lead Ad', ext: ext, created: created, rows: rows, formName: form.name }, rules));
            seen[ext] = 1; s.saved++;
          });
          after = r.paging && r.paging.cursors && r.paging.next ? r.paging.cursors.after : '';
          if (!after) break;
        }
        if (newest > since) props_().setProperty(key, String(newest));
      });
    }
  } catch (e) { s.errors++; notes.push(e.message); } finally { lock.releaseLock(); }
  logRun_(trigger, 'facebook', s, notes, started);
  return { saved: s.saved, duplicates: s.duplicates, found: s.found, errors: s.errors, notes: notes.join('; ') };
}
function scheduledFacebook() { runFacebookImport_('facebook-schedule'); }

// ---------- LinkedIn Lead Gen Forms (CSV import tab) ----------
function ensureLinkedInTab_() {
  var ss = SpreadsheetApp.getActive(), sh = ss.getSheetByName(LI_TAB);
  if (!sh) {
    sh = ss.insertSheet(LI_TAB);
    var head = ['First Name', 'Last Name', 'Email', 'Phone Number', 'Company Name', 'Job Title', 'City', 'Budget', 'Form Name', 'Created Time', 'Imported'];
    sh.getRange(1, 1, 1, head.length).setValues([head]);
  }
  return sh;
}
function runLinkedInImport_() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(2000)) return { skipped: 'An import is already running' };
  var started = new Date(), s = { found: 0, saved: 0, duplicates: 0, errors: 0 }, notes = [];
  try {
    var sh = SpreadsheetApp.getActive().getSheetByName(LI_TAB);
    if (!sh) { notes.push('Import tab missing. Use Lead Hunter > LinkedIn: set up import tab.'); s.errors++; }
    else {
      var data = sh.getDataRange().getValues(), headers = data[0].map(String), imp = headers.indexOf('Imported');
      if (imp < 0) { imp = headers.length; sh.getRange(1, imp + 1).setValue('Imported'); headers.push('Imported'); }
      var rules = getRules_(), seen = existingExt_(), today = fmtDate_(new Date());
      for (var r = 1; r < data.length; r++) {
        var row = data[r];
        if (String(row[imp] || '').trim()) continue;                                   // already imported
        var rows = [];
        headers.forEach(function (h, c) { if (h && h !== 'Imported' && row[c] !== '' && row[c] != null) rows.push([h, row[c]]); });
        if (!rows.length) continue;
        s.found++;
        var norm = {}; rows.forEach(function (x) { norm[normKey_(x[0])] = String(x[1]); });
        var idCol = norm.leadid || norm.id;
        var fp = idCol || bytesToHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, (norm.email || '').toLowerCase() + '|' + ((norm.firstname || '') + (norm.lastname || '') + (norm.fullname || '')).toLowerCase() + '|' + (norm.formname || '').toLowerCase()));
        var ext = 'li-lead:' + fp, created = new Date();
        var ct = norm.createdtime || norm.created || norm.submitted || norm.date;
        if (ct && !isNaN(new Date(ct).getTime())) created = new Date(ct);
        if (seen[ext]) { s.duplicates++; } else {
          appendRow_('Leads', LEAD_FIELDS, buildSocialLead_({ source: 'LinkedIn Lead Gen Form', ext: ext, created: created, rows: rows, formName: norm.formname || norm.campaignname || '' }, rules));
          seen[ext] = 1; s.saved++;
        }
        var cell = sh.getRange(r + 1, imp + 1); cell.setNumberFormat('@'); cell.setValue(today); // mark the row so it is never imported twice
      }
    }
  } catch (e) { s.errors++; notes.push(e.message); } finally { lock.releaseLock(); }
  logRun_('linkedin-import', 'linkedin', s, notes, started);
  return { saved: s.saved, duplicates: s.duplicates, found: s.found, errors: s.errors, notes: notes.join('; ') };
}

// ---------- menu actions ----------
function menuFbConnect() {
  var ui = SpreadsheetApp.getUi();
  var page = ask_('Facebook', 'Facebook Page ID (the number, from Page settings > Page transparency):'); if (!page) return;
  var token = ask_('Facebook', 'Page access token (stays in Script Properties, never in the Sheet):'); if (!token) return;
  props_().setProperties({ FB_PAGE_ID: page, FB_TOKEN: token });
  try {
    var info = fbGet_('/' + page + '?fields=name'), forms = fbGet_('/' + page + '/leadgen_forms?fields=id,name&limit=50').data || [];
    ui.alert('Connected to "' + info.name + '". Found ' + forms.length + ' lead form(s). Next: Facebook: import leads now.');
  } catch (e) {
    props_().deleteProperty('FB_TOKEN'); props_().deleteProperty('FB_PAGE_ID');
    ui.alert('Could not connect. ' + e.message + '\n\nNothing was saved.');
  }
}
function menuFbImport() {
  var r = runFacebookImport_('facebook-manual');
  SpreadsheetApp.getUi().alert(r.skipped || ('Facebook import done. New: ' + r.saved + ', duplicates skipped: ' + r.duplicates + (r.notes ? '\nNotes: ' + r.notes : '')));
}
function menuFbTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'scheduledFacebook') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('scheduledFacebook').timeBased().everyMinutes(15).create();
  SpreadsheetApp.getUi().alert('Facebook leads will now be imported every 15 minutes.');
}
function menuLiSetup() {
  ensureLinkedInTab_();
  SpreadsheetApp.getUi().alert('The "' + LI_TAB + '" tab is ready. Download your leads CSV from LinkedIn Campaign Manager (Lead gen forms > Download leads), paste the rows under the headers (the column names can differ), then use LinkedIn: import leads now.');
}
function menuLiImport() {
  var r = runLinkedInImport_();
  SpreadsheetApp.getUi().alert(r.skipped || ('LinkedIn import done. New: ' + r.saved + ', duplicates skipped: ' + r.duplicates + (r.notes ? '\nNotes: ' + r.notes : '')));
}
