// "B2B HNI" rule: a lead is kept only when the person is a business owner or
// senior decision maker (B2B) AND the stated budget reaches the HNI threshold.
export const B2B_TITLE = /\b(owner|proprietor|founder|co-?founder|director|managing|md|ceo|cfo|coo|cxo|chairman|promoter|partner|president|entrepreneur|businessman|business ?man|industrialist|investor|general manager|senior manager|vice president|vp|head)\b/i;

export function isB2b(profession) {
  return B2B_TITLE.test(String(profession || ''));
}

export function isHni(budgetCr, hniMinCr = 1) {
  return Number(budgetCr) >= hniMinCr;
}

export function segmentOf({ budgetCr, profession }, hniMinCr = 1) {
  return isB2b(profession) && isHni(budgetCr, hniMinCr) ? 'HNI B2B' : 'Other';
}

export function qualityOf(budgetCr) {
  const b = Number(budgetCr);
  if (b >= 5) return 'Hot';
  if (b >= 1.5) return 'Hot';
  if (b >= 1) return 'Warm';
  return 'Cold';
}
