/**
 * DAILY BRAND-WISE TAT SOURCE SHEET
 * Loads the TeleCRM exports (EBGWorkSpace_*.csv and FWWorkSpace_*.csv) from Google Drive into ONE tab.
 *
 * Menu "TAT Source":
 *   Refresh data             : THE BUTTON. Clears the tab and reloads every CSV from the Drive folder
 *   Continue import          : only needed if a refresh was interrupted (it normally continues by itself)
 *   Show import status       : shows which files are done
 *
 * Which columns? The CSVs have 160 columns x 105,588 rows = 16.9 million cells, but one Google Spreadsheet holds at most
 * 10 million cells in total. 62 of the 160 columns are completely empty in all four files, and a further 20 are almost empty
 * (under 2 percent filled). The COLUMNS list below therefore loads the 78 columns that carry data (about 8.4 million cells).
 * Name, phone and email are left out unless you set INCLUDE_CONTACT_DETAILS to true (that adds about 0.6 million cells).
 *
 * Cleaning done while loading: the placeholders "-", "_" and blank spaces become empty cells; dates become real
 * date-times (exactly as written in the CSV, no time zone shift); call counts become numbers.
 */
const CFG = {
  SHEET_ID: 'PASTE_TAT_SOURCE_SHEET_ID',   // Daily Brand-Wise TAT Source Sheet
  INCLUDE_CONTACT_DETAILS: false,   // true = also load Name, Phone, Email, Alternate Phone, Full Name, Phone Number
  TAB: 'Source Data',          // the one tab that receives the data
  FOLDER_ID: 'PASTE_DRIVE_FOLDER_ID',   // Google Drive folder that holds the CSV files (the text after /folders/ in the folder URL).
                               // Every EBGWorkSpace*.csv and FWWorkSpace*.csv file in this folder is imported (new months are picked up automatically).
                               // Blank = look for the exact file names in FILE_NAMES anywhere in your Drive instead.
  FILE_NAMES: ['EBGWorkSpace_September2026.csv', 'EBGWorkSpace_October2026.csv', 'EBGWorkSpace_November2026.csv', 'FWWorkSpace_All.csv'],
  FILE_PATTERN: /^(EBG|FW)WorkSpace.*\.csv$/i,   // used when FOLDER_ID is set: every matching file in the folder is imported
  CHUNK_ROWS: 5000,            // rows written to the sheet per call
  TIME_BUDGET_MS: 4.5 * 60 * 1000   // stop starting new files after this long (Apps Script stops a run at 6 minutes)
};

// [column name in the CSV (exact), type]  type: text | date | num
const BASE_COLUMNS = [
  ['Status', 'text'],
  ['Lost Reason', 'text'],
  ['Assignee name', 'text'],
  ['Assignee emailid', 'text'],
  ['Lead Source', 'text'],
  ['Lead Temperature', 'text'],
  ['City', 'text'],
  ['Facebook Lead ID', 'text'],
  ['Facebook Ad Set ID', 'text'],
  ['Facebook Ad Set Name', 'text'],
  ['Facebook Ad', 'text'],
  ['Facebook Campaign Name', 'text'],
  ['Interest Level', 'text'],
  ['Call Summary', 'text'],
  ['Brand', 'text'],
  ['Investment Range', 'text'],
  ['Qualification', 'text'],
  ['Are you avilable for discussion', 'text'],
  ['How soon you are planning to start', 'text'],
  ['Have you invested in any business', 'text'],
  ['experience in Franchise business', 'text'],
  ['How will you fund this investment', 'text'],
  ['Where you plan open the outlet', 'text'],
  ['Are you interested for master franchise', 'text'],
  ['Are you the final decision maker', 'text'],
  ['Business Presentation', 'text'],
  ['Preferred Location for investment', 'text'],
  ['Which best describes you', 'text'],
  ['business category', 'text'],
  ['lead capture count', 'num'],
  ['Unique lead ID', 'text'],
  ['Sales Leader', 'text'],
  ['Custom lead source', 'text'],
  ['Created Time', 'text'],
  ['Preferred Location', 'text'],
  ['Notes', 'text'],
  ['Red Flags', 'text'],
  ['Call Score', 'num'],
  ['Call Reviewed On', 'date'],
  ['Gistly Call Link', 'text'],
  ['Address', 'text'],
  ['Brand cluster', 'text'],
  ['search term', 'text'],
  ['website', 'text'],
  ['business rating', 'num'],
  ['review count', 'num'],
  ['city of business', 'text'],
  ['Priority label', 'text'],
  ['Created On', 'date'],
  ['Modified On', 'date'],
  ['Capture Frequency', 'num'],
  ['Captured On', 'date'],
  ['First Call', 'date'],
  ['Last Call', 'date'],
  ['Total Call Duration', 'num'],
  ['Calls Count', 'num'],
  ['Connected Call Count', 'num'],
  ['Call Connection Rate (%)', 'num'],
  ['First Attempted Call', 'date'],
  ['First Successful Call', 'date'],
  ['Last Activity Type', 'text'],
  ['Last Activity On', 'date'],
  ['Last Outgoing Activity Type', 'text'],
  ['Last Outgoing Activity On', 'date'],
  ['Last Incoming Activity Type', 'text'],
  ['Last Incoming Activity On', 'date'],
  ['Last Incoming WhatsApp On', 'date'],
  ['Last Outgoing WhatsApp On', 'date'],
  ['Status Last Updated On', 'date'],
  ['Assignee Last Changed On', 'date'],
  ['Last Assignee Change From', 'text'],
  ['Last Assigned By', 'text'],
  ['Assignee Manager name', 'text'],
  ['Assignee Manager emailid', 'text'],
  ['Lead Link', 'text'],
  ['Lead id', 'text'],
  ['Batch Names', 'text'],
  ['Unique Lead ID', 'text']
];
const CONTACT_COLUMNS = [['Name', 'text'], ['Phone', 'text'], ['Email', 'text'], ['Alternate Phone', 'text'], ['Full Name', 'text'], ['Phone Number', 'text']];
const COLUMNS = CFG.INCLUDE_CONTACT_DETAILS ? BASE_COLUMNS.concat(CONTACT_COLUMNS) : BASE_COLUMNS;
const EXTRA = ['Workspace', 'Source File'];          // two columns added by the script at the right
const NCOLS = COLUMNS.length + EXTRA.length;
const PLACEHOLDERS = { '': 1, '-': 1, '_': 1 };

/* ------------------------------ menu and button ------------------------------ */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('TAT Source')
    .addItem('Refresh data (upload the files to Drive first)', 'refreshData')
    .addItem('Continue import (only if a refresh was interrupted)', 'continueImport')
    .addItem('Show import status', 'showImportStatus')
    .addToUi();
}

function say_(title, msg) {
  try { SpreadsheetApp.getUi().alert(title, msg, SpreadsheetApp.getUi().ButtonSet.OK); }
  catch (e) { Logger.log(title + ': ' + msg); }
}

/* ------------------------------ entry points ------------------------------ */

/**
 * THE BUTTON. Assign this function to a drawing/button on the sheet (see the instructions) or use the menu.
 * It clears the tab and reloads every CSV from the Drive folder. If Apps Script's 6-minute limit is reached,
 * it schedules itself to carry on automatically every minute until everything is loaded.
 */
function refreshData() { importAll(); }

function importAll() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(3000)) { say_('Already running', 'A refresh is already in progress. Please wait for it to finish.'); return; }
  try {
    removeTriggers_();
    const files = listFiles_();
    const sh = getTab_();
    const f = sh.getFilter(); if (f) f.remove();
    sh.clear();
    sh.setFrozenRows(0);
    ensureSize_(sh, 2, NCOLS);
    sh.getRange(1, 1, 1, NCOLS).setValues([COLUMNS.map(c => c[0]).concat(EXTRA)]);
    saveState_({ done: {}, current: null, nextRow: 2 });
    toast_('Refresh started. This takes several minutes; it continues by itself if needed.');
    runImport_(files);
  } finally { lock.releaseLock(); }
}

function continueImport() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(3000)) { say_('Already running', 'An import is already in progress. Please wait.'); return; }
  try {
    const st = loadState_();
    if (!st) { say_('Nothing to continue', 'Run "Refresh data" first.'); return; }
    if (st.complete) { say_('Already complete', 'The data is already fully loaded. Use "Refresh data" to reload.'); return; }
    removeTriggers_();
    runImport_(listFiles_());
  } finally { lock.releaseLock(); }
}

/** Called by the automatic one-time trigger. Do not run by hand. */
function continueFromTrigger() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(3000)) return;
  try {
    removeTriggers_();
    const st = loadState_();
    if (!st || st.complete) return;
    runImport_(listFiles_());
  } finally { lock.releaseLock(); }
}

function showImportStatus() {
  const st = loadState_();
  if (!st) { say_('Import status', 'No import has been run yet.'); return; }
  const lines = Object.keys(st.done).map(k => k + ': ' + st.done[k].toLocaleString() + ' rows');
  if (st.current) lines.push(st.current.name + ': ' + st.current.rows.toLocaleString() + ' rows so far (in progress)');
  say_('Import status', (lines.join('\n') || 'No file finished yet') + '\n\nTotal rows in the tab so far: ' + (st.nextRow - 2).toLocaleString() +
       (st.complete ? '\nStatus: COMPLETE' : '\nStatus: not finished. It continues automatically; or use "Continue import".'));
}

/* ------------------------------ import engine ------------------------------ */

function runImport_(files) {
  const started = Date.now();
  const sh = getTab_();
  const st = loadState_();
  for (let n = 0; n < files.length; n++) {
    const f = files[n];
    if (st.done[f.getName()] !== undefined) continue;
    const finished = importFile_(sh, f, st, started);
    if (!finished) {                                           // time budget reached: carry on automatically in a minute
      saveState_(st);
      ScriptApp.newTrigger('continueFromTrigger').timeBased().after(60 * 1000).create();
      const msg = (st.nextRow - 2).toLocaleString() + ' rows loaded so far. The refresh continues automatically every minute until all files are loaded.';
      setNote_(sh, 'Refresh in progress: ' + msg);
      toast_(msg);
      return;
    }
    st.done[f.getName()] = st.current.rows;
    st.current = null;
    saveState_(st);
  }
  finalize_(sh, st);
  st.complete = true; saveState_(st);
  removeTriggers_();
  const lines = Object.keys(st.done).map(k => k + ': ' + st.done[k].toLocaleString() + ' rows');
  say_('Refresh complete', lines.join('\n') + '\n\nTotal: ' + (st.nextRow - 2).toLocaleString() + ' rows in tab "' + CFG.TAB + '".');
}

/**
 * Reads one CSV file and appends its rows (selected columns only) after the last written row.
 * If this file was started in an earlier run, the rows already written are skipped.
 * Returns true when the file is fully loaded, false when the time budget ran out (progress is saved).
 */
function importFile_(sh, file, st, started) {
  const name = file.getName();
  const workspace = /^FW/i.test(name) ? 'FW' : 'EBG';
  const text = file.getBlob().getDataAsString('UTF-8');
  if (!st.current || st.current.name !== name) st.current = { name: name, rows: 0 };
  const skip = st.current.rows;
  let seen = 0, stop = false, buf = [], missing = [];

  const flush = () => {
    if (!buf.length) return;
    ensureSize_(sh, st.nextRow + buf.length - 1, NCOLS);
    sh.getRange(st.nextRow, 1, buf.length, NCOLS).setValues(buf);
    st.nextRow += buf.length; st.current.rows += buf.length; buf = [];
    saveState_(st);
    if (Date.now() - started > CFG.TIME_BUDGET_MS) stop = true;
  };

  const aborted = streamCsv_(text, header => {
    const pos = {};
    header.forEach((h, i) => { if (!(h in pos)) pos[h] = i; });
    const map = new Array(header.length).fill(-1);
    COLUMNS.forEach((c, k) => { if (c[0] in pos) map[pos[c[0]]] = k; else missing.push(c[0]); });
    return map;
  }, raw => {
    if (seen++ < skip) return false;                            // already written in an earlier run
    const out = new Array(NCOLS);
    for (let k = 0; k < COLUMNS.length; k++) out[k] = convert_(raw[k], COLUMNS[k][1]);
    out[COLUMNS.length] = workspace;
    out[COLUMNS.length + 1] = name;
    buf.push(out);
    if (buf.length >= CFG.CHUNK_ROWS) flush();
    return stop;
  }, COLUMNS.length);
  if (aborted) return false;
  flush();
  if (missing.length) Logger.log(name + ': columns not found and left blank: ' + missing.join(', '));
  return true;
}

/**
 * Streaming CSV reader that keeps only the wanted columns (the files have 131-160 columns, most of them empty).
 * Handles quoted fields, "" escapes, line breaks inside quotes, CRLF, and a BOM.
 *   onHeader(headerNames) -> array: for each CSV column index the output position, or -1 to skip it
 *   onRow(valuesByOutputPosition) -> return true to stop reading (the function then returns true)
 */
function streamCsv_(text, onHeader, onRow, outCount) {
  const n = text.length;
  let i = text.charCodeAt(0) === 0xFEFF ? 1 : 0;
  let col = 0, header = null, map = null, names = [], row = null;
  while (i < n) {
    if (col === 0) {                                          // skip empty lines between rows
      const c0 = text.charCodeAt(i);
      if (c0 === 10 || c0 === 13) { i++; continue; }
    }
    const keep = !header || (col < map.length && map[col] >= 0);
    let val = '';
    if (text.charCodeAt(i) === 34) {                          // quoted field
      let j = i + 1, acc = '';
      for (;;) {
        const k = text.indexOf('"', j);
        if (k < 0) { if (keep) val = acc + text.slice(j); i = n; break; }
        if (text.charCodeAt(k + 1) === 34) { if (keep) acc += text.slice(j, k + 1); j = k + 2; continue; }   // "" = one quote
        if (keep) val = acc + text.slice(j, k);
        i = k + 1; break;
      }
    } else {                                                   // unquoted field
      let k = i;
      while (k < n) { const c = text.charCodeAt(k); if (c === 44 || c === 10 || c === 13) break; k++; }
      if (keep) val = text.slice(i, k);
      i = k;
    }
    if (!header) names.push(val);
    else if (keep) { if (!row) row = new Array(outCount).fill(''); row[map[col]] = val; }

    const c = text.charCodeAt(i);
    if (c === 44) { i++; col++; continue; }                    // next field
    if (c === 13) { i++; if (text.charCodeAt(i) === 10) i++; } else if (c === 10) { i++; }
    if (!header) { header = names; map = onHeader(header); }   // end of the header row
    else { const stop = onRow(row || new Array(outCount).fill('')); row = null; if (stop) return true; }
    col = 0;
  }
  return false;
}

/** Placeholder cleaning and typing of one value. */
function convert_(v, type) {
  if (v === '' || v === undefined) return '';
  const s = v.trim();
  if (PLACEHOLDERS[s]) return '';
  if (type === 'date') {                                       // dd/MM/yyyy HH:mm:ss -> spreadsheet serial number (no time zone shift)
    if (s.length !== 19 || s.charAt(2) !== '/' || s.charAt(5) !== '/') return s;   // unexpected format: keep the original text
    const d = +s.substr(0, 2), mo = +s.substr(3, 2), y = +s.substr(6, 4), h = +s.substr(11, 2), mi = +s.substr(14, 2), se = +s.substr(17, 2);
    if (!(d > 0 && mo > 0 && y > 1900)) return s;
    return Date.UTC(y, mo - 1, d, h, mi, se) / 86400000 + 25569;
  }
  if (type === 'num') { const x = Number(s); return isFinite(x) ? x : s; }
  return s;
}

/* ------------------------------ sheet helpers ------------------------------ */

function getTab_() {
  const ss = CFG.SHEET_ID ? SpreadsheetApp.openById(CFG.SHEET_ID) : SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(CFG.TAB) || ss.insertSheet(CFG.TAB);
}

function toast_(msg) { try { SpreadsheetApp.openById(CFG.SHEET_ID).toast(msg, 'TAT Source', 8); } catch (e) {} }
function setNote_(sh, text) { try { sh.getRange(1, 1).setNote(text); } catch (e) {} }

function removeTriggers_() {
  ScriptApp.getProjectTriggers().forEach(t => { if (t.getHandlerFunction() === 'continueFromTrigger') ScriptApp.deleteTrigger(t); });
}

function ensureSize_(sh, rows, cols) {
  if (sh.getMaxColumns() < cols) sh.insertColumnsAfter(sh.getMaxColumns(), cols - sh.getMaxColumns());
  if (sh.getMaxRows() < rows) sh.insertRowsAfter(sh.getMaxRows(), Math.max(rows - sh.getMaxRows(), 20000));
}

function finalize_(sh, st) {
  const last = st.nextRow - 1;                                 // last data row
  if (sh.getMaxRows() > last) sh.deleteRows(last + 1, sh.getMaxRows() - last);          // free unused cells (10 million limit)
  if (sh.getMaxColumns() > NCOLS) sh.deleteColumns(NCOLS + 1, sh.getMaxColumns() - NCOLS);
  sh.getRange(1, 1, 1, NCOLS).setFontWeight('bold').setBackground('#0d47a1').setFontColor('#ffffff').setWrap(true).setVerticalAlignment('middle');
  sh.setFrozenRows(1);
  COLUMNS.forEach((c, k) => {
    if (c[1] === 'date') sh.getRange(2, k + 1, last - 1, 1).setNumberFormat('dd/mm/yyyy hh:mm:ss');
    if (c[1] === 'num') sh.getRange(2, k + 1, last - 1, 1).setNumberFormat('0');
  });
  sh.setColumnWidths(1, NCOLS, 120);
  const f = sh.getFilter(); if (f) f.remove();
  sh.getRange(1, 1, last, NCOLS).createFilter();
  setNote_(sh, 'Last refresh: ' + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd-MMM-yyyy HH:mm') +
               ' | ' + (st.nextRow - 2).toLocaleString() + ' rows from ' + Object.keys(st.done).length + ' CSV file(s). Placeholders "-" and "_" were cleared.');
}

/* ------------------------------ Drive and state ------------------------------ */

function listFiles_() {
  const found = {};
  if (CFG.FOLDER_ID) {
    let folder;
    try { folder = DriveApp.getFolderById(CFG.FOLDER_ID); }
    catch (e) { throw new Error('Cannot open the Drive folder (' + CFG.FOLDER_ID + '). Open the script with the Google account that owns or can view that folder. Details: ' + e.message); }
    const it = folder.getFiles();
    const seen = [];
    while (it.hasNext()) {
      const f = it.next();
      seen.push(f.getName());
      if (CFG.FILE_PATTERN.test(f.getName())) keepNewest_(found, f);
    }
    if (!Object.keys(found).length) {
      throw new Error('The folder was opened but no EBGWorkSpace*.csv or FWWorkSpace*.csv file is in it. Files seen: ' + (seen.join(', ') || 'none') +
                      '. Keep the CSV files as .csv (do not convert them to Google Sheets).');
    }
  } else {
    CFG.FILE_NAMES.forEach(nm => { const it = DriveApp.getFilesByName(nm); while (it.hasNext()) keepNewest_(found, it.next()); });
  }
  const files = Object.keys(found).map(k => found[k]).sort((a, b) => sortKey_(a.getName()).localeCompare(sortKey_(b.getName())));
  if (!files.length) {
    throw new Error('No CSV files found. Upload ' + CFG.FILE_NAMES.join(', ') + ' to Google Drive (keep the file names; do not convert them to Google Sheets)' +
                    (CFG.FOLDER_ID ? ', inside the folder set in FOLDER_ID.' : ', or set FOLDER_ID at the top of the script.'));
  }
  if (!CFG.FOLDER_ID) {
    const missing = CFG.FILE_NAMES.filter(nm => !found[nm]);
    if (missing.length) throw new Error('These files were not found in Google Drive: ' + missing.join(', '));
  }
  return files;
}

function keepNewest_(found, f) {
  const nm = f.getName();
  const key = nm.replace(/\s*\(\d+\)(?=\.csv$)/i, '');                  // "name (1).csv" is a re-upload of "name.csv": keep the newest
  if (!found[key] || f.getLastUpdated() > found[key].getLastUpdated()) found[key] = f;
}

/** Chronological order: EBG September, October, November ..., then FW. */
function sortKey_(name) {
  const months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];
  const m = name.toLowerCase().match(/([a-z]+)(\d{4})/);
  const mi = m ? months.indexOf(m[1]) : -1;
  const key = (/^fw/i.test(name) ? '2' : '1') + (m && mi >= 0 ? m[2] + ('0' + (mi + 1)).slice(-2) : '999999') + name;
  return key;
}

function props_() { return PropertiesService.getDocumentProperties() || PropertiesService.getScriptProperties(); }
function saveState_(st) { props_().setProperty('tat_import_state', JSON.stringify(st)); }
function loadState_() {
  const s = props_().getProperty('tat_import_state');
  return s ? JSON.parse(s) : null;
}
