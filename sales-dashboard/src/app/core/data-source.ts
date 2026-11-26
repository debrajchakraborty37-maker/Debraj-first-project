import { Injectable } from '@angular/core';
import { DailyRow } from './models';
import { buildSampleData } from './sample-data';

/**
 * Where the dashboard gets its rows.
 *   'sample' : invented demo data (default, nothing leaves the browser)
 *   'api'    : your secure back end. It must return a JSON array of DailyRow objects (see README, "Connect real data").
 */
export const APP_CONFIG: { dataSource: 'sample' | 'api'; apiUrl: string; title: string } = {
  dataSource: 'sample',
  apiUrl: '',
  title: 'Sales Insights Dashboard',
};

@Injectable({ providedIn: 'root' })
export class DataSourceService {
  readonly label = APP_CONFIG.dataSource === 'sample' ? 'Sample data' : 'Daily Data';

  async load(): Promise<DailyRow[]> {
    if (APP_CONFIG.dataSource === 'sample') return buildSampleData();
    const res = await fetch(APP_CONFIG.apiUrl, { credentials: 'include' });
    if (!res.ok) throw new Error(`The data service answered ${res.status}`);
    return (await res.json()) as DailyRow[];
  }
}
