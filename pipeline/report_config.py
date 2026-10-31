"""Loads config/report_config.json — the single source of truth for months, status lists, FW rule and brand mapping.
Override the file with the REPORT_CONFIG environment variable (used to test other periods)."""
import json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("REPORT_CONFIG", os.path.join(_HERE, "..", "config", "report_config.json"))
CFG = json.load(open(PATH, encoding="utf-8"))

YEAR = CFG["year"]
MONTHS = [m["key"] for m in CFG["months"]]
N = len(MONTHS)
MNAME = {m["key"]: m["name"] for m in CFG["months"]}
PARTIAL = next((m["key"] for m in CFG["months"] if m.get("partial")), None)
PARTIAL_IN_LABEL = CFG.get("partial_in_label", True)   # False: column/month labels read "Oct 2026"; the partial-month note stays in the text
MLAB = {k: f"{k} {YEAR}" + (" (partial)" if k == PARTIAL and PARTIAL_IN_LABEL else "") for k in MONTHS}            # pivot / dashboard labels
MFULL = {k: f"{MNAME[k].upper()} {YEAR}" + (" (partial — data to {end})" if k == PARTIAL else "") for k in MONTHS}  # '{end}' filled by data_end()
FIRST, LAST = MONTHS[0], MONTHS[-1]
PERIOD = f"{FIRST}–{LAST} {YEAR}" if N > 1 else f"{FIRST} {YEAR}"           # Jul–Oct 2026
PERIOD_UP = PERIOD.upper()
PERIOD_DOTS = " · ".join(k.upper() for k in MONTHS) + f" {YEAR}"                # JUL · AUG · SEP · OCT 2026
MONTH_LIST = ", ".join(MONTHS) + f" {YEAR}"                                     # Jul, Aug, Sep, Oct 2026
FILE_TAG = f"{FIRST}-{LAST}{YEAR}" if N > 1 else f"{FIRST}{YEAR}"               # Jul-Oct2026
TOTAL_LABEL = f"{PERIOD} total"
LEAD_FILE_PATTERN = CFG["lead_file_pattern"]
QUAL = CFG["qualified_statuses"]
MEET = CFG["meeting_statuses"]
FW_REGEX = CFG["fw_exclusion_regex"]
META_LEADS_INDICATOR = CFG.get("meta_leads_indicator", "actions:leadgen.other")
BRANDS = {b: (v["meta_file_prefix"], v["crm_brand_values"]) for b, v in CFG["brands"].items()}
EARLIER = {b: v["earlier_meta_total"] for b, v in CFG["brands"].items() if v.get("earlier_meta_total") is not None}

_END = {"txt": "the end of the extract"}


def lead_file(key):
    return LEAD_FILE_PATTERN.format(name=MNAME[key], year=YEAR)


def set_data_end(dt):
    """Call once the lead files are loaded; texts about the partial month then quote the real last date."""
    _END["txt"] = f"{dt:%d %b}"


def mfull(key):
    return MFULL[key].replace("{end}", _END["txt"])


def partial_sentence():
    """'October 2026 is a partial month (data to 30 Oct)' — empty string if every month is complete."""
    return f"{MNAME[PARTIAL]} {YEAR} is a partial month (data to {_END['txt']})" if PARTIAL else ""


def partial_short():
    return f"{MNAME[PARTIAL]} is partial (data to {_END['txt']})" if PARTIAL else ""


def last_two_note():
    """'Change Sep → Oct is NOT like-for-like (October is partial)' (or '')."""
    return f"Change {MONTHS[-2]} → {MONTHS[-1]} is NOT like-for-like ({MNAME[PARTIAL]} is partial)" if PARTIAL and N > 1 else ""
