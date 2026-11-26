import { describe, expect, it } from 'vitest';
import {
  apcByType, asOfDate, brandRanking, computeTotals, filterRows, normalizeRows, notReported, scopeRows, topLocations, trend31, weekdayAverage,
} from './calc';
import { addDays, mondayOf, monthStart, weekdayIndex } from './dates';
import { fmtCompact, fmtNum, fmtPct } from './format';
import { DailyRow, Filters } from './models';
import { buildSampleData } from './sample-data';

const base = (o: Partial<DailyRow>): DailyRow => ({
  date: '2026-11-18', brand: 'B1', businessType: 'Cafe', location: 'L1',
  gross: null, net: null, total: null, bills: null,
  zomatoOnlineOrders: null, zomatoOnlineNet: null, zomatoDineInOrders: null, zomatoDineInNet: null,
  swiggyOnlineOrders: null, swiggyOnlineNet: null, swiggyDineInOrders: null, swiggyDineInNet: null, ownlyOrders: null, ownlyNet: null, ...o,
});
const F: Filters = { from: null, to: null, brands: [], locations: [], businessTypes: [], metric: 'Net Sales' };

describe('dates', () => {
  it('knows weekdays, Mondays and month starts (2026-11-21 is a Saturday)', () => {
    expect(weekdayIndex('2026-11-21')).toBe(5);
    expect(mondayOf('2026-11-21')).toBe('2026-11-16');
    expect(mondayOf('2026-11-16')).toBe('2026-11-16');
    expect(monthStart('2026-11-21')).toBe('2026-11-01');
    expect(addDays('2026-11-01', -1)).toBe('2026-10-31');
  });
});

describe('normalizeRows', () => {
  it('adds repeated entries of the same date + brand + location and keeps blank only when all are blank', () => {
    const { rows, merged } = normalizeRows([
      base({ net: 100, bills: 1 }), base({ net: 50, bills: null }), base({ location: 'L2', net: null }), base({ location: 'L2', net: null }),
    ]);
    expect(merged).toBe(2);
    expect(rows).toHaveLength(2);
    expect(rows.find(r => r.location === 'L1')).toMatchObject({ net: 150, bills: 1 });
    expect(rows.find(r => r.location === 'L2')!.net).toBeNull();
  });
  it('labels a blank business type "Unclassified"', () => {
    expect(normalizeRows([base({ businessType: '  ' })]).rows[0].businessType).toBe('Unclassified');
  });
});

describe('computeTotals', () => {
  const rows = [
    base({ gross: 120, net: 100, total: 110, bills: 4, zomatoOnlineNet: 30, zomatoOnlineOrders: 2, swiggyOnlineNet: 20, swiggyOnlineOrders: 1, ownlyNet: 10, ownlyOrders: 1, zomatoDineInNet: 15, zomatoDineInOrders: 1 }),
    base({ location: 'L2', net: 300, bills: 6 }),                  // gross and total not reported
    base({ location: 'L3', net: null, bills: null }),              // not reported
  ];
  const t = computeTotals(rows, 'Net Sales');
  it('adds the numbers and counts what was really entered', () => {
    expect(t).toMatchObject({ rows: 3, gross: 120, net: 400, total: 110, bills: 10, grossReported: 1, totalReported: 1 });
    expect(t.apc).toBe(40);
    expect(t.activeLocations).toBe(2);
  });
  it('splits online (Zomato Online + Swiggy Online + Ownly) from offline (net - online, dine-in included)', () => {
    expect(t.online).toBe(60);
    expect(t.offline).toBe(340);
    expect(t.onlineShare).toBeCloseTo(15);
    expect(t.onlineOrders).toBe(4);
    expect(t.zomatoDineIn).toEqual({ net: 15, orders: 1 });
  });
  it('gives APC null when there are no bills', () => { expect(computeTotals([base({ net: 10 })], 'Net Sales').apc).toBeNull(); });
});

describe('filters, WTD / MTD, trend and rankings', () => {
  const rows = normalizeRows([
    base({ date: '2026-11-16', net: 100, bills: 1 }), base({ date: '2026-11-21', net: 200, bills: 2 }), base({ date: '2026-11-23', net: 50, bills: 1 }),
    base({ date: '2026-11-21', brand: 'B2', location: 'L9', businessType: 'EV Showroom', net: 1000, bills: 1 }),
    base({ date: '2026-10-30', net: 999, bills: 9 }),
  ]).rows;
  it('finds the as-of date: the picked "To" date, else the latest date', () => {
    expect(asOfDate(rows, F)).toBe('2026-11-23');
    expect(asOfDate(rows, { ...F, to: '2026-11-21' })).toBe('2026-11-21');
  });
  it('filters by brand and date', () => {
    expect(filterRows(rows, { ...F, brands: ['B2'] })).toHaveLength(1);
    expect(filterRows(rows, { ...F, from: '2026-11-20', to: '2026-11-22' })).toHaveLength(2);
    expect(scopeRows(rows, { ...F, businessTypes: ['EV Showroom'] })).toHaveLength(1);
  });
  it('the 31-day trend ends on the as-of date and has 31 points', () => {
    const t = trend31(rows, '2026-11-23', 'Net Sales');
    expect(t).toHaveLength(31);
    expect(t.at(-1)).toEqual({ label: '23 Nov', value: 50 });
    expect(t.find(p => p.label === '21 Nov')!.value).toBe(1200);
    expect(t[0].label).toBe('24 Oct');
  });
  it('ranks brands and locations by the chosen metric', () => {
    const nov = rows.filter(r => r.date >= '2026-11-01');                       // November only (B1 also has an October row)
    expect(brandRanking(nov, 'Net Sales')[0]).toEqual({ label: 'B2', value: 1000 });
    expect(brandRanking(nov, 'Bill Cuts')[0]).toEqual({ label: 'B1', value: 4 });
    expect(topLocations(nov, 'Net Sales', 1)).toEqual([{ label: 'L9', value: 1000 }]);
  });
  it('averages per weekday after adding each date first', () => {
    const w = weekdayAverage(rows.filter(r => r.date >= '2026-11-01'), 'Net Sales');
    expect(w.find(x => x.label === 'Sat')!.value).toBe(1200);        // 21 Nov (Sat): 200 + 1000
    expect(w.find(x => x.label === 'Mon')!.value).toBe(75);          // 16 Nov: 100 and 23 Nov: 50 -> average 75
  });
  it('keeps APC per business type', () => {
    const a = apcByType(rows.filter(r => r.date >= '2026-11-01'));
    expect(a.find(x => x.type === 'EV Showroom')!.apc).toBe(1000);
    expect(a.find(x => x.type === 'Cafe')!.apc).toBeCloseTo(87.5);
  });
  it('lists locations with no Net Sales on a date', () => {
    expect(notReported(rows, '2026-11-23')).toEqual(['L9']);
  });
});

describe('sample data and number formats', () => {
  const sample = normalizeRows(buildSampleData());
  it('is the same every time and has the quirks of the real data', () => {
    expect(buildSampleData().length).toBe(buildSampleData().length);
    expect(sample.rows.length).toBeGreaterThan(1000);
    expect(sample.merged).toBeGreaterThan(0);
    const t = computeTotals(sample.rows, 'Net Sales');
    expect(t.net).toBeGreaterThan(0);
    expect(t.grossReported).toBeLessThan(t.rows);
    expect(t.online + t.offline).toBeCloseTo(t.net);
  });
  it('formats Indian style', () => {
    expect(fmtNum(1234567)).toBe('12,34,567');
    expect(fmtCompact(175590)).toBe('1.76 Lakh');
    expect(fmtCompact(11518026)).toBe('1.15 Cr');
    expect(fmtCompact(54321)).toBe('54,321');
    expect(fmtPct(null)).toBe('-');
  });
});
