import { addDays, dayMonth, mondayOf, monthStart, WEEKDAYS, weekdayIndex } from './dates';
import { Channel, DailyRow, Filters, Metric, SeriesPoint, Totals } from './models';

export const UNCLASSIFIED = 'Unclassified';
const num = (v: number | null): number => (v == null ? 0 : v);
const sumNullable = (a: number | null, b: number | null): number | null => (a == null && b == null ? null : num(a) + num(b));
const NUMERIC_KEYS = ['gross', 'net', 'total', 'bills', 'zomatoOnlineOrders', 'zomatoOnlineNet', 'zomatoDineInOrders', 'zomatoDineInNet',
  'swiggyOnlineOrders', 'swiggyOnlineNet', 'swiggyDineInOrders', 'swiggyDineInNet', 'ownlyOrders', 'ownlyNet'] as const;

/**
 * Rule: rows with the same date + brand + location are ADDED together (a day can have more than one entry).
 * Blank stays blank only when every entry is blank. Blank business type becomes "Unclassified".
 */
export function normalizeRows(rows: DailyRow[]): { rows: DailyRow[]; merged: number } {
  const map = new Map<string, DailyRow>();
  let merged = 0;
  for (const r of rows) {
    const key = `${r.date}|${r.brand}|${r.location}`;
    const prev = map.get(key);
    if (!prev) {
      map.set(key, { ...r, businessType: r.businessType?.trim() || UNCLASSIFIED });
      continue;
    }
    merged++;
    for (const k of NUMERIC_KEYS) prev[k] = sumNullable(prev[k], r[k]);
  }
  return { rows: [...map.values()], merged };
}

export function metricValue(r: DailyRow, metric: Metric): number {
  switch (metric) {
    case 'Net Sales': return num(r.net);
    case 'Total Sales': return num(r.total);
    case 'Gross Sales': return num(r.gross);
    case 'Bill Cuts': return num(r.bills);
  }
}

/** Brand / location / business type filters only (no dates). */
export function scopeRows(rows: DailyRow[], f: Filters): DailyRow[] {
  return rows.filter(r =>
    (!f.brands.length || f.brands.includes(r.brand)) &&
    (!f.locations.length || f.locations.includes(r.location)) &&
    (!f.businessTypes.length || f.businessTypes.includes(r.businessType)));
}

export function latestDate(rows: DailyRow[]): string | null {
  let max: string | null = null;
  for (const r of rows) if (max == null || r.date > max) max = r.date;
  return max;
}

/** The date WTD, MTD and the trend count up to: the "To" date if one is picked, otherwise the latest date in the data. */
export function asOfDate(rows: DailyRow[], f: Filters): string | null {
  return f.to ?? latestDate(rows);
}

export function inRange(rows: DailyRow[], from: string | null, to: string | null): DailyRow[] {
  return rows.filter(r => (!from || r.date >= from) && (!to || r.date <= to));
}

/** Rows that match every filter, including the date range. */
export function filterRows(rows: DailyRow[], f: Filters): DailyRow[] {
  return inRange(scopeRows(rows, f), f.from, f.to);
}

const channel = (net: number | null, orders: number | null): Channel => ({ net: num(net), orders: num(orders) });

export function computeTotals(rows: DailyRow[], metric: Metric): Totals {
  const t: Totals = {
    rows: rows.length, gross: 0, net: 0, total: 0, bills: 0, grossReported: 0, totalReported: 0, apc: null, activeLocations: 0,
    online: 0, offline: 0, onlineShare: null, offlineShare: null, onlineOrders: 0,
    zomatoOnline: { net: 0, orders: 0 }, zomatoDineIn: { net: 0, orders: 0 }, swiggyOnline: { net: 0, orders: 0 },
    swiggyDineIn: { net: 0, orders: 0 }, ownly: { net: 0, orders: 0 },
  };
  const active = new Set<string>();
  const add = (c: Channel, net: number | null, orders: number | null) => { const x = channel(net, orders); c.net += x.net; c.orders += x.orders; };
  for (const r of rows) {
    t.gross += num(r.gross); t.net += num(r.net); t.total += num(r.total); t.bills += num(r.bills);
    if (r.gross != null) t.grossReported++;
    if (r.total != null) t.totalReported++;
    if (metricValue(r, metric) !== 0) active.add(r.location);
    add(t.zomatoOnline, r.zomatoOnlineNet, r.zomatoOnlineOrders);
    add(t.zomatoDineIn, r.zomatoDineInNet, r.zomatoDineInOrders);
    add(t.swiggyOnline, r.swiggyOnlineNet, r.swiggyOnlineOrders);
    add(t.swiggyDineIn, r.swiggyDineInNet, r.swiggyDineInOrders);
    add(t.ownly, r.ownlyNet, r.ownlyOrders);
  }
  t.activeLocations = active.size;
  t.apc = t.bills > 0 ? t.net / t.bills : null;
  // Online = Zomato Online + Swiggy Online + Ownly (net). Offline = Net Sales - Online (so aggregator dine-in counts as offline).
  t.online = t.zomatoOnline.net + t.swiggyOnline.net + t.ownly.net;
  t.onlineOrders = t.zomatoOnline.orders + t.swiggyOnline.orders + t.ownly.orders;
  t.offline = t.net - t.online;
  t.onlineShare = t.net > 0 ? (t.online * 100) / t.net : null;
  t.offlineShare = t.net > 0 ? (t.offline * 100) / t.net : null;
  return t;
}

/** Totals over a date window, ignoring the date filter (used for WTD and MTD). */
export function windowTotals(scope: DailyRow[], from: string, to: string, metric: Metric): Totals {
  return computeTotals(inRange(scope, from, to), metric);
}

export function weekToDateStart(asOf: string): string { return mondayOf(asOf); }
export function monthToDateStart(asOf: string): string { return monthStart(asOf); }

/** Daily values of the selected metric for the 31 days ending on asOf (ignores the date filter, like the Excel version). */
export function trend31(scope: DailyRow[], asOf: string, metric: Metric): SeriesPoint[] {
  const perDay = new Map<string, number>();
  for (const r of scope) perDay.set(r.date, (perDay.get(r.date) ?? 0) + metricValue(r, metric));
  const out: SeriesPoint[] = [];
  for (let i = 30; i >= 0; i--) {
    const d = addDays(asOf, -i);
    out.push({ label: dayMonth(d), value: perDay.get(d) ?? 0 });
  }
  return out;
}

function ranking(rows: DailyRow[], key: (r: DailyRow) => string, metric: Metric, top?: number): SeriesPoint[] {
  const m = new Map<string, number>();
  for (const r of rows) m.set(key(r), (m.get(key(r)) ?? 0) + metricValue(r, metric));
  const list = [...m.entries()].map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
  return top ? list.slice(0, top) : list;
}
export const brandRanking = (rows: DailyRow[], metric: Metric): SeriesPoint[] => ranking(rows, r => r.brand, metric);
export const topLocations = (rows: DailyRow[], metric: Metric, n = 10): SeriesPoint[] => ranking(rows, r => r.location, metric, n);

/** Average per day for each weekday: total of each calendar date first, then the average over the dates of that weekday. */
export function weekdayAverage(rows: DailyRow[], metric: Metric): SeriesPoint[] {
  const perDay = new Map<string, number>();
  for (const r of rows) perDay.set(r.date, (perDay.get(r.date) ?? 0) + metricValue(r, metric));
  const sum = new Array(7).fill(0), cnt = new Array(7).fill(0);
  for (const [d, v] of perDay) { const w = weekdayIndex(d); sum[w] += v; cnt[w]++; }
  return WEEKDAYS.map((label, i) => ({ label, value: cnt[i] ? sum[i] / cnt[i] : 0 }));
}

/** APC (net / bills) per business type: cafes and showrooms must not be averaged together. */
export function apcByType(rows: DailyRow[]): { type: string; net: number; bills: number; apc: number | null }[] {
  const m = new Map<string, { net: number; bills: number }>();
  for (const r of rows) {
    const x = m.get(r.businessType) ?? { net: 0, bills: 0 };
    x.net += num(r.net); x.bills += num(r.bills); m.set(r.businessType, x);
  }
  return [...m.entries()].map(([type, x]) => ({ type, ...x, apc: x.bills > 0 ? x.net / x.bills : null })).sort((a, b) => b.net - a.net);
}

/** Locations in scope that have no Net Sales entry on the given date (blank = not reported). */
export function notReported(scope: DailyRow[], date: string): string[] {
  const all = new Set<string>(), done = new Set<string>();
  for (const r of scope) {
    all.add(r.location);
    if (r.date === date && r.net != null) done.add(r.location);
  }
  return [...all].filter(l => !done.has(l)).sort();
}

export function distinct(rows: DailyRow[], pick: (r: DailyRow) => string): string[] {
  return [...new Set(rows.map(pick))].sort((a, b) => a.localeCompare(b));
}
