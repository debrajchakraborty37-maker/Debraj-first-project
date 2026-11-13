import { LEAD_FIELDS, AGENCY_FIELDS, RUN_FIELDS, RULE_FIELDS, DEFAULT_RULES } from './schema.js';
import { newId, extractUrl } from './util.js';
import { segmentOf } from './segment.js';

const TTL_MS = 10_000; // Sheets API read quota is limited; cache briefly

class Collection {
  constructor(store, tab, fields, { prefix = null, prepare = null } = {}) {
    this.store = store; this.tab = tab; this.fields = fields; this.prefix = prefix; this.prepare = prepare;
    this.headers = []; this.cache = null;
  }

  toObject(values, row) {
    const o = { _row: row };
    for (const [key, header] of this.fields) {
      let v = values[header] ?? '';
      if (key === 'budgetCr') { const n = parseFloat(v); v = Number.isFinite(n) ? n : null; }
      o[key] = v;
    }
    return o;
  }

  toValues(obj) {
    const v = {};
    for (const [key, header] of this.fields) if (key in obj) v[header] = obj[key] ?? '';
    return v;
  }

  async init() {
    this.headers = await this.store.ensureTab(this.tab, this.fields.map(([, h]) => h));
    if (!this.prefix) return;
    // Backfill ids / derived columns on rows that pre-date the app (one-time, only fills blanks).
    const { rows } = await this.store.readRows(this.tab);
    const updates = [];
    for (const r of rows) {
      const o = this.toObject(r.values, r._row);
      if (this.isBlankRow(o)) continue;
      const before = JSON.stringify(o);
      if (!o.id) o.id = newId(this.prefix);
      if (this.prepare) this.prepare(o);
      if (JSON.stringify(o) !== before) updates.push({ row: r._row, values: this.toValues(o) });
    }
    if (updates.length) await this.store.updateCells(this.tab, updates);
    this.cache = null;
  }

  isBlankRow(o) { return !o.name; }

  async list({ fresh = false } = {}) {
    if (!fresh && this.cache && Date.now() - this.cache.at < TTL_MS) return this.cache.rows;
    const { rows } = await this.store.readRows(this.tab);
    const list = rows.map((r) => this.toObject(r.values, r._row)).filter((o) => !this.isBlankRow(o));
    this.cache = { at: Date.now(), rows: list };
    return list;
  }

  async get(id) { return (await this.list()).find((o) => o.id === id) || null; }

  async create(obj) {
    const o = { ...obj, id: obj.id || newId(this.prefix) };
    if (this.prepare) this.prepare(o);
    await this.store.appendRows(this.tab, [this.toValues(o)]);
    this.cache = null;
    return o;
  }

  async patch(id, partial) {
    const list = await this.list({ fresh: true });
    const cur = list.find((o) => o.id === id);
    if (!cur) return null;
    const next = { ...cur, ...partial, id: cur.id };
    if (this.prepare) this.prepare(next);
    const changed = {};
    for (const k of Object.keys(next)) if (k !== '_row' && next[k] !== cur[k]) changed[k] = next[k];
    await this.store.updateCells(this.tab, [{ row: cur._row, values: this.toValues(changed) }]);
    this.cache = null;
    return next;
  }
}

export async function createRepos(store, { hniMinCr = DEFAULT_RULES.hniMinCr } = {}) {
  const leads = new Collection(store, 'Leads', LEAD_FIELDS, {
    prefix: 'L',
    prepare(o) {
      if (!o.sourceUrl) o.sourceUrl = extractUrl(o.notes);
      o.segment = segmentOf(o, hniMinCr);
    },
  });
  const agencies = new Collection(store, 'Agencies', AGENCY_FIELDS, { prefix: 'A' });
  agencies.isBlankRow = (o) => !o.name;
  const runs = new Collection(store, 'Runs', RUN_FIELDS);
  runs.isBlankRow = (o) => !o.id;
  await Promise.all([leads.init(), agencies.init(), runs.init()]);

  // Rules: a tiny key/value tab shared by the whole team.
  await store.ensureTab('Rules', RULE_FIELDS.map(([, h]) => h));
  const rules = {
    async get() {
      const { rows } = await store.readRows('Rules');
      const out = { ...DEFAULT_RULES };
      for (const r of rows) {
        const k = r.values.Key;
        if (!(k in DEFAULT_RULES)) continue;
        try { out[k] = JSON.parse(r.values.Value); } catch { /* keep default */ }
      }
      return out;
    },
    async set(partial) {
      const current = await this.get();
      const next = { ...current, ...partial };
      const { rows } = await store.readRows('Rules');
      const updates = [], appends = [];
      for (const [k, v] of Object.entries(next)) {
        const hit = rows.find((r) => r.values.Key === k);
        const val = JSON.stringify(v);
        if (hit) { if (hit.values.Value !== val) updates.push({ row: hit._row, values: { Value: val } }); }
        else appends.push({ Key: k, Value: val });
      }
      if (updates.length) await store.updateCells('Rules', updates);
      if (appends.length) await store.appendRows('Rules', appends);
      return next;
    },
  };
  return { leads, agencies, runs, rules };
}
