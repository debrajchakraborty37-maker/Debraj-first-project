import { parseDate } from './util.js';

const count = (items, key) => {
  const m = {};
  for (const i of items) { const k = i[key] || 'Not set'; m[k] = (m[k] || 0) + 1; }
  return m;
};
const top = (m, n = 5) => Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, n).map(([name, count]) => ({ name, count }));

export async function buildDashboard(repos, hunter, now = new Date()) {
  const [leads, agencies, runs, rules] = await Promise.all([
    repos.leads.list(), repos.agencies.list(), repos.runs.list(), repos.rules.get(),
  ]);
  const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const open = leads.filter((l) => !['Won', 'Lost', 'Skipped'].includes(l.status));
  const due = open.filter((l) => { const d = parseDate(l.nextFollowUp); return d && d <= today; });
  const hni = leads.filter((l) => l.segment === 'HNI B2B');
  const pipelineValue = hni.filter((l) => !['Lost', 'Skipped'].includes(l.status)).reduce((s, l) => s + (l.budgetCr || 0), 0);
  const lastRun = runs.length ? runs[runs.length - 1] : null;
  const used = await hunter.queriesUsedThisMonth();
  return {
    leads: {
      total: leads.length,
      hniB2b: hni.length,
      newCount: leads.filter((l) => l.status === 'New').length,
      hot: leads.filter((l) => l.quality === 'Hot').length,
      followUpsDue: due.length,
      pipelineValueCr: Math.round(pipelineValue * 100) / 100,
      byQuality: count(leads, 'quality'),
      byStatus: count(leads, 'status'),
      topCities: top(count(leads, 'city')),
      topBrands: top(count(leads, 'brand')),
    },
    agencies: {
      total: agencies.length,
      leadsOnly: agencies.filter((a) => a.leadsOnly === 'Yes').length,
      newCount: agencies.filter((a) => a.status === 'New').length,
      byType: count(agencies, 'type'),
      byStatus: count(agencies, 'status'),
    },
    hunt: {
      lastRun,
      schedule: rules.schedule,
      queriesUsedThisMonth: used,
      monthlyQueryCap: rules.monthlyQueryCap,
      searchConfigured: hunter.search.configured,
    },
  };
}
