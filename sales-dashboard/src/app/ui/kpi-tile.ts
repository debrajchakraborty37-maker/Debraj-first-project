import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export type Tone = 'blue' | 'green' | 'orange' | 'purple' | 'teal' | 'grey';

@Component({
  selector: 'app-kpi-tile',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class]': '"tile tone-" + tone()' },
  template: `
    <div class="tile-label">{{ label() }}</div>
    <div class="tile-value">{{ value() }}</div>
    <div class="tile-sub">{{ sub() }}</div>
  `,
})
export class KpiTileComponent {
  readonly label = input.required<string>();
  readonly value = input.required<string>();
  readonly sub = input('');
  readonly tone = input<Tone>('blue');
}
