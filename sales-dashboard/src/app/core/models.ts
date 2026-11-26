/** One row of "Daily Data": one brand + location + date. A null number means "not reported" (different from 0). */
export interface DailyRow {
  date: string;                       // ISO date, yyyy-mm-dd
  brand: string;
  businessType: string;               // Cafe, EV Showroom, Hotel ... (blank rows are shown as "Unclassified")
  location: string;
  gross: number | null;
  net: number | null;
  total: number | null;
  bills: number | null;
  zomatoOnlineOrders: number | null;
  zomatoOnlineNet: number | null;
  zomatoDineInOrders: number | null;
  zomatoDineInNet: number | null;
  swiggyOnlineOrders: number | null;
  swiggyOnlineNet: number | null;
  swiggyDineInOrders: number | null;
  swiggyDineInNet: number | null;
  ownlyOrders: number | null;
  ownlyNet: number | null;
}

export type Metric = 'Net Sales' | 'Total Sales' | 'Gross Sales' | 'Bill Cuts';
export const METRICS: Metric[] = ['Net Sales', 'Total Sales', 'Gross Sales', 'Bill Cuts'];

export interface Filters {
  from: string | null;                // inclusive; null = from the first date in the data
  to: string | null;                  // inclusive; null = up to the latest date in the data
  brands: string[];                   // empty = all
  locations: string[];                // empty = all
  businessTypes: string[];            // empty = all
  metric: Metric;
}

export interface Channel { net: number; orders: number }

export interface Totals {
  rows: number;
  gross: number; net: number; total: number; bills: number;
  grossReported: number; totalReported: number;   // rows that actually have the value (blank is not zero)
  apc: number | null;                             // net / bills
  activeLocations: number;                        // locations with a non-zero value of the selected metric
  online: number; offline: number; onlineShare: number | null; offlineShare: number | null;
  onlineOrders: number;
  zomatoOnline: Channel; zomatoDineIn: Channel; swiggyOnline: Channel; swiggyDineIn: Channel; ownly: Channel;
}

export interface SeriesPoint { label: string; value: number }
