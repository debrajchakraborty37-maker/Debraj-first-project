// Field key (API) -> column header (Google Sheet). The first columns match the
// existing Leads / Agencies tabs exactly; extra columns are appended on the right.
export const LEAD_FIELDS = [
  ['dateReceived', 'Date received'], ['source', 'Source'], ['brand', 'Brand interested'], ['name', 'Name'],
  ['phone', 'Phone'], ['email', 'Email'], ['city', 'City'], ['profession', 'Profession'],
  ['budgetCr', 'Stated budget (Rs crore)'], ['quality', 'Lead quality'], ['status', 'Status'],
  ['nextFollowUp', 'Next follow-up'], ['notes', 'Notes'],
  ['id', 'Lead ID'], ['owner', 'Owner'], ['sourceUrl', 'Source URL'], ['segment', 'Segment'],
];

export const AGENCY_FIELDS = [
  ['dateAdded', 'Date added'], ['name', 'Agency name'], ['type', 'Type'], ['website', 'Website'],
  ['phone', 'Public phone'], ['email', 'Public email'], ['city', 'City'], ['leadsOnly', 'Leads only?'],
  ['services', 'Services and claims'], ['pricing', 'Pricing signals'], ['sourceUrl', 'Source URL'],
  ['status', 'Status'], ['notes', 'Notes'], ['linkedin', 'LinkedIn Profile'],
  ['id', 'Agency ID'], ['owner', 'Owner'],
];

export const RUN_FIELDS = [
  ['id', 'Run ID'], ['startedAt', 'Started'], ['finishedAt', 'Finished'], ['trigger', 'Trigger'], ['by', 'By'],
  ['queries', 'Queries'], ['found', 'Found'], ['saved', 'Saved'], ['duplicates', 'Duplicates'],
  ['filtered', 'Filtered out'], ['errors', 'Errors'], ['notes', 'Notes'],
];

export const RULE_FIELDS = [['key', 'Key'], ['value', 'Value']];

export const TABS = {
  Leads: LEAD_FIELDS,
  Agencies: AGENCY_FIELDS,
  Runs: RUN_FIELDS,
  Rules: RULE_FIELDS,
};

export const LEAD_STATUSES = ['New', 'Shortlisted', 'Contacted', 'Meeting', 'Negotiation', 'Won', 'Lost', 'Skipped'];
export const QUALITIES = ['Hot', 'Warm', 'Cold'];

export const DEFAULT_RULES = {
  brands: ['Cafe / F&B', 'Beauty and wellness', 'Gyms'],
  cities: ['Delhi', 'Bangalore', 'Mumbai'],
  hniMinCr: 1,          // HNI = stated budget of at least Rs 1 crore
  maxBudgetCr: 25,
  schedule: 'hourly',   // hourly | every3h | daily | off
  maxQueriesPerRun: 12,
  monthlyQueryCap: 2000, // monthly search budget, counted from the Runs tab
};
