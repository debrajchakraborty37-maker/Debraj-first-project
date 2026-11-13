import { parseInvestor, parseAgency } from './parse.js';
import { segmentOf, qualityOf } from '../segment.js';
import { formatDate, domainOf, newId, parseDate } from '../util.js';

export function buildQueries(rules) {
  const q = [];
  const cities = rules.cities.length ? rules.cities : ['India'];
  for (const brand of rules.brands) {
    for (const city of cities) {
      q.push({ kind: 'lead', text: `franchise investor in ${city} looking to invest in ${brand} upto INR crore site:smergers.com` });
    }
  }
  q.push({ kind: 'agency', text: 'franchise lead generation agency India investors' });
  q.push({ kind: 'agency', text: 'franchise lead generation company HNI investors pricing' });
  return q;
}

function monthKey(d) { return `${d.getUTCFullYear()}-${d.getUTCMonth()}`; }

export class Hunter {
  constructor({ repos, search, now = () => new Date() }) {
    this.repos = repos; this.search = search; this.now = now; this.running = false;
  }

  async queriesUsedThisMonth() {
    const runs = await this.repos.runs.list({ fresh: true });
    const key = monthKey(this.now());
    return runs.reduce((sum, r) => {
      const d = parseDate(String(r.startedAt).slice(0, 11));
      return d && monthKey(d) === key ? sum + (Number(r.queries) || 0) : sum;
    }, 0);
  }

  /** One full hunt: search, keep only HNI B2B, drop duplicates, save, log the run. */
  async run({ trigger = 'manual', by = 'system' } = {}) {
    if (this.running) return { skipped: 'A hunt is already running' };
    this.running = true;
    const started = this.now();
    const stats = { queries: 0, found: 0, saved: 0, duplicates: 0, filtered: 0, errors: 0 };
    const notes = [];
    try {
      const rules = await this.repos.rules.get();
      const used = await this.queriesUsedThisMonth();
      let budget = Math.min(rules.maxQueriesPerRun, Math.max(0, rules.monthlyQueryCap - used));
      if (!this.search.configured) { notes.push('Search API not configured'); budget = 0; }
      else if (budget === 0) notes.push('Monthly search budget used up');

      const leads = await this.repos.leads.list({ fresh: true });
      const agencies = await this.repos.agencies.list({ fresh: true });
      const seenUrls = new Set(leads.map((l) => l.sourceUrl).filter(Boolean));
      const seenDomains = new Set(agencies.map((a) => domainOf(a.website)).filter(Boolean));
      const today = formatDate(this.now());

      for (const q of buildQueries(rules)) {
        if (stats.queries >= budget) { notes.push('Stopped at query limit'); break; }
        stats.queries += 1;
        let results = [];
        try { results = await this.search.search(q.text); } catch (e) { stats.errors += 1; notes.push(e.message); continue; }
        for (const r of results) {
          stats.found += 1;
          if (q.kind === 'lead') {
            const p = parseInvestor(r);
            if (!p) { stats.filtered += 1; continue; }
            if (seenUrls.has(p.sourceUrl)) { stats.duplicates += 1; continue; }
            if (segmentOf(p, rules.hniMinCr) !== 'HNI B2B' || p.budgetCr > rules.maxBudgetCr) { stats.filtered += 1; continue; }
            seenUrls.add(p.sourceUrl);
            await this.repos.leads.create({
              ...p, dateReceived: today, phone: '', email: '', quality: qualityOf(p.budgetCr),
              status: 'New', nextFollowUp: '', owner: '',
            });
            stats.saved += 1;
          } else {
            const a = parseAgency(r);
            const dom = a && domainOf(a.website);
            if (!a || !dom) { stats.filtered += 1; continue; }
            if (seenDomains.has(dom)) { stats.duplicates += 1; continue; }
            seenDomains.add(dom);
            await this.repos.agencies.create({
              ...a, dateAdded: today, phone: '', email: '', city: '', status: 'New', linkedin: '', owner: '',
            });
            stats.saved += 1;
          }
        }
      }
    } catch (e) {
      stats.errors += 1; notes.push(`Run failed: ${e.message}`);
    } finally {
      this.running = false;
    }
    const finished = this.now();
    const run = {
      id: newId('R'), startedAt: `${formatDate(started)} ${started.toISOString().slice(11, 16)}`,
      finishedAt: `${formatDate(finished)} ${finished.toISOString().slice(11, 16)}`,
      trigger, by, ...stats, notes: notes.join('; ').slice(0, 500),
    };
    await this.repos.runs.create(run);
    return run;
  }
}
