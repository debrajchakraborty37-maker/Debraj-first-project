import crypto from 'node:crypto';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatDate(d = new Date()) {
  return `${String(d.getUTCDate()).padStart(2, '0')} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** "06 Nov 2026" -> Date (UTC) or null */
export function parseDate(s) {
  const m = /^(\d{1,2}) ([A-Za-z]{3}) (\d{4})$/.exec(String(s || '').trim());
  if (!m) return null;
  const mi = MONTHS.findIndex((x) => x.toLowerCase() === m[2].toLowerCase());
  return mi < 0 ? null : new Date(Date.UTC(Number(m[3]), mi, Number(m[1])));
}

export const newId = (prefix) => `${prefix}-${crypto.randomBytes(5).toString('hex')}`;

export function extractUrl(text) {
  const m = /https?:\/\/[^\s"'<>)]+/i.exec(String(text || ''));
  return m ? m[0] : '';
}

export function domainOf(url) {
  try { return new URL(/^https?:/i.test(url) ? url : `https://${url}`).hostname.replace(/^www\./, '').toLowerCase(); }
  catch { return ''; }
}

/** Spreadsheet cells starting with = + - @ can run as formulas in Excel/Sheets. */
export function safeCell(v) {
  const s = String(v ?? '');
  return /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
}

export function toCsv(rows, columns) {
  const esc = (v) => `"${safeCell(v).replace(/"/g, '""')}"`;
  const head = columns.map(([, h]) => esc(h)).join(',');
  const body = rows.map((r) => columns.map(([k]) => esc(r[k])).join(','));
  return [head, ...body].join('\r\n') + '\r\n';
}
