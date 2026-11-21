// In-memory stand-in for the Google Sheet. Same interface as GoogleSheetStore.
// Used for tests and `npm run dev:demo`; never in production.
export class MemoryStore {
  constructor(seed = {}) {
    this.tabs = new Map(); // tab -> { headers: [], rows: [ {header: value} ] }
    for (const [tab, { headers, rows }] of Object.entries(seed)) {
      this.tabs.set(tab, { headers: [...headers], rows: rows.map((r) => ({ ...r })) });
    }
  }
  async ensureTab(tab, headers) {
    let t = this.tabs.get(tab);
    if (!t) { t = { headers: [], rows: [] }; this.tabs.set(tab, t); }
    for (const h of headers) if (!t.headers.includes(h)) t.headers.push(h);
    return [...t.headers];
  }
  async readRows(tab) {
    const t = this.tabs.get(tab);
    if (!t) return { headers: [], rows: [] };
    return { headers: [...t.headers], rows: t.rows.map((r, i) => ({ _row: i + 2, values: { ...r } })) };
  }
  async appendRows(tab, rows) {
    this.tabs.get(tab).rows.push(...rows.map((r) => ({ ...r })));
  }
  async updateCells(tab, updates) { // [{row, values:{header:value}}]
    const t = this.tabs.get(tab);
    for (const u of updates) Object.assign(t.rows[u.row - 2], u.values);
  }
}
