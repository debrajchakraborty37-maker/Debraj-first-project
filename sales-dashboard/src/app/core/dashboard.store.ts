import { Injectable, computed, inject, signal } from '@angular/core';
import {
  apcByType, asOfDate, brandRanking, computeTotals, distinct, filterRows, latestDate, normalizeRows, notReported, scopeRows,
  topLocations, trend31, weekdayAverage, weekToDateStart, monthToDateStart, windowTotals,
} from './calc';
import { DataSourceService } from './data-source';
import { addDays } from './dates';
import { DailyRow, Filters, Metric } from './models';

const START: Filters = { from: null, to: null, brands: [], locations: [], businessTypes: [], metric: 'Net Sales' };

/** One place that holds the data and the filter choices; every number on the screen is a computed value of these two. */
@Injectable({ providedIn: 'root' })
export class DashboardStore {
  private readonly source = inject(DataSourceService);

  readonly status = signal<'loading' | 'ready' | 'error'>('loading');
  readonly error = signal('');
  readonly sourceLabel = this.source.label;
  readonly filters = signal<Filters>({ ...START });

  private readonly loaded = signal<{ rows: DailyRow[]; merged: number }>({ rows: [], merged: 0 });
  readonly rows = computed(() => this.loaded().rows);
  readonly merged = computed(() => this.loaded().merged);

  readonly latest = computed(() => latestDate(this.rows()));
  readonly asOf = computed(() => asOfDate(this.rows(), this.filters()));

  /** brand + location + business type filters, all dates */
  readonly scope = computed(() => scopeRows(this.rows(), this.filters()));
  readonly selected = computed(() => filterRows(this.rows(), this.filters()));
  readonly totals = computed(() => computeTotals(this.selected(), this.filters().metric));

  readonly wtd = computed(() => { const a = this.asOf(); return a ? windowTotals(this.scope(), weekToDateStart(a), a, this.filters().metric) : null; });
  readonly mtd = computed(() => { const a = this.asOf(); return a ? windowTotals(this.scope(), monthToDateStart(a), a, this.filters().metric) : null; });
  readonly wtdFrom = computed(() => { const a = this.asOf(); return a ? weekToDateStart(a) : ''; });
  readonly mtdFrom = computed(() => { const a = this.asOf(); return a ? monthToDateStart(a) : ''; });

  readonly trend = computed(() => { const a = this.asOf(); return a ? trend31(this.scope(), a, this.filters().metric) : []; });
  readonly brandsRank = computed(() => brandRanking(this.selected(), this.filters().metric));
  readonly locationsRank = computed(() => topLocations(this.selected(), this.filters().metric));
  readonly weekdays = computed(() => weekdayAverage(this.selected(), this.filters().metric));
  readonly apc = computed(() => apcByType(this.selected()));
  readonly missing = computed(() => { const a = this.asOf(); return a ? notReported(this.scope(), a) : []; });

  readonly brandOptions = computed(() => distinct(this.rows(), r => r.brand));
  readonly typeOptions = computed(() => distinct(this.rows(), r => r.businessType));
  /** locations shrink when brands or business types are picked */
  readonly locationOptions = computed(() => distinct(scopeRows(this.rows(), { ...this.filters(), locations: [] }), r => r.location));

  async load(): Promise<void> {
    this.status.set('loading');
    try {
      const raw = await this.source.load();
      const norm = normalizeRows(raw);
      this.loaded.set({ rows: norm.rows, merged: norm.merged });
      this.status.set('ready');
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : String(e));
      this.status.set('error');
    }
  }

  patch(p: Partial<Filters>): void { this.filters.update(f => ({ ...f, ...p })); }
  setMetric(metric: Metric): void { this.patch({ metric }); }
  clearAll(): void { this.filters.set({ ...START, metric: this.filters().metric }); }

  /** Quick date ranges counted back from the latest date in the data. */
  preset(kind: 'all' | 'latest' | 'last7' | 'mtd'): void {
    const last = this.latest();
    if (!last) return;
    if (kind === 'all') this.patch({ from: null, to: null });
    else if (kind === 'latest') this.patch({ from: last, to: last });
    else if (kind === 'last7') this.patch({ from: addDays(last, -6), to: last });
    else this.patch({ from: monthToDateStart(last), to: last });
  }
}
