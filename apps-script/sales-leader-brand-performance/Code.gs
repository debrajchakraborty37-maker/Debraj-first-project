/**
 * SALES LEADER_BRAND_PERFORMANCE
 *
 * Tabs written by "Performance > Refresh data" (manual refresh only; no auto-update):
 *   Master Dashboard  : one-page view for management (KPI tiles, insights, charts, leader and brand tables, checks)
 *   Performance       : MTD (month to date) - one row per Leader x Brand (x Lead Source counted in the CRM column)
 *   FTD Performance   : the same layout for the report day only (FTD = "for the day", normally yesterday)
 *   Brand Performance : the same as Performance (MTD) with the columns swapped: Brand Name in column A, Sales Leader Name in column B,
 *                       rows grouped by brand (brand name shown once per brand)
 *
 * Sources (Master = Master PM Report v5, EBG = EBG Ad Accounts):
 *                        MTD                                   FTD
 *   Lead Target         : Master > Prep_Req column H           Master > Prep_Req column G
 *   Budget              : monthly budget x MTD days / 30       monthly budget / 30      (Master > Prep_Req column F, Settings B14)
 *   Lead Achieved: META : EBG > This Month (MTD) column G      EBG > Yesterday column G (grouped to brands through Master > Maps)
 *   META Spent          : EBG > This Month (MTD) column F      EBG > Yesterday column F
 *                         The one ad account shared by two brands (Carlton Suites 2: Acer + Realty) is split with the
 *                         Master's Manual_Spend entry for the period (MTD: columns E:G, FTD: columns B:D); the rest goes to Realty.
 *   Lead Achieved: CRM  : Facebook leads only. Lead Source = Master > CRM_Dump column F, matched row-by-row to
 *                         Master > Prep_Leads (Report Brand, Report Leader, In MTD = column I, In FTD = column J).
 *   Number of Quality Leads : those CRM leads whose Status (Master > CRM_Dump column A) is in QUALITY_STATUSES.
 *   Qualified Lead %    : (Number of Quality Leads x 100) / Lead Achieved: CRM.
 *   Checks              : Master > MTD/FTD Brand wise (target, Meta leads, spend) and MTD/FTD Leader wise (column E, CRM).
 *
 * Brand rules (kept separate, never merged):
 *   Daewoo (Aryan) = Meta account "Daewoo Appliances Affairs Studio"
 *   S.O Daewoo     = Meta account "Daewoo x ShootOrder"
 *
 * Red + bold alerts:
 *   META Spent        : red when Meta Spent is above the Budget of that leader-brand pair
 *   Lead Achieved CRM : red when the pair's CRM leads are below its Lead Target
 */
const CFG = {
  OUT_SHEET_ID: 'PASTE_THIS_SHEET_ID', // this sheet
  OUT_TAB:      'Performance',                                   // MTD tab
  FTD_TAB:      'FTD Performance',                               // FTD tab
  BRAND_TAB:    'Brand Performance',                             // MTD tab with Brand in column A and Sales Leader in column B
  DASH_TAB:     'Master Dashboard',                              // dashboard tab
  MASTER_ID:    'PASTE_MASTER_PM_REPORT_SHEET_ID',  // Master PM Report v5
  EBG_ID:       'PASTE_EBG_AD_ACCOUNTS_SHEET_ID',  // EBG Ad Accounts
  META_SOURCE:  'EBG',                       // 'EBG' = Meta leads/spend from EBG tabs | 'MASTER' = Master > MTD/FTD Brand wise
  SHARED_SPLIT: 'MANUAL',                    // shared ad account: 'MANUAL' = split with Master > Manual_Spend | 'MAPS' = whole account to its Maps brand
  CRM_SOURCES:  ['Facebook'],                // lead sources counted in the CRM column (CRM_Dump column F)
  QUALITY_STATUSES: ['Qualified', 'Details Shared', 'Meeting Scheduled', 'Meeting Conducted', 'Negotiation',
                     'Follow-Up', 'Token Received', 'Agreement Signed', 'Won'],  // CRM_Dump column A
  EXCLUDE_LEADERS: ['Unassigned'],           // leaders left out of the tables (add more names if needed)
  ALLOCATE_META: true,         // true  = split each brand's Meta leads/spend across its leaders (totals stay exact)
                               // false = repeat the full brand figure on every leader-brand pair
  ALLOCATE_BASIS: 'REQUEST',   // how to split: 'REQUEST' = share of requested leads/day
                               //               'CRM'     = share of actual CRM leads
  CRM_RED_RULE: 'TARGET',      // CRM shown red when below: 'TARGET' = Lead Target | 'META' = Meta leads
  LEADER_ONCE: true            // true = show each leader name once; false = repeat on every row
};

// The two periods share one engine. Column positions are 0-based indexes into the Master / EBG ranges.
const PERIODS = {
  MTD: { key: 'MTD', label: 'MTD', tab: CFG.OUT_TAB, ebgTab: 'This Month (MTD)', targetIdx: 7, flagIdx: 8,
         mDate: 4, mLeads: 5, mCpl: 6, brandTab: 'MTD Brand wise', leaderTab: 'MTD Leader wise', color: '#1976d2' },
  FTD: { key: 'FTD', label: 'FTD', tab: CFG.FTD_TAB, ebgTab: 'Yesterday', targetIdx: 6, flagIdx: 9,
         mDate: 1, mLeads: 2, mCpl: 3, brandTab: 'FTD Brand wise', leaderTab: 'FTD Leader wise', color: '#e65100' }
};

const SOURCES = ['Facebook', 'Whatsapp Cloud API', 'Website', 'Other'];

// Layout of the period tabs: main table = columns A:L (12 columns); the check blocks start at column N.
const NC = 12;
const SC = 14;
const INFO_ROWS = 26, KEY_ROW = 28, CHK_TITLE = 30, CHK_HEAD = 31, CHK_DATA = 32;

// Safety net so the two Daewoo brands can never be merged or mixed up.
const BRAND_FIX = {
  'daewoo':         'S.O Daewoo',      // Meta: Daewoo x ShootOrder
  'daewoo (aryan)': 'Daewoo (Aryan)'   // Meta: Daewoo Appliances Affairs Studio
};

/* ------------------------------ small helpers ------------------------------ */

const clean_ = s => String(s == null ? '' : s).trim();
const norm_ = s => clean_(s).toLowerCase();
const list_ = s => clean_(s).split(',').map(norm_).filter(Boolean);
const normStatus_ = s => clean_(s).toLowerCase().replace(/[-\s]+/g, ' ');   // "Follow-Up" = "follow up"
const p1_ = n => (Math.round(n * 10) / 10).toFixed(1);

/** Indian digit grouping, no decimals: 5486176 -> 54,86,176 */
function inr_(n) {
  const neg = n < 0;
  const s = String(Math.round(Math.abs(n)));
  let out = s.slice(-3);
  const rest = s.slice(0, -3);
  if (rest) out = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + out;
  return (neg ? '-' : '') + out;
}

function zeroSrc_() {
  return { 'Facebook': 0, 'Whatsapp Cloud API': 0, 'Website': 0, 'Other': 0 };
}

function newPair_(leader, brand) {
  return { leader, brand, target: 0, perDay: 0, monthlyBudget: 0, crm: 0, quality: 0,
           src: zeroSrc_(), qsrc: zeroSrc_() };
}

function canonSource_(v) {
  const s = norm_(v);
  if (s.indexOf('whatsapp') >= 0 || s.indexOf('whats app') >= 0) return 'Whatsapp Cloud API';  // any WhatsApp spelling
  if (s === 'facebook') return 'Facebook';
  if (s === 'website') return 'Website';
  return 'Other';
}

/** Removes any leftover auto-refresh triggers from an earlier version, so nothing runs by itself. */
function removeAutoRefresh() {
  try {
    ScriptApp.getProjectTriggers().forEach(t => {
      const f = t.getHandlerFunction();
      if (f === 'onSourceChange' || f === 'autoRefreshCheck') ScriptApp.deleteTrigger(t);
    });
    PropertiesService.getScriptProperties().deleteAllProperties();
  } catch (err) { /* ignore */ }
}

function onOpen() {
  removeAutoRefresh();
  SpreadsheetApp.getUi()
    .createMenu('Performance')
    .addItem('Refresh data', 'refreshPerformance')
    .addItem('Refresh Brand Performance (1 tab)', 'refreshBrandPerformance')
    .addItem('Refresh MTM-Trends (2 tabs)', 'refreshMtmTrends')
    .addToUi();
}

/* ------------------------------ main entry ------------------------------ */

function refreshPerformance() {
  const ctx = loadContext_();                           // Master settings, maps, requirement, CRM rows (read once)
  const out = SpreadsheetApp.openById(CFG.OUT_SHEET_ID);
  const mtd = computePeriod_(ctx, PERIODS.MTD);
  const ftd = computePeriod_(ctx, PERIODS.FTD);
  writePeriod_(out, mtd);
  writePeriod_(out, ftd);
  writePeriod_(out, brandView_(mtd));                   // Brand Performance: same data as Performance, brand first
  buildDashboard_(out, ctx, mtd, ftd);
  orderTabs_(out);
  out.toast('Refreshed: Master Dashboard, Performance (MTD, ' + mtd.rows.length + ' rows), FTD Performance (' +
            ftd.rows.length + ' rows) and Brand Performance.', 'Performance', 6);
}

/** Refreshes only the Brand Performance tab (the other tabs are not touched). */
function refreshBrandPerformance() {
  const ctx = loadContext_();
  const out = SpreadsheetApp.openById(CFG.OUT_SHEET_ID);
  const mtd = computePeriod_(ctx, PERIODS.MTD);
  writePeriod_(out, brandView_(mtd));
  orderTabs_(out);
  out.toast('Refreshed: Brand Performance (MTD, ' + mtd.rows.length + ' rows).', 'Performance', 6);
}

/**
 * Brand Performance = the MTD result of the Performance tab with the first two columns swapped
 * (A = Brand Name, B = Sales Leader Name; E:F swapped the same way), rows sorted by brand, then leader, then lead source.
 * Every number is the same as on the Performance tab, so the totals and the check blocks tie exactly.
 */
function brandView_(R) {
  const order = R.rows.map((r, i) => i).sort((a, b) => {
    const x = R.rows[a], y = R.rows[b];
    return x[1].localeCompare(y[1]) || x[0].localeCompare(y[0]) || (SOURCES.indexOf(x[6]) - SOURCES.indexOf(y[6]));
  });
  const swap = r => [r[1], r[0], r[2], r[3], r[5], r[4], r[6], r[7], r[8], r[9], r[10], r[11]];
  return Object.assign({}, R, {
    P: Object.assign({}, R.P, { tab: CFG.BRAND_TAB, color: '#00897b' }),
    rows: order.map(i => swap(R.rows[i])),
    rowInfo: order.map(i => R.rowInfo[i]),
    swap: true
  });
}

/* ------------------------------ data loading ------------------------------ */

function loadContext_() {
  const master = SpreadsheetApp.openById(CFG.MASTER_ID);
  const tz = master.getSpreadsheetTimeZone();
  const fmt = (d, f) => Utilities.formatDate(d, tz, f);

  // Settings: report date, MTD days, budget divisor, excluded/hidden brands
  const st = master.getSheetByName('Settings').getRange('A1:B52').getValues();
  const S = r => st[r - 1][1];
  const reportDate = S(6);
  const days = Number(S(11));          // "MTD target days (auto)": the Master's own day count
  const divisor = Number(S(14)) || 30; // monthly budget -> daily budget
  if (!(reportDate instanceof Date) || !(days > 0)) {
    throw new Error('Master > Settings B6 (report date) or B11 (MTD days) is not valid. Open the Master and check Settings.');
  }
  const hidden = new Set(list_(S(47)).concat(list_(S(50))));

  // Maps: Meta ad accounts -> brand, shared ad accounts
  const maps = master.getSheetByName('Maps').getRange('A5:X400').getValues();
  const acctBrand = {}, acctNames = {};
  const sharedAcc = new Set(), sharedBrands = new Set(), sharedDef = {};
  maps.forEach(r => {
    if (norm_(r[0]) === 'meta' && clean_(r[1])) {
      acctBrand[norm_(r[1])] = clean_(r[2]);
      (acctNames[norm_(r[2])] = acctNames[norm_(r[2])] || []).push(clean_(r[1]));
    }
    if (clean_(r[22])) {
      sharedAcc.add(norm_(r[22]));
      sharedDef[norm_(r[22])] = clean_(r[23]).split(',').map(clean_).filter(Boolean);   // brands sharing this ad account
      list_(r[23]).forEach(b => sharedBrands.add(b));
    }
  });

  // Prep_Req: A Report Leader, C Report Brand, E Leads/Day, F Monthly Budget, G FTD target, H MTD target, J On Brand/Leader tabs
  const prep = master.getSheetByName('Prep_Req').getRange('A2:J400').getValues();

  // CRM_Dump: A Status, F Lead Source. Prep_Leads (row-aligned): A Report Brand, B Report Leader, I In MTD, J In FTD
  const crmSheet = master.getSheetByName('CRM_Dump');
  const nRows = Math.max(crmSheet.getLastRow() - 1, 0);
  let stCol = [], srcCol = [], pl = [];
  if (nRows > 0) {
    stCol  = crmSheet.getRange(2, 1, nRows, 1).getValues();
    srcCol = crmSheet.getRange(2, 6, nRows, 1).getValues();
    pl     = master.getSheetByName('Prep_Leads').getRange(2, 1, nRows, 10).getValues();
  }

  // Manual_Spend: A brand, B FTD date, C FTD leads, D FTD CPL, E MTD date, F MTD leads, G MTD CPL
  const manualRows = master.getSheetByName('Manual_Spend').getRange('A2:G60').getValues();

  // "FTD" is normally yesterday; EBG's Yesterday / This Month tabs are built on yesterday too
  const yesterday = fmt(new Date(Date.now() - 24 * 3600 * 1000), 'yyyy-MM-dd');

  return {
    master: master, ebgBook: SpreadsheetApp.openById(CFG.EBG_ID), fmt: fmt,
    reportDate: reportDate, days: days, divisor: divisor, hidden: hidden,
    acctBrand: acctBrand, acctNames: acctNames, sharedAcc: sharedAcc, sharedBrands: sharedBrands, sharedDef: sharedDef,
    prep: prep, nRows: nRows, stCol: stCol, srcCol: srcCol, pl: pl, manualRows: manualRows,
    ydayOk: fmt(reportDate, 'yyyy-MM-dd') === yesterday,
    exLead: new Set(CFG.EXCLUDE_LEADERS.map(norm_)),
    incSrc: new Set(CFG.CRM_SOURCES.map(norm_)),
    qualSet: new Set(CFG.QUALITY_STATUSES.map(normStatus_))
  };
}

/* ------------------------------ one period (MTD or FTD) ------------------------------ */

function computePeriod_(ctx, P) {
  const clean = clean_, norm = norm_;
  const { master, fmt, reportDate, days, divisor, hidden, exLead, incSrc, qualSet } = ctx;
  const budgetMult = P.key === 'MTD' ? days / divisor : 1 / divisor;   // monthly budget -> budget for the period

  // ---- Lead target and budget per Leader x Brand: Master > Prep_Req
  const pairMap = {};
  let monthlyBudgetTotal = 0;
  ctx.prep.forEach(r => {
    const leader = clean(r[0]), brand0 = clean(r[2]);
    if (!leader || !brand0) return;
    if (exLead.has(norm(leader))) return;                   // excluded leader (e.g. Unassigned)
    if (r[9] !== '' && Number(r[9]) === 0) return;          // brand hidden on Brand/Leader tabs (e.g. Kabego)
    const brand = BRAND_FIX[norm(brand0)] || brand0;
    if (hidden.has(norm(brand))) return;
    const target = Number(r[P.targetIdx]) || 0, perDay = Number(r[4]) || 0, budget = Number(r[5]) || 0;
    if (!target && !perDay && !budget) return;
    const key = norm(leader) + '|' + norm(brand);
    if (!pairMap[key]) pairMap[key] = newPair_(leader, brand);
    pairMap[key].target        += target;
    pairMap[key].perDay        += perDay;
    pairMap[key].monthlyBudget += budget;
    monthlyBudgetTotal         += budget;
  });

  // ---- CRM leads for the period. Every lead in the period is counted per leader and source (for the check against
  //      the Master's Leader wise tab); only CRM_SOURCES of non-excluded leaders go into the table,
  //      split into "quality" (Status in QUALITY_STATUSES) and the rest.
  const leaderAll = {};
  const srcTotals = zeroSrc_();
  let allCounted = 0, leftOutSource = 0, leftOutLeader = 0;
  for (let i = 0; i < ctx.nRows; i++) {
    const row = ctx.pl[i];
    if (Number(row[P.flagIdx]) !== 1) continue;              // not in this period / not counted
    const leader = clean(row[1]), brand0 = clean(row[0]);
    if (!leader || !brand0) continue;
    const brand = BRAND_FIX[norm(brand0)] || brand0;
    if (hidden.has(norm(brand))) continue;
    const s = canonSource_(ctx.srcCol[i][0]);
    const lk = norm(leader);
    const la = leaderAll[lk] || (leaderAll[lk] = { name: leader, total: 0, src: zeroSrc_() });
    la.total++; la.src[s]++; allCounted++; srcTotals[s]++;
    if (!incSrc.has(norm(s))) { leftOutSource++; continue; }   // other lead sources are not shown
    if (exLead.has(lk)) { leftOutLeader++; continue; }         // excluded leader (e.g. Unassigned)
    const key = lk + '|' + norm(brand);
    if (!pairMap[key]) pairMap[key] = newPair_(leader, brand);
    const p = pairMap[key];
    p.src[s]++;
    p.crm++;
    if (qualSet.has(normStatus_(ctx.stCol[i][0]))) { p.qsrc[s]++; p.quality++; }
  }
  const pairs = Object.keys(pairMap).map(k => pairMap[k]);
  const crmOnlyPairs = pairs.filter(p => p.crm > 0 && !p.perDay && !p.target && !p.monthlyBudget).length;

  // ---- Master Brand wise tab: B brand, E target, R Spend, S Meta Leads, U CRM Leads (checks, MASTER source)
  const bw = master.getSheetByName(P.brandTab).getRange('A5:AB80').getValues();
  const meta = {}, metaOrder = [];
  let masterTotal = { target: 0, spend: 0, leads: 0 };
  for (const r of bw) {
    const b = clean(r[1]);
    if (!b) continue;
    if (norm(b) === 'total') { masterTotal = { target: Number(r[4]) || 0, spend: Number(r[17]) || 0, leads: Number(r[18]) || 0 }; break; }
    meta[norm(b)] = { name: b, spend: Number(r[17]) || 0, leads: Number(r[18]) || 0, crm: Number(r[20]) || 0 };
    metaOrder.push(norm(b));
  }

  // ---- EBG tab for the period: B account, F spend, G leads. Grouped to brands through Maps.
  //      The shared ad account (Acer + Realty) is split with the Master's Manual_Spend entry for the period.
  const manual = {};
  if (CFG.SHARED_SPLIT === 'MANUAL') {
    ctx.manualRows.forEach(r => {
      const b = clean(r[0]);
      const d = r[P.mDate];
      if (!b || !(d instanceof Date) || fmt(d, 'yyyy-MM-dd') !== fmt(reportDate, 'yyyy-MM-dd')) return;
      const ld = Number(r[P.mLeads]) || 0, cpl = Number(r[P.mCpl]) || 0;
      if (ld > 0) manual[norm(b)] = { leads: ld, spend: ld * cpl };
    });
  }
  const ebg = ctx.ebgBook.getSheetByName(P.ebgTab);
  const ebgBrand = {}, splitNotes = [];
  const nameOf = (bk, raw) => (meta[bk] || {}).name || raw;
  const addBrand = (bn, sp, ld) => {
    const bk = norm(bn);
    if (hidden.has(bk)) return;
    ebgBrand[bk] = ebgBrand[bk] || { name: nameOf(bk, bn), spend: 0, leads: 0 };
    ebgBrand[bk].spend += sp; ebgBrand[bk].leads += ld;
  };
  const shared = { spend: 0, leads: 0 }, other = { spend: 0, leads: 0 }, total = { spend: 0, leads: 0 };
  const otherNames = [];
  if (ebg.getLastRow() >= 4) {
    ebg.getRange(4, 2, ebg.getLastRow() - 3, 6).getValues().forEach(r => {   // B:G
      const name = clean(r[0]);
      if (!name || norm(name) === 'total') return;
      const sp = Number(r[4]) || 0, ld = Number(r[5]) || 0, k = norm(name);
      total.spend += sp; total.leads += ld;
      if (ctx.sharedAcc.has(k)) {
        shared.spend += sp; shared.leads += ld;
        const defs = ctx.sharedDef[k] || [];
        const manualBrands = defs.filter(d => manual[norm(d)]);
        if (manualBrands.length) {
          let remL = ld, remS = sp;
          manualBrands.forEach(d => {
            const m = manual[norm(d)];
            const l = Math.min(m.leads, remL), s = Math.min(m.spend, remS);
            addBrand(d, s, l); remL -= l; remS -= s;
            splitNotes.push(nameOf(norm(d), d) + ' ' + l + ' leads');
          });
          const rest = defs.filter(d => !manual[norm(d)]);
          const mainName = ctx.acctBrand[k] || '';
          const target = rest.find(d => norm(d) === norm(mainName)) || rest[0] || mainName;
          if (target) { addBrand(target, remS, remL); splitNotes.push(nameOf(norm(target), target) + ' ' + remL + ' leads'); }
        } else if (ctx.acctBrand[k]) {
          addBrand(ctx.acctBrand[k], sp, ld);
          splitNotes.push((CFG.SHARED_SPLIT === 'MAPS' ? 'whole account to ' : 'no Manual_Spend entry for the report date: all to ') + ctx.acctBrand[k]);
        }
        return;
      }
      if (!ctx.acctBrand[k]) { other.spend += sp; other.leads += ld; otherNames.push(name); return; }
      addBrand(ctx.acctBrand[k], sp, ld);
    });
  }
  Object.keys(ebgBrand).forEach(k => { if (metaOrder.indexOf(k) < 0) metaOrder.push(k); });

  // ---- Meta leads (EBG column G) and spend (EBG column F) used per brand
  const metaUsed = {};
  metaOrder.forEach(k => {
    const m = meta[k] || { name: (ebgBrand[k] || {}).name || k, spend: 0, leads: 0, crm: 0 };
    const e = ebgBrand[k] || { spend: 0, leads: 0 };
    metaUsed[k] = CFG.META_SOURCE === 'MASTER' ? { spend: m.spend, leads: m.leads } : { spend: e.spend, leads: e.leads };
  });
  const noMeta = [...new Set(pairs.filter(p => p.perDay > 0 && !metaUsed[norm(p.brand)]).map(p => p.brand))];

  // ---- Master Leader wise tab: B leader, E Leads Achieved (all sources, per leader)
  const mlw = master.getSheetByName(P.leaderTab).getRange('A5:Y80').getValues();
  const masterLeader = {};
  let masterLeaderTotal = 0;
  for (const r of mlw) {
    const nm = clean(r[1]);
    if (!nm) continue;
    if (norm(nm) === 'all leaders') { masterLeaderTotal = Number(r[4]) || 0; break; }
    if (norm(nm).indexOf('spend not linked') === 0) continue;
    masterLeader[norm(nm)] = { name: nm, leads: Number(r[4]) || 0 };
  }

  // ---- Leader x Brand rows (pair level), Meta split
  const brandReq = {}, brandCrm = {};
  pairs.forEach(p => {
    const k = norm(p.brand);
    brandReq[k] = (brandReq[k] || 0) + p.perDay;
    brandCrm[k] = (brandCrm[k] || 0) + p.crm;
  });
  const shareOf = p => {
    if (!CFG.ALLOCATE_META) return 1;
    const k = norm(p.brand);
    if (CFG.ALLOCATE_BASIS === 'CRM' && brandCrm[k]) return p.crm / brandCrm[k];
    return brandReq[k] ? p.perDay / brandReq[k] : 0;
  };
  const pairRows = pairs.map(p => {
    const m = metaUsed[norm(p.brand)] || { spend: 0, leads: 0 };
    const share = shareOf(p);
    return { leader: p.leader, brand: p.brand, target: p.target,
             budget: p.monthlyBudget * budgetMult,
             metaLeads: m.leads * share, metaSpend: m.spend * share,
             crm: p.crm, quality: p.quality, src: p.src, qsrc: p.qsrc };
  });

  // Whole-number Meta leads: round each pair's share, keeping each brand's total exact
  if (CFG.ALLOCATE_META) {
    const byBrand = {};
    pairRows.forEach(p => { (byBrand[norm(p.brand)] = byBrand[norm(p.brand)] || []).push(p); });
    Object.keys(byBrand).forEach(k => {
      const grp = byBrand[k];
      const brandTotal = Math.round(grp.reduce((t, p) => t + p.metaLeads, 0));
      const fracs = grp.map(p => p.metaLeads - Math.floor(p.metaLeads));
      grp.forEach(p => { p.metaLeads = Math.floor(p.metaLeads); });
      let left = brandTotal - grp.reduce((t, p) => t + p.metaLeads, 0);
      grp.map((p, i) => ({ p, f: fracs[i] }))
         .sort((a, b) => b.f - a.f)
         .forEach(x => { if (left > 0) { x.p.metaLeads += 1; left--; } });
    });
  }
  pairRows.sort((a, b) => a.leader.localeCompare(b.leader) || a.brand.localeCompare(b.brand));

  // ---- Expand to one row per Leader x Brand x counted Lead Source
  //      Target, Budget and Meta numbers appear once per pair (first row); CRM and Quality are exact per source.
  //      Row layout: 0 leader, 1 brand, 2 target, 3 budget, 4 leader, 5 brand, 6 source,
  //                  7 META leads, 8 CRM leads, 9 quality leads, 10 qualified lead %, 11 META spent
  const rows = [], rowInfo = [];
  pairRows.forEach(p => {
    const active = SOURCES.filter(s => p.src[s] > 0);
    (active.length ? active : ['-']).forEach((s, i) => {
      const first = i === 0;
      const crmN = s === '-' ? 0 : p.src[s];
      const qualN = s === '-' ? 0 : p.qsrc[s];
      rows.push([p.leader, p.brand,
                 first ? p.target : '', first ? p.budget : '',
                 p.leader, p.brand, s,
                 first ? p.metaLeads : '',
                 crmN,
                 qualN,
                 crmN > 0 ? qualN * 100 / crmN : '',      // Qualified Lead % = Quality x 100 / CRM
                 first ? p.metaSpend : '']);
      rowInfo.push({ first, target: p.target, budget: p.budget, meta: p.metaLeads, spend: p.metaSpend, crm: p.crm });
    });
  });
  const sum = i => rows.reduce((t, r) => t + (Number(r[i]) || 0), 0);
  const crmByBrand = {}, shownByLeader = {};
  rows.forEach(r => {
    const bk = norm(r[1]), lk = norm(r[0]);
    crmByBrand[bk] = (crmByBrand[bk] || 0) + (Number(r[8]) || 0);
    shownByLeader[lk] = (shownByLeader[lk] || 0) + (Number(r[8]) || 0);
  });
  const totals = { target: sum(2), budget: sum(3), meta: sum(7), crm: sum(8), quality: sum(9), spend: sum(11) };
  const totalQualPct = totals.crm > 0 ? totals.quality * 100 / totals.crm : '';

  // ---- Leader check: counted CRM leads vs the Master's Leader wise tab (column E)
  const leaderKeys = {};
  Object.keys(leaderAll).forEach(k => { leaderKeys[k] = leaderAll[k].name; });
  Object.keys(masterLeader).forEach(k => { if (!leaderKeys[k]) leaderKeys[k] = masterLeader[k].name; });
  const ldrKeys = Object.keys(leaderKeys).sort((a, b) => leaderKeys[a].localeCompare(leaderKeys[b]));
  let leaderDiffCount = 0;
  const ldr = ldrKeys.map(k => {
    const la = leaderAll[k] || { total: 0, src: zeroSrc_() };
    const ml = masterLeader[k];
    const diff = ml ? la.total - ml.leads : '';
    if (ml && Math.abs(diff) > 0.5) leaderDiffCount++;
    return [leaderKeys[k], ml ? ml.leads : '', la.total, diff,
            la.src['Facebook'], la.src['Website'], la.src['Whatsapp Cloud API'], la.src['Other'],
            shownByLeader[k] || 0,
            exLead.has(k) ? 'Left out of the table' : (!ml ? 'Not on Master ' + P.leaderTab : '')];
  });
  const ldrSum = i => ldr.reduce((t, r) => t + (Number(r[i]) || 0), 0);
  ldr.push(['TOTAL', masterLeaderTotal, allCounted, allCounted - masterLeaderTotal,
            ldrSum(4), ldrSum(5), ldrSum(6), ldrSum(7), ldrSum(8), '']);

  // ---- Totals check block (columns N:O of the period tab)
  const L = P.label;
  const info = [
    ['Report date', reportDate],
    [P.key === 'MTD' ? 'Days counted (MTD)' : 'Period', P.key === 'MTD' ? days : 'FTD = the report date'],
    ['Last refreshed', fmt(new Date(), 'dd-MMM-yyyy HH:mm')],
    ['Meta leads & spend source', CFG.META_SOURCE === 'MASTER' ? 'Master > ' + P.brandTab : 'EBG > ' + P.ebgTab + ': col G leads, col F spend'],
    ['TOTALS CHECK', ''],
    ['Lead target: this table', totals.target],
    ['Lead target: Master ' + P.brandTab + ' total', masterTotal.target],
    ['Meta leads: this table', totals.meta],
    ['Meta leads: Master ' + P.brandTab + ' total', masterTotal.leads],
    ['CRM leads, all sources: counted from CRM_Dump', allCounted],
    ['CRM leads, all sources: Master ' + P.leaderTab + ' (col E)', masterLeaderTotal],
    ['Meta spend: this table', totals.spend],
    ['Meta spend: Master ' + P.brandTab + ' total', masterTotal.spend],
    ['Meta spend: EBG ' + P.ebgTab + ', all accounts', total.spend],
    ['Budget (' + L + '): this table / monthly budget in Master', Math.round(totals.budget) + ' / ' + Math.round(monthlyBudgetTotal)],
    ['CRM leads: ' + CFG.CRM_SOURCES.join(', ') + ' (this table)', totals.crm],
    ['CRM leads left out: other lead sources', leftOutSource],
    ['CRM leads left out: ' + CFG.EXCLUDE_LEADERS.join(', ') + ' (counted sources)', leftOutLeader],
    ['Leader-brand pairs with CRM leads but no requirement', crmOnlyPairs],
    ['Brands with a requirement but no Meta row', noMeta.join(', ') || 'None'],
    ['EBG accounts not on Maps / excluded', otherNames.join('; ') || 'None'],
    ['Shared ad account split (Master Manual_Spend)', splitNotes.join('; ') || 'None'],
    ['Leaders where CRM count differs from Master ' + P.leaderTab, leaderDiffCount],
    ['Number of Quality Leads (this table, of the CRM leads above)', totals.quality],
    ['Qualified Lead % (Quality x 100 / CRM, this table)', totalQualPct],
    ['Report date = yesterday (EBG period matches)', ctx.ydayOk ? 'OK' : 'CHECK: report date is not yesterday']
  ];

  // ---- Per-brand check: EBG (used) vs Master vs CRM
  const chk = metaOrder.map(k => {
    const m = meta[k] || { name: (ebgBrand[k] || {}).name || k, spend: 0, leads: 0, crm: 0 };
    const u = metaUsed[k];
    const crmT = crmByBrand[k] || 0;
    return [m.name, (ctx.acctNames[k] || []).join('; '),
            u.spend, m.spend, u.spend - m.spend,
            u.leads, m.leads, u.leads - m.leads,
            crmT, m.crm, u.leads - crmT,
            (CFG.META_SOURCE !== 'MASTER' && ctx.sharedBrands.has(k)) ? 'Shared ad account: split using the Master Manual_Spend entry' : ''];
  });
  chk.push(['Shared accounts (EBG)', '', shared.spend, '', '', shared.leads, '', '', '', '', '', 'Already included in the brand rows above (split)']);
  chk.push(['Not on Maps / excluded (EBG)', otherNames.join('; '), other.spend, '', '', other.leads, '', '', '', '', '', 'Left out of the Master']);

  // ---- Check statuses for the dashboard
  const checks = [
    { label: 'Lead target ties to Master', ok: Math.abs(totals.target - masterTotal.target) <= 0.5,
      detail: inr_(totals.target) + ' vs Master ' + inr_(masterTotal.target) },
    { label: 'Meta leads (EBG) tie to Master', ok: Math.abs(totals.meta - masterTotal.leads) <= 0.5,
      detail: inr_(totals.meta) + ' vs Master ' + inr_(masterTotal.leads) },
    { label: 'Meta spend (EBG) within Rs 1,000 of Master', ok: Math.abs(totals.spend - masterTotal.spend) <= 1000,
      detail: 'Rs ' + inr_(totals.spend) + ' vs Master Rs ' + inr_(masterTotal.spend) },
    { label: 'CRM leads (all sources) tie to Master leader-wise total', ok: leaderDiffCount === 0 && Math.abs(allCounted - masterLeaderTotal) <= 0.5,
      detail: inr_(allCounted) + ' counted vs Master ' + inr_(masterLeaderTotal) + '; leaders differing: ' + leaderDiffCount },
    { label: 'Report date = yesterday (EBG period matches)', ok: ctx.ydayOk,
      detail: 'Report date ' + fmt(reportDate, 'dd-MMM-yyyy') },
    { label: 'Shared ad account split found in Manual_Spend', ok: !splitNotes.some(s => s.indexOf('no Manual_Spend') === 0),
      detail: splitNotes.join('; ') || 'None' }
  ];

  return { P: P, rows: rows, rowInfo: rowInfo, pairRows: pairRows, totals: totals, totalQualPct: totalQualPct,
           info: info, chk: chk, ldr: ldr, checks: checks, srcTotals: srcTotals, allCounted: allCounted,
           masterTotal: masterTotal, days: days, reportDate: reportDate };
}

/* ------------------------------ period tab (Performance / FTD Performance) ------------------------------ */

function writePeriod_(out, R) {
  const P = R.P, rows = R.rows, norm = norm_;
  const sh = out.getSheetByName(P.tab) || out.insertSheet(P.tab);
  sh.clear();   // clears old values, formats and borders so each refresh starts clean
  const L = P.label;

  const lead = R.swap ? ['Brand Name', 'Sales Leader Name'] : ['Sales Leader Name', 'Brand Name'];   // Brand Performance: brand first
  const header = [lead[0], lead[1], 'Lead Target (' + L + ')', 'Budget (' + L + ')',
                  lead[0], lead[1], 'Lead Source',
                  'Lead Achieved: META (' + L + ')', 'Lead Achieved: CRM (' + L + ')', 'Number of Quality Leads',
                  'Qualified Lead %', 'META Spent (' + L + ')'];
  const n = rows.length;
  sh.getRange(1, 1, 1, NC).setValues([header]).setFontWeight('bold').setBackground('#e8eaed');

  const shown = rows.map((r, i) => {
    const first = !CFG.LEADER_ONCE || i === 0 || norm(r[0]) !== norm(rows[i - 1][0]);
    const x = r.slice();
    if (!first) { x[0] = ''; x[4] = ''; }
    return x;
  });
  if (n) sh.getRange(2, 1, n, NC).setValues(shown);

  const T = R.totals;
  sh.getRange(n + 2, 1, 1, NC)
    .setValues([['TOTAL', '', T.target, T.budget, '', '', '', T.meta, T.crm, T.quality, R.totalQualPct, T.spend]])
    .setFontWeight('bold').setBackground('#f1f3f4');
  sh.getRange(2, 3, n + 1, 2).setNumberFormat('#,##0');
  sh.getRange(2, 8, n + 1, 3).setNumberFormat('#,##0');
  sh.getRange(2, 11, n + 1, 1).setNumberFormat('0.0"%"');       // value is already x100
  sh.getRange(2, 12, n + 1, 1).setNumberFormat('#,##0.00');
  sh.setFrozenRows(1);

  // Totals check block (N:O)
  sh.getRange(1, SC, R.info.length, 2).setValues(R.info);
  sh.getRange(1, SC + 1).setNumberFormat('dd-mmm-yyyy');
  sh.getRange(6, SC + 1, 9, 1).setNumberFormat('#,##0');
  sh.getRange(16, SC + 1, 4, 1).setNumberFormat('#,##0');
  sh.getRange(23, SC + 1, 2, 1).setNumberFormat('#,##0');
  sh.getRange(25, SC + 1, 1, 1).setNumberFormat('0.0"%"');

  // Per-brand check (N30 onward)
  const chkHead = ['Brand', 'Meta ad account(s)',
                   'Spend: used (EBG)', 'Spend: Master', 'Spend diff',
                   'Meta leads: used (EBG)', 'Meta leads: Master', 'Meta leads diff',
                   'CRM leads: Facebook (this table)', 'CRM leads: all sources (Master brand tab)', 'Meta minus CRM', 'Note'];
  sh.getRange(CHK_TITLE, SC).setValue('PER-BRAND CHECK: EBG (used) vs Master vs CRM. Small spend gaps are sync timing. Meta minus CRM = Meta leads (all sources) minus CRM Facebook leads.');
  sh.getRange(CHK_HEAD, SC, 1, 12).setValues([chkHead]);
  sh.getRange(CHK_DATA, SC, R.chk.length, 12).setValues(R.chk);
  sh.getRange(CHK_DATA, SC + 2, R.chk.length, 9).setNumberFormat('#,##0');

  // Leader check
  const ldrTitle = CHK_DATA + R.chk.length + 1, ldrHead = ldrTitle + 1, ldrData = ldrHead + 1;
  sh.getRange(ldrTitle, SC).setValue('LEADER CHECK: CRM leads counted from CRM_Dump (all sources) vs Master ' + P.leaderTab + ' column E. Only Facebook is shown in the table.');
  sh.getRange(ldrHead, SC, 1, 10).setValues([['Leader', 'Master ' + P.leaderTab + ' (col E)', 'Counted (all sources)', 'Diff',
                                              'Facebook', 'Website', 'Whatsapp Cloud API', 'Other', 'Shown in table (Facebook)', 'Note']]);
  sh.getRange(ldrData, SC, R.ldr.length, 10).setValues(R.ldr);
  sh.getRange(ldrData, SC + 1, R.ldr.length, 8).setNumberFormat('#,##0');

  sh.autoResizeColumns(1, SC + 11);
  applyStyle_(sh, R, {
    chkCount: R.chk.length, ldrTitle: ldrTitle, ldrHead: ldrHead, ldrData: ldrData, ldrCount: R.ldr.length
  });
}

/** Colourful formatting for a period tab. Called at the end of every write. */
function applyStyle_(sh, R, lay) {
  const P = R.P, rows = R.rows, rowInfo = R.rowInfo;
  const n = rows.length;
  const norm = norm_;
  const SOLID = SpreadsheetApp.BorderStyle.SOLID;
  const lastRow = sh.getLastRow();
  const RED = '#d50000';
  const isNum = x => typeof x === 'number';

  sh.setHiddenGridlines(true);
  sh.setTabColor(P.color);
  sh.getRange(1, 1, lastRow, SC + 11).setFontFamily('Roboto').setFontSize(10).setVerticalAlignment('middle');

  // Column widths and row heights
  [150, 190, 120, 120, 150, 190, 170, 150, 150, 150, 130, 150, 30, 300, 260].forEach((w, i) => sh.setColumnWidth(i + 1, w));
  sh.setColumnWidths(SC + 2, 9, 150);   // P:X
  sh.setColumnWidth(SC + 11, 340);      // Y
  sh.setRowHeight(1, 42);
  if (n) sh.setRowHeights(2, n + 1, 26);

  // Colour-coded header blocks
  [['A1:B1', '#0d47a1'], ['C1:D1', '#1976d2'], ['E1:F1', '#00695c'], ['G1', '#455a64'],
   ['H1', '#ef6c00'], ['I1', '#2e7d32'], ['J1', '#0097a7'], ['K1', '#26a69a'], ['L1', '#6a1b9a']].forEach(([a, c]) =>
    sh.getRange(a).setBackground(c).setFontColor('#ffffff').setFontWeight('bold')
      .setFontSize(11).setHorizontalAlignment('center').setWrap(true));

  // One soft colour band per sales leader
  const bands = ['#e3f2fd', '#fff8e1', '#e8f5e9', '#f3e5f5', '#fce4ec', '#e0f7fa'];
  const groups = [];
  rows.forEach((r, i) => {
    if (i === 0 || norm(r[0]) !== norm(rows[i - 1][0])) {
      groups.push({ start: i, end: i, color: bands[groups.length % bands.length] });
    } else {
      groups[groups.length - 1].end = i;
    }
  });
  groups.forEach(gr => sh.getRange(gr.start + 2, 1, gr.end - gr.start + 1, NC).setBackground(gr.color));

  if (n) {
    sh.getRange(2, 1, n, NC).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
    sh.getRange(2, 1, n, 1).setFontWeight('bold').setFontSize(11).setFontColor('#0d47a1');
    sh.getRange(2, 5, n, 1).setFontWeight('bold').setFontSize(11).setFontColor('#00695c');
    sh.getRange(2, 3, n, 2).setHorizontalAlignment('right');
    sh.getRange(2, 8, n, 5).setHorizontalAlignment('right');

    // Lead Source colours
    const srcColor = { 'Facebook': '#1565c0', 'Whatsapp Cloud API': '#2e7d32', 'Website': '#6a1b9a', 'Other': '#757575', '-': '#9e9e9e' };
    sh.getRange(2, 7, n, 1).setFontColors(rows.map(r => [srcColor[r[6]] || '#37474f']))
      .setFontWeight('bold').setHorizontalAlignment('center');

    // META achieved: green = at/above target, orange = 50-99%, red = below 50% (judged on the pair's first row)
    // CRM achieved: bold red when the pair's CRM leads are below its target (or below Meta, if CRM_RED_RULE = 'META')
    const pick = (t, v) => !t ? '#37474f' : (v >= t ? '#1b5e20' : (v >= 0.5 * t ? '#e65100' : '#b71c1c'));
    const crmLess = d => {
      const ref = CFG.CRM_RED_RULE === 'META' ? d.meta : d.target;
      return ref > 0 && d.crm < ref;
    };
    const colors = rows.map((r, i) => {
      const d = rowInfo[i];
      const crmRef = CFG.CRM_RED_RULE === 'META' ? d.meta : d.target;
      return [d.first ? pick(d.target, d.meta) : '#37474f',
              !crmRef ? '#37474f' : (crmLess(d) ? RED : '#1b5e20')];
    });
    sh.getRange(2, 8, n, 2).setFontColors(colors).setFontWeight('bold');

    // Number of Quality Leads and Qualified Lead %
    sh.getRange(2, 10, n, 1).setFontColor('#006064').setFontWeight('bold');
    sh.getRange(2, 11, n, 1).setFontColor('#00695c').setFontWeight('bold');

    // META Spent: bold red when spend is above the Budget of the pair
    const over = d => d.first && d.spend > d.budget + 0.5;
    sh.getRange(2, 12, n, 1)
      .setFontColors(rowInfo.map(d => [over(d) ? RED : '#37474f']))
      .setFontWeights(rowInfo.map(d => [over(d) ? 'bold' : 'normal']));

    // Stronger line above each new leader group
    groups.forEach(gr => sh.getRange(gr.start + 2, 1, 1, NC)
      .setBorder(true, null, null, null, null, null, '#546e7a', SpreadsheetApp.BorderStyle.SOLID_MEDIUM));
  }

  // TOTAL row (light red on the dark band so alerts stay visible)
  const tr = n + 2, T = R.totals;
  sh.getRange(tr, 1, 1, NC).setBackground('#0d47a1').setFontColor('#ffffff').setFontWeight('bold').setFontSize(11);
  sh.getRange(tr, 3, 1, 2).setHorizontalAlignment('right');
  sh.getRange(tr, 8, 1, 5).setHorizontalAlignment('right');
  const totRef = CFG.CRM_RED_RULE === 'META' ? T.meta : T.target;
  if (totRef > 0 && T.crm < totRef) sh.getRange(tr, 9).setFontColor('#ff8a80');
  if (T.spend > T.budget + 0.5) sh.getRange(tr, 12).setFontColor('#ff8a80');

  // Totals check block (N:O), rows 1-26
  sh.getRange(1, SC, 4, 2).setBackground('#eceff1');
  sh.getRange(1, SC, 4, 1).setFontWeight('bold');
  sh.getRange(1, SC + 1, INFO_ROWS, 1).setHorizontalAlignment('right');
  sh.getRange(5, SC, 1, 2).setBackground('#006064').setFontColor('#ffffff').setFontWeight('bold');
  for (let r = 6; r <= INFO_ROWS; r++) sh.getRange(r, SC, 1, 2).setBackground(r % 2 ? '#f5f5f5' : '#ffffff');
  sh.getRange(1, SC, INFO_ROWS, 2).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
  const iv = sh.getRange(6, SC + 1, 8, 1).getValues();   // this table vs Master, in pairs
  const tol = [0.5, 0.5, 0.5, 1000];                      // the spend pair allows for EBG vs Master sync timing
  [[0, 1], [2, 3], [4, 5], [6, 7]].forEach(([a, b], idx) => {
    const ok = Math.abs(Number(iv[a][0]) - Number(iv[b][0])) <= tol[idx];
    sh.getRange(6 + a, SC, 2, 2).setBackground(ok ? '#c8e6c9' : '#ffcdd2');
  });
  const gd = Number(sh.getRange(23, SC + 1).getValue());
  sh.getRange(23, SC, 1, 2).setBackground(gd === 0 ? '#c8e6c9' : '#ffcdd2');
  sh.getRange(INFO_ROWS, SC, 1, 2).setBackground(R.info[INFO_ROWS - 1][1] === 'OK' ? '#c8e6c9' : '#ffcdd2');
  sh.getRange(KEY_ROW, SC)
    .setValue('Colour key: CRM leads in bold red = below target; Meta Spent in bold red = over Budget; Lead Achieved META: green = at/above target, orange = 50-99%, red = below 50%. Qualified Lead % = Number of Quality Leads x 100 / CRM leads. Target, Budget and Meta show once per leader-brand pair.')
    .setFontStyle('italic').setFontColor('#546e7a');

  // Per-brand check block
  sh.getRange(CHK_TITLE, SC, 1, 12).setBackground('#006064').setFontColor('#ffffff').setFontWeight('bold').setFontSize(11);
  sh.getRange(CHK_HEAD, SC, 1, 12).setBackground('#00838f').setFontColor('#ffffff').setFontWeight('bold').setHorizontalAlignment('center');
  if (lay.chkCount > 0) {
    const vals = sh.getRange(CHK_DATA, SC, lay.chkCount, 12).getValues();
    vals.forEach((r, i) => {
      const row = CHK_DATA + i;
      sh.getRange(row, SC, 1, 12).setBackground(i % 2 ? '#ffffff' : '#f1f8f9')
        .setBorder(true, true, true, true, false, false, '#cfd8dc', SOLID);
      sh.getRange(row, SC + 2, 1, 9).setHorizontalAlignment('right');
      sh.getRange(row, SC + 11).setFontStyle('italic').setFontColor('#78909c');
      const paint = (col, ok) => sh.getRange(row, col)
        .setBackground(ok ? '#c8e6c9' : '#ffcdd2').setFontWeight('bold');
      if (isNum(r[4])) paint(SC + 4, Math.abs(r[4]) <= 1000);   // spend diff (EBG used - Master)
      if (isNum(r[7])) paint(SC + 7, Math.abs(r[7]) <= 0.5);    // Meta leads diff (EBG used - Master)
      if (isNum(r[10])) {                                        // Meta leads minus CRM Facebook leads
        const m = r[5];
        sh.getRange(row, SC + 10)
          .setBackground(m > 0 && Math.abs(r[10]) / m > 0.1 ? '#ffe0b2' : '#c8e6c9').setFontWeight('bold');
      }
    });
  }

  // Leader check block
  sh.getRange(lay.ldrTitle, SC, 1, 10).setBackground('#004d40').setFontColor('#ffffff').setFontWeight('bold').setFontSize(11);
  sh.getRange(lay.ldrHead, SC, 1, 10).setBackground('#00695c').setFontColor('#ffffff').setFontWeight('bold')
    .setHorizontalAlignment('center').setWrap(true);
  if (lay.ldrCount > 0) {
    const lv = sh.getRange(lay.ldrData, SC, lay.ldrCount, 10).getValues();
    lv.forEach((r, i) => {
      const row = lay.ldrData + i;
      const isTotal = String(r[0]).toUpperCase() === 'TOTAL';
      sh.getRange(row, SC, 1, 10).setBackground(isTotal ? '#b2dfdb' : (i % 2 ? '#ffffff' : '#f1f8f9'))
        .setBorder(true, true, true, true, false, false, '#cfd8dc', SOLID);
      sh.getRange(row, SC + 1, 1, 8).setHorizontalAlignment('right');
      sh.getRange(row, SC + 9).setFontStyle('italic').setFontColor('#78909c');
      sh.getRange(row, SC + 8).setFontWeight('bold');
      if (isTotal) sh.getRange(row, SC, 1, 10).setFontWeight('bold');
      if (isNum(r[3])) sh.getRange(row, SC + 3).setBackground(Math.abs(r[3]) <= 0.5 ? '#c8e6c9' : '#ffcdd2').setFontWeight('bold');
    });
  }
}

/* ------------------------------ Master Dashboard ------------------------------ */

/** Sum pair rows by leader or brand and add the derived measures. */
function aggregate_(pairRows, key) {
  const m = {};
  pairRows.forEach(p => {
    const k = norm_(p[key]);
    const a = m[k] || (m[k] = { name: p[key], target: 0, meta: 0, crm: 0, quality: 0, spend: 0, budget: 0 });
    a.target += p.target; a.meta += p.metaLeads; a.crm += p.crm;
    a.quality += p.quality; a.spend += p.metaSpend; a.budget += p.budget;
  });
  return Object.keys(m).map(k => derive_(m[k]));
}

function derive_(a) {
  a.ach     = a.target > 0 ? a.crm * 100 / a.target : null;        // CRM achievement %
  a.metaAch = a.target > 0 ? a.meta * 100 / a.target : null;       // Meta achievement %
  a.qpct    = a.crm > 0 ? a.quality * 100 / a.crm : null;          // Qualified lead %
  a.spPct   = a.budget > 0 ? a.spend * 100 / a.budget : null;      // spend as % of budget
  a.cpl     = a.meta > 0 ? a.spend / a.meta : null;                // cost per Meta lead
  a.cpql    = a.quality > 0 ? a.spend / a.quality : null;          // cost per quality lead
  a.sync    = a.meta > 0 ? a.crm * 100 / a.meta : null;            // CRM leads as % of Meta leads
  a.over    = a.spend > a.budget + 0.5;                            // spend above budget
  return a;
}

function statusOf_(a) {
  const parts = [];
  if (a.target > 0) parts.push(a.crm >= a.target ? 'On target' : (a.crm >= 0.5 * a.target ? 'Behind target' : 'Critical'));
  else parts.push('No target');
  if (a.over && (a.budget > 0 || a.spend > 0)) parts.push('Over budget');
  return parts.join(' | ');
}

function sevColor_(status) {
  if (status.indexOf('Critical') >= 0 || status.indexOf('Over budget') >= 0) return '#b71c1c';
  if (status.indexOf('Behind') >= 0) return '#e65100';
  if (status.indexOf('On target') >= 0) return '#1b5e20';
  return '#546e7a';
}

function sortAgg_(aggs) {
  return aggs.slice().sort((a, b) => {
    const x = a.ach == null ? -1 : a.ach, y = b.ach == null ? -1 : b.ach;
    return (y - x) || (b.crm - a.crm) || a.name.localeCompare(b.name);
  });
}

function buildDashboard_(out, ctx, mtd, ftd) {
  const NCOL = 16;                       // dashboard grid: 16 columns x 110 px
  const SOLID = SpreadsheetApp.BorderStyle.SOLID;
  const fmtD = d => ctx.fmt(d, 'dd-MMM-yyyy');
  const sh = out.getSheetByName(CFG.DASH_TAB) || out.insertSheet(CFG.DASH_TAB);
  sh.getCharts().forEach(c => sh.removeChart(c));
  sh.getRange(1, 1, sh.getMaxRows(), sh.getMaxColumns()).breakApart();
  sh.clear();
  sh.setRowHeights(1, sh.getMaxRows(), 21);
  sh.setHiddenGridlines(true);
  sh.setTabColor('#0d47a1');
  sh.setColumnWidths(1, NCOL, 110);
  sh.getRange(1, 1, 400, NCOL).setFontFamily('Roboto').setFontSize(10).setVerticalAlignment('middle').setBackground('#ffffff');

  const band = (row, text, bg, fg, size, height) => {
    const rg = sh.getRange(row, 1, 1, NCOL).merge();
    rg.setValue(text).setBackground(bg).setFontColor(fg).setFontWeight('bold').setFontSize(size)
      .setHorizontalAlignment('left').setVerticalAlignment('middle');
    sh.setRowHeight(row, height);
    return rg;
  };

  // ---- Title
  band(1, '  SALES LEADER & BRAND PERFORMANCE  |  MASTER DASHBOARD', '#0d47a1', '#ffffff', 22, 48);
  const sub = '  Report date: ' + fmtD(ctx.reportDate) + '   |   MTD: 1st to ' + ctx.fmt(ctx.reportDate, 'd MMM') + ' (' + ctx.days +
              ' days)   |   FTD: ' + fmtD(ctx.reportDate) + '   |   Refreshed: ' + ctx.fmt(new Date(), 'dd-MMM-yyyy HH:mm') +
              '   |   CRM = Facebook leads only   |   Meta = EBG Ad Accounts (all lead sources)';
  band(2, sub, '#1565c0', '#e3f2fd', 10, 26);
  sh.setRowHeight(3, 10);

  // ---- KPI tiles
  const kpis = (T, firstSub) => {
    const ach = T.target > 0 ? T.crm * 100 / T.target : null;
    const metaAch = T.target > 0 ? T.meta * 100 / T.target : null;
    const qp = T.crm > 0 ? T.quality * 100 / T.crm : null;
    const sp = T.budget > 0 ? T.spend * 100 / T.budget : null;
    const cpl = T.meta > 0 ? T.spend / T.meta : null;
    const cpql = T.quality > 0 ? T.spend / T.quality : null;
    const diff = T.spend - T.budget;
    return [
      { l: 'LEAD TARGET', v: T.target, f: '#,##0', s: firstSub, bg: '#1976d2', c: '#0d47a1' },
      { l: 'META LEADS (EBG)', v: T.meta, f: '#,##0', s: 'CPL: ' + (cpl == null ? '-' : 'Rs ' + inr_(cpl)) +
          '  |  Meta ach: ' + (metaAch == null ? '-' : p1_(metaAch) + '%'), bg: '#ef6c00', c: '#bf360c' },
      { l: 'CRM LEADS (FACEBOOK)', v: T.crm, f: '#,##0', s: 'CRM = ' + (T.meta > 0 ? p1_(T.crm * 100 / T.meta) + '% of Meta leads' : '-'), bg: '#2e7d32', c: '#1b5e20' },
      { l: 'CRM ACHIEVEMENT %', v: ach == null ? '' : ach, f: '0.0"%"', s: 'CRM leads / Lead Target',
        bg: '#00695c', c: ach == null ? '#37474f' : (ach >= 100 ? '#1b5e20' : (ach >= 50 ? '#e65100' : '#b71c1c')) },
      { l: 'QUALITY LEADS', v: T.quality, f: '#,##0', s: 'CPQL: ' + (cpql == null ? '-' : 'Rs ' + inr_(cpql)), bg: '#0097a7', c: '#006064' },
      { l: 'QUALIFIED LEAD %', v: qp == null ? '' : qp, f: '0.0"%"', s: 'Quality x 100 / CRM leads', bg: '#26a69a', c: '#00695c' },
      { l: 'META SPENT (Rs)', v: T.spend, f: '#,##0', s: 'Budget: Rs ' + inr_(T.budget), bg: '#6a1b9a', c: '#4a148c' },
      { l: 'SPEND % OF BUDGET', v: sp == null ? '' : sp, f: '0.0"%"', s: diff > 0 ? 'Over budget by Rs ' + inr_(diff) : 'Under budget by Rs ' + inr_(-diff),
        bg: '#8e24aa', c: sp == null ? '#37474f' : (sp > 100 ? '#b71c1c' : '#1b5e20') }
    ];
  };
  const tiles = (row, T, firstSub) => {
    kpis(T, firstSub).forEach((k, i) => {
      const c = 1 + i * 2;
      sh.getRange(row, c, 1, 2).merge().setValue(k.l).setBackground(k.bg).setFontColor('#ffffff')
        .setFontWeight('bold').setFontSize(9).setHorizontalAlignment('center');
      sh.getRange(row + 1, c, 1, 2).merge().setValue(k.v === '' ? '-' : k.v).setNumberFormat(k.f).setBackground('#fafafa')
        .setFontSize(22).setFontWeight('bold').setFontColor(k.c).setHorizontalAlignment('center');
      sh.getRange(row + 2, c, 1, 2).merge().setValue(k.s).setBackground('#fafafa')
        .setFontSize(9).setFontColor('#546e7a').setHorizontalAlignment('center');
      sh.getRange(row, c, 3, 2).setBorder(true, true, true, true, false, false, '#cfd8dc', SOLID);
    });
    sh.setRowHeight(row, 24); sh.setRowHeight(row + 1, 46); sh.setRowHeight(row + 2, 24);
  };
  band(4, '  MONTH TO DATE (MTD)  -  1st to ' + ctx.fmt(ctx.reportDate, 'd MMM'), '#e3f2fd', '#0d47a1', 12, 28);
  tiles(5, mtd.totals, 'Days counted: ' + ctx.days);
  sh.setRowHeight(8, 10);
  band(9, '  FOR THE DAY (FTD)  -  ' + fmtD(ctx.reportDate), '#fff3e0', '#e65100', 12, 28);
  tiles(10, ftd.totals, 'Report day');
  sh.setRowHeight(13, 10);

  // ---- Aggregates and tables data
  const mL = sortAgg_(aggregate_(mtd.pairRows, 'leader')), mB = sortAgg_(aggregate_(mtd.pairRows, 'brand'));
  const fL = sortAgg_(aggregate_(ftd.pairRows, 'leader')), fB = sortAgg_(aggregate_(ftd.pairRows, 'brand'));
  const totalAgg = T => derive_({ name: 'TOTAL', target: T.target, meta: T.meta, crm: T.crm, quality: T.quality, spend: T.spend, budget: T.budget });

  // ---- Key insights
  const insights = buildInsights_(mtd, ftd, mL, mB, fL, fB, ctx);
  band(14, '  KEY INSIGHTS AT A GLANCE', '#fff8e1', '#e65100', 12, 28);
  const INSIGHT_ROWS = 11;
  insights.slice(0, INSIGHT_ROWS).forEach((it, i) => {
    const rg = sh.getRange(15 + i, 1, 1, NCOL).merge();
    rg.setValue('  ' + it.t).setFontColor(it.c).setFontSize(10).setWrap(true).setHorizontalAlignment('left')
      .setBackground(i % 2 ? '#ffffff' : '#fafafa');
    sh.setRowHeight(15 + i, 30);
  });
  sh.setRowHeight(15 + INSIGHT_ROWS, 10);

  // ---- Charts section header (charts are placed after the tables are written)
  const CH_TOP = 27;
  band(CH_TOP, '  CHARTS', '#e8eaf6', '#283593', 12, 28);
  const CH1 = CH_TOP + 1, CH2 = CH1 + 19, CH3 = CH2 + 19;        // 19 rows x 21 px = 399 px per chart row
  const TABLES_TOP = CH3 + 19 + 1;

  // ---- Tables
  const hdrCells = ['', '', 'Lead Target', 'Meta Leads', 'CRM Leads', 'CRM Ach %', 'Quality Leads', 'Qualified %',
                    'Meta Spent (Rs)', 'Budget (Rs)', 'Spend % of Budget', 'CPL (Rs)', 'CPQL (Rs)', 'CRM / Meta %', 'Status', 'Rank'];
  const table = (startRow, title, bg, entity, aggs, tot) => {
    band(startRow, '  ' + title, bg, '#ffffff', 12, 30);
    const hdrRow = startRow + 1;
    const hdr = hdrCells.slice(); hdr[0] = entity;
    sh.getRange(hdrRow, 1, 1, NCOL).setValues([hdr]).setBackground('#37474f').setFontColor('#ffffff')
      .setFontWeight('bold').setHorizontalAlignment('center').setWrap(true);
    sh.getRange(hdrRow, 1).setHorizontalAlignment('left');
    sh.setRowHeight(hdrRow, 38);
    const toRow = (a, rank) => {
      const st = statusOf_(a);
      return [a.name, '', a.target, a.meta, a.crm, a.ach == null ? '' : a.ach, a.quality, a.qpct == null ? '' : a.qpct,
              a.spend, a.budget, a.spPct == null ? '' : a.spPct, a.cpl == null ? '' : a.cpl, a.cpql == null ? '' : a.cpql,
              a.sync == null ? '' : a.sync, st, rank];
    };
    const n = aggs.length;
    const first = hdrRow + 1;
    if (n) {
      const data = aggs.map((a, i) => toRow(a, a.ach == null ? '' : i + 1));
      sh.getRange(first, 1, n, NCOL).setValues(data);
      sh.getRange(first, 1, n, NCOL).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
      sh.getRange(first, 1, n, 1).setFontWeight('bold').setFontColor('#0d47a1');
      sh.getRange(first, 3, n, 1).setFontColor('#37474f');
      sh.getRange(first, 6, n, 1).setFontColors(aggs.map(a => [a.ach == null ? '#37474f' : (a.ach >= 100 ? '#1b5e20' : (a.ach >= 50 ? '#e65100' : '#b71c1c'))])).setFontWeight('bold');
      sh.getRange(first, 8, n, 1).setFontColor('#00695c').setFontWeight('bold');
      sh.getRange(first, 11, n, 1).setFontColors(aggs.map(a => [a.spPct != null && a.spPct > 100 ? '#b71c1c' : '#1b5e20'])).setFontWeight('bold');
      sh.getRange(first, 15, n, 1).setFontColors(aggs.map(a => [sevColor_(statusOf_(a))])).setFontWeight('bold');
      for (let i = 0; i < n; i++) if (i % 2) sh.getRange(first + i, 1, 1, NCOL).setBackground('#f5f9ff');
    }
    const totalRow = first + n;
    const tr = toRow(tot, '');
    sh.getRange(totalRow, 1, 1, NCOL).setValues([tr]).setBackground('#cfd8dc').setFontWeight('bold').setFontColor('#263238');
    sh.getRange(totalRow, 1, 1, NCOL).setBorder(true, true, true, true, true, true, '#90a4ae', SOLID);
    const r0 = first, cnt = n + 1;
    sh.getRange(r0, 3, cnt, 3).setNumberFormat('#,##0').setHorizontalAlignment('right');
    sh.getRange(r0, 6, cnt, 1).setNumberFormat('0.0"%"').setHorizontalAlignment('right');
    sh.getRange(r0, 7, cnt, 1).setNumberFormat('#,##0').setHorizontalAlignment('right');
    sh.getRange(r0, 8, cnt, 1).setNumberFormat('0.0"%"').setHorizontalAlignment('right');
    sh.getRange(r0, 9, cnt, 2).setNumberFormat('#,##0').setHorizontalAlignment('right');
    sh.getRange(r0, 11, cnt, 1).setNumberFormat('0.0"%"').setHorizontalAlignment('right');
    sh.getRange(r0, 12, cnt, 2).setNumberFormat('#,##0').setHorizontalAlignment('right');
    sh.getRange(r0, 14, cnt, 1).setNumberFormat('0.0"%"').setHorizontalAlignment('right');
    sh.getRange(r0, 15, cnt, 2).setHorizontalAlignment('center');
    sh.setRowHeights(first, n + 1, 24);
    return { hdrRow: hdrRow, first: first, n: n, totalRow: totalRow, next: totalRow + 2 };
  };
  const t1 = table(TABLES_TOP, 'MTD  |  LEADER-WISE PERFORMANCE', '#0d47a1', 'Sales Leader', mL, totalAgg(mtd.totals));
  const t2 = table(t1.next, 'MTD  |  BRAND-WISE PERFORMANCE', '#00695c', 'Brand', mB, totalAgg(mtd.totals));
  const t3 = table(t2.next, 'FTD (' + fmtD(ctx.reportDate) + ')  |  LEADER-WISE PERFORMANCE', '#e65100', 'Sales Leader', fL, totalAgg(ftd.totals));
  const t4 = table(t3.next, 'FTD (' + fmtD(ctx.reportDate) + ')  |  BRAND-WISE PERFORMANCE', '#6a1b9a', 'Brand', fB, totalAgg(ftd.totals));

  // ---- Data quality and lead source mix
  let r = t4.next;
  band(r, '  DATA QUALITY & SYNC CHECKS', '#37474f', '#ffffff', 12, 30);
  const chkHdr = r + 1;
  sh.getRange(chkHdr, 1, 1, NCOL).setValues([['Check', '', '', '', '', 'MTD', 'FTD', 'Detail (MTD)', '', '', '', '', '', '', '', '']])
    .setBackground('#546e7a').setFontColor('#ffffff').setFontWeight('bold');
  sh.getRange(chkHdr, 6, 1, 2).setHorizontalAlignment('center');
  let failed = 0;
  mtd.checks.forEach((c, i) => {
    const f = ftd.checks[i];
    const row = chkHdr + 1 + i;
    sh.getRange(row, 1, 1, NCOL).setValues([[c.label, '', '', '', '', c.ok ? 'OK' : 'CHECK', f.ok ? 'OK' : 'CHECK', c.detail, '', '', '', '', '', '', '', '']])
      .setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
    sh.getRange(row, 6, 1, 2).setHorizontalAlignment('center').setFontWeight('bold');
    sh.getRange(row, 6).setBackground(c.ok ? '#c8e6c9' : '#ffcdd2').setFontColor(c.ok ? '#1b5e20' : '#b71c1c');
    sh.getRange(row, 7).setBackground(f.ok ? '#c8e6c9' : '#ffcdd2').setFontColor(f.ok ? '#1b5e20' : '#b71c1c');
    sh.getRange(row, 8).setFontColor('#546e7a');
    if (!c.ok) failed++;
    if (!f.ok) failed++;
  });
  r = chkHdr + mtd.checks.length + 2;
  band(r, '  LEAD SOURCE MIX  -  all CRM leads (MTD), before the Facebook-only filter', '#455a64', '#ffffff', 12, 30);
  const mixHdr = r + 1;
  sh.getRange(mixHdr, 1, 1, NCOL).setValues([['Lead Source', '', 'CRM Leads', 'Share %', '', '', '', '', '', '', '', '', '', '', '', '']])
    .setBackground('#546e7a').setFontColor('#ffffff').setFontWeight('bold');
  const mixTotal = mtd.allCounted || 1;
  SOURCES.forEach((s, i) => {
    const row = mixHdr + 1 + i;
    sh.getRange(row, 1, 1, 4).setValues([[s, '', mtd.srcTotals[s], mtd.srcTotals[s] * 100 / mixTotal]])
      .setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
    sh.getRange(row, 3).setNumberFormat('#,##0');
    sh.getRange(row, 4).setNumberFormat('0.0"%"');
  });
  sh.getRange(mixHdr + 1, 1, 4, 1).setFontWeight('bold');
  const mixEnd = mixHdr + 4;
  sh.getRange(mixEnd + 2, 1).setValue('Notes: CRM = Facebook leads only (CRM_Dump column F). Quality leads = Status in ' +
    CFG.QUALITY_STATUSES.join(', ') + '. Meta leads and spend = EBG Ad Accounts. Targets, budgets and leads follow the Master PM Report v5. ' +
    'Per-leader Meta numbers are an allocation of each brand total (Meta does not record the sales leader).')
    .setFontStyle('italic').setFontColor('#78909c');

  // ---- Charts
  const addChart = (type, title, ranges, row, col, colors, extra) => {
    let b = sh.newChart().setChartType(type);
    ranges.forEach(rg => { b = b.addRange(rg); });
    b = b.setNumHeaders(1).setPosition(row, col, 0, 0)
         .setOption('title', title).setOption('width', 876).setOption('height', 380)
         .setOption('legend', { position: 'top' }).setOption('colors', colors)
         .setOption('titleTextStyle', { fontSize: 14, bold: true });
    if (extra) Object.keys(extra).forEach(k => { b = b.setOption(k, extra[k]); });
    sh.insertChart(b.build());
  };
  const col = (t, c) => sh.getRange(t.hdrRow, c, t.n + 1, 1);
  if (t1.n > 0) {
    addChart(Charts.ChartType.BAR, 'MTD: CRM Leads vs Lead Target by Sales Leader',
      [col(t1, 1), col(t1, 3), col(t1, 5)], CH1, 1, ['#90caf9', '#2e7d32'], { reverseCategories: true });
    addChart(Charts.ChartType.BAR, 'MTD: CRM Achievement % vs Qualified Lead % by Sales Leader',
      [col(t1, 1), col(t1, 6), col(t1, 8)], CH1, 9, ['#2e7d32', '#0097a7'], { reverseCategories: true });
  }
  if (t2.n > 0) {
    addChart(Charts.ChartType.COLUMN, 'MTD: Meta Spent vs Budget by Brand (Rs)',
      [col(t2, 1), col(t2, 10), col(t2, 9)], CH2, 1, ['#b39ddb', '#6a1b9a']);
    addChart(Charts.ChartType.COLUMN, 'MTD: Meta Leads vs CRM Leads by Brand',
      [col(t2, 1), col(t2, 4), col(t2, 5)], CH2, 9, ['#ef6c00', '#2e7d32']);
  }
  if (t3.n > 0) {
    addChart(Charts.ChartType.BAR, 'FTD: CRM Leads vs Lead Target by Sales Leader',
      [col(t3, 1), col(t3, 3), col(t3, 5)], CH3, 1, ['#ffcc80', '#2e7d32'], { reverseCategories: true });
  }
  addChart(Charts.ChartType.PIE, 'Lead Source Mix (all CRM leads, MTD)',
    [sh.getRange(mixHdr, 1, 5, 1), sh.getRange(mixHdr, 3, 5, 1)], CH3, 9,
    ['#1565c0', '#6a1b9a', '#2e7d32', '#757575'], { pieHole: 0.4, legend: { position: 'right' } });

  return { failedChecks: failed };
}

/** Tab order: Performance, FTD Performance, Master Dashboard, Brand Performance (any other tab stays after them). */
function orderTabs_(out) {
  [CFG.OUT_TAB, CFG.FTD_TAB, CFG.DASH_TAB, CFG.BRAND_TAB].forEach((name, i) => {
    const s = out.getSheetByName(name);
    if (s) { out.setActiveSheet(s); out.moveActiveSheet(i + 1); }
  });
  out.setActiveSheet(out.getSheetByName(CFG.DASH_TAB));   // open on the dashboard
}

/** Plain-language insights, most important first. Colour: green good, orange watch, red problem, blue info. */
function buildInsights_(mtd, ftd, mL, mB, fL, fB, ctx) {
  const G = '#1b5e20', O = '#e65100', R = '#b71c1c', B = '#0d47a1';
  const out = [];
  const headline = (label, T) => {
    const ach = T.target > 0 ? T.crm * 100 / T.target : null;
    const qp = T.crm > 0 ? T.quality * 100 / T.crm : null;
    const sp = T.budget > 0 ? T.spend * 100 / T.budget : null;
    const cpl = T.meta > 0 ? T.spend / T.meta : null;
    const cpql = T.quality > 0 ? T.spend / T.quality : null;
    const c = ach == null ? B : (ach >= 100 ? G : (ach >= 50 ? O : R));
    return { c: c, t: label + ': CRM leads ' + inr_(T.crm) + ' vs target ' + inr_(T.target) + (ach == null ? '' : ' (' + p1_(ach) + '%)') +
      '. Quality leads ' + inr_(T.quality) + (qp == null ? '' : ' (' + p1_(qp) + '% of CRM)') +
      '. Meta spend Rs ' + inr_(T.spend) + (sp == null ? '' : ' = ' + p1_(sp) + '% of budget Rs ' + inr_(T.budget)) +
      (cpl == null ? '' : '. CPL Rs ' + inr_(cpl)) + (cpql == null ? '' : ', cost per quality lead Rs ' + inr_(cpql)) + '.' };
  };
  out.push(headline('MTD', mtd.totals));
  out.push(headline('FTD', ftd.totals));

  const names = (arr, f) => arr.map(f).join(', ');
  const withT = mL.filter(a => a.target > 0);
  if (withT.length) {
    const behind = withT.filter(a => a.crm < a.target), crit = withT.filter(a => a.crm < 0.5 * a.target);
    const worst = withT.slice().sort((a, b) => a.ach - b.ach).slice(0, 3);
    out.push({ c: crit.length ? R : (behind.length ? O : G),
      t: 'MTD leaders: ' + (withT.length - behind.length) + ' of ' + withT.length + ' at or above target; ' + crit.length +
         ' below 50% of target. Lowest CRM achievement: ' + names(worst, a => a.name + ' ' + p1_(a.ach) + '%') + '.' });
    const best = withT.slice().sort((a, b) => b.ach - a.ach).slice(0, 3);
    out.push({ c: G, t: 'Best CRM achievement (MTD): ' + names(best, a => a.name + ' ' + p1_(a.ach) + '%') + '.' });
  }
  const qL = mL.filter(a => a.crm >= 50 && a.qpct != null);
  if (qL.length >= 2) {
    const hi = qL.slice().sort((a, b) => b.qpct - a.qpct).slice(0, 3), lo = qL.slice().sort((a, b) => a.qpct - b.qpct).slice(0, 3);
    out.push({ c: B, t: 'Qualified Lead % (MTD, leaders with 50+ CRM leads): highest ' + names(hi, a => a.name + ' ' + p1_(a.qpct) + '%') +
      '; lowest ' + names(lo, a => a.name + ' ' + p1_(a.qpct) + '%') + '.' });
  }
  const overB = mB.filter(a => a.over && a.budget > 0).sort((a, b) => (b.spend - b.budget) - (a.spend - a.budget));
  out.push(overB.length
    ? { c: R, t: 'Over budget (MTD): ' + overB.length + ' brand(s). Largest: ' + names(overB.slice(0, 3), a => a.name + ' +Rs ' + inr_(a.spend - a.budget) + ' (' + p1_(a.spPct) + '% of budget)') + '.' }
    : { c: G, t: 'No brand is over its MTD budget.' });
  const gap = mB.filter(a => a.meta > 0).map(a => ({ a: a, g: (a.meta - a.crm) * 100 / a.meta })).sort((x, y) => y.g - x.g).slice(0, 3);
  if (gap.length) {
    out.push({ c: O, t: 'Biggest Meta-to-CRM gap (MTD): ' + names(gap, x => x.a.name + ' (Meta ' + inr_(x.a.meta) + ' vs CRM ' + inr_(x.a.crm) + ', ' + p1_(x.g) + '% not in CRM Facebook)') +
      '. Meta counts all lead sources; CRM counts Facebook only.' });
  }
  const cq = mB.filter(a => a.cpql != null && a.quality >= 5).sort((a, b) => a.cpql - b.cpql);
  if (cq.length >= 2) {
    out.push({ c: B, t: 'Cost per quality lead (MTD): lowest ' + cq[0].name + ' Rs ' + inr_(cq[0].cpql) +
      '; highest ' + cq[cq.length - 1].name + ' Rs ' + inr_(cq[cq.length - 1].cpql) + '.' });
  }
  const fT = fL.filter(a => a.target > 0), fCrit = fT.filter(a => a.crm < 0.5 * a.target);
  const fOver = fB.filter(a => a.over && a.budget > 0).sort((a, b) => (b.spend - b.budget) - (a.spend - a.budget));
  out.push({ c: (fCrit.length || fOver.length) ? O : G,
    t: 'FTD (' + ctx.fmt(ctx.reportDate, 'd MMM') + '): ' + fT.filter(a => a.crm >= a.target).length + ' of ' + fT.length +
       ' leaders hit their day target; ' + fCrit.length + ' below 50%. ' +
       (fOver.length ? 'Brands over the day budget: ' + names(fOver.slice(0, 3), a => a.name) + '.' : 'No brand over the day budget.') });
  const tot = mtd.allCounted || 1, S = mtd.srcTotals;
  out.push({ c: B, t: 'Lead source mix (all CRM leads, MTD): Facebook ' + p1_(S['Facebook'] * 100 / tot) + '% | Website ' + p1_(S['Website'] * 100 / tot) +
    '% | Whatsapp Cloud API ' + p1_(S['Whatsapp Cloud API'] * 100 / tot) + '% | Other ' + p1_(S['Other'] * 100 / tot) + '%.' });
  const bad = mtd.checks.filter(c => !c.ok).length + ftd.checks.filter(c => !c.ok).length;
  out.push({ c: bad ? O : G, t: bad ? bad + ' data check(s) need attention. See the DATA QUALITY & SYNC CHECKS section below.' : 'All data checks passed: targets, Meta leads, spend and CRM counts tie to the Master.' });
  return out;
}

/* ====================================================================================================
   PART 2: MTM-TRENDS (two extra tabs)
   ==================================================================================================== */

/**
 * MTM-TRENDS (Month-To-Month trends)  -  BRAND-WISE performance and gap analysis, Sales vs Performance Marketing.
 *
 * Creates ONLY two tabs and never touches Performance, FTD Performance or Master Dashboard:
 *   MTM-Trends            : Brand Name | Sales Leader Name | Total Number of Leads | Number of Quality Leads | Quality Leads % | CPL (Rs) |
 *                           TAT (avg working hrs) | TAT within 30 min % | Leads measured for TAT | Target CPL (Rs) | Gap Owner | Where is the gap
 *                           (brand total rows and a grand total), plus the regression analysis (Quality ~ TAT) and its checks.
 *   MTM-Trends Dashboard  : tiles, Sales-vs-Performance-Marketing scorecard, insights, charts and tables.
 *
 * Menu: Performance > Refresh MTM-Trends (2 tabs)   (manual only, like the rest of the project).
 *
 * Sources (all figures are MTD = 1st of the month to the Master's report date):
 *   Total Number of Leads / Number of Quality Leads / Quality Leads % : exactly the Performance tab (Facebook CRM leads of
 *                           Master > CRM_Dump; Quality = Status in CFG.QUALITY_STATUSES; % = Quality x 100 / Total Number of Leads).
 *   CPL / Target CPL      : Master PM Report v5 > "MTD Brand wise" column D (CPL) and column AB (Target CPL). Brand level; a leader or grand
 *                           total is the average of its brands' CPL weighted by Meta leads.
 *   TAT (turn-around time): Daily Brand-Wise TAT Source Sheet > "Source Data". Working time between "Created On" and "First Attempted
 *                           Call": working hours 10:00-19:00 IST (MTM.WORK_START / WORK_END), no Sundays or Master holidays; a lead created
 *                           outside working hours starts its clock at the next 10:00; target = Master Settings B18 (30 minutes).
 *   Assignee -> Sales Leader and lead brand -> report brand : the Master's Roster and Maps (same as the Performance tab).
 *
 * REGRESSION ANALYSIS (Dependent variable = Quality, Independent variable = TAT)
 *   Observation = one called, measured lead. Quality = 1 if the lead's Status is a Quality status, else 0. TAT = working hours to the
 *   first call. Model: Quality = brand effect + beta x TAT (linear probability model with brand fixed effects, heteroskedasticity-robust
 *   standard errors). beta is the change in the chance of a Quality Lead for each extra working hour before the first call, with every
 *   brand compared only with itself, so differences in lead quality between brands cannot be mistaken for the effect of call speed.
 *   Pooled (no brand adjustment) results are shown as a cross-check. This shows an association; it does not by itself prove cause.
 *
 * GAP ANALYSIS (per brand, leader-brand row, leader total and grand total)
 *   Quality of called leads   = Quality % / call coverage (leads that were never called cannot become Quality Leads).
 *   Quality lost: never called = Quality of called leads - Quality %.                                   (Sales)
 *   Quality lost: slow TAT     = |beta| x (average TAT - TAT target), only for a negative, significant beta (p < 0.05).   (Sales)
 *   Quality at target TAT      = Quality of called leads + Quality lost to slow TAT: what the row would deliver if every lead were
 *                                called within the target.
 *   Lead-quality gap (pts)     = portfolio "Quality at target TAT" minus the row's: leads weaker than the portfolio even with the same
 *                                call speed and coverage, so a Performance Marketing issue. A CPL above Target CPL is also a Performance Marketing gap.
 *   Gap Owner: Sales (either Sales loss >= MTM.GAP_MIN_PTS, or most measured leads never called), Performance Marketing (lead-quality gap
 *   >= GAP_MIN_PTS or CPL above target), Both, On track. Rows with fewer than MTM.MIN_LEADS leads are not judged.
 */
const MTM = {
  TAB:          'MTM-Trends',
  DASH_TAB:     'MTM-Trends Dashboard',
  TAT_SHEET_ID: 'PASTE_TAT_SOURCE_SHEET_ID',   // Daily Brand-Wise TAT Source Sheet
  TAT_TAB:      'Source Data',
  KEEP_HISTORY: true,        // true = remember each month so the next months appear side by side (Month-To-Month)
  MAX_MONTHS:   6,           // how many months are kept and shown
  MIN_LEADS:    10,          // rows with fewer leads are not judged good or bad
  GAP_MIN_PTS:  1.0,         // a gap smaller than this many Quality points is not flagged
  REG_ALPHA:    0.05,        // significance level of the regression
  BRAND_ONCE:   true,        // true = show each brand name once; false = repeat it on every row
  WORK_START:   10,          // organisation working hours (IST): TAT counts only time between 10:00 and 19:00, Monday to Saturday
  WORK_END:     19,
  TAT_WINDOW:   'ALL'        // 'ALL'    = every lead is measured; a lead created outside working hours starts its clock at the next 10:00
                             // 'MASTER' = only leads created between the Master's two TAT hours (Settings B19:B20, 10:30-18:30), as in the Master
};

/* ------------------------------ entry point ------------------------------ */

function refreshMtmTrends() {
  const ctx = loadContext_();                                   // Master settings, maps, CRM rows (read only)
  const mtd = computePeriod_(ctx, PERIODS.MTD);                 // same numbers as the Performance tab (read only)
  const set = mtmSettings_(ctx);
  const tat = mtmTat_(ctx, set);
  const reg = mtmRegression_(tat.obs, set);                     // Quality ~ TAT (lead level, brand fixed effects)
  const cur = mtmCurrentMonth_(ctx, set, mtd, tat, reg);
  const months = mtmHistory_(cur);                              // previous months + current month
  const out = SpreadsheetApp.openById(CFG.OUT_SHEET_ID);
  const view = mtmBuildView_(ctx, set, months, mtd, tat, reg);
  mtmWriteTrends_(out, ctx, set, view);
  mtmWriteDashboard_(out, ctx, set, view);
  mtmOrderTabs_(out);
  out.toast('Refreshed: ' + MTM.TAB + ' and ' + MTM.DASH_TAB + ' (' + cur.label + ', ' + view.pairKeys.length + ' leader-brand rows).', 'MTM-Trends', 6);
}

/* ------------------------------ settings, maps, roster ------------------------------ */

const MTM_HR = 3600000, MTM_DAY = 86400000;

function mtmSettings_(ctx) {
  const master = ctx.master, fmt = ctx.fmt;
  const st = master.getSheetByName('Settings').getRange('A1:B52').getValues();
  const S = r => st[r - 1][1];
  const num = (v, d) => (v === '' || v === null || isNaN(Number(v))) ? d : Number(v);
  const set = {
    tatTarget: num(S(18), 0.5), fromHr: num(S(19), 10.5), toHr: num(S(20), 18.5), workStart: MTM.WORK_START, workEnd: MTM.WORK_END,
    sundayLeads: norm_(S(23)) !== 'n',
    poor: num(S(33), 0.7), good: num(S(34), 0.9), defCpl: num(S(13), 400),
    fwBrand: clean_(S(26)) || 'FW',
    exclSrc: new Set(list_(S(27))), exclCustom: new Set(list_(S(44))), exclPriority: new Set(list_(S(46)))
  };
  const ymd = d => fmt(d, 'yyyy-MM-dd');
  const dayNum = s => Date.UTC(+s.substr(0, 4), +s.substr(5, 2) - 1, +s.substr(8, 2)) / MTM_DAY;
  const rep = ymd(ctx.reportDate);
  set.monthKey = fmt(ctx.reportDate, 'yyyy-MM');
  set.monthLabel = fmt(ctx.reportDate, 'MMM yyyy');
  set.rangeLabel = '1 to ' + fmt(ctx.reportDate, 'd MMM');          // MTD range shown in the headers
  set.loWall = dayNum(set.monthKey + '-01') * MTM_DAY;                 // first day 00:00 (wall clock)
  set.hiWall = (dayNum(rep) + 1) * MTM_DAY;                            // end of the report date (exclusive)
  set.dayNum = dayNum;

  const maps = master.getSheetByName('Maps').getRange('A5:X400').getValues();
  set.brandMap = {}; set.leaderMap = {}; set.domainMap = {}; set.hol = new Set();
  maps.forEach(r => {
    if (norm_(r[0]) === 'telecrm' && clean_(r[1]) && clean_(r[2])) set.brandMap[norm_(r[1])] = clean_(r[2]);
    if (clean_(r[4]) && clean_(r[5])) set.leaderMap[norm_(r[4])] = clean_(r[5]);
    if (clean_(r[7]) && clean_(r[8])) set.domainMap[norm_(r[7])] = clean_(r[8]);
    if (r[19] instanceof Date) set.hol.add(dayNum(ymd(r[19])));
  });
  set.roster = {};                                                       // e-mail -> Sales Leader (Master > Roster B and J)
  master.getSheetByName('Roster').getRange('A2:J2000').getValues().forEach(r => {
    const e = norm_(r[1]);
    if (e && clean_(r[9])) set.roster[e] = clean_(r[9]);
  });
  return set;
}

/** Report brand of a CRM brand name: same rule as Master > Prep_Leads column A. */
function mtmBrand_(set, raw) {
  const b = clean_(raw);
  if (!b || b === '-') return 'Unattributed';
  const m = set.brandMap[norm_(b)];
  const out = m || (/^FW[_-]/i.test(b) ? set.fwBrand : b);
  return BRAND_FIX[norm_(out)] || out;
}

/** Report leader of an assignee e-mail: same rule as Master > Prep_Leads column B. */
function mtmLeader_(set, rawEmail) {
  const e = norm_(rawEmail);
  if (!e || e === '-') return 'Unassigned';
  const rl = set.roster[e];
  if (rl) return set.leaderMap[norm_(rl)] || rl;
  const dm = set.domainMap[e.split('@').pop()];
  return dm || 'No leader (not on roster)';
}

function mtmHm_(h) { return Math.floor(h) + ':' + ('0' + Math.round((h % 1) * 60)).slice(-2); }
/** Short text for the TAT rule used in headers and tiles. */
function mtmWinTxt_(set) {
  return MTM.TAT_WINDOW === 'MASTER' ? 'Leads created ' + mtmHm_(set.fromHr) + '-' + mtmHm_(set.toHr) : 'All leads (clock runs ' + mtmHm_(set.workStart) + '-' + mtmHm_(set.workEnd) + ' IST)';
}

/* ------------------------------ TAT from the TAT Source Sheet ------------------------------ */

/** Working minutes between two wall-clock times (ms): only 'workStart'-'workEnd' on days that are not Sunday or a holiday. */
function mtmWorkMin_(s, e, set) {
  if (!(e > s)) return 0;
  let total = 0;
  const d0 = Math.floor(s / MTM_DAY), d1 = Math.floor(e / MTM_DAY);
  for (let d = d0; d <= d1 && d - d0 < 400; d++) {
    if ((d + 4) % 7 === 0 || set.hol.has(d)) continue;                  // Sunday (day 0 = Thursday 1 Jan 1970) or holiday
    const lo = Math.max(s, d * MTM_DAY + set.workStart * MTM_HR), hi = Math.min(e, d * MTM_DAY + set.workEnd * MTM_HR);
    if (hi > lo) total += (hi - lo) / 60000;
  }
  return total;
}

function mtmTat_(ctx, set) {
  const book = SpreadsheetApp.openById(MTM.TAT_SHEET_ID);
  const sh = book.getSheetByName(MTM.TAT_TAB);
  if (!sh) throw new Error('Tab "' + MTM.TAT_TAB + '" was not found in the Daily Brand-Wise TAT Source Sheet. Run its "Refresh data" first.');
  const nRows = sh.getLastRow() - 1;
  if (nRows < 1) throw new Error('The TAT Source Sheet tab "' + MTM.TAT_TAB + '" has no data. Run its "Refresh data" first.');
  const tz = book.getSpreadsheetTimeZone();
  const header = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0].map(norm_);
  const colOf = name => header.indexOf(norm_(name));
  const need = ['Created On', 'First Attempted Call', 'Assignee emailid', 'Brand', 'Lead Source'];
  need.forEach(n => { if (colOf(n) < 0) throw new Error('Column "' + n + '" is missing in the TAT Source Sheet tab "' + MTM.TAT_TAB + '".'); });
  const read = name => sh.getRange(2, colOf(name) + 1, nRows, 1).getValues();
  const cCreated = read('Created On'), cFirst = read('First Attempted Call'), cMail = read('Assignee emailid'),
        cBrand = read('Brand'), cSrc = read('Lead Source');
  const needCustom = set.exclCustom.size > 0 && colOf('Custom lead source') >= 0;
  const needPrio = set.exclPriority.size > 0 && colOf('Priority label') >= 0;
  const cCustom = needCustom ? read('Custom lead source') : null, cPrio = needPrio ? read('Priority label') : null;
  const cStatus = colOf('Status') >= 0 ? read('Status') : null;           // for the regression (Quality = 1 / 0)
  const obs = { ok: !!cStatus, y: [], x: [], g: [], names: [], idx: {} };

  const wall = d => {                                                   // wall-clock time of a sheet date, as ms
    const s = Utilities.formatDate(d, tz, 'yyyy-MM-dd HH:mm:ss');
    return Date.UTC(+s.substr(0, 4), +s.substr(5, 2) - 1, +s.substr(8, 2), +s.substr(11, 2), +s.substr(14, 2), +s.substr(17, 2));
  };
  const margin = 36 * MTM_HR;
  // snapshot time of the TAT sheet = newest "created" or "first call" time in the data. A lead that is still not called is a miss
  // only when its working-time clock has already run past the target; otherwise it is "pending".
  let maxT = 0;
  for (let i = 0; i < nRows; i++) {
    const a1 = cCreated[i][0], b1 = cFirst[i][0];
    if (a1 instanceof Date && a1.getTime() > maxT) maxT = a1.getTime();
    if (b1 instanceof Date && b1.getTime() > maxT) maxT = b1.getTime();
  }
  const asOf = maxT ? wall(new Date(maxT)) : set.hiWall;
  const byKey = {};
  const st = { rows: nRows, inMonth: 0, notSource: 0, hidden: 0, unassigned: 0, counted: 0, eligible: 0, called: 0, within: 0,
               sumH: 0, outsideWindow: 0, beforeCreated: 0, unreadable: 0, pending: 0, asOf: asOf };
  for (let i = 0; i < nRows; i++) {
    const cd = cCreated[i][0];
    if (!(cd instanceof Date)) { if (clean_(cd) !== '') st.unreadable++; continue; }
    const t = cd.getTime();
    if (t < set.loWall - margin || t > set.hiWall + margin) continue;   // cheap pre-filter before the exact wall-clock test
    const w = wall(cd);
    if (w < set.loWall || w >= set.hiWall) continue;
    st.inMonth++;
    const rawSrc = clean_(cSrc[i][0]);
    if (set.exclSrc.has(norm_(rawSrc)) || !ctx.incSrc.has(norm_(canonSource_(rawSrc)))) { st.notSource++; continue; }
    if (needCustom && set.exclCustom.has(norm_(cCustom[i][0]))) { st.notSource++; continue; }
    if (needPrio && set.exclPriority.has(norm_(cPrio[i][0]))) { st.notSource++; continue; }
    const brand = mtmBrand_(set, cBrand[i][0]);
    if (ctx.hidden.has(norm_(brand))) { st.hidden++; continue; }
    const leader = mtmLeader_(set, cMail[i][0]);
    if (ctx.exLead.has(norm_(leader))) { st.unassigned++; continue; }
    st.counted++;
    const key = norm_(leader) + '|' + norm_(brand);
    const a = byKey[key] || (byKey[key] = { leader: leader, brand: brand, leads: 0, elig: 0, called: 0, within: 0, sumH: 0 });
    a.leads++;
    const tod = (w % MTM_DAY) / MTM_HR;
    const dnum = Math.floor(w / MTM_DAY);
    const workDay = (dnum + 4) % 7 !== 0 && !set.hol.has(dnum);
    if (MTM.TAT_WINDOW === 'MASTER' && (tod < set.fromHr || tod > set.toHr || (!set.sundayLeads && !workDay))) { st.outsideWindow++; continue; }   // not measured
    const fc = cFirst[i][0];
    if (!(fc instanceof Date)) {                                          // not called yet
      if (mtmWorkMin_(w, asOf, set) < set.tatTarget * 60) { st.pending++; continue; }   // its clock has not reached the target yet: not a miss
      a.elig++; st.eligible++;                                            // clock has run out: counts against the target
      continue;
    }
    const fw = wall(fc);
    if (fw < w) { st.beforeCreated++; continue; }                         // first call before creation: data issue, not measured
    a.elig++; st.eligible++;
    const hrs = mtmWorkMin_(w, fw, set) / 60;
    a.called++; a.sumH += hrs; st.called++; st.sumH += hrs;
    if (cStatus) {                                                        // one observation for the regression
      const bk = norm_(brand);
      if (!(bk in obs.idx)) { obs.idx[bk] = obs.names.length; obs.names.push(brand); }
      obs.y.push(ctx.qualSet.has(normStatus_(cStatus[i][0])) ? 1 : 0); obs.x.push(hrs); obs.g.push(obs.idx[bk]);
    }
    if (hrs <= set.tatTarget + 1e-9) { a.within++; st.within++; }
  }
  return { byKey: byKey, stats: st, obs: obs };
}

/* ------------------------------ statistics (t distribution) ------------------------------ */

function mtmLnGamma_(x) {
  const c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
             12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  if (x < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * x)) - mtmLnGamma_(1 - x);
  x -= 1;
  let a = c[0];
  const t = x + 7.5;
  for (let i = 1; i < 9; i++) a += c[i] / (x + i);
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
}

function mtmBetaCf_(a, b, x) {
  const FPMIN = 1e-300;
  const qab = a + b, qap = a + 1, qam = a - 1;
  let c = 1, d = 1 - qab * x / qap;
  if (Math.abs(d) < FPMIN) d = FPMIN;
  d = 1 / d;
  let h = d;
  for (let m = 1; m <= 300; m++) {
    const m2 = 2 * m;
    let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
    d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
    c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
    d = 1 / d; h *= d * c;
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
    c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
    d = 1 / d;
    const del = d * c;
    h *= del;
    if (Math.abs(del - 1) < 3e-14) break;
  }
  return h;
}

/** Regularised incomplete beta function I_x(a, b). */
function mtmIbeta_(x, a, b) {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const bt = Math.exp(mtmLnGamma_(a + b) - mtmLnGamma_(a) - mtmLnGamma_(b) + a * Math.log(x) + b * Math.log(1 - x));
  return x < (a + 1) / (a + b + 2) ? bt * mtmBetaCf_(a, b, x) / a : 1 - bt * mtmBetaCf_(b, a, 1 - x) / b;
}

/** Two-sided p-value of a t statistic with df degrees of freedom. */
function mtmTP_(t, df) {
  if (!isFinite(t)) return 0;
  return mtmIbeta_(df / (df + t * t), df / 2, 0.5);
}

/** Critical t value for a two-sided test at level alpha. */
function mtmTCrit_(df, alpha) {
  let lo = 0, hi = 60;
  for (let i = 0; i < 80; i++) { const mid = (lo + hi) / 2; if (mtmTP_(mid, df) > alpha) lo = mid; else hi = mid; }
  return (lo + hi) / 2;
}

/**
 * Regression of Quality (1/0) on TAT (working hours), one observation per called lead.
 *  - Main model: brand fixed effects (each brand compared only with itself), robust (HC1) standard errors.
 *  - Cross-check: pooled model without brand effects.
 * beta is the change in the probability of a Quality Lead per extra working hour; the pts values are beta x 100.
 */
function mtmRegression_(obs, set) {
  const n = obs.y.length, G = obs.names.length;
  const base = { ok: false, n: n, groups: G, note: '' };
  if (!obs.ok) { base.note = 'The TAT Source Sheet has no "Status" column, so Quality cannot be regressed on TAT.'; return base; }
  if (n < 30 || G < 1) { base.note = 'Fewer than 30 called leads; a regression would not be reliable.'; return base; }
  const sx = new Array(G).fill(0), sy = new Array(G).fill(0), cnt = new Array(G).fill(0);
  let tx = 0, ty = 0;
  for (let i = 0; i < n; i++) { sx[obs.g[i]] += obs.x[i]; sy[obs.g[i]] += obs.y[i]; cnt[obs.g[i]]++; tx += obs.x[i]; ty += obs.y[i]; }
  const xb = tx / n, yb = ty / n;
  // within (brand fixed effects)
  let Sxx = 0, Sxy = 0, Syy = 0;
  for (let i = 0; i < n; i++) {
    const g = obs.g[i], xt = obs.x[i] - sx[g] / cnt[g], yt = obs.y[i] - sy[g] / cnt[g];
    Sxx += xt * xt; Sxy += xt * yt; Syy += yt * yt;
  }
  if (!(Sxx > 0) || !(Syy > 0)) { base.note = 'TAT does not vary enough to run a regression.'; return base; }
  const beta = Sxy / Sxx, df = n - G - 1;
  let sse = 0, meat = 0;
  for (let i = 0; i < n; i++) {
    const g = obs.g[i], xt = obs.x[i] - sx[g] / cnt[g], yt = obs.y[i] - sy[g] / cnt[g], e = yt - beta * xt;
    sse += e * e; meat += xt * xt * e * e;
  }
  const se = Math.sqrt((n / df) * meat / (Sxx * Sxx));
  const t = se > 0 ? beta / se : 0;
  const p = mtmTP_(t, df), tc = mtmTCrit_(df, 0.05);
  // pooled
  let pxx = 0, pxy = 0, pyy = 0;
  for (let i = 0; i < n; i++) { const xt = obs.x[i] - xb, yt = obs.y[i] - yb; pxx += xt * xt; pxy += xt * yt; pyy += yt * yt; }
  const bP = pxy / pxx;
  let pmeat = 0;
  for (let i = 0; i < n; i++) { const xt = obs.x[i] - xb, e = (obs.y[i] - yb) - bP * xt; pmeat += xt * xt * e * e; }
  const seP = Math.sqrt((n / (n - 2)) * pmeat / (pxx * pxx)), tP = seP > 0 ? bP / seP : 0;
  // Quality by TAT band
  const T0 = set.tatTarget, edges = [T0, 2, 4, 8, 16];
  const labels = ['Up to ' + Math.round(T0 * 60) + ' min', Math.round(T0 * 60) + ' min - 2 h', '2 - 4 h', '4 - 8 h', '8 - 16 h', 'Over 16 h'];
  const bc = [0, 0, 0, 0, 0, 0], bq = [0, 0, 0, 0, 0, 0];
  for (let i = 0; i < n; i++) {
    let k = 0; while (k < edges.length && obs.x[i] > edges[k]) k++;
    bc[k]++; bq[k] += obs.y[i];
  }
  return {
    ok: true, n: n, groups: G, df: df, note: '',
    beta: beta, se: se, t: t, p: p, ci: [beta - tc * se, beta + tc * se],
    r2w: Syy > 0 ? 1 - sse / Syy : 0, sig: p < MTM.REG_ALPHA, negative: beta < 0,
    betaP: bP, seP: seP, tP: tP, pP: mtmTP_(tP, n - 2), r2P: (pxy * pxy) / (pxx * pyy),
    meanQ: yb, meanT: xb,
    bands: labels.map((l, k) => ({ label: l, n: bc[k], q: bq[k], pct: bc[k] > 0 ? bq[k] * 100 / bc[k] : '' }))
  };
}

/* ------------------------------ month data ------------------------------ */

function mtmCpl_(ctx) {
  const rows = ctx.master.getSheetByName(PERIODS.MTD.brandTab).getRange('A5:AB80').getValues();
  const o = {};
  for (const r of rows) {
    const b = clean_(r[1]);
    if (!b) continue;
    if (norm_(b) === 'total') break;
    const cpl = Number(r[3]), tc = Number(r[27]);
    o[norm_(b)] = { cpl: cpl > 0 ? cpl : '', tcpl: tc > 0 ? tc : '' };
  }
  return o;
}

/** One entry per Leader x Brand: [leader, brand, quality, crm, cpl, metaLeads, eligible, called, within, sumHrs, targetCpl] */
function mtmCurrentMonth_(ctx, set, mtd, tat, reg) {
  const cpl = mtmCpl_(ctx);
  const rows = [];
  let matched = 0;
  mtd.pairRows.forEach(p => {
    const key = norm_(p.leader) + '|' + norm_(p.brand);
    const t = tat.byKey[key] || { elig: 0, called: 0, within: 0, sumH: 0, leads: 0 };
    matched += t.leads || 0;
    const c = cpl[norm_(p.brand)] || { cpl: '', tcpl: '' };
    rows.push([p.leader, p.brand, p.quality, p.crm, c.cpl, Math.round(p.metaLeads), t.elig, t.called, t.within,
               Math.round(t.sumH * 100) / 100, c.tcpl === '' ? set.defCpl : c.tcpl]);
  });
  tat.stats.matchedToPairs = matched;
  tat.stats.notMatched = tat.stats.counted - matched;
  const rg = reg && reg.ok ? { beta: reg.beta, p: reg.p, n: reg.n } : null;
  return { key: set.monthKey, label: set.monthLabel, range: set.rangeLabel, rows: rows, reg: rg };
}

/* history: every refresh stores the month in the document properties (chunks of 8,000 characters) */

function mtmProps_() { try { return PropertiesService.getDocumentProperties(); } catch (e) { return null; } }

function mtmHistory_(cur) {
  const P = MTM.KEEP_HISTORY ? mtmProps_() : null;
  if (!P) return [cur];
  let idx = {};
  try { idx = JSON.parse(P.getProperty('mtm_index') || '{}'); } catch (e) { idx = {}; }
  const all = P.getProperties();
  const months = [];
  Object.keys(idx).sort().forEach(k => {
    if (k === cur.key) return;
    let s = '';
    for (let i = 0; i < idx[k].chunks; i++) s += all['mtm_' + k + '_' + i] || '';
    try { months.push({ key: k, label: idx[k].label, range: idx[k].range || '', reg: idx[k].reg || null, rows: JSON.parse(s) }); } catch (e) { /* damaged month: skipped */ }
  });
  months.push(cur);
  months.sort((a, b) => a.key < b.key ? -1 : 1);
  const keep = months.slice(-MTM.MAX_MONTHS);
  // save
  const toSet = {}, newIdx = {};
  keep.forEach(m => {
    const s = JSON.stringify(m.rows);
    const n = Math.ceil(s.length / 8000);
    for (let i = 0; i < n; i++) toSet['mtm_' + m.key + '_' + i] = s.substr(i * 8000, 8000);
    newIdx[m.key] = { label: m.label, range: m.range || '', reg: m.reg || null, chunks: n };
  });
  Object.keys(all).forEach(k => { if (k.indexOf('mtm_') === 0 && k !== 'mtm_index' && !(k in toSet)) P.deleteProperty(k); });
  toSet['mtm_index'] = JSON.stringify(newIdx);
  P.setProperties(toSet);
  return keep;
}

/* ------------------------------ metrics and gap rules ------------------------------ */

/** Metrics of a group of month rows (array of the 11-field arrays). */
function mtmMetrics_(items) {
  const m = { q: 0, crm: 0, meta: 0, elig: 0, called: 0, within: 0, sumH: 0 };
  let wCpl = 0, wMeta = 0, wT = 0, plain = [], plainT = [];
  items.forEach(r => {
    m.q += r[2]; m.crm += r[3]; m.meta += r[5]; m.elig += r[6]; m.called += r[7]; m.within += r[8]; m.sumH += r[9];
    if (r[4] !== '') { plain.push(r[4]); if (r[5] > 0) { wCpl += r[4] * r[5]; wMeta += r[5]; } }
    if (r[10] !== '' && r[4] !== '') { plainT.push(r[10]); if (r[5] > 0) wT += r[10] * r[5]; }
  });
  m.qp = m.crm > 0 ? m.q * 100 / m.crm : '';
  m.cpl = wMeta > 0 ? wCpl / wMeta : (plain.length ? plain.reduce((a, b) => a + b, 0) / plain.length : '');
  m.tcpl = wMeta > 0 ? wT / wMeta : (plainT.length ? plainT.reduce((a, b) => a + b, 0) / plainT.length : '');
  m.tat = m.called > 0 ? m.sumH / m.called : '';
  m.tp = m.elig > 0 ? m.within * 100 / m.elig : '';
  return m;
}

/** Quality points lost to slow TAT (regression): |beta| x (average TAT - target), only for a negative, significant beta. */
function mtmSalesLoss_(m, reg, set) {
  if (!reg || !reg.ok || !reg.negative || !reg.sig || m.tat === '') return 0;
  return -reg.beta * 100 * Math.max(0, m.tat - set.tatTarget);
}

/**
 * Potential Quality % of a row = what it would deliver if every lead got a first call within the TAT target.
 *   Quality of called leads  = Quality % / call coverage (leads that were never called cannot become Quality Leads)
 *   Lost to leads never called = Quality of called leads - Quality %
 *   Lost to slow TAT           = regression: |beta| x (average TAT - target)
 * Needs at least MTM.MIN_LEADS called leads.
 */
function mtmPot_(m, reg, set) {
  const none = { qc: '', noCall: 0, tatLoss: 0, pot: '' };
  if (m.qp === '' || m.elig <= 0 || m.called < MTM.MIN_LEADS) return none;
  const cov = m.called / m.elig;
  const qc = Math.min(100, m.qp / cov);
  const tatLoss = mtmSalesLoss_(m, reg, set);
  return { qc: qc, noCall: qc - m.qp, tatLoss: tatLoss, pot: qc + tatLoss };
}

/**
 * Gap analysis of one row. benchPot = the portfolio's Potential Quality % ('' when unknown).
 * Returns the gap owner, the explanation and the regression-based numbers.
 */
function mtmGap_(m, reg, benchPot, set) {
  const p = mtmPot_(m, reg, set);
  const out = { noCall: p.noCall, tatLoss: p.tatLoss, loss: p.noCall + p.tatLoss, pot: p.pot, lq: 0, owner: 'Too few leads', text: 'Fewer than ' + MTM.MIN_LEADS + ' leads' };
  if (!(m.crm >= MTM.MIN_LEADS && m.qp !== '')) return out;
  const lq = benchPot !== '' && p.pot !== '' ? Math.max(0, benchPot - p.pot) : 0;
  out.lq = lq;
  const cplOver = m.cpl !== '' && m.tcpl !== '' && m.cpl > m.tcpl + 0.5;
  const uncalled = m.elig - m.called;
  const noQ = p.pot === '' && m.elig >= MTM.MIN_LEADS && uncalled / m.elig >= 0.5;        // most leads never got a first call
  const salesTat = m.elig >= MTM.MIN_LEADS && p.tatLoss >= MTM.GAP_MIN_PTS;
  const salesNo = m.elig >= MTM.MIN_LEADS && p.noCall >= MTM.GAP_MIN_PTS;
  const sales = salesTat || salesNo || noQ;
  const mkt = cplOver || lq >= MTM.GAP_MIN_PTS;
  const tags = [];
  if (noQ) tags.push('Sales: ' + uncalled + ' of ' + m.elig + ' measured leads never got a first call, so lead quality cannot be judged');
  if (salesNo) tags.push('Sales: ' + uncalled + ' of ' + m.elig + ' measured leads (' + p1_(uncalled * 100 / m.elig) + '%) never got a first call, costing about ' + p1_(p.noCall) + ' Quality pts');
  if (salesTat) tags.push('Sales: average TAT ' + p1_(m.tat) + ' working hrs (target ' + p1_(set.tatTarget) + ') costs about ' + p1_(p.tatLoss) + ' Quality pts');
  if (sales && p.pot !== '' && tags.length) tags[tags.length - 1] += ' (Quality ' + p1_(m.qp) + '% could be ' + p1_(p.pot) + '%)';
  if (lq >= MTM.GAP_MIN_PTS) tags.push('Marketing: lead quality is ' + p1_(lq) + ' pts below the portfolio at equal call speed and coverage');
  if (cplOver) tags.push('Marketing: CPL Rs ' + inr_(m.cpl) + ' vs target Rs ' + inr_(m.tcpl));
  out.owner = sales && mkt ? 'Both' : (sales ? 'Sales' : (mkt ? 'Performance Marketing' : 'On track'));
  out.text = tags.length ? tags.join('; ') : 'No gap found: Quality loss under ' + p1_(MTM.GAP_MIN_PTS) + ' pt, lead quality in line with the portfolio, CPL within target';
  return out;
}

/** Everything the two tabs show. */
function mtmBuildView_(ctx, set, months, mtd, tat, reg) {
  const cur = months[months.length - 1];
  const keyOf = r => norm_(r[0]) + '|' + norm_(r[1]);
  const byMonth = months.map(m => { const o = {}; m.rows.forEach(r => { o[keyOf(r)] = r; }); return o; });
  const names = {};
  for (let i = 0; i < months.length; i++) months[i].rows.forEach(r => { names[keyOf(r)] = { leader: r[0], brand: r[1] }; });
  months[months.length - 1].rows.forEach(r => { names[keyOf(r)] = { leader: r[0], brand: r[1] }; });
  const pairKeys = Object.keys(names).sort((a, b) =>
    names[a].brand.localeCompare(names[b].brand) || names[a].leader.localeCompare(names[b].leader));
  const brands = [], leaders = [];
  pairKeys.forEach(k => {
    if (brands.indexOf(names[k].brand) < 0) brands.push(names[k].brand);
    if (leaders.indexOf(names[k].leader) < 0) leaders.push(names[k].leader);
  });
  leaders.sort((a, b) => a.localeCompare(b));

  const metOf = keys => months.map((m, i) => {
    const items = keys.map(k => byMonth[i][k]).filter(Boolean);
    return items.length ? mtmMetrics_(items) : null;
  });
  const li = months.length - 1;
  const total = metOf(pairKeys);
  const tl = total[li];
  const benchPot = tl ? mtmPot_(tl, reg, set).pot : '';
  const gapOf = mm => mm[li] ? mtmGap_(mm[li], reg, benchPot, set) : null;

  const lines = [];
  brands.forEach(b => {
    const keys = pairKeys.filter(k => names[k].brand === b);
    keys.forEach((k, i) => {
      const mm = metOf([k]);
      lines.push({ type: 'pair', brand: b, leader: names[k].leader, first: i === 0, m: mm, gap: gapOf(mm) });
    });
    const bm = metOf(keys);
    lines.push({ type: 'brand', brand: b, leader: 'TOTAL: ' + b, m: bm, gap: gapOf(bm) });
  });
  lines.push({ type: 'total', brand: 'GRAND TOTAL', leader: '', m: total, gap: gapOf(total) });

  const brandRows = lines.filter(l => l.type === 'brand').map(l => ({ name: l.brand, m: l.m, gap: l.gap }));
  const leaderRows = leaders.map(ld => {
    const keys = pairKeys.filter(k => names[k].leader === ld);
    const mm = metOf(keys);
    return { name: ld, m: mm, gap: gapOf(mm) };
  });
  return { months: months, cur: cur, lines: lines, pairKeys: pairKeys, brands: brands, leaders: leaders, brandRows: brandRows, leaderRows: leaderRows,
           total: total, benchPot: benchPot, lastIdx: li, reg: reg, target: mtd.totals.target, metaTot: mtd.totals.meta,
           quality: mtd.totals.quality, crmTot: mtd.totals.crm, tat: tat };
}

/* ------------------------------ tab: MTM-Trends ------------------------------ */

function mtmWriteTrends_(out, ctx, set, V) {
  const SOLID = SpreadsheetApp.BorderStyle.SOLID;
  const sh = out.getSheetByName(MTM.TAB) || out.insertSheet(MTM.TAB);
  sh.getCharts().forEach(c => sh.removeChart(c));
  sh.getRange(1, 1, sh.getMaxRows(), sh.getMaxColumns()).breakApart();
  sh.clear();
  const NC2 = 17;                                                          // A:L main table, M spacer, N:Q regression-based gap
  if (sh.getMaxColumns() < NC2) sh.insertColumnsAfter(sh.getMaxColumns(), NC2 - sh.getMaxColumns());
  if (sh.getMaxRows() < 400) sh.insertRowsAfter(sh.getMaxRows(), 400 - sh.getMaxRows());
  const TATMIN = Math.round(set.tatTarget * 60);
  const li = V.lastIdx, R = V.reg;
  sh.getRange(1, 1, 400, NC2).setFontFamily('Roboto').setFontSize(10).setVerticalAlignment('middle').setBackground('#ffffff');
  sh.setHiddenGridlines(true);
  sh.setTabColor('#6a1b9a');

  const band = (row, text, bg, fg, size, height, c1, c2) => {
    sh.getRange(row, c1 || 1, 1, (c2 || NC2) - (c1 || 1) + 1).merge().setValue(text).setBackground(bg).setFontColor(fg).setFontWeight('bold').setFontSize(size)
      .setHorizontalAlignment('left').setVerticalAlignment('middle').setWrap(true);
    sh.setRowHeight(row, height);
  };
  band(1, '  MTM-TRENDS  |  BRAND-WISE PERFORMANCE AND GAP ANALYSIS: SALES vs PERFORMANCE MARKETING', '#4a148c', '#ffffff', 20, 44);
  band(2, '  MTD: ' + V.cur.label + ' (' + V.cur.range + ')   |   Report date: ' + ctx.fmt(ctx.reportDate, 'dd-MMM-yyyy') + '   |   Refreshed: ' + ctx.fmt(new Date(), 'dd-MMM-yyyy HH:mm') +
          '   |   Quality leads & CPL: Master PM Report v5   |   TAT: Daily Brand-Wise TAT Source Sheet   |   Facebook leads only', '#6a1b9a', '#f3e5f5', 10, 24);
  band(3, '  ALL FIGURES ARE MTD.   TAT = working time from lead creation to the first call attempt (working hours ' + mtmHm_(set.workStart) + '-' + mtmHm_(set.workEnd) +
          ' IST, Monday to Saturday; a lead created outside working hours starts at the next 10:00; target ' + TATMIN + ' min).   GAP ANALYSIS uses the regression Quality ~ TAT below: Sales gap = Quality points lost to leads never called and to slow first calls; ' +
          'Lead-quality gap = Quality below the portfolio at equal call speed and coverage; a CPL above target is also a Performance Marketing gap.',
       '#f3e5f5', '#4a148c', 9, 34);
  sh.setRowHeight(4, 8);

  // group header (row 5) and column headers (row 6)
  const gh = new Array(NC2).fill(''), hd = new Array(NC2).fill('');
  gh[0] = 'BRAND-WISE PERFORMANCE AND GAP ANALYSIS  -  MTD ' + V.cur.label.toUpperCase();
  gh[13] = 'REGRESSION-BASED GAP (Quality ~ TAT)';
  const heads = ['Brand Name', 'Sales Leader Name', 'Total Number of Leads', 'Number of Quality Leads', 'Quality Leads %', 'CPL (Rs)', 'TAT (avg working hrs)',
                 'TAT within ' + TATMIN + ' min %', 'Leads measured for TAT', 'Target CPL (Rs)', 'Gap Owner', 'Where is the gap'];
  heads.forEach((t, j) => { hd[j] = t; });
  hd[13] = 'Quality lost: leads never called (pts)'; hd[14] = 'Quality lost: slow TAT (pts)'; hd[15] = 'Quality at target TAT (%)'; hd[16] = 'Lead-quality gap vs portfolio (pts)';
  sh.getRange(5, 1, 1, NC2).setValues([gh]).setFontWeight('bold').setFontColor('#ffffff').setHorizontalAlignment('center').setBackground('#37474f');
  sh.getRange(5, 1, 1, 12).merge().setBackground('#6a1b9a');
  sh.getRange(5, 14, 1, 4).merge().setBackground('#b71c1c');
  sh.getRange(6, 1, 1, NC2).setValues([hd]).setBackground('#263238').setFontColor('#ffffff').setFontWeight('bold').setWrap(true).setHorizontalAlignment('center');
  sh.getRange(6, 1, 1, 2).setHorizontalAlignment('left');
  sh.getRange(6, 13).setBackground('#ffffff');
  sh.setRowHeight(5, 26); sh.setRowHeight(6, 46);

  // data rows
  const n = V.lines.length, first = 7;
  const vals = [], fonts = [], bgs = [], bolds = [];
  const ownerCol = { 'Sales': ['#ffcdd2', '#b71c1c'], 'Performance Marketing': ['#ffe0b2', '#e65100'], 'Both': ['#ef9a9a', '#7f0000'],
                     'On track': ['#c8e6c9', '#1b5e20'], 'Too few leads': ['#eceff1', '#546e7a'] };
  V.lines.forEach(l => {
    const row = new Array(NC2).fill(''), f = new Array(NC2).fill('#263238'), b = new Array(NC2).fill('#ffffff');
    const isP = l.type === 'pair';
    row[0] = isP ? ((MTM.BRAND_ONCE && !l.first) ? '' : l.brand) : (l.type === 'total' ? 'GRAND TOTAL' : '');
    row[1] = isP ? l.leader : (l.type === 'brand' ? l.leader : '');
    const m = l.m[li];
    if (m) {
      row[2] = m.crm; row[3] = m.q; row[4] = m.qp;
      row[5] = m.cpl === '' ? '' : Math.round(m.cpl * 100) / 100;
      row[6] = m.tat === '' ? '' : Math.round(m.tat * 100) / 100;
      row[7] = m.tp === '' ? '' : m.tp;
      row[8] = m.elig;
      row[9] = m.tcpl === '' ? '' : Math.round(m.tcpl * 100) / 100;
      if (m.qp !== '' && V.total[li] && V.total[li].qp !== '' && m.crm >= MTM.MIN_LEADS) f[4] = m.qp < V.total[li].qp - MTM.GAP_MIN_PTS ? '#b71c1c' : '#1b5e20';
      if (m.cpl !== '' && m.tcpl !== '' && m.cpl > m.tcpl + 0.5) f[5] = '#b71c1c';
      if (m.tp !== '' && m.elig >= MTM.MIN_LEADS) f[7] = m.tp < set.poor * 100 ? '#b71c1c' : (m.tp < set.good * 100 ? '#e65100' : '#1b5e20');
    }
    if (l.gap) {
      row[10] = l.gap.owner; row[11] = l.gap.text;
      const oc = ownerCol[l.gap.owner];
      b[10] = oc[0]; f[10] = oc[1];
      if (l.gap.owner !== 'Too few leads') {
        row[13] = Math.round(l.gap.noCall * 100) / 100;
        row[14] = Math.round(l.gap.tatLoss * 100) / 100;
        row[15] = l.gap.pot === '' ? '' : Math.round(l.gap.pot * 100) / 100;
        row[16] = Math.round(l.gap.lq * 100) / 100;
        f[13] = l.gap.noCall >= MTM.GAP_MIN_PTS ? '#b71c1c' : '#263238';
        f[14] = l.gap.tatLoss >= MTM.GAP_MIN_PTS ? '#b71c1c' : '#263238';
        f[16] = l.gap.lq >= MTM.GAP_MIN_PTS ? '#e65100' : '#263238';
      }
    }
    if (l.type === 'brand') { for (let c = 0; c < NC2; c++) if (c !== 12 && b[c] === '#ffffff') b[c] = '#ede7f6'; }
    if (l.type === 'total') { for (let c = 0; c < NC2; c++) if (c !== 12 && b[c] === '#ffffff') b[c] = '#d1c4e9'; }
    vals.push(row); fonts.push(f); bgs.push(b); bolds.push(isP ? 'normal' : 'bold');
  });
  sh.getRange(first, 1, n, NC2).setValues(vals).setFontColors(fonts).setBackgrounds(bgs)
    .setFontWeights(bolds.map(w => new Array(NC2).fill(w)));
  sh.getRange(first, 1, n, 12).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
  sh.getRange(first, 14, n, 4).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
  sh.getRange(first, 1, n, 1).setFontWeight('bold').setFontColor('#4a148c');
  sh.getRange(first, 3, n, 2).setNumberFormat('#,##0');
  sh.getRange(first, 5, n, 1).setNumberFormat('0.0"%"');
  sh.getRange(first, 6, n, 1).setNumberFormat('#,##0.00');
  sh.getRange(first, 7, n, 1).setNumberFormat('0.0');
  sh.getRange(first, 8, n, 1).setNumberFormat('0.0"%"');
  sh.getRange(first, 9, n, 1).setNumberFormat('#,##0');
  sh.getRange(first, 10, n, 1).setNumberFormat('#,##0.00');
  sh.getRange(first, 14, n, 4).setNumberFormat('0.0');
  sh.getRange(first, 3, n, 8).setHorizontalAlignment('center');
  sh.getRange(first, 11, n, 1).setHorizontalAlignment('center').setFontWeight('bold');
  sh.getRange(first, 12, n, 1).setWrap(true);
  sh.getRange(first, 14, n, 4).setHorizontalAlignment('center');
  [170, 190, 105, 105, 105, 95, 105, 105, 105, 95, 150, 520, 18, 130, 130, 120, 140].forEach((w, i) => sh.setColumnWidth(i + 1, w));
  sh.setFrozenRows(6);

  // ---- regression analysis block
  let r = first + n + 1;
  band(r, '  REGRESSION ANALYSIS  -  Dependent variable: QUALITY (a lead is a Quality Lead = 1, otherwise 0)   |   Independent variable: TAT (working hours to the first call)', '#4a148c', '#ffffff', 11, 30);
  sh.getRange(r + 1, 1, 1, 12).setValues([['Statistic', '', 'Value', 'What it means', '', '', '', '', '', '', '', '']]).setBackground('#546e7a').setFontColor('#ffffff').setFontWeight('bold');
  const pt = v => (v * 100).toFixed(3);
  const sg = p => p < 0.0001 ? '< 0.0001' : p.toFixed(4);
  const regRows = !R || !R.ok ? [['Regression', 'not run', (R && R.note) || 'No regression result.']] : [
    ['Model', 'Linear probability, brand fixed effects', 'Quality = brand effect + beta x TAT. Each brand is compared only with itself, so lead-quality differences between brands are kept out of the TAT effect. Robust standard errors.'],
    ['Leads in the regression / brands', inr_(R.n) + ' / ' + R.groups, 'Called, measured leads of the month (MTD) with a first call attempt. Leads never called have no TAT and are not part of the regression.'],
    ['beta: Quality change per extra working hour of TAT', pt(R.beta) + ' pts', R.beta < 0 ? 'Each extra working hour before the first call lowers the chance that a lead becomes a Quality Lead by ' + pt(-R.beta) + ' percentage points.' : 'Quality does not fall as TAT gets longer (the slope is not negative), so slow calls are not shown to cost Quality in this data.'],
    ['Standard error / t-statistic', pt(R.se) + ' pts / ' + R.t.toFixed(2), 'How precisely beta is measured. A t-statistic beyond about 2 (either sign) is significant at 5%.'],
    ['p-value', sg(R.p), R.sig ? 'Significant at ' + (MTM.REG_ALPHA * 100) + '%: the TAT effect on Quality is real and not chance.' : 'Not significant at ' + (MTM.REG_ALPHA * 100) + '%: the data cannot prove an effect of TAT on Quality; no Sales gap is flagged from the regression.'],
    ['95% confidence interval for beta', pt(R.ci[0]) + ' to ' + pt(R.ci[1]) + ' pts', 'The effect of one extra working hour is expected to lie in this range.'],
    ['R-squared (within brand)', (R.r2w * 100).toFixed(2) + '%', 'Share of the lead-to-lead variation in Quality explained by TAT alone. It is small because Quality depends on many other things (the lead itself, the pitch, the product); a small R-squared does not make a significant beta wrong.'],
    ['Cross-check: pooled slope / R-squared', pt(R.betaP) + ' pts / ' + (R.r2P * 100).toFixed(2) + '%', 'The same regression without the brand adjustment (t = ' + R.tP.toFixed(2) + ', p = ' + sg(R.pP) + '). It should point the same way as beta.'],
    ['Average Quality % / average TAT of these leads', (R.meanQ * 100).toFixed(2) + '% / ' + R.meanT.toFixed(2) + ' hrs', 'Quality share and mean TAT of the leads in the regression.']
  ];
  regRows.forEach((x, i) => {
    const rr = r + 2 + i;
    sh.getRange(rr, 1, 1, 12).setValues([[x[0], '', x[1], x[2], '', '', '', '', '', '', '', '']]).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID).setVerticalAlignment('middle');
    sh.getRange(rr, 1, 1, 2).merge().setFontWeight('bold').setFontColor('#4a148c');
    sh.getRange(rr, 4, 1, 9).merge().setWrap(true).setFontColor('#37474f');
    sh.getRange(rr, 3).setFontWeight('bold').setHorizontalAlignment('center').setWrap(true);
    sh.setRowHeight(rr, 34);
  });
  r = r + 2 + regRows.length + 1;
  if (R && R.ok) {
    band(r, '  QUALITY % BY FIRST-CALL SPEED (called leads, MTD)  -  the same relationship in plain numbers', '#6a1b9a', '#ffffff', 11, 28, 1, 12);
    sh.getRange(r + 1, 1, 1, 4).setValues([['TAT band (working time)', '', 'Called leads', 'Quality %']]).setBackground('#546e7a').setFontColor('#ffffff').setFontWeight('bold');
    R.bands.forEach((bd, i) => {
      sh.getRange(r + 2 + i, 1, 1, 4).setValues([[bd.label, '', bd.n, bd.pct]]).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
      sh.getRange(r + 2 + i, 1, 1, 2).merge().setFontWeight('bold');
      sh.getRange(r + 2 + i, 3).setNumberFormat('#,##0').setHorizontalAlignment('center');
      sh.getRange(r + 2 + i, 4).setNumberFormat('0.0"%"').setHorizontalAlignment('center').setFontWeight('bold');
    });
    r = r + 2 + R.bands.length + 1;
  }

  // ---- notes and checks
  const T = V.tat.stats, crmPerf = V.crmTot, tq = V.total[li] ? V.total[li].q : 0;
  band(r, '  DATA CHECKS AND NOTES', '#455a64', '#ffffff', 11, 26);
  const checks = [
    ['Number of Quality Leads: this tab vs Performance tab (MTD)', tq, V.quality, Math.abs(tq - V.quality) < 0.5 ? 'OK' : 'CHECK'],
    ['Total Number of Leads: this tab vs Performance tab (MTD, Facebook CRM leads)', V.total[li] ? V.total[li].crm : 0, crmPerf, Math.abs((V.total[li] ? V.total[li].crm : 0) - crmPerf) < 0.5 ? 'OK' : 'CHECK'],
    ['TAT source rows read / created in ' + V.cur.label + ' up to the report date', T.rows, T.inMonth, ''],
    ['Leads counted for TAT (Facebook, not Unassigned, brand shown) vs CRM Facebook leads (Performance)', T.counted, crmPerf,
      Math.abs(T.counted - crmPerf) <= Math.max(25, crmPerf * 0.01) ? 'OK (small gap = leads reassigned or added after the Master was pasted)' : 'CHECK: differs by ' + inr_(T.counted - crmPerf)],
    ['TAT leads not matched to a Performance row (leader or brand differs)', T.notMatched, '', T.notMatched <= Math.max(25, crmPerf * 0.01) ? 'OK' : 'CHECK'],
    ['Leads measured for TAT / left out (outside the TAT window; 0 when every lead is measured)', T.eligible, T.outsideWindow, ''],
    ['Measured leads: called / not called although the clock ran out (a miss) / pending (clock not run yet) / first call before creation', T.called, (T.eligible - T.called) + ' / ' + T.pending + ' / ' + T.beforeCreated, ''],
    ['Regression leads vs called leads (should be equal)', R && R.ok ? R.n : 0, T.called, R && R.ok && R.n === T.called ? 'OK' : 'CHECK'],
    ['Portfolio: leads within ' + TATMIN + ' min  |  average TAT (working hrs)', T.eligible > 0 ? p1_(T.within * 100 / T.eligible) + '%' : '-', T.called > 0 ? p1_(T.sumH / T.called) : '-', '']
  ];
  sh.getRange(r + 1, 1, 1, 6).setValues([['Check', '', 'This tab / TAT sheet', 'Compare with', 'Status', '']]).setBackground('#546e7a').setFontColor('#ffffff').setFontWeight('bold');
  checks.forEach((c, i) => {
    const rr = r + 2 + i;
    sh.getRange(rr, 1, 1, 6).setValues([[c[0], '', c[1], c[2], c[3], '']]).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
    sh.getRange(rr, 1, 1, 2).merge().setWrap(true);
    sh.getRange(rr, 3, 1, 2).setNumberFormat('#,##0').setHorizontalAlignment('center');
    sh.getRange(rr, 5, 1, 2).merge().setFontWeight('bold').setFontColor(String(c[3]).indexOf('OK') === 0 ? '#1b5e20' : (String(c[3]).indexOf('CHECK') === 0 ? '#b71c1c' : '#546e7a'));
    sh.setRowHeight(rr, 30);
  });
  const nr = r + 2 + checks.length + 1;
  sh.getRange(nr, 1).setValue('Notes: ALL figures are MTD. Total Number of Leads, Quality Leads and Quality % are the Master CRM_Dump leads of the Performance tab. CPL is the brand CPL from the Master (MTD Brand wise, column D); brand and grand totals use the Meta-lead-weighted average. ' +
    'The regression uses the lead Status in the TAT Source Sheet (a little fresher than the Master paste). It shows an association between slow first calls and lower Quality; it does not by itself prove that faster calls would raise Quality by exactly that amount. ' +
    'Months are saved on every refresh; the month-to-month view is on the MTM-Trends Dashboard.')
    .setFontStyle('italic').setFontColor('#78909c');
}

/* ------------------------------ tab: MTM-Trends Dashboard ------------------------------ */

function mtmWriteDashboard_(out, ctx, set, V) {
  const NCOL = 16, SOLID = SpreadsheetApp.BorderStyle.SOLID;
  const li = V.lastIdx, TATMIN = Math.round(set.tatTarget * 60), R = V.reg;
  const sh = out.getSheetByName(MTM.DASH_TAB) || out.insertSheet(MTM.DASH_TAB);
  sh.getCharts().forEach(c => sh.removeChart(c));
  sh.getRange(1, 1, sh.getMaxRows(), sh.getMaxColumns()).breakApart();
  sh.clear();
  if (sh.getMaxColumns() < NCOL) sh.insertColumnsAfter(sh.getMaxColumns(), NCOL - sh.getMaxColumns());
  if (sh.getMaxRows() < 450) sh.insertRowsAfter(sh.getMaxRows(), 450 - sh.getMaxRows());
  sh.setRowHeights(1, sh.getMaxRows(), 21);
  sh.setHiddenGridlines(true);
  sh.setTabColor('#4a148c');
  sh.setColumnWidths(1, NCOL, 110);
  sh.getRange(1, 1, 450, NCOL).setFontFamily('Roboto').setFontSize(10).setVerticalAlignment('middle').setBackground('#ffffff');
  const band = (row, text, bg, fg, size, height) => {
    sh.getRange(row, 1, 1, NCOL).merge().setValue(text).setBackground(bg).setFontColor(fg).setFontWeight('bold').setFontSize(size)
      .setHorizontalAlignment('left').setVerticalAlignment('middle');
    sh.setRowHeight(row, height);
  };
  const T = V.total[li] || mtmMetrics_([]);
  const gapT = V.lines[V.lines.length - 1].gap || { owner: '-', text: '', loss: 0, noCall: 0, tatLoss: 0, pot: '', lq: 0 };

  band(1, '  MTM-TRENDS DASHBOARD  |  BRAND-WISE: SALES vs PERFORMANCE MARKETING (REGRESSION: QUALITY ~ TAT)', '#4a148c', '#ffffff', 20, 48);
  band(2, '  MTD: ' + V.cur.label + ' (' + V.cur.range + ')   |   Report date: ' + ctx.fmt(ctx.reportDate, 'dd-MMM-yyyy') + '   |   Months shown: ' + V.months.map(m => m.label).join(', ') +
          '   |   Refreshed: ' + ctx.fmt(new Date(), 'dd-MMM-yyyy HH:mm') + '   |   Facebook leads only', '#6a1b9a', '#f3e5f5', 10, 26);
  sh.setRowHeight(3, 10);

  // ---- tiles
  band(4, '  THE BIG PICTURE  -  MTD (month till date)  -  ' + V.cur.label + ', 1st to ' + ctx.fmt(ctx.reportDate, 'd MMM'), '#ede7f6', '#4a148c', 12, 28);
  const cplGood = T.cpl !== '' && T.tcpl !== '' && T.cpl <= T.tcpl + 0.5;
  const regOk = R && R.ok;
  const tiles = [
    { l: 'TOTAL NUMBER OF LEADS', v: T.crm, f: '#,##0', s: 'Facebook CRM leads, MTD', bg: '#2e7d32', c: '#1b5e20' },
    { l: 'QUALITY LEADS', v: T.q, f: '#,##0', s: 'Quality % = Quality x 100 / leads', bg: '#0097a7', c: '#006064' },
    { l: 'QUALITY LEADS %', v: T.qp, f: '0.0"%"', s: gapT.pot !== '' ? 'At target TAT: ' + p1_(gapT.pot) + '%' : '-', bg: '#26a69a', c: '#00695c' },
    { l: 'CPL (Rs)', v: T.cpl, f: '#,##0.00', s: T.tcpl !== '' ? 'Target CPL: Rs ' + inr_(T.tcpl) : 'Master MTD Brand wise, col D', bg: '#ef6c00', c: T.cpl === '' ? '#37474f' : (cplGood ? '#1b5e20' : '#b71c1c') },
    { l: 'AVG TAT (WORKING HRS)', v: T.tat, f: '0.0', s: 'Working hrs ' + mtmHm_(set.workStart) + '-' + mtmHm_(set.workEnd) + ' IST', bg: '#6a1b9a', c: T.tat === '' ? '#37474f' : (T.tat <= set.tatTarget ? '#1b5e20' : '#b71c1c') },
    { l: 'FIRST CALL WITHIN ' + TATMIN + ' MIN', v: T.tp, f: '0.0"%"', s: 'Target: ' + Math.round(set.good * 100) + '% or more', bg: '#8e24aa', c: T.tp === '' ? '#37474f' : (T.tp >= set.good * 100 ? '#1b5e20' : (T.tp >= set.poor * 100 ? '#e65100' : '#b71c1c')) },
    { l: 'EFFECT OF +1 HR TAT ON QUALITY', v: regOk ? R.beta * 100 : '', f: '+0.000" pts";-0.000" pts"', s: regOk ? (R.sig ? 'Significant (p ' + (R.p < 0.0001 ? '< 0.0001' : '= ' + R.p.toFixed(4)) + ')' : 'Not significant (p = ' + R.p.toFixed(3) + ')') : 'Regression not run',
      bg: '#5e35b1', c: !regOk ? '#37474f' : (R.sig && R.negative ? '#b71c1c' : '#546e7a') },
    { l: 'WHO OWNS THE GAP?', v: gapT.owner, f: '@', s: 'Whole portfolio, see below', bg: '#b71c1c', c: gapT.owner === 'On track' ? '#1b5e20' : '#b71c1c' }
  ];
  tiles.forEach((k, i) => {
    const c = 1 + i * 2;
    sh.getRange(5, c, 1, 2).merge().setValue(k.l).setBackground(k.bg).setFontColor('#ffffff').setFontWeight('bold').setFontSize(9).setHorizontalAlignment('center');
    sh.getRange(6, c, 1, 2).merge().setValue(k.v === '' ? '-' : k.v).setNumberFormat(k.f).setBackground('#fafafa')
      .setFontSize(k.f === '@' ? 14 : 22).setFontWeight('bold').setFontColor(k.c).setHorizontalAlignment('center');
    sh.getRange(7, c, 1, 2).merge().setValue(k.s).setBackground('#fafafa').setFontSize(9).setFontColor('#546e7a').setHorizontalAlignment('center');
    sh.getRange(5, c, 3, 2).setBorder(true, true, true, true, false, false, '#cfd8dc', SOLID);
  });
  sh.setRowHeight(5, 24); sh.setRowHeight(6, 46); sh.setRowHeight(7, 24); sh.setRowHeight(8, 10);

  // ---- scorecard
  band(9, '  WHERE IS THE GAP?  PERFORMANCE MARKETING vs SALES  (regression-based)', '#fff3e0', '#e65100', 12, 28);
  const hdr = ['Side', '', 'What is measured', '', '', 'Actual', 'Target / benchmark', 'Gap', 'Verdict', '', '', '', '', '', '', ''];
  sh.getRange(10, 1, 1, NCOL).setValues([hdr]).setBackground('#37474f').setFontColor('#ffffff').setFontWeight('bold').setHorizontalAlignment('center');
  const metaAch = V.target > 0 ? V.metaTot * 100 / V.target : '';
  const wc = V.brandRows.filter(b => b.m[li] && b.m[li].cpl !== '' && b.m[li].tcpl !== '');
  const brandOver = wc.filter(b => b.m[li].cpl > b.m[li].tcpl + 0.5);
  const judgedB = V.brandRows.filter(b => b.gap && b.gap.owner !== 'Too few leads');
  const salesB = judgedB.filter(b => b.gap.owner === 'Sales' || b.gap.owner === 'Both');
  const lqB = judgedB.filter(b => b.gap.lq >= MTM.GAP_MIN_PTS);
  const verdict = (ok, goodTxt, badTxt) => ok === null ? 'Not enough data' : (ok ? goodTxt : badTxt);
  const score = [
    ['PERFORMANCE MARKETING', 'Meta lead achievement % (Meta leads / Lead Target)', metaAch, 100, metaAch === '' ? '' : metaAch - 100, '0.0"%"', verdict(metaAch === '' ? null : metaAch >= 100, 'Target met', 'Below target by ' + (metaAch === '' ? '' : p1_(100 - metaAch)) + ' pts')],
    ['PERFORMANCE MARKETING', 'CPL (Rs) vs Target CPL (weighted by Meta leads)', T.cpl, T.tcpl, T.cpl === '' || T.tcpl === '' ? '' : T.cpl - T.tcpl, '#,##0.00', verdict(T.cpl === '' || T.tcpl === '' ? null : T.cpl <= T.tcpl + 0.5, 'CPL within target', 'CPL above target')],
    ['PERFORMANCE MARKETING', 'Brands with CPL above target', brandOver.length, 0, brandOver.length, '0', wc.length ? brandOver.length + ' of ' + wc.length + ' brands above target' : 'Not enough data'],
    ['PERFORMANCE MARKETING', 'Brands whose leads are weaker than the portfolio at equal call speed', lqB.length, 0, lqB.length, '0', judgedB.length ? lqB.length + ' of ' + judgedB.length + ' brands (lead-quality gap of ' + p1_(MTM.GAP_MIN_PTS) + ' pts or more)' : 'Not enough data'],
    ['SALES', 'First calls within ' + TATMIN + ' min %', T.tp, set.good * 100, T.tp === '' ? '' : T.tp - set.good * 100, '0.0"%"', verdict(T.tp === '' ? null : T.tp >= set.good * 100, 'Target met', 'Far below target (poor below ' + Math.round(set.poor * 100) + '%)')],
    ['SALES', 'Average TAT (working hours) vs target', T.tat, set.tatTarget, T.tat === '' ? '' : T.tat - set.tatTarget, '0.0', verdict(T.tat === '' ? null : T.tat <= set.tatTarget, 'Within target', 'Slower than target')],
    ['SALES', 'Quality points lost to leads never called + slow first calls', gapT.loss, 0, gapT.loss, '0.0" pts"', gapT.pot !== '' ? 'Quality ' + p1_(T.qp) + '% could be ' + p1_(gapT.pot) + '%: ' + p1_(gapT.noCall) + ' pts never called, ' + p1_(gapT.tatLoss) + ' pts slow TAT' + (regOk && !R.sig ? ' (TAT effect not significant)' : '') : 'Not enough data'],
    ['SALES', 'Brands where Sales costs Quality (Sales gap)', salesB.length, 0, salesB.length, '0', judgedB.length ? salesB.length + ' of ' + judgedB.length + ' brands (loss of ' + p1_(MTM.GAP_MIN_PTS) + ' pts or more)' : 'Not enough data']
  ];
  score.forEach((s, i) => {
    const r = 11 + i;
    sh.getRange(r, 1, 1, NCOL).setValues([[s[0], '', s[1], '', '', s[2], s[3], s[4], s[6], '', '', '', '', '', '', '']]).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
    sh.getRange(r, 1, 1, 2).merge().setFontWeight('bold').setFontColor(s[0].indexOf('SALES') === 0 ? '#b71c1c' : '#e65100');
    sh.getRange(r, 3, 1, 3).merge();
    sh.getRange(r, 6, 1, 3).setNumberFormat(s[5]).setHorizontalAlignment('center').setFontWeight('bold');
    sh.getRange(r, 9, 1, 8).merge().setFontColor('#37474f');
    sh.setRowHeight(r, 26);
  });
  sh.setRowHeight(11 + score.length, 10);

  // ---- insights
  const ins = mtmInsights_(V, set, TATMIN, brandOver, salesB, lqB);
  const INS_TOP = 11 + score.length + 1;
  band(INS_TOP, '  KEY INSIGHTS AT A GLANCE', '#fff8e1', '#e65100', 12, 28);
  const INS_ROWS = 8;
  ins.slice(0, INS_ROWS).forEach((it, i) => {
    sh.getRange(INS_TOP + 1 + i, 1, 1, NCOL).merge().setValue('  ' + it.t).setFontColor(it.c).setWrap(true).setHorizontalAlignment('left')
      .setBackground(i % 2 ? '#ffffff' : '#fafafa');
    sh.setRowHeight(INS_TOP + 1 + i, 32);
  });
  const CH_TOP = INS_TOP + INS_ROWS + 2;
  sh.setRowHeight(CH_TOP - 1, 10);
  band(CH_TOP, '  CHARTS', '#e8eaf6', '#283593', 12, 28);
  const CH1 = CH_TOP + 1, CH2 = CH1 + 19, CH3 = CH2 + 19, CH4 = CH3 + 19;
  const hasTrend = V.months.length >= 2;
  const TABLES_TOP = (hasTrend ? CH4 + 19 : CH3 + 19) + 1;

  // ---- tables (the charts read these)
  const tbl = (startRow, title, bg, hdrCells, dataRows, fmts) => {
    band(startRow, '  ' + title, bg, '#ffffff', 12, 30);
    const h = startRow + 1;
    sh.getRange(h, 1, 1, hdrCells.length).setValues([hdrCells]).setBackground('#37474f').setFontColor('#ffffff').setFontWeight('bold').setHorizontalAlignment('center').setWrap(true);
    sh.getRange(h, 1).setHorizontalAlignment('left');
    sh.setRowHeight(h, 40);
    const n = dataRows.length;
    if (n) {
      sh.getRange(h + 1, 1, n, hdrCells.length).setValues(dataRows).setBorder(true, true, true, true, true, true, '#cfd8dc', SOLID);
      fmts.forEach((f, j) => { if (f) sh.getRange(h + 1, j + 1, n, 1).setNumberFormat(f); });
      sh.getRange(h + 1, 1, n, 1).setFontWeight('bold').setFontColor('#4a148c');
      sh.getRange(h + 1, 2, n, hdrCells.length - 1).setHorizontalAlignment('center');
    }
    return { hdrRow: h, n: n, next: h + n + 2 };
  };
  const r2 = v => v === '' || v === undefined ? '' : Math.round(v * 100) / 100;
  const gapSize = b => (b.gap ? b.gap.loss + b.gap.lq : 0);
  const brandSorted = V.brandRows.filter(b => b.m[li] && b.m[li].crm > 0).sort((a, b) => gapSize(b) - gapSize(a) || a.name.localeCompare(b.name));
  const t1 = tbl(TABLES_TOP, 'BRAND VIEW  -  MTD ' + V.cur.label + '  (biggest gap at the top)', '#1565c0',
    ['Brand', 'Total Number of Leads', 'Quality Leads', 'Quality Leads %', 'CPL (Rs)', 'Target CPL (Rs)', 'TAT (avg working hrs)', 'TAT within ' + TATMIN + ' min %', 'Quality lost: leads never called (pts)', 'Quality lost: slow TAT (pts)', 'Lead-quality gap (pts)', 'Quality at target TAT (%)', 'Gap Owner'],
    brandSorted.map(b => { const m = b.m[li]; return [b.name, m.crm, m.q, m.qp, r2(m.cpl), r2(m.tcpl), r2(m.tat), m.tp, r2(b.gap.noCall), r2(b.gap.tatLoss), r2(b.gap.lq), r2(b.gap.pot), b.gap.owner]; }),
    [null, '#,##0', '#,##0', '0.0"%"', '#,##0.00', '#,##0.00', '0.0', '0.0"%"', '0.00', '0.00', '0.00', '0.0"%"', null]);
  const leaderSorted = V.leaderRows.filter(l => l.m[li] && l.m[li].crm > 0).sort((a, b) => gapSize(b) - gapSize(a) || a.name.localeCompare(b.name));
  const t2 = tbl(t1.next, 'SALES LEADER VIEW  -  MTD ' + V.cur.label + '  (biggest gap at the top)', '#00838f',
    ['Sales Leader', 'Total Number of Leads', 'Quality Leads', 'Quality Leads %', 'CPL (Rs)', 'TAT (avg working hrs)', 'TAT within ' + TATMIN + ' min %', 'Quality lost: leads never called (pts)', 'Quality lost: slow TAT (pts)', 'Quality at target TAT (%)', 'Gap Owner'],
    leaderSorted.map(l => { const m = l.m[li]; return [l.name, m.crm, m.q, m.qp, r2(m.cpl), r2(m.tat), m.tp, r2(l.gap.noCall), r2(l.gap.tatLoss), r2(l.gap.pot), l.gap.owner]; }),
    [null, '#,##0', '#,##0', '0.0"%"', '#,##0.00', '0.0', '0.0"%"', '0.00', '0.00', '0.0"%"', null]);
  const bandRows = regOk ? R.bands.map(b => [b.label, b.n, b.q, b.pct]) : [];
  const t3 = tbl(t2.next, 'REGRESSION EVIDENCE  -  Quality % by first-call TAT band (called leads, MTD)', '#5e35b1',
    ['TAT band (working time)', 'Called leads', 'Quality leads', 'Quality %'], bandRows, [null, '#,##0', '#,##0', '0.0"%"']);
  const regSummary = regOk ? [
    ['Leads / brands in the regression', inr_(R.n) + ' / ' + R.groups],
    ['beta: Quality change per extra working hour', (R.beta * 100).toFixed(3) + ' pts'],
    ['Standard error (robust) / t', (R.se * 100).toFixed(3) + ' pts / ' + R.t.toFixed(2)],
    ['p-value (significant if below ' + MTM.REG_ALPHA + ')', R.p < 0.0001 ? '< 0.0001' : R.p.toFixed(4)],
    ['95% confidence interval', (R.ci[0] * 100).toFixed(3) + ' to ' + (R.ci[1] * 100).toFixed(3) + ' pts'],
    ['R-squared (within brand)', (R.r2w * 100).toFixed(2) + '%'],
    ['Pooled slope (no brand adjustment)', (R.betaP * 100).toFixed(3) + ' pts (p ' + (R.pP < 0.0001 ? '< 0.0001' : '= ' + R.pP.toFixed(4)) + ')']
  ] : [['Regression', (R && R.note) || 'not run']];
  const t4 = tbl(t3.next, 'REGRESSION SUMMARY  -  Dependent variable: Quality (1/0)  |  Independent variable: TAT (working hours)', '#4a148c',
    ['Statistic', 'Value'], regSummary, [null, null]);
  sh.getRange(t4.hdrRow + 1, 2, t4.n, 1).setHorizontalAlignment('left');
  const mm = V.months.map((m, i) => { const x = V.total[i] || mtmMetrics_([]); return [m.label + (m.range ? ' (' + m.range + ')' : ''), x.crm, x.q, x.qp, r2(x.cpl), r2(x.tat), x.tp, m.reg ? r2(m.reg.beta * 100) : '']; });
  const t5 = tbl(t4.next, 'MONTH-TO-MONTH (MTD)  -  whole portfolio', '#6a1b9a',
    ['Month (MTD)', 'Total Number of Leads', 'Quality Leads', 'Quality Leads %', 'CPL (Rs)', 'TAT (avg working hrs)', 'TAT within ' + TATMIN + ' min %', 'TAT effect on Quality (pts per hour)'], mm,
    [null, '#,##0', '#,##0', '0.0"%"', '#,##0.00', '0.0', '0.0"%"', '0.000']);
  sh.getRange(t5.next - 1 + 1, 1).setValue('Each refresh saves the month. When the Master starts a new month, it is added here and the trend lines appear.')
    .setFontStyle('italic').setFontColor('#78909c');

  // ---- Gap Owner colours
  const ownerColor = o => ({ 'Sales': ['#ffcdd2', '#b71c1c'], 'Performance Marketing': ['#ffe0b2', '#e65100'], 'Both': ['#ef9a9a', '#7f0000'],
                             'On track': ['#c8e6c9', '#1b5e20'], 'Too few leads': ['#eceff1', '#546e7a'] }[o] || ['#ffffff', '#263238']);
  [[t1, brandSorted, 13], [t2, leaderSorted, 11]].forEach(x => {
    if (!x[0].n) return;
    const g = x[1].map(e => (e.gap ? e.gap.owner : ''));
    sh.getRange(x[0].hdrRow + 1, x[2], x[0].n, 1).setBackgrounds(g.map(o => [ownerColor(o)[0]])).setFontColors(g.map(o => [ownerColor(o)[1]])).setFontWeight('bold');
  });

  // ---- charts
  const addChart = (type, title, ranges, row, col, colors, extra) => {
    let b = sh.newChart().setChartType(type);
    ranges.forEach(rg => { b = b.addRange(rg); });
    b = b.setNumHeaders(1).setPosition(row, col, 0, 0).setOption('title', title).setOption('width', 876).setOption('height', 380)
         .setOption('legend', { position: 'top' }).setOption('colors', colors).setOption('titleTextStyle', { fontSize: 14, bold: true });
    if (extra) Object.keys(extra).forEach(k => { b = b.setOption(k, extra[k]); });
    sh.insertChart(b.build());
  };
  const col = (t, c) => sh.getRange(t.hdrRow, c, t.n + 1, 1);
  if (t3.n > 0) addChart(Charts.ChartType.COLUMN, 'Regression evidence: Quality % falls as the first call gets slower', [col(t3, 1), col(t3, 4)], CH1, 1, ['#5e35b1'], { legend: { position: 'none' } });
  if (t1.n > 0) {
    addChart(Charts.ChartType.COLUMN, 'Brand gap in Quality pts: Sales (never called, slow TAT) vs Performance Marketing (lead quality)', [col(t1, 1), col(t1, 9), col(t1, 10), col(t1, 11)], CH1, 9, ['#c62828', '#ef5350', '#fb8c00'], { isStacked: true });
    addChart(Charts.ChartType.BAR, 'Brand: first calls within ' + TATMIN + ' min %', [col(t1, 1), col(t1, 8)], CH2, 1, ['#8e24aa'], { reverseCategories: true, legend: { position: 'none' } });
    addChart(Charts.ChartType.COLUMN, 'Brand: CPL vs Target CPL (Rs)', [col(t1, 1), col(t1, 5), col(t1, 6)], CH2, 9, ['#ef6c00', '#bdbdbd']);
    addChart(Charts.ChartType.COLUMN, 'Brand: Quality % today vs Quality % if first calls met the target', [col(t1, 1), col(t1, 4), col(t1, 12)], CH3, 1, ['#26a69a', '#80cbc4']);
  }
  if (t2.n > 0) addChart(Charts.ChartType.BAR, 'Sales Leader: Quality points lost (never called + slow TAT)', [col(t2, 1), col(t2, 8), col(t2, 9)], CH3, 9, ['#c62828', '#ef5350'], { reverseCategories: true, isStacked: true });
  if (hasTrend) {
    addChart(Charts.ChartType.LINE, 'Month-to-month: Quality Leads % and first calls within ' + TATMIN + ' min %', [col(t5, 1), col(t5, 4), col(t5, 7)], CH4, 1, ['#26a69a', '#8e24aa'], { curveType: 'function' });
    addChart(Charts.ChartType.LINE, 'Month-to-month: CPL (Rs) and average TAT (hrs)', [col(t5, 1), col(t5, 5), col(t5, 6)], CH4, 9, ['#ef6c00', '#6a1b9a'], { curveType: 'function' });
  } else {
    sh.getRange(CH4, 1, 1, NCOL).merge().setValue('  Month-to-month trend lines appear here automatically from the second month (only ' + V.cur.label + ' is available today).')
      .setFontStyle('italic').setFontColor('#78909c').setBackground('#fafafa');
  }
}

/** Plain-language insights, most important first. Colour: red problem, orange watch, green good, blue info. */
function mtmInsights_(V, set, TATMIN, brandOver, salesB, lqB) {
  const li = V.lastIdx, T = V.total[li], R = V.reg;
  const out = [];
  if (!T) return [{ t: 'No data for the latest month.', c: '#546e7a' }];
  const g = V.lines[V.lines.length - 1].gap;
  const regOk = R && R.ok;
  const topN = (arr, f, k) => arr.slice().sort((a, b) => f(b) - f(a)).slice(0, k);
  // 1. verdict
  const cplOver = T.cpl !== '' && T.tcpl !== '' && T.cpl > T.tcpl + 0.5;
  if (g.loss >= MTM.GAP_MIN_PTS && g.pot !== '') {
    out.push({ c: '#b71c1c', t: (cplOver ? 'The gap is on BOTH sides, led by SALES. ' : 'The gap is on the SALES side. ') + 'Leads that are never called (' + p1_(g.noCall) + ' Quality pts) and slow first calls (average TAT ' + p1_(T.tat) + ' working hrs against a ' + p1_(set.tatTarget) + ' hr target, ' + p1_(g.tatLoss) +
      ' pts) cost about ' + p1_(g.loss) + ' Quality points: Quality is ' + p1_(T.qp) + '% and would be about ' + p1_(g.pot) + '% if every lead were called within the target. ' + (cplOver ? 'CPL is Rs ' + inr_(T.cpl) + ' against Rs ' + inr_(T.tcpl) + '.' : 'CPL (Rs ' + inr_(T.cpl) + ') is within the Rs ' + inr_(T.tcpl) + ' target, so the leads are bought at the right price.') });
  } else if (cplOver) {
    out.push({ c: '#e65100', t: 'The gap is on the PERFORMANCE MARKETING side: CPL is Rs ' + inr_(T.cpl) + ' against a target of Rs ' + inr_(T.tcpl) + (regOk && R.sig ? '' : '; the regression could not show a significant TAT effect on Quality.') });
  } else {
    out.push({ c: '#1b5e20', t: 'No big portfolio-level gap: CPL is within target and slow TAT costs less than ' + p1_(MTM.GAP_MIN_PTS) + ' Quality point.' });
  }
  // 2. regression result
  if (regOk) {
    out.push({ c: '#5e35b1', t: 'Regression (Quality on TAT, ' + inr_(R.n) + ' called leads, brand-adjusted): each extra working hour before the first call changes the chance of a Quality Lead by ' + (R.beta * 100).toFixed(3) + ' points (p ' +
      (R.p < 0.0001 ? '< 0.0001' : '= ' + R.p.toFixed(4)) + ', 95% range ' + (R.ci[0] * 100).toFixed(3) + ' to ' + (R.ci[1] * 100).toFixed(3) + '). ' + (R.sig ? 'The effect is statistically significant.' : 'The effect is not statistically significant.') });
    const b0 = R.bands[0], bl = R.bands[R.bands.length - 1];
    if (b0.n > 0 && bl.n > 0) out.push({ c: '#6a1b9a', t: 'In plain numbers: leads called within ' + TATMIN + ' minutes become Quality Leads ' + p1_(b0.pct) + '% of the time (' + inr_(b0.n) + ' leads); leads first called after more than 16 working hours only ' + p1_(bl.pct) + '% of the time (' + inr_(bl.n) + ' leads).' });
  } else {
    out.push({ c: '#546e7a', t: 'The regression could not be run: ' + ((R && R.note) || 'no result') });
  }
  // 3. sales brands
  const sb = topN(V.brandRows.filter(b => b.gap && b.gap.owner !== 'Too few leads'), b => b.gap.loss, 3).filter(b => b.gap.loss >= MTM.GAP_MIN_PTS);
  if (sb.length) out.push({ c: '#b71c1c', t: 'Largest Sales gap (Quality points lost to leads never called and slow TAT): ' + sb.map(b => b.name + ' ' + p1_(b.gap.loss) + ' pts (never called ' + p1_(b.gap.noCall) + ', slow TAT ' + p1_(b.gap.tatLoss) + '; avg TAT ' + p1_(b.m[li].tat) + ' hrs)').join(', ') + '. ' + salesB.length + ' brand(s) lose at least ' + p1_(MTM.GAP_MIN_PTS) + ' pt.' });
  // 4. marketing: lead quality
  const lb = topN(lqB, b => b.gap.lq, 3);
  if (lb.length) out.push({ c: '#e65100', t: 'Weakest leads at equal call speed and coverage (Performance Marketing): ' + lb.map(b => b.name + ' ' + p1_(b.gap.lq) + ' pts below the portfolio').join(', ') + '.' });
  // 5. CPL
  if (brandOver.length) {
    const top = topN(brandOver, b => b.m[li].cpl - b.m[li].tcpl, 3).map(b => b.name + ' (Rs ' + inr_(b.m[li].cpl) + ' vs Rs ' + inr_(b.m[li].tcpl) + ')').join(', ');
    out.push({ c: '#e65100', t: 'Brands with CPL above target: ' + top + (brandOver.length > 3 ? ' and ' + (brandOver.length - 3) + ' more.' : '.') });
  }
  // 6. leaders
  const lr = V.leaderRows.filter(l => l.gap && l.gap.owner !== 'Too few leads' && l.m[li].elig >= MTM.MIN_LEADS && l.m[li].tp !== '');
  if (lr.length > 1) {
    const w = lr.slice().sort((a, b) => a.m[li].tp - b.m[li].tp)[0], bst = lr.slice().sort((a, b) => b.m[li].tp - a.m[li].tp)[0];
    out.push({ c: '#00695c', t: 'First calls within ' + TATMIN + ' min by Sales Leader: lowest ' + w.name + ' (' + p1_(w.m[li].tp) + '%, average TAT ' + p1_(w.m[li].tat) + ' hrs), highest ' + bst.name + ' (' + p1_(bst.m[li].tp) + '%, average TAT ' + p1_(bst.m[li].tat) + ' hrs).' });
  }
  // 7. data note
  const st = V.tat.stats;
  out.push({ c: '#1565c0', t: 'Data note: all figures are MTD. TAT counts only working time (' + mtmHm_(set.workStart) + '-' + mtmHm_(set.workEnd) + ' IST, no Sundays): ' + mtmWinTxt_(set) + '. ' + inr_(st.eligible) + ' of ' + inr_(st.counted) +
    ' leads are measured; ' + inr_(st.pending) + ' not-yet-called leads are pending. The regression shows an association between slow first calls and lower Quality; it is strong evidence but does not by itself prove the exact gain from faster calls.' });
  return out;
}

/* ------------------------------ tab order ------------------------------ */

/** Puts the two MTM tabs right after the Performance tabs; does not touch those tabs. */
function mtmOrderTabs_(out) {
  const a = out.getSheetByName(MTM.TAB), b = out.getSheetByName(MTM.DASH_TAB);
  const base = [CFG.OUT_TAB, CFG.FTD_TAB, CFG.DASH_TAB, CFG.BRAND_TAB].filter(n => out.getSheetByName(n)).length;
  if (a) { out.setActiveSheet(a); out.moveActiveSheet(base + 1); }
  if (b) { out.setActiveSheet(b); out.moveActiveSheet(base + 2); }
  if (b) out.setActiveSheet(b);
}
