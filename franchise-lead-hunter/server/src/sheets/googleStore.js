import { google } from 'googleapis';

function colLetter(i) { // 0 -> A
  let s = '';
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  return s;
}

function parseCredentials(raw) {
  const text = raw.trim().startsWith('{') ? raw : Buffer.from(raw, 'base64').toString('utf8');
  return JSON.parse(text);
}

/** The Google Sheet is the database. Needs a service account with Editor access to the sheet. */
export class GoogleSheetStore {
  constructor({ sheetId, serviceAccountJson }) {
    // On Cloud Run no key is needed: the service's own service account is used. A key is only for running elsewhere.
    const auth = new google.auth.GoogleAuth({
      ...(serviceAccountJson ? { credentials: parseCredentials(serviceAccountJson) } : {}),
      scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    });
    this.sheets = google.sheets({ version: 'v4', auth });
    this.id = sheetId;
    this.headers = new Map();
  }

  async ensureTab(tab, wanted) {
    const meta = await this.sheets.spreadsheets.get({ spreadsheetId: this.id, fields: 'sheets.properties.title' });
    const exists = meta.data.sheets.some((s) => s.properties.title === tab);
    if (!exists) {
      await this.sheets.spreadsheets.batchUpdate({
        spreadsheetId: this.id, requestBody: { requests: [{ addSheet: { properties: { title: tab } } }] },
      });
    }
    const res = await this.sheets.spreadsheets.values.get({ spreadsheetId: this.id, range: `${tab}!1:1` });
    const headers = (res.data.values?.[0] || []).map(String);
    const missing = wanted.filter((h) => !headers.includes(h)); // only ever append columns; never reorder
    if (missing.length) {
      const all = [...headers, ...missing];
      await this.sheets.spreadsheets.values.update({
        spreadsheetId: this.id, range: `${tab}!A1`, valueInputOption: 'RAW', requestBody: { values: [all] },
      });
      this.headers.set(tab, all);
      return all;
    }
    this.headers.set(tab, headers);
    return headers;
  }

  async readRows(tab) {
    const res = await this.sheets.spreadsheets.values.get({
      spreadsheetId: this.id, range: tab, valueRenderOption: 'UNFORMATTED_VALUE', dateTimeRenderOption: 'FORMATTED_STRING',
    });
    const [headers = [], ...body] = res.data.values || [];
    this.headers.set(tab, headers.map(String));
    const rows = body.map((r, i) => {
      const values = {};
      headers.forEach((h, c) => { values[h] = r[c] ?? ''; });
      return { _row: i + 2, values };
    });
    return { headers: headers.map(String), rows };
  }

  async appendRows(tab, rows) {
    const headers = this.headers.get(tab) || (await this.readRows(tab)).headers;
    await this.sheets.spreadsheets.values.append({
      spreadsheetId: this.id, range: `${tab}!A1`, valueInputOption: 'RAW', insertDataOption: 'INSERT_ROWS',
      requestBody: { values: rows.map((r) => headers.map((h) => r[h] ?? '')) },
    });
  }

  async updateCells(tab, updates) {
    const headers = this.headers.get(tab) || (await this.readRows(tab)).headers;
    const data = [];
    for (const u of updates) {
      for (const [h, v] of Object.entries(u.values)) {
        const c = headers.indexOf(h);
        if (c < 0) continue;
        data.push({ range: `${tab}!${colLetter(c)}${u.row}`, values: [[v ?? '']] });
      }
    }
    if (!data.length) return;
    await this.sheets.spreadsheets.values.batchUpdate({
      spreadsheetId: this.id, requestBody: { valueInputOption: 'RAW', data },
    });
  }
}
