import { addDays } from './dates';
import { DailyRow } from './models';

/**
 * SAMPLE DATA ONLY: invented brands, locations and numbers so the dashboard can be shown and tested without real company data.
 * The shape (and the quirks: blank Gross/Total, brands that do not report, a duplicate entry, missing days) copies the real Daily Data.
 */
function rng(seed: number): () => number {            // small seeded generator: the same sample every time
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const blank = (): Omit<DailyRow, 'date' | 'brand' | 'businessType' | 'location'> => ({
  gross: null, net: null, total: null, bills: null,
  zomatoOnlineOrders: null, zomatoOnlineNet: null, zomatoDineInOrders: null, zomatoDineInNet: null,
  swiggyOnlineOrders: null, swiggyOnlineNet: null, swiggyDineInOrders: null, swiggyDineInNet: null, ownlyOrders: null, ownlyNet: null,
});

export function buildSampleData(firstDate = '2026-10-01', days = 54): DailyRow[] {
  const rand = rng(20261123);
  const between = (lo: number, hi: number) => lo + rand() * (hi - lo);
  const rows: DailyRow[] = [];

  const cafes = [
    { brand: 'Cafe Brand A', locs: ['City Centre', 'Lake Road', 'Tech Park', 'Old Town', 'Airport Road', 'Mall Street'], base: 26000, apc: 410 },
    { brand: 'Cafe Brand B', locs: ['North Plaza', 'Riverside', 'Station Road', 'University'], base: 17000, apc: 360 },
  ];
  const evLocs = ['Showroom 1', 'Showroom 2', 'Showroom 3', 'Showroom 4', 'Showroom 5', 'Showroom 6', 'Showroom 7', 'Showroom 8'];
  const mobLocs = ['Mobility Hub 1', 'Mobility Hub 2', 'Mobility Hub 3'];

  for (let i = 0; i < days; i++) {
    const date = addDays(firstDate, i);
    const dow = (new Date(date + 'T00:00:00Z').getUTCDay() + 6) % 7;      // Mon = 0
    const weekend = dow >= 5 ? 1.35 : 1;

    // Cafes: every field filled, gross > total > net, some aggregator sales
    for (const c of cafes) {
      for (const loc of c.locs) {
        const f = (0.55 + (loc.length % 7) / 10) * weekend;
        const net = Math.round(c.base * f * between(0.7, 1.3));
        const bills = Math.max(1, Math.round(net / (c.apc * between(0.9, 1.1))));
        const zo = Math.round(between(0, 6)), so = Math.round(between(0, 6)), zd = Math.round(between(0, 2)), sd = Math.round(between(0, 2));
        const own = rand() < 0.15 ? Math.round(between(1, 3)) : 0;
        rows.push({
          ...blank(), date, brand: c.brand, businessType: 'Cafe', location: loc,
          gross: Math.round(net * 1.08), net, total: Math.round(net * 1.05), bills,
          zomatoOnlineOrders: zo, zomatoOnlineNet: zo * Math.round(between(300, 520)),
          zomatoDineInOrders: zd, zomatoDineInNet: zd * Math.round(between(500, 900)),
          swiggyOnlineOrders: so, swiggyOnlineNet: so * Math.round(between(300, 520)),
          swiggyDineInOrders: sd, swiggyDineInNet: sd * Math.round(between(500, 900)),
          ownlyOrders: own, ownlyNet: own * Math.round(between(380, 600)),
        });
      }
    }

    // EV showrooms: few, very large bills; Gross and Total are not reported; some days are split into two entries
    for (const loc of evLocs) {
      const sold = rand() < 0.28;
      const bills = sold ? (rand() < 0.2 ? 2 : 1) : 0;
      const net = bills * Math.round(between(75000, 190000));
      rows.push({ ...blank(), date, brand: 'EV Brand', businessType: 'EV Showroom', location: loc, net, bills });
      if (sold && rand() < 0.12) rows.push({ ...blank(), date, brand: 'EV Brand', businessType: 'EV Showroom', location: loc, net: 4500, bills: 0 });
    }

    // Hotel: one location, Gross and Total not reported
    {
      const bills = Math.round(between(6, 20) * weekend);
      rows.push({ ...blank(), date, brand: 'Hotel Brand', businessType: 'Hotel', location: 'Hotel Main', net: Math.round(bills * between(2400, 3600)), bills });
    }

    // Mobility: rare sales, and no row at all on some days
    for (const loc of mobLocs) {
      if (rand() < 0.2) continue;                                  // row missing (not entered)
      const sold = rand() < 0.3;
      rows.push({ ...blank(), date, brand: 'Mobility Brand', businessType: 'Mobility', location: loc, net: sold ? Math.round(between(2500, 16000)) : 0, bills: sold ? 1 : 0 });
    }

    // Wellness: rows exist but Net Sales and Bill Cuts are blank (not reporting yet)
    rows.push({ ...blank(), date, brand: 'Wellness Brand', businessType: 'Wellness', location: 'Salon' });
    rows.push({ ...blank(), date, brand: 'Wellness Brand', businessType: 'Wellness', location: 'Spa' });
  }
  return rows;
}
