#!/usr/bin/env python3
"""Build the Campaign / Ad Set / Ad performance workbook (MTD + FTD) from exports.

Inputs (CSV, or .xlsx with the first sheet used):
  --campaigns   Meta Ads Manager campaign export
  --adsets      Meta Ads Manager ad set export  (needs a "Parent Campaign" column)
  --ads         Meta Ads Manager ad export      (needs "Ad set name" and "Parent Campaign")
  --crm         CRM leads already mapped to Meta ads (Lead Date, Mapped Campaign (LeadChain),
                Mapped Ad Set (LeadChain), Mapped Ad (LeadChain), Lead Status, Qualified (1/0))
  --meetings    (optional) meetings: Mapped Campaign/Ad Set/Ad (LeadChain), Meeting Date (value)

Example:
  python meta_ads_report.py --campaigns c.csv --adsets a.csv --ads ad.csv --crm crm.csv \\
      --meetings m.csv --client "DAEWOO × SHOOTORDER" --currency INR \\
      --mtd-start 2026-10-01 --mtd-end 2026-10-18 --ftd-start 2026-10-17 --ftd-end 2026-10-18
"""
import argparse
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}
NAVY, TEAL, GOLD, GREY, TOTAL_FILL, SUB_FILL = "1F3864", "0E7C7B", "BF8F00", "404040", "FCE4B4", "D9E2F3"
UNMAPPED = "Not mapped to a campaign"
INSIGHT_ICONS = ["🔎", "📈", "🏆", "⭐", "⚠️", "🎯", "🤝", "💰", "📊"]


# ---------------------------------------------------------------- loading
def read_any(path):
    if str(path).lower().endswith((".xlsx", ".xlsm")):
        return pd.read_excel(path)
    return pd.read_csv(path, encoding="utf-8-sig", on_bad_lines="skip")


def spend_col(df):
    for c in df.columns:
        if c.lower().startswith("amount spent"):
            return c
    sys.exit("error: no 'Amount spent' column found")


def num(df, cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0) if c in df.columns else 0.0


def load_meta(path):
    df = read_any(path)
    sc = spend_col(df)
    df = df.rename(columns={sc: "Spend", "Cost per results": "Cost per result"})
    num(df, ["Spend", "Impressions", "Reach", "Link clicks", "Results"])
    return df


def load_crm(path, start, end):
    df = read_any(path).rename(columns={
        "Mapped Campaign (LeadChain)": "campaign", "Mapped Ad Set (LeadChain)": "adset",
        "Mapped Ad (LeadChain)": "ad", "Qualified (1/0)": "qualified", "Lead Date": "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"])
    df["qualified"] = pd.to_numeric(df["qualified"], errors="coerce").fillna(0)
    for c in ("campaign", "adset", "ad"):
        df[c] = df[c].fillna(UNMAPPED)
    return df[(df["date"] >= start) & (df["date"] <= end)]


def load_meetings(path, start, end):
    if not path:
        return pd.DataFrame(columns=["campaign", "adset", "ad", "date"])
    df = read_any(path).rename(columns={
        "Mapped Campaign (LeadChain)": "campaign", "Mapped Ad Set (LeadChain)": "adset",
        "Mapped Ad (LeadChain)": "ad", "Meeting Date (value)": "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    for c in ("campaign", "adset", "ad"):
        df[c] = df[c].fillna(UNMAPPED)
    return df[(df["date"] >= start) & (df["date"] <= end)]


def count(df, **eq):
    m = pd.Series(True, index=df.index)
    for k, v in eq.items():
        m &= df[k] == v
    return int(m.sum())


def qual(df, **eq):
    m = pd.Series(True, index=df.index)
    for k, v in eq.items():
        m &= df[k] == v
    return int(df.loc[m, "qualified"].sum())


def div(a, b):
    return a / b if b else None


# ---------------------------------------------------------------- sheet writer
class Sheet:
    def __init__(self, ws, cur):
        self.ws, self.r, self.cur = ws, 1, cur
        self.money = f'"{cur}"#,##0'
        self.money2 = f'"{cur}"#,##0.00'

    def fill(self, c, color):
        c.fill = PatternFill("solid", fgColor=color)

    def banner(self, text, color, size=12, ncols=26, height=None):
        c = self.ws.cell(self.r, 1, text)
        c.font = Font(name="Calibri", size=size, bold=True, color="FFFFFF")
        for i in range(1, ncols + 1):
            self.fill(self.ws.cell(self.r, i), color)
        c.alignment = Alignment(horizontal="left", vertical="center")
        if height:
            self.ws.row_dimensions[self.r].height = height
        self.r += 1

    def note(self, text, ncols=26, height=45):
        self.ws.merge_cells(start_row=self.r, start_column=1, end_row=self.r, end_column=ncols)
        c = self.ws.cell(self.r, 1, text)
        c.font = Font(size=9, italic=True)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        self.ws.row_dimensions[self.r].height = height
        self.r += 1

    def header(self, labels):
        for i, t in enumerate(labels, 1):
            c = self.ws.cell(self.r, i, t)
            c.font = Font(size=9, bold=True, color="FFFFFF")
            self.fill(c, NAVY)
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        self.ws.row_dimensions[self.r].height = 36
        self.r += 1

    def row(self, values, fmts, kind="data", bold_cols=(1,)):
        for i, v in enumerate(values, 1):
            c = self.ws.cell(self.r, i, "n/a" if v is None else v)
            c.font = Font(size=9, bold=(kind != "data") or i in bold_cols)
            c.alignment = Alignment(horizontal="left" if i in bold_cols else "center", vertical="center")
            if fmts[i - 1] and v is not None:
                c.number_format = fmts[i - 1]
            if kind == "total":
                self.fill(c, TOTAL_FILL)
            elif kind == "sub":
                self.fill(c, SUB_FILL)
        self.r += 1

    def kpis(self, items):
        """items: [(label, value)], each tile 4 columns wide."""
        for k, (label, value) in enumerate(items):
            col = 1 + 4 * (k % 7)
            row = self.r + 3 * (k // 7)
            for r_off, text, fnt, color in ((0, label, Font(size=8, bold=True, color="FFFFFF"), GREY),
                                            (1, value, Font(size=14, bold=True, color=NAVY), SUB_FILL)):
                self.ws.merge_cells(start_row=row + r_off, start_column=col, end_row=row + r_off, end_column=col + 3)
                c = self.ws.cell(row + r_off, col, text)
                c.font, c.alignment = fnt, Alignment(horizontal="center", vertical="center")
                for i in range(col, col + 4):
                    self.fill(self.ws.cell(row + r_off, i), color)
            self.ws.row_dimensions[row + 1].height = 26
        self.r += 3 * ((len(items) - 1) // 7 + 1) + 1


def fmt_money(cur, v, d=0):
    return "n/a" if v is None else f"{cur}{v:,.{d}f}"


def pct(v, d=1):
    return "n/a" if v is None else f"{v * 100:.{d}f}%"


# ---------------------------------------------------------------- report
def build(args):
    start, end = pd.Timestamp(args.mtd_start), pd.Timestamp(args.mtd_end)
    fstart, fend = pd.Timestamp(args.ftd_start or args.mtd_end), pd.Timestamp(args.ftd_end or args.mtd_end)
    cur = SYMBOLS.get(args.currency.upper(), args.currency + " ")
    camps, sets, ads = load_meta(args.campaigns), load_meta(args.adsets), load_meta(args.ads)
    crm = load_crm(args.crm, start, end)
    mtg = load_meetings(args.meetings, start, end)
    crm_f = crm[(crm["date"] >= fstart) & (crm["date"] <= fend)]
    mtg_f = mtg[(mtg["date"] >= fstart) & (mtg["date"] <= fend)]

    # campaigns with no spend, impressions or results carry no data: leave them out
    camps = camps[(camps["Spend"] > 0) | (camps["Impressions"] > 0) | (camps["Results"] > 0)].reset_index(drop=True)
    keep = set(camps["Campaign name"])
    sets = sets[sets["Parent Campaign"].isin(keep)].reset_index(drop=True)
    ads = ads[ads["Parent Campaign"].isin(keep)].reset_index(drop=True)
    total_mtg = len(mtg)

    wb = Workbook()
    ws = wb.active
    ws.title = "Campaign Report"
    ws.sheet_view.showGridLines = False
    S = Sheet(ws, cur)
    M, M2, P, I = S.money, S.money2, "0.0%", "#,##0"

    # ---- title + snapshot
    S.banner(f"{args.client.upper()} — CAMPAIGN, AD SET & AD-WISE PERFORMANCE REPORT", NAVY, 16, height=28)
    S.banner(f"MTD: {start:%d %b %Y} – {end:%d %b %Y}   |   FTD: {fstart:%d %b} – {fend:%d %b %Y}   |   "
             f"Currency: {args.currency}   |   Attribution: Meta Lead Ads → CRM join", GREY, 10)
    S.r += 1
    spend, imps, reach = camps["Spend"].sum(), camps["Impressions"].sum(), camps["Reach"].sum()
    clicks, results = camps["Link clicks"].sum(), camps["Results"].sum()
    leads, qd = len(crm), int(crm["qualified"].sum())
    S.banner(f"{end:%B %Y} — PERFORMANCE SNAPSHOT   (MTD {start:%d}–{end:%d %b}  ·  FTD {fstart:%d}–{fend:%d %b})", GOLD, ncols=28)
    S.kpis([("MTD SPEND", fmt_money(cur, spend)), ("MTD LEADS / RESULTS (META)", f"{results:,.0f}"),
            ("BLENDED CPL (per CRM Lead)", fmt_money(cur, div(spend, leads))),
            ("MTD IMPRESSIONS", f"{imps:,.0f}"), ("MTD REACH", f"{reach:,.0f}"),
            ("MTD CTR", pct(div(clicks, imps), 2)), ("MTD CPQL", fmt_money(cur, div(spend, qd))),
            ("TOTAL CRM LEADS (MTD)", f"{leads:,}"), ("QUALIFIED LEADS (CRM, MTD)", f"{qd:,}"),
            ("MEETINGS SCHEDULED (total)", f"{total_mtg:,}"), ("FTD — CRM LEADS", f"{len(crm_f):,}")])

    # ---- 1. campaigns MTD
    S.banner(f"1.  CAMPAIGN-WISE PERFORMANCE  —  MTD ({start:%d %b} – {end:%d %b %Y})", TEAL)
    S.header(["Reporting starts", "Reporting ends", "Campaign name", "Campaign delivery", "Results", "Result indicator",
              "Cost per result", "Ad set budget", "Ad set budget type", f"Amount spent ({args.currency})", "Impressions",
              "Reach", "Ends", "Attribution setting", "CRM Leads", "Qualified Leads", "Qualified Lead %",
              "Meetings Scheduled", "Meeting Scheduled %", "Link Clicks", "CTR", "CPQL"])
    fm = [None, None, None, None, I, None, M, None, None, M2, I, I, None, None, I, I, P, I, P, I, "0.00%", M]
    camp_rows = {}
    for _, r in camps.iterrows():
        n = r["Campaign name"]
        l, q, m = count(crm, campaign=n), qual(crm, campaign=n), count(mtg, campaign=n)
        camp_rows[n] = dict(leads=l, qd=q, mtg=m)
        S.row([r.get("Reporting starts"), r.get("Reporting ends"), n, r.get("Campaign delivery"), r["Results"],
               r.get("Result indicator"), div(r["Spend"], r["Results"]), r.get("Ad set budget"),
               r.get("Ad set budget type"), r["Spend"], r["Impressions"], r["Reach"], r.get("Ends"),
               r.get("Attribution setting"), l, q, div(q, l), m, div(m, l), r["Link clicks"],
               div(r["Link clicks"], r["Impressions"]), div(r["Spend"], q)], fm, bold_cols=(3,))
    S.row([None, None, "TOTAL / BLENDED AVERAGE", None, results, None, div(spend, results), None, None, spend, imps,
           reach, None, None, leads, qd, div(qd, leads), sum(v["mtg"] for v in camp_rows.values()),
           div(sum(v["mtg"] for v in camp_rows.values()), leads), clicks, div(clicks, imps), div(spend, qd)],
          fm, "total", bold_cols=(3,))
    S.note(f"Total Meeting Scheduled in period: {total_mtg} (campaign rows sum to "
           f"{sum(v['mtg'] for v in camp_rows.values())}; the difference could not be mapped to a campaign). "
           "Meta metrics are verbatim from the Ads Manager exports; CRM columns come from the CRM export mapped "
           "to campaigns, date-scoped to the MTD window.", height=30)
    S.r += 1

    # ---- 2. campaigns FTD
    S.banner(f"2.  CAMPAIGN-WISE PERFORMANCE  —  FTD {fstart:%d %b} – {fend:%d %b %Y}  (CRM lead data)", TEAL)
    S.note("Meta exports are cumulative with no daily breakdown, so FTD spend / impressions / CPL / CTR cannot be "
           "derived. FTD figures are CRM lead-intake counts and meetings for the FTD window.", height=28)
    S.header(["Campaign name", "CRM Leads (FTD)", "Qualified Leads (FTD)", "Qualified Lead % (FTD)",
              "Meetings Scheduled (FTD)", "Meeting Scheduled % (FTD)"])
    ffm = [None, I, I, P, I, P]
    for n in list(camps["Campaign name"]) + [UNMAPPED]:
        l, q, m = count(crm_f, campaign=n), qual(crm_f, campaign=n), count(mtg_f, campaign=n)
        if n == UNMAPPED and not (l or m):
            continue
        S.row([n, l, q, div(q, l), m, div(m, l)], ffm)
    fl, fq = len(crm_f), int(crm_f["qualified"].sum())
    S.row(["TOTAL (FULL CRM EXPORT FOR THE FTD PERIOD)", fl, fq, div(fq, fl), len(mtg_f), div(len(mtg_f), fl)],
          ffm, "total")
    S.r += 1

    # ---- 3. ad sets
    S.banner(f"3.  AD SET-WISE PERFORMANCE  —  MTD ({start:%d %b} – {end:%d %b %Y}),  grouped by campaign", TEAL)
    S.header(["Parent Campaign", "Ad set name", "Ad set delivery", "Results", "Result indicator", "Cost per result",
              "Ad set budget", "Ad set budget type", f"Amount spent ({args.currency})", "Impressions", "Reach",
              "Ends", "Starts", "Attribution setting", "Bid type", "% of Campaign Spend", "% of Campaign Results",
              "Meetings Scheduled", "% of Total Meetings", "Link Clicks", "CTR", "CRM Leads", "Qualified Leads",
              "CPQL", "Qualified Lead %"])
    sfm = [None, None, None, I, None, M, None, None, M2, I, I, None, None, None, None, P, P, I, P, I, "0.00%", I, I, M, P]
    cs = camps.set_index("Campaign name")
    grand = dict(res=0, sp=0, im=0, rc=0, mt=0, cl=0, ld=0, qd=0)
    for cn in camps["Campaign name"]:
        grp = sets[sets["Parent Campaign"] == cn]
        if grp.empty:
            continue
        sub = dict(res=0, sp=0, im=0, rc=0, mt=0, cl=0, ld=0, qd=0)
        for _, r in grp.iterrows():
            n = r["Ad set name"]
            l, q, m = count(crm, campaign=cn, adset=n), qual(crm, campaign=cn, adset=n), count(mtg, campaign=cn, adset=n)
            S.row([cn, n, r.get("Ad set delivery"), r["Results"], r.get("Result indicator"), div(r["Spend"], r["Results"]),
                   r.get("Ad set budget"), r.get("Ad set budget type"), r["Spend"], r["Impressions"], r["Reach"],
                   r.get("Ends"), r.get("Starts"), r.get("Attribution setting"), r.get("Bid type"),
                   div(r["Spend"], cs.at[cn, "Spend"]), div(r["Results"], cs.at[cn, "Results"]), m,
                   div(m, total_mtg), r["Link clicks"], div(r["Link clicks"], r["Impressions"]), l, q,
                   div(r["Spend"], q), div(q, l)], sfm, bold_cols=(1, 2))
            for k, v in zip(sub, (r["Results"], r["Spend"], r["Impressions"], r["Reach"], m, r["Link clicks"], l, q)):
                sub[k] += v
        S.row([f"Subtotal — {cn}", None, None, sub["res"], None, div(sub["sp"], sub["res"]), None, None, sub["sp"],
               sub["im"], sub["rc"], None, None, None, None, None, None, sub["mt"], div(sub["mt"], total_mtg),
               sub["cl"], div(sub["cl"], sub["im"]), sub["ld"], sub["qd"], div(sub["sp"], sub["qd"]),
               div(sub["qd"], sub["ld"])], sfm, "sub")
        for k in grand:
            grand[k] += sub[k]
    g = grand
    S.row(["GRAND TOTAL — ALL AD SETS (this export)", None, None, g["res"], None, div(g["sp"], g["res"]), None, None,
           g["sp"], g["im"], g["rc"], None, None, None, None, None, None, g["mt"], div(g["mt"], total_mtg), g["cl"],
           div(g["cl"], g["im"]), g["ld"], g["qd"], div(g["sp"], g["qd"]), div(g["qd"], g["ld"])], sfm, "total")
    S.r += 1

    # ---- 4. ads
    S.banner(f"4.  AD-WISE PERFORMANCE  —  MTD ({start:%d %b} – {end:%d %b %Y}),  grouped by ad set", TEAL)
    S.header(["Parent Campaign", "Ad set name", "Ad name", "Ad delivery", "Results", "Result indicator", "Cost per result",
              f"Amount spent ({args.currency})", "Impressions", "Reach", "Attribution setting", "Quality ranking",
              "Engagement rate ranking", "Conversion rate ranking", "% of Ad Set Spend", "Meetings Scheduled",
              "% of Total Meetings", "Link Clicks", "CTR", "CRM Leads", "Qualified Leads", "CPQL", "Qualified Lead %"])
    afm = [None, None, None, None, I, None, M, M2, I, I, None, None, None, None, P, I, P, I, "0.00%", I, I, M, P]
    ss = sets.set_index(["Parent Campaign", "Ad set name"])
    grand = dict(res=0, sp=0, im=0, rc=0, mt=0, cl=0, ld=0, qd=0)
    for (cn, sn), grp in ads.groupby(["Parent Campaign", "Ad set name"], sort=False):
        sub = dict(res=0, sp=0, im=0, rc=0, mt=0, cl=0, ld=0, qd=0)
        set_spend = ss.at[(cn, sn), "Spend"] if (cn, sn) in ss.index else grp["Spend"].sum()
        for _, r in grp.iterrows():
            n = r["Ad name"]
            l = count(crm, campaign=cn, adset=sn, ad=n)
            q = qual(crm, campaign=cn, adset=sn, ad=n)
            m = count(mtg, campaign=cn, adset=sn, ad=n)
            S.row([cn, sn, n, r.get("Ad delivery"), r["Results"], r.get("Result indicator"),
                   div(r["Spend"], r["Results"]), r["Spend"], r["Impressions"], r["Reach"],
                   r.get("Attribution setting"), r.get("Quality ranking"), r.get("Engagement rate ranking"),
                   r.get("Conversion rate ranking"), div(r["Spend"], set_spend), m, div(m, total_mtg),
                   r["Link clicks"], div(r["Link clicks"], r["Impressions"]), l, q, div(r["Spend"], q), div(q, l)],
                  afm, bold_cols=(1, 2, 3))
            for k, v in zip(sub, (r["Results"], r["Spend"], r["Impressions"], r["Reach"], m, r["Link clicks"], l, q)):
                sub[k] += v
        S.row([f"Subtotal — {sn}", None, None, None, sub["res"], None, div(sub["sp"], sub["res"]), sub["sp"],
               sub["im"], sub["rc"], None, None, None, None, None, sub["mt"], div(sub["mt"], total_mtg), sub["cl"],
               div(sub["cl"], sub["im"]), sub["ld"], sub["qd"], div(sub["sp"], sub["qd"]),
               div(sub["qd"], sub["ld"])], afm, "sub")
        for k in grand:
            grand[k] += sub[k]
    g = grand
    S.row(["GRAND TOTAL — ALL ADS (this export)", None, None, None, g["res"], None, div(g["sp"], g["res"]), g["sp"],
           g["im"], g["rc"], None, None, None, None, None, g["mt"], div(g["mt"], total_mtg), g["cl"],
           div(g["cl"], g["im"]), g["ld"], g["qd"], div(g["sp"], g["qd"]), div(g["qd"], g["ld"])], afm, "total")
    S.r += 1

    # ---- key insights
    S.banner("KEY INSIGHTS", NAVY)
    for icon, text in zip(INSIGHT_ICONS, insights(camps, camp_rows, crm, mtg, cur, spend, results, leads, qd, total_mtg)):
        ws.cell(S.r, 1, icon)
        ws.merge_cells(start_row=S.r, start_column=3, end_row=S.r, end_column=26)
        c = ws.cell(S.r, 3, text)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.font = Font(size=10)
        ws.row_dimensions[S.r].height = 32
        S.r += 1
    for i, w in enumerate([34, 30, 30, 14, 12, 18, 13, 15, 15, 14, 12, 12, 14, 18, 14, 13, 13, 13, 13, 12, 12, 12, 12, 12, 12, 12], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    daily_sheet(wb, camps, crm, mtg, start, end)
    for name, df in (("Data_Campaigns", camps), ("Data_AdSets", sets), ("Data_Ads", ads), ("Data_CRM", crm),
                     ("Data_MeetingScheduled", mtg)):
        dump(wb.create_sheet(name), df)
    wb.save(args.out)
    print(f"wrote {args.out}")
    print(f"MTD: spend {fmt_money(cur, spend)} | CRM leads {leads} | qualified {qd} | meetings {total_mtg} | "
          f"FTD leads {fl} | CPQL {fmt_money(cur, div(spend, qd))}")


def insights(camps, rows, crm, mtg, cur, spend, results, leads, qd, total_mtg):
    out = []
    mapped = leads - count(crm, campaign=UNMAPPED)
    out.append(f"Attribution basis: {mapped} of {leads} MTD CRM leads ({pct(div(mapped, leads), 0)}) are mapped to a "
               "specific Ad, Ad Set and Campaign.")
    daily = crm.groupby("date").agg(n=("qualified", "size"), q=("qualified", "sum"))
    out.append("Day-by-day: " + "; ".join(f"{d:%d %b} → {int(r.n)} ({int(r.q)} Qualified, {pct(div(r.q, r.n))})"
                                         for d, r in daily.iterrows()))
    lead_rows = {k: v for k, v in rows.items() if v["leads"]}
    if lead_rows:
        top = max(lead_rows, key=lambda k: lead_rows[k]["leads"])
        out.append(f"Biggest lead driver: {top} with {lead_rows[top]['leads']} CRM leads "
                   f"({pct(div(lead_rows[top]['leads'], leads))} of total).")
        elig = {k: v for k, v in lead_rows.items() if v["leads"] >= 5}
        if elig:
            b = max(elig, key=lambda k: elig[k]["qd"] / elig[k]["leads"])
            out.append(f"Best qualification rate (campaigns with 5+ leads): {b} at "
                       f"{pct(elig[b]['qd'] / elig[b]['leads'])} ({elig[b]['qd']}/{elig[b]['leads']}).")
        cpl = camps[camps["Results"] > 0].assign(cpl=lambda d: d["Spend"] / d["Results"])
        if not cpl.empty:
            w = cpl.loc[cpl["cpl"].idxmax()]
            out.append(f"Highest cost per lead (Meta basis): {w['Campaign name']} at {fmt_money(cur, w['cpl'])} per result.")
    out.append(f"CRM lead quality (MTD, {leads} leads): {qd} ({pct(div(qd, leads))}) are Qualified or better; "
               f"CPQL is {fmt_money(cur, div(spend, qd))}.")
    out.append(f"Meetings Scheduled: {total_mtg} in the period ({pct(div(total_mtg, leads))} of CRM leads).")
    out.append(f"Overall MTD (Meta): {fmt_money(cur, spend)} spent generated {results:,.0f} results "
               f"({fmt_money(cur, div(spend, results))} per result).")
    out.append("Small-sample caveat: percentages on low lead counts swing widely; read rates with the counts beside them.")
    return out


def daily_sheet(wb, camps, crm, mtg, start, end):
    ws = wb.create_sheet("Daily Trend", 1)
    ws.sheet_view.showGridLines = False
    days = pd.date_range(start, end)
    names = list(camps["Campaign name"])
    head = ["Date", "CRM Leads", "Qualified", "Qualified %", "Meetings"] + [f"Leads: {n}" for n in names]
    for i, t in enumerate(head, 1):
        c = ws.cell(1, i, t)
        c.font = Font(bold=True, color="FFFFFF", size=9)
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(wrap_text=True, horizontal="center")
        ws.column_dimensions[get_column_letter(i)].width = 14 if i < 6 else 22
    ws.row_dimensions[1].height = 48
    for r, d in enumerate(days, 2):
        day = crm[crm["date"] == d]
        vals = [d.date(), len(day), int(day["qualified"].sum()), div(day["qualified"].sum(), len(day)),
                int((mtg["date"] == d).sum())] + [int((day["campaign"] == n).sum()) for n in names]
        for i, v in enumerate(vals, 1):
            c = ws.cell(r, i, "n/a" if v is None else v)
            c.alignment = Alignment(horizontal="center")
            if i == 4 and v is not None:
                c.number_format = "0.0%"
    ws.freeze_panes = "B2"


def dump(ws, df):
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.date
    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in row])
    for c in ws[1]:
        c.font = Font(bold=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ("campaigns", "adsets", "ads", "crm"):
        p.add_argument(f"--{a}", required=True)
    p.add_argument("--meetings")
    p.add_argument("--client", default="Client")
    p.add_argument("--currency", default="INR")
    p.add_argument("--mtd-start", required=True)
    p.add_argument("--mtd-end", required=True)
    p.add_argument("--ftd-start")
    p.add_argument("--ftd-end")
    p.add_argument("--out", default="Campaign_Performance_Report.xlsx")
    build(p.parse_args())


if __name__ == "__main__":
    main()
