import { ChangeDetectionStrategy, Component, OnInit, computed, inject } from '@angular/core';
import { DashboardStore } from './core/dashboard.store';
import { APP_CONFIG } from './core/data-source';
import { dayMonthYear } from './core/dates';
import { fmtAxis, fmtCompact, fmtNum, fmtPct, fmtRs } from './core/format';
import { METRICS, Metric } from './core/models';
import { BarChartComponent } from './ui/bar-chart';
import { KpiTileComponent, Tone } from './ui/kpi-tile';
import { MultiSelectComponent } from './ui/multi-select';

interface Tile { label: string; value: string; sub: string; tone: Tone }

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MultiSelectComponent, KpiTileComponent, BarChartComponent],
  templateUrl: './app.html',
})
export class App implements OnInit {
  protected readonly store = inject(DashboardStore);
  protected readonly title = APP_CONFIG.title;
  protected readonly metrics = METRICS;
  protected readonly fmtNum = fmtNum;
  protected readonly fmtRs = fmtRs;
  protected readonly dayMonthYear = dayMonthYear;

  ngOnInit(): void { void this.store.load(); }

  /** money charts show Lakh / Crore, bill charts show plain numbers */
  protected readonly chartFormat = computed(() => (this.store.filters().metric === 'Bill Cuts' ? fmtNum : fmtCompact));
  protected readonly axisFormat = computed(() => (this.store.filters().metric === 'Bill Cuts' ? fmtNum : fmtAxis));
  protected readonly metric = computed<Metric>(() => this.store.filters().metric);

  protected readonly subtitle = computed(() => {
    const f = this.store.filters(), rows = this.store.rows();
    const first = rows.reduce((m, r) => (m && m < r.date ? m : r.date), '');
    const from = f.from ?? first, to = f.to ?? this.store.latest() ?? '';
    const part = (n: number, picked: string[], total: number) => (picked.length ? `${n}` : `all (${total})`);
    return `Metric: ${f.metric}   |   Dates: ${from ? dayMonthYear(from) : '-'} to ${to ? dayMonthYear(to) : '-'}   |   ` +
      `Brands: ${part(f.brands.length, f.brands, this.store.brandOptions().length)}   |   ` +
      `Locations: ${part(f.locations.length, f.locations, this.store.locationOptions().length)}   |   Source: ${this.store.sourceLabel}`;
  });

  protected readonly topTiles = computed<Tile[]>(() => {
    const t = this.store.totals(), f = this.store.filters();
    const mixed = this.store.apc().length > 1;
    const cover = (n: number) => (n === 0 ? 'not reported for this selection' : n < t.rows ? `entered in ${n} of ${t.rows} entries` : 'all entries reported');
    return [
      { label: 'GROSS SALES', value: t.grossReported ? fmtRs(t.gross) : 'Not reported', sub: cover(t.grossReported), tone: 'blue' },
      { label: 'NET SALES', value: fmtRs(t.net), sub: `${fmtNum(t.rows)} entries in selection`, tone: 'green' },
      { label: 'TOTAL SALES', value: t.totalReported ? fmtRs(t.total) : 'Not reported', sub: cover(t.totalReported), tone: 'blue' },
      { label: 'BILL CUTS', value: fmtNum(t.bills), sub: 'total bills in selection', tone: 'orange' },
      { label: 'APC (NET / BILL)', value: t.apc == null ? '-' : fmtRs(t.apc), sub: mixed ? 'mixed business types: see APC by business type' : 'net sales per bill', tone: 'purple' },
      { label: 'ACTIVE LOCATIONS', value: fmtNum(t.activeLocations), sub: `with a non-zero ${f.metric}`, tone: 'teal' },
    ];
  });

  protected readonly channelTiles = computed<Tile[]>(() => {
    const t = this.store.totals(), w = this.store.wtd(), m = this.store.mtd(), a = this.store.asOf();
    const span = (x: typeof w, from: string) => (x && a
      ? `Online ${fmtCompact(x.online)} | Offline ${fmtCompact(x.offline)} | ${dayMonthYear(from)} to ${dayMonthYear(a)}` : 'no data');
    return [
      { label: 'ONLINE SALES (NET)', value: fmtRs(t.online), sub: `${fmtPct(t.onlineShare)} of net | ${fmtNum(t.onlineOrders)} orders`, tone: 'orange' },
      { label: 'OFFLINE SALES (NET)', value: fmtRs(t.offline), sub: `${fmtPct(t.offlineShare)} of net | ${fmtNum(Math.max(0, t.bills - t.onlineOrders))} bills`, tone: 'green' },
      { label: 'WEEK TO DATE NET SALES', value: fmtRs(w?.net ?? 0), sub: span(w, this.store.wtdFrom()), tone: 'blue' },
      { label: 'MONTH TO DATE NET SALES', value: fmtRs(m?.net ?? 0), sub: span(m, this.store.mtdFrom()), tone: 'purple' },
    ];
  });

  protected readonly platformTiles = computed<Tile[]>(() => {
    const t = this.store.totals();
    const share = (n: number) => (t.net > 0 ? fmtPct((n * 100) / t.net) : '0.0%');
    const one = (label: string, c: { net: number; orders: number }): Tile =>
      ({ label, value: fmtRs(c.net), sub: `${fmtNum(c.orders)} orders | ${share(c.net)} of net sales`, tone: 'grey' });
    return [
      one('SWIGGY ONLINE (NET)', t.swiggyOnline), one('ZOMATO ONLINE (NET)', t.zomatoOnline),
      one('SWIGGY DINE IN (NET)', t.swiggyDineIn), one('ZOMATO DINE IN (NET)', t.zomatoDineIn),
    ];
  });

  protected readonly noticeMissing = computed(() => {
    const m = this.store.missing();
    return m.length ? `${m.length} location${m.length === 1 ? '' : 's'} with no Net Sales on ${dayMonthYear(this.store.asOf() ?? '')}` : '';
  });

  // event handlers (the template stays free of casts)
  protected setFrom(e: Event): void { this.store.patch({ from: (e.target as HTMLInputElement).value || null }); }
  protected setTo(e: Event): void { this.store.patch({ to: (e.target as HTMLInputElement).value || null }); }
  protected labels(s: { label: string }[]): string[] { return s.map(x => x.label); }
  protected values(s: { value: number }[]): number[] { return s.map(x => x.value); }
  protected metricName(): string { return this.store.filters().metric; }
}
