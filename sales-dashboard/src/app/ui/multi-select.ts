import { ChangeDetectionStrategy, Component, ElementRef, HostListener, computed, inject, input, output, signal } from '@angular/core';

/** A small drop-down with check boxes. Nothing ticked means "All". */
@Component({
  selector: 'app-multi-select',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="ms-button" (click)="open.set(!open())" [attr.aria-expanded]="open()">
      <span class="ms-label">{{ label() }}</span>
      <span class="ms-value">{{ summary() }}</span>
      <span class="ms-caret" aria-hidden="true">▾</span>
    </button>
    @if (open()) {
      <div class="ms-panel" role="listbox">
        <div class="ms-tools">
          <button type="button" class="link" (click)="clear()">All</button>
          <span class="muted">{{ options().length }} options</span>
        </div>
        <div class="ms-list">
          @for (o of options(); track o) {
            <label class="ms-row">
              <input type="checkbox" [checked]="selected().includes(o)" (change)="toggle(o)" />
              <span>{{ o }}</span>
            </label>
          }
        </div>
      </div>
    }
  `,
  styles: [`:host { position: relative; display: block; }`],
})
export class MultiSelectComponent {
  readonly label = input.required<string>();
  readonly options = input.required<string[]>();
  readonly selected = input<string[]>([]);
  readonly changed = output<string[]>();
  protected readonly open = signal(false);
  private readonly host = inject(ElementRef<HTMLElement>);

  protected readonly summary = computed(() => {
    const s = this.selected().filter(x => this.options().includes(x));
    if (!s.length) return 'All';
    return s.length === 1 ? s[0] : `${s.length} selected`;
  });

  protected toggle(o: string): void {
    const s = this.selected();
    this.changed.emit(s.includes(o) ? s.filter(x => x !== o) : [...s, o]);
  }
  protected clear(): void { this.changed.emit([]); }

  @HostListener('document:click', ['$event'])
  protected outside(e: Event): void {
    if (this.open() && !(this.host.nativeElement as HTMLElement).contains(e.target as Node)) this.open.set(false);
  }
}
