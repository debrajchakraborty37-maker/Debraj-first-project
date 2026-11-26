import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, afterRenderEffect, inject, input, viewChild } from '@angular/core';
import { BarController, BarElement, CategoryScale, Chart, LinearScale, Tooltip } from 'chart.js';

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

/** A bar chart (vertical or horizontal). It redraws by itself whenever its inputs change. */
@Component({
  selector: 'app-bar-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h3 class="card-title">{{ title() }}</h3>
    <div class="chart-box"><canvas #cv></canvas></div>
  `,
})
export class BarChartComponent {
  readonly title = input.required<string>();
  readonly labels = input.required<string[]>();
  readonly values = input.required<number[]>();
  readonly horizontal = input(false);
  readonly color = input('#1565c0');
  readonly format = input<(v: number) => string>(v => String(v));
  readonly axisFormat = input<(v: number) => string>(v => String(v));

  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('cv');
  private chart?: Chart;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.chart?.destroy());
    afterRenderEffect(() => {
      const labels = this.labels(), values = this.values(), horizontal = this.horizontal(), color = this.color(), fmt = this.format(), axisFmt = this.axisFormat();
      const el = this.canvas().nativeElement;
      let ctx: CanvasRenderingContext2D | null = null;
      try { ctx = el.getContext('2d'); } catch { ctx = null; }
      if (!ctx) return;                                     // no canvas available (for example in unit tests)
      this.chart?.destroy();
      this.chart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ data: values, backgroundColor: color, borderRadius: 4, maxBarThickness: 34 }] },
        options: {
          indexAxis: horizontal ? 'y' : 'x',
          responsive: true, maintainAspectRatio: false, animation: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ' ' + fmt(Number(horizontal ? c.parsed.x : c.parsed.y)) } } },
          scales: {
            x: { grid: { display: horizontal }, ticks: { callback: v => (horizontal ? axisFmt(Number(v)) : this.tick(labels, v)), maxRotation: 60, autoSkip: true } },
            y: { grid: { display: !horizontal }, beginAtZero: true, ticks: { callback: v => (horizontal ? this.tick(labels, v) : axisFmt(Number(v))) } },
          },
        },
      });
    });
  }

  private tick(labels: string[], v: string | number): string {
    const s = labels[Number(v)] ?? '';
    return s.length > 26 ? s.slice(0, 25) + '…' : s;
  }
}
