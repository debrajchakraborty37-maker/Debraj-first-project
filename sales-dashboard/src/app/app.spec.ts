import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';
import { App } from './app';

describe('App', () => {
  it('loads the sample data and shows the title, 14 tiles and the filters', async () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);   // no canvas in the test browser: the charts skip drawing
    await TestBed.configureTestingModule({ imports: [App] }).compileComponents();
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('h1')?.textContent).toContain('Sales Insights Dashboard');
    expect(el.querySelectorAll('app-kpi-tile').length).toBe(14);
    expect(el.querySelectorAll('app-multi-select').length).toBe(3);
    expect(el.querySelectorAll('.segmented button').length).toBe(4);
  });
});
