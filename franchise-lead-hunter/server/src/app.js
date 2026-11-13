import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import { z } from 'zod';
import { UserDirectory, signToken, requireAuth, requireAdmin } from './auth.js';
import { LEAD_FIELDS, AGENCY_FIELDS, LEAD_STATUSES, QUALITIES } from './schema.js';
import { buildDashboard } from './dashboard.js';
import { toCsv, formatDate } from './util.js';

const AGENCY_STATUSES = ['New', 'Shortlisted', 'Contacted', 'Meeting', 'Negotiation', 'Won', 'Lost', 'Skipped'];
const str = (max) => z.string().trim().max(max);

const leadPatch = z.object({
  status: z.enum(LEAD_STATUSES), nextFollowUp: str(20), notes: str(2000), owner: str(120),
  quality: z.enum(QUALITIES), phone: str(40), email: str(120),
}).partial().strict();
const agencyPatch = z.object({
  status: z.enum(AGENCY_STATUSES), notes: str(2000), owner: str(120), phone: str(60), email: str(120), city: str(120),
}).partial().strict();
const leadCreate = z.object({
  name: str(160).min(1), brand: str(120), city: str(120), profession: str(160), budgetCr: z.number().min(0).max(1000),
  phone: str(40).optional(), email: str(120).optional(), notes: str(2000).optional(), sourceUrl: str(500).optional(),
}).strict();
const rulesPatch = z.object({
  brands: z.array(str(60)).max(20), cities: z.array(str(60)).max(30), hniMinCr: z.number().min(0).max(100),
  maxBudgetCr: z.number().min(0).max(1000), schedule: z.enum(['hourly', 'every3h', 'daily', 'off']),
  maxQueriesPerRun: z.number().int().min(1).max(50), monthlyQueryCap: z.number().int().min(0).max(100000),
}).partial().strict();

const wrap = (fn) => (req, res, next) => fn(req, res, next).catch(next);
const publicRow = ({ _row, ...rest }) => rest;

function applyFilters(items, q, fields) {
  let out = items;
  for (const f of fields) if (q[f]) out = out.filter((i) => String(i[f]) === String(q[f]));
  if (q.q) {
    const needle = String(q.q).toLowerCase();
    out = out.filter((i) => Object.values(i).some((v) => String(v).toLowerCase().includes(needle)));
  }
  return out;
}

export function createApp({ cfg, repos, hunter, users = new UserDirectory(cfg) }) {
  const app = express();
  app.disable('x-powered-by');
  app.set('trust proxy', cfg.nodeEnv === 'production' ? 1 : false);
  app.use(helmet());
  if (cfg.corsOrigins.length) app.use(cors({ origin: cfg.corsOrigins, methods: ['GET', 'POST', 'PATCH', 'PUT'] }));
  app.use(express.json({ limit: '50kb' }));
  if (cfg.nodeEnv === 'production') {
    app.use((req, res, next) => (req.secure ? next() : res.status(426).json({ error: 'https_required' })));
  }
  app.use(rateLimit({ windowMs: 60_000, limit: 240, standardHeaders: true, legacyHeaders: false }));

  app.get('/health', (_req, res) => res.json({ ok: true })); // the only unauthenticated route besides login

  // --- login: strict per-IP limit plus a per-account lockout ---
  const failures = new Map(); // email -> {n, until}
  const loginLimiter = rateLimit({ windowMs: 15 * 60_000, limit: 20, standardHeaders: true, legacyHeaders: false });
  app.post('/api/auth/login', loginLimiter, (req, res) => {
    const parsed = z.object({ email: z.string().max(200), password: z.string().max(200) }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: 'invalid_request' });
    const email = parsed.data.email.trim().toLowerCase();
    const f = failures.get(email);
    if (f && f.until > Date.now()) return res.status(429).json({ error: 'too_many_attempts' });
    const user = users.authenticate(email, parsed.data.password);
    if (!user) {
      const n = (f && Date.now() - f.at < 15 * 60_000 ? f.n : 0) + 1;
      failures.set(email, { n, at: Date.now(), until: n >= 5 ? Date.now() + 15 * 60_000 : 0 });
      console.warn(`login failed for ${email}`);
      return res.status(401).json({ error: 'invalid_credentials' });
    }
    failures.delete(email);
    console.info(`login ok for ${email}`);
    res.json({ token: signToken(cfg, user), user });
  });

  const api = express.Router();
  api.use(requireAuth(cfg, users)); // everything below needs a valid token
  app.use('/api', api);

  api.get('/auth/me', (req, res) => res.json({ user: req.user }));

  api.get('/dashboard', wrap(async (_req, res) => res.json(await buildDashboard(repos, hunter))));

  // --- leads ---
  api.get('/leads', wrap(async (req, res) => {
    const all = await repos.leads.list();
    // B2B HNI data only unless the caller explicitly asks for everything.
    const base = req.query.segment === 'all' ? all : all.filter((l) => l.segment === 'HNI B2B');
    const items = applyFilters(base, req.query, ['quality', 'status', 'city', 'owner']);
    const limit = Math.min(Number(req.query.limit) || 200, 500), offset = Number(req.query.offset) || 0;
    res.json({ total: items.length, items: items.slice(offset, offset + limit).map(publicRow) });
  }));
  api.get('/leads/:id', wrap(async (req, res) => {
    const l = await repos.leads.get(req.params.id);
    return l ? res.json(publicRow(l)) : res.status(404).json({ error: 'not_found' });
  }));
  api.patch('/leads/:id', wrap(async (req, res) => {
    const p = leadPatch.safeParse(req.body);
    if (!p.success) return res.status(400).json({ error: 'invalid_request' });
    const l = await repos.leads.patch(req.params.id, p.data);
    return l ? res.json(publicRow(l)) : res.status(404).json({ error: 'not_found' });
  }));
  api.post('/leads', wrap(async (req, res) => {
    const p = leadCreate.safeParse(req.body);
    if (!p.success) return res.status(400).json({ error: 'invalid_request' });
    const { qualityOf } = await import('./segment.js');
    const l = await repos.leads.create({
      source: `Added manually by ${req.user.email}`, phone: '', email: '', notes: '', sourceUrl: '', ...p.data,
      dateReceived: formatDate(), quality: qualityOf(p.data.budgetCr), status: 'New', nextFollowUp: '', owner: req.user.email,
    });
    res.status(201).json(publicRow(l));
  }));

  // --- agencies ---
  api.get('/agencies', wrap(async (req, res) => {
    const items = applyFilters(await repos.agencies.list(), req.query, ['status', 'leadsOnly', 'type', 'owner']);
    res.json({ total: items.length, items: items.map(publicRow) });
  }));
  api.get('/agencies/:id', wrap(async (req, res) => {
    const a = await repos.agencies.get(req.params.id);
    return a ? res.json(publicRow(a)) : res.status(404).json({ error: 'not_found' });
  }));
  api.patch('/agencies/:id', wrap(async (req, res) => {
    const p = agencyPatch.safeParse(req.body);
    if (!p.success) return res.status(400).json({ error: 'invalid_request' });
    const a = await repos.agencies.patch(req.params.id, p.data);
    return a ? res.json(publicRow(a)) : res.status(404).json({ error: 'not_found' });
  }));

  // --- hunt, runs, rules ---
  api.get('/runs', wrap(async (_req, res) => res.json({ items: (await repos.runs.list()).slice(-50).reverse().map(publicRow) })));
  api.post('/hunt/run', rateLimit({ windowMs: 60_000, limit: 3 }), wrap(async (req, res) => {
    const run = await hunter.run({ trigger: 'manual', by: req.user.email });
    res.json(run);
  }));
  api.get('/rules', wrap(async (_req, res) => res.json(await repos.rules.get())));
  api.put('/rules', requireAdmin, wrap(async (req, res) => {
    const p = rulesPatch.safeParse(req.body);
    if (!p.success) return res.status(400).json({ error: 'invalid_request' });
    res.json(await repos.rules.set(p.data));
  }));

  // --- export (Sheet stays master; this gives a copy) ---
  api.get('/export/:kind.csv', wrap(async (req, res) => {
    const kinds = { leads: [repos.leads, LEAD_FIELDS], agencies: [repos.agencies, AGENCY_FIELDS] };
    const k = kinds[req.params.kind];
    if (!k) return res.status(404).json({ error: 'not_found' });
    const rows = await k[0].list({ fresh: true });
    res.set({
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${req.params.kind}-${formatDate().replace(/ /g, '-')}.csv"`,
      'Cache-Control': 'no-store',
    });
    res.send(toCsv(rows, k[1]));
  }));

  app.use((_req, res) => res.status(404).json({ error: 'not_found' }));
  // eslint-disable-next-line no-unused-vars
  app.use((err, _req, res, _next) => {
    console.error(err);
    res.status(500).json({ error: 'server_error' }); // never leak details
  });
  return app;
}
