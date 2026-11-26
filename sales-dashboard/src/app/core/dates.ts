/** Date helpers. Dates travel as ISO strings (yyyy-mm-dd) and are handled in UTC so the time zone can never shift a day. */
const DAY = 86400000;

export const toMs = (iso: string): number => {
  const [y, m, d] = iso.split('-').map(Number);
  return Date.UTC(y, m - 1, d);
};
export const toIso = (ms: number): string => new Date(ms).toISOString().slice(0, 10);
export const addDays = (iso: string, n: number): string => toIso(toMs(iso) + n * DAY);
/** Monday = 0 ... Sunday = 6 */
export const weekdayIndex = (iso: string): number => (new Date(toMs(iso)).getUTCDay() + 6) % 7;
export const mondayOf = (iso: string): string => addDays(iso, -weekdayIndex(iso));
export const monthStart = (iso: string): string => iso.slice(0, 8) + '01';
export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** 21 Nov */
export const dayMonth = (iso: string): string => `${iso.slice(8, 10)} ${MONTHS[Number(iso.slice(5, 7)) - 1]}`;
/** 21 Nov 2026 */
export const dayMonthYear = (iso: string): string => `${dayMonth(iso)} ${iso.slice(0, 4)}`;
