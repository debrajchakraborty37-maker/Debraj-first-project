import { domainOf } from '../util.js';

const clean = (s) => String(s || '').replace(/\s+/g, ' ').replace(/\s+-\s+SMERGERS.*$/i, '').trim();
const titleCase = (s) => s.replace(/\b[a-z]/g, (c) => c.toUpperCase());

function toCrore(amount, unit) {
  const n = parseFloat(amount);
  if (!Number.isFinite(n)) return null;
  return /lakh|lac/i.test(unit) ? n / 100 : n;
}

/**
 * Turn one search result about a franchise investor profile into a lead, or null.
 * Works on the title, the snippet and, as a fallback, the URL slug
 * (e.g. .../owner-food-beverages-real-estate-franchise-investor-in-bangalore-looking-to-invest-in-restaurants-and-bars-upto-inr-5-crore/xyz/).
 * Only public text is read; names and contact details are never guessed.
 */
export function parseInvestor({ title = '', snippet = '', link = '' }) {
  const slug = (() => { try { return decodeURIComponent(new URL(link).pathname).split('/').filter(Boolean).sort((a, b) => b.length - a.length)[0] || ''; } catch { return ''; } })()
    .replace(/-/g, ' ');
  const text = `${title} ${snippet} ${slug}`;
  const AMT = /(?:up ?to|upto|budget of|invest(?:ment)? of)?\s*(?:inr|rs\.?|₹)\s*([\d.,]+)\s*(crore|cr|lakh|lac)/i;
  const fromText = AMT.exec(`${title} ${snippet}`);
  const amt = fromText || AMT.exec(slug); // URL slugs drop decimals (1.8 becomes 18), so flag that case
  const budgetCr = amt ? toCrore(amt[1].replace(/,/g, ''), amt[2]) : null;
  const inv = /^(.*?)\s*(?:[-–|:,]\s*)?franchise investor in\s+(.+?)\s+looking to invest in\s+(.+?)\s*(?:up ?to|upto|\bfor\b|$)/i.exec(clean(title))
    || /^(.*?)\s+franchise investor in\s+(.+?)\s+looking to invest in\s+(.+?)\s+up ?to/i.exec(slug);
  if (!inv || budgetCr == null) return null;
  const profession = titleCase(inv[1].trim().replace(/^[-–|:,\s]+|[-–|:,\s]+$/g, '')) || 'Not shown';
  return {
    source: `Google search (${domainOf(link) || 'web'} investor profile)`,
    brand: titleCase(inv[3].trim()),
    name: `Name not shown (${profession})`,
    city: titleCase(inv[2].trim()),
    profession,
    budgetCr,
    sourceUrl: link,
    notes: `Public profile, up to INR ${budgetCr} crore${fromText ? '' : ' (budget read from the URL, verify)'}. Contact details appear only after connecting on the source site. ${link}`,
  };
}

/** Turn one search result about a lead-generation agency into an agency row, or null. */
export function parseAgency({ title = '', snippet = '', link = '' }) {
  const website = domainOf(link);
  if (!website) return null;
  const name = clean(title).split(/\s+[|–—-]\s+|\s*:\s+/)[0].trim() || website;
  const text = `${title} ${snippet}`.toLowerCase();
  const type = /portal|directory|listing/.test(text) ? 'Franchise portal'
    : /consult/.test(text) ? 'Franchise consultancy'
      : /lead generation|leads?\b/.test(text) ? 'Lead generation agency' : 'Marketing agency';
  const leadsOnly = /lead generation|pay[- ]per[- ]lead|exclusive leads|franchise leads/.test(text) ? 'Yes' : 'Unclear';
  const price = /(?:rs\.?|inr|₹)\s*[\d.,]+\s*(?:lakh|lac|k|crore)?/i.exec(`${title} ${snippet}`);
  return {
    type, website: `https://${website}`, leadsOnly,
    name,
    services: clean(snippet) || 'Not stated',
    pricing: price ? price[0] : 'Not public',
    sourceUrl: link,
    notes: 'Claims are from the agency\'s own site or search snippet and are unverified.',
  };
}
