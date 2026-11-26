/** Indian number formats: 1,23,456 and Lakh / Crore. */
const inGroup = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

export const fmtNum = (n: number): string => inGroup.format(Math.round(n));

/** 1.76 Lakh, 1.15 Cr, 54,321 */
export const fmtCompact = (n: number): string => {
  const a = Math.abs(n);
  if (a >= 1e7) return `${(n / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `${(n / 1e5).toFixed(2)} Lakh`;
  return fmtNum(n);
};

/** Short axis labels: 20 Lakh, 1.5 Cr, 54,000 (no trailing zeros) */
export const fmtAxis = (n: number): string => {
  const a = Math.abs(n), t = (x: number) => String(Number(x.toFixed(2)));
  if (a >= 1e7) return `${t(n / 1e7)} Cr`;
  if (a >= 1e5) return `${t(n / 1e5)} Lakh`;
  return fmtNum(n);
};

export const fmtRs = (n: number): string => `Rs ${fmtCompact(n)}`;
export const fmtPct = (n: number | null): string => (n == null ? '-' : `${n.toFixed(1)}%`);
