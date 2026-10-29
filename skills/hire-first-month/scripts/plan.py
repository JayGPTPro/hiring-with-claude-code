"""Builds every first-thirty-days document for one hire from first-month/config.json.

The role scorecard becomes the onboarding plan. The outcomes in criteria.md ("By day 14: ...",
"By day 60: ...", "By day 90: ...") set the spine of the plan, the day-30 check-in and the reviews.
The five tasks to map come from task-log.md ("## Five candidates ...") or "five_tasks" in the config.

Reads:   first-month/config.json   (copy templates/config.example.json and fill it)
         criteria.md                 the outcomes section (or "outcomes" in the config)
         task-log.md                 optional, the five candidates for the day-14 map
Writes:  out/first-month/
           offer.md                the letter, with the raise schedule and the dates it sets
           contract-checklist.md   the three doors and the clauses to tick (not legal advice)
           access-plan.md          least privilege: the permission grid per system, the ladder, the log
           access.html             the same grid as a page, plus the offboarding checklist
           onboarding.md           the scorecard as a plan, the five task maps, two weeks day by day, the daily report
           checkpoints.md          day 7, 14, the day-30 check-in (four columns), 60 and 90
           day-30.html             the day-30 check-in as a page: expected result / actual evidence / missing training / next action
           checkpoints.ics         three all-day events you import. Nothing touches a calendar.
           silence.md              the one calm message, and the ladder before it
           offboarding.md          the 24-hour routine, with the systems table
           phishing-talk.md        the five-line first security conversation

The offer comes first, before the call: plan.py --offer writes only offer.md and contract-checklist.md. Both
need "structure" in the config (contractor, eor or entity), chosen by the founder; there is no default. A
contractor letter speaks of deliverables, availability and a fee; an employment letter of hours, probation
and raises. A later full run keeps an offer.md that already exists (rerun --offer to rewrite it).

Dates: day N is start_date plus N minus 1 days; a Saturday or Sunday is held on the Monday after.
The day-30 check-in never concludes "end it" on its own: it checks expectations, training and the
conditions to succeed first, and the person decides. Nothing here sends, pays, grants or schedules anything.

Usage: run from your hiring/ folder, or from the folder above it:
  python3 plan.py            the 30-day plan, access, check-ins (and the offer, if it is not written yet)
  python3 plan.py --offer    the offer letter and the contract checklist only, before the offer call
  (--root path/to/hiring overrides)
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import esc, demo_label, page, js_json  # noqa: E402

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python older than 3.9
    ZoneInfo = None

SKILL = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = SKILL / "templates"
OFFER_DOCS = ["offer", "contract-checklist"]
PLAN_DOCS = ["access-plan", "onboarding", "checkpoints", "silence", "offboarding", "phishing-talk"]
STRUCTURES = ("contractor", "eor", "entity")
FEE_LINES = {"founder": "I cover the transfer fee", "hire": "the transfer fee is on your side",
             "split": "we split the transfer fee"}
PHASES = [("week1", "Week 1"), ("month1", "Month 1"), ("month3", "Month 3")]
LEVELS = ("none", "view", "edit", "full")
RANK = {"none": 0, "view": 1, "edit": 2, "full": 3, "other": 1}
DEFAULT_OUTCOMES = [
    (14, "Five repeatable tasks are mapped.", "For each one: the steps, the inputs, the time it takes, what breaks when it is wrong, and whether a tool could help."),
    (60, "One AI-assisted workflow with human checks is in use every week.", "It ran four weeks in a row, every run has a written check step, and the checks caught or cleared every flagged line."),
    (90, "The SOP and the handoff for that workflow are written.", "Someone else runs it once from the SOP alone."),
]


def find_root(arg=None):
    """The hiring project root: the folder that holds criteria.md.

    Without --root: "." when ./criteria.md exists, "./hiring" when ./hiring/criteria.md exists,
    otherwise exit and name both. With --root: that folder, or its hiring/ child.
    """
    here = pathlib.Path(arg) if arg else pathlib.Path(".")
    for cand in (here, here / "hiring"):
        if (cand / "criteria.md").is_file():
            return cand.resolve()
    raise SystemExit("no criteria.md in %s or %s. Run this from your hiring/ folder (the one that holds "
                     "criteria.md) or from the folder above it, or pass --root path/to/hiring."
                     % (here / "criteria.md", here / "hiring" / "criteria.md"))


# ---------- dates ----------

def parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def long(d: dt.date) -> str:
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


def short(d: dt.date) -> str:
    return f"{d:%a} {d:%b} {d.day}"


def add_months(d: dt.date, months: int) -> dt.date:
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    last = (dt.date(y + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(y, m, min(d.day, last))


def roll_to_workday(d: dt.date):
    if d.weekday() >= 5:
        return d + dt.timedelta(days=7 - d.weekday()), True
    return d, False


def checkpoint(start: dt.date, day_n: int):
    return roll_to_workday(start + dt.timedelta(days=day_n - 1))


def working_days(start: dt.date, n: int):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def parse_window(s: str):
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*to\s*(\d{1,2}):(\d{2})\s*$", s or "")
    if not m:
        return None
    a, b, c, e = (int(x) for x in m.groups())
    return dt.time(a, b), dt.time(c, e)


def founder_window(start: dt.date, window: str, hire_tz: str, founder_tz: str):
    """Returns (founder window text, overlap hours) or (None, hours)."""
    parsed = parse_window(window)
    if not parsed:
        return None, None
    t1, t2 = parsed
    hours = (dt.datetime.combine(start, t2) - dt.datetime.combine(start, t1)).seconds / 3600
    if ZoneInfo is None:
        return None, hours
    try:
        z_h, z_f = ZoneInfo(hire_tz), ZoneInfo(founder_tz)
    except Exception:
        return None, hours
    a = dt.datetime.combine(start, t1, tzinfo=z_h).astimezone(z_f)
    b = dt.datetime.combine(start, t2, tzinfo=z_h).astimezone(z_f)
    return f"{a:%H:%M} to {b:%H:%M}", hours


# ---------- the role scorecard ----------

OUTCOME_HEADING = re.compile(r"^(#{2,3})\s+[^\n]*\b(outcomes?|results?|scorecard|first 90 days)\b[^\n]*$", re.I | re.M)
ITEM_START = re.compile(r"^\s*(?:\d+[.)]\s+|[-*+]\s+|(?=\**\s*by day\s*\d))(.*)$", re.I)


def list_items(block: str):
    """The list items in a block, each with its wrapped lines joined: a numbered or bulleted line (or a line that
    starts "By day N") starts an item, the lines under it continue it, a blank line or a heading ends it."""
    items, cur = [], None
    for line in block.splitlines():
        m = ITEM_START.match(line)
        if m and line.strip():
            if cur is not None:
                items.append(cur)
            cur = m.group(1).strip()
        elif cur is not None and line.strip() and not line.lstrip().startswith("#"):
            cur += " " + line.strip()
        elif cur is not None:
            items.append(cur)
            cur = None
    return items + ([cur] if cur is not None else [])


def outcomes_from(block: str):
    out = []
    for item in list_items(block):
        dm = re.match(r"^by day (\d+)\s*[:,.]?\s*(.*)$", re.sub(r"\*\*|__", "", item).strip(), re.I)
        if dm and dm.group(2).strip():
            head, _, rest = dm.group(2).strip().partition(". ")
            head = head.rstrip(".") + "."
            out.append((int(dm.group(1)), head[:1].upper() + head[1:], rest.strip()))
    return out


def read_outcomes(root: pathlib.Path, cfg: dict):
    """[(day, headline, done looks like)] from criteria.md, else config "outcomes", else defaults with a warning.

    criteria.md: the list under a heading with Outcomes, Results, Scorecard or "first 90 days" in it, where each
    item starts "By day N:". Numbered or bulleted, bold or not, wrapped over several lines. With no such heading,
    any list item in the file that starts "By day N:" counts."""
    crit = root / "criteria.md"
    text = crit.read_text(encoding="utf-8") if crit.exists() else ""
    out = []
    for m in OUTCOME_HEADING.finditer(text):
        end = re.compile(r"^#{2,%d}\s" % len(m.group(1)), re.M).search(text, m.end())
        out = outcomes_from(text[m.end():end.start() if end else len(text)])
        if out:
            return out, "criteria.md"
    out = outcomes_from(text)
    if out:
        print("note: criteria.md has no Outcomes heading; read the 'By day N:' lines found elsewhere in it.")
        return out, "criteria.md"
    for o in cfg.get("outcomes") or []:
        if isinstance(o, dict) and o.get("by_day"):
            out.append((int(o["by_day"]), o.get("outcome", ""), o.get("done", "")))
    if out:
        print("warning: no 'By day N:' outcomes in criteria.md; the plan uses the outcomes in first-month/config.json.")
        return out, "config.json"
    print("warning: no outcomes found in criteria.md (a heading with Outcomes, Results or Scorecard, and lines that start "
          "'By day N:'). The plan uses three DEFAULT outcomes that are not yours. Write your own in criteria.md and rerun.")
    return DEFAULT_OUTCOMES, "defaults"


def read_five_tasks(root: pathlib.Path, cfg: dict):
    if isinstance(cfg.get("five_tasks"), list) and cfg["five_tasks"]:
        return [str(t) for t in cfg["five_tasks"]][:5], "config.json"
    log = root / "task-log.md"
    if log.exists():
        m = re.search(r"^##\s+Five[^\n]*\n(.*?)(?=^## |\Z)", log.read_text(encoding="utf-8"), re.M | re.S | re.I)
        if m:
            tasks = [re.sub(r"\s*\(line \d+\)\s*$", "", im.group(1)).strip()
                     for im in (re.match(r"^\s*\d+[.)]\s+(.*)$", l) for l in m.group(1).splitlines()) if im]
            if tasks:
                return tasks[:5], "task-log.md"
    return [f"[repeat task {i} from your task log]" for i in range(1, 6)], "placeholders"


def day30_expectations(cfg, outcomes, tasks, ctx):
    """[(expected result, what to look for)] for the day-30 check-in, from the scorecard first."""
    rows = []
    by = {d: (h, r) for d, h, r in outcomes}
    if 14 in by:
        rows.append(("Five task maps done, due day 14: " + "; ".join(tasks) + ".",
                     "The five maps in the shared folder. Read one cold: can you follow it?"))
    if 60 in by:
        rows.append(("The day-60 workflow chosen from the maps, with a written check step, first weekly runs done.",
                     "The run log: every flagged line checked or cleared before anyone acted on it."))
    if 90 in by:
        rows.append(("The SOP for that workflow started: the first page exists, and " + (ctx["buddy"] or "the person who will run it") + " has read it.",
                     "The draft in the shared folder, and one question from the reader."))
    rows.append(("The week-one deliverable arrived and was usable.", ctx["first_deliverable"]))
    rows.append(("Daily reports on time, honest about problems, with a plan for the next day.",
                 "Read one week of reports in a row."))
    rows.append(("Month 1 access in place and used; nothing the work needs is missing.",
                 "The log at the bottom of access-plan.md."))
    for x in cfg.get("day30_extra") or []:
        if isinstance(x, dict):
            rows.append((x.get("expected", ""), x.get("evidence", "")))
        elif str(x).strip():
            rows.append((str(x), ""))
    return rows


# ---------- text helpers ----------

def fill(template: str, ctx: dict) -> str:
    return re.sub(r"\{([a-z0-9_]+)\}", lambda m: str(ctx[m.group(1)]) if m.group(1) in ctx else m.group(0), template)


def level_of(text: str) -> str:
    first = (text or "none").strip().split(":")[0].split(" ")[0].lower()
    return first if first in LEVELS else "other"


def md_cell(s: str) -> str:
    return (s or "").replace("|", "/").replace("\n", " ")


def structure_bits(cfg: dict, ctx: dict):
    s = (cfg.get("structure") or "").lower()
    brand, country, eor = ctx["brand"], ctx["hire_country"], cfg.get("eor_name") or "the service"
    if s == "eor":
        return (
            f"an employer-of-record or contractor-of-record service ({eor})",
            f"You are engaged through {eor}, which handles the contract, the invoices and the local paperwork. "
            f"The agreement still assigns the work you create to {brand} and covers confidentiality and subcontracting.",
            "The service carries the paperwork or the liability; read which one you bought. The IP, subcontracting and "
            "disclosure clauses still need to be in the agreement, because a service template may not carry them.",
        )
    if s == "entity":
        return (
            f"a local employment contract through {brand}'s entity in {country}",
            f"You are employed by {brand}'s entity in {country}, under a local employment contract that follows.",
            "Local law sets probation, notice and the IP default for employees. The lawyer there drives this checklist.",
        )
    return (
        "an independent contractor agreement",
        f"You work as an independent contractor under a written agreement. The agreement assigns the work you create to "
        f"{brand}, asks you to tell me about other paid work before it starts, and does not allow subcontracting without "
        f"my written approval. You invoice me; taxes and your own tools stay on your side.",
        "You carry the classification risk. Keep the terms honest: an output-based scope, hours set by the hire inside "
        "the overlap window, other clients allowed with disclosure, no expense reimbursement.",
    )


# ---------- markdown tables ----------

def systems_table(systems):
    head = "| System | Owner account | Login | Week 1 | Month 1 | Month 3 | Never |\n|---|---|---|---|---|---|---|\n"
    rows = []
    for s in systems:
        rows.append("| " + " | ".join(md_cell(x) for x in (
            s.get("name", ""), s.get("owner", ""), login_text(s), s.get("week1", ""), s.get("month1", ""),
            s.get("month3", ""), s.get("never", ""))) + " |")
    return head + "\n".join(rows)


def login_text(s: dict) -> str:
    return f"{s.get('login', 'Personal account')}; 2FA: {s.get('two_factor', 'authenticator app')}; vault: {s.get('vault', 'none')}"


def system_details(systems):
    parts = []
    for s in systems:
        lines = [f"### {s['name']}", f"- Owner account: {s.get('owner', '')}", f"- Login: {login_text(s)}"]
        if s.get("grant_via"):
            lines.append(f"- Granted via: {s['grant_via']}")
        for k, lbl in PHASES:
            lines.append(f"- {lbl}: {s.get(k, 'None')}")
        lines.append(f"- Never: {s.get('never', '')}")
        if s.get("notes"):
            lines.append(f"- Notes: {s['notes']}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def ladder_steps(systems, dates, approver):
    day1 = [f"{s['name']}: {s.get('week1', 'None')}" for s in systems]
    day7 = [f"{s['name']}: {s.get('month1', 'None')}" for s in systems if s.get("month1") != s.get("week1")]
    day30 = [f"{s['name']}: {s.get('month3', 'None')}" for s in systems if s.get("month3") != s.get("month1")]
    return [
        ("Day 1", dates["start"], day1 or ["nothing yet"]),
        ("Day 7", dates["cp7"], (day7 or ["no change planned"]) + [f"Only where the daily reports were clean and {approver} approves."]),
        ("Day 14", dates["cp14"], ["Confirm the Month 1 levels are in place. Nothing new unless something was held back at day 7."]),
        ("Day 30", dates["cp30"], (day30 or ["no change planned"]) + ["After the day-30 check-in, as responsibilities grow."]),
    ]


def ladder_table(steps):
    head = "| Checkpoint | Date | What changes |\n|---|---|---|\n"
    return head + "\n".join(f"| {a} | {b} | {md_cell('; '.join(c))} |" for a, b, c in steps)


def offboarding_table(systems):
    head = "| Step | System | Where to revoke | Done (date, time) |\n|---|---|---|---|\n"
    rows = [f"| {i} | {md_cell(s['name'])} | {md_cell(s.get('grant_via', 'where it was granted'))} | |" for i, s in enumerate(systems, 1)]
    rows.append(f"| {len(systems) + 1} | Shared secrets the person could have seen | Rotate in the password manager | |")
    return head + "\n".join(rows)


def scorecard_table(outcomes, cps, cp_label):
    head = "| By | Outcome, from the role scorecard | Done looks like | Checked at |\n|---|---|---|---|\n"
    rows = []
    for d, h, r in outcomes:
        when = long(cps[d][0]) if d in cps else f"day {d}"
        rows.append(f"| Day {d} ({when}) | {md_cell(h)} | {md_cell(r) or 'see criteria.md'} | {cp_label.get(d, f'the day {d} review')} |")
    return head + "\n".join(rows)


def five_tasks_table(tasks, due_dates):
    head = "| # | Task from the task log | Map ready by | Each map has |\n|---|---|---|---|\n"
    return head + "\n".join(
        f"| {i} | {md_cell(t)} | {due_dates[i - 1]} | steps, inputs, time it takes, what breaks when it is wrong, a tool could help or not |"
        for i, t in enumerate(tasks, 1))


def day30_table(rows):
    head = "| Expected result | Actual evidence | Missing training | Next action |\n|---|---|---|---|\n"
    return head + "\n".join(f"| {md_cell(e)}" + (f" Look for: {md_cell(h)}" if h else "") + " | | | |" for e, h in rows)


# ---------- ics ----------

def ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_fold(line: str) -> str:
    out, chunk = [], ""
    for ch in line:
        if len((chunk + ch).encode("utf-8")) > 74:
            out.append(chunk)
            chunk = " " + ch
        else:
            chunk += ch
    out.append(chunk)
    return "\r\n".join(out)


def build_ics(slug: str, events):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//hire-first-month//hiring-with-claude-code//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for day_n, d, summary, desc in events:
        uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"hire-first-month/{slug}/day{day_n}")) + "@hire-first-month"
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                  f"DTEND;VALUE=DATE:{d + dt.timedelta(days=1):%Y%m%d}", f"SUMMARY:{ics_escape(summary)}",
                  f"DESCRIPTION:{ics_escape(desc)}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(l) for l in lines) + "\r\n"


# ---------- html ----------

ACCESS_CSS = """
.rules{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 22px}
.rules span{background:var(--card);border:2px solid var(--ink);border-radius:999px;padding:6px 16px;font-size:20px;font-weight:600}
table.acc{table-layout:fixed;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
table.acc thead th{background:var(--ink);color:#fff;font-size:22px}
table.acc thead th .when{display:block;font-size:19px;font-weight:500;opacity:.85}
td.sys b{display:block;font-size:22px}
td.sys span{display:block;font-size:19px;color:var(--mute);line-height:1.35;margin-top:4px}
.detail{display:block;font-size:20px;line-height:1.4;margin-top:4px}
.gate{display:block;margin-top:8px;font-size:19px;font-weight:700;color:var(--warn);border-left:4px solid var(--warn);padding-left:8px}
.lv-none{background:var(--soft);color:var(--mute)}.lv-view{background:var(--acc-bg);color:var(--acc)}
.lv-edit{background:var(--warn-bg);color:var(--warn)}.lv-full{background:var(--ok-bg);color:var(--ok)}
.lv-never{background:var(--no-bg);color:var(--no)}.lv-other{background:var(--soft);color:var(--ink)}
tr.star td{background:#fffbea}
.ladder{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.ladder .card{margin:0}.ladder b{display:block;font-size:22px}.ladder .date{color:var(--mute);font-size:20px;margin-bottom:6px}
.ladder ul{margin:0;padding-left:22px;font-size:20px}.ladder li{margin:4px 0}
ul.why{margin:0;padding-left:28px}ul.why li{margin:6px 0}
table.off td label{display:flex;gap:10px;align-items:flex-start;cursor:pointer}
table.off input{margin-top:6px;width:20px;height:20px}
table.off tr.done td{color:var(--mute);text-decoration:line-through}
@media (max-width:1100px){.ladder{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:760px){.ladder{grid-template-columns:1fr}}
"""

DAY30_CSS = """
.ask{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:6px 0 18px}
.ask div{background:var(--card);border:2px solid var(--ink);border-radius:14px;padding:12px 16px;font-size:23px;font-weight:700}
table.d30{table-layout:fixed;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
table.d30 col.e{width:34%}
table.d30 thead th{background:var(--ink);color:#fff;font-size:22px}
table.d30 thead th span{display:block;font-size:19px;font-weight:500;opacity:.85}
td.exp b{display:block;font-size:21px;font-weight:600;line-height:1.4}
td.exp span{display:block;font-size:19px;color:var(--mute);margin-top:6px;line-height:1.35}
td.fill{background:#fdfcf8}
td.fill div[contenteditable]{min-height:80px;font-size:20px;outline:none;border-radius:6px;padding:4px}
td.fill div[contenteditable]:empty:before{content:attr(data-hint);color:#9a9890;font-style:italic}
td.fill div[contenteditable]:focus{background:#fff6d6}
.checks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.checks .card{margin:0}.checks b{display:block;font-size:22px;margin-bottom:4px}
.never{font-size:22px;font-weight:800;margin:14px 0 0}
ul.follow{margin:0;padding-left:28px}ul.follow li{margin:8px 0}
@media (max-width:1100px){.ask,.checks{grid-template-columns:1fr}}
"""


def level_pill(text: str) -> str:
    text = text or "None"
    lv = level_of(text)
    word, _, rest = text.partition(":")
    if lv == "other":
        word, rest = "", text
    pill = f'<span class="pill lv-{lv}">{esc(word.strip())}</span>' if word.strip() else ""
    detail = f'<span class="detail">{esc(rest.strip())}</span>' if rest.strip() else ""
    return pill + detail


def build_access_html(cfg, ctx, steps, dates, badge):
    systems = cfg.get("systems", [])
    approver = ctx["signoff"] or "the founder"
    gate_when = {"week1": f"the day-7 call ({dates['cp7_short']})", "month1": f"the day-30 check-in ({dates['cp30_short']})"}
    rows = []
    for s in systems:
        cells = []
        for i, (k, _) in enumerate(PHASES):
            cur = s.get(k, "None")
            gate = ""
            if i + 1 < len(PHASES):
                nxt = s.get(PHASES[i + 1][0], "None")
                if RANK[level_of(nxt)] > RANK[level_of(cur)] and level_of(cur) in ("view", "none"):
                    gate = (f'<span class="gate">{"View only" if level_of(cur) == "view" else "No access"} until {esc(approver)} '
                            f'approves, at {esc(gate_when[k])}</span>')
            cells.append(f"<td>{level_pill(cur)}{gate}</td>")
        login = (f'<span class="pill p-ok">{esc(s.get("login", "Personal account"))}</span>'
                 f'<span class="pill p-acc">2FA on</span>'
                 f'<span class="detail">{esc(str(s.get("two_factor", "authenticator app")).capitalize())}. Vault: {esc(s.get("vault", "none"))}</span>')
        star = " class='star'" if "seller central" in s.get("name", "").lower() else ""
        rows.append(f"<tr{star}><td class='sys'><b>{esc(s.get('name', ''))}</b><span>{esc(s.get('owner', ''))}</span></td>"
                    f"<td>{login}</td>{''.join(cells)}"
                    f"<td><span class='pill lv-never'>Never</span><span class='detail'>{esc(s.get('never', ''))}</span></td></tr>")
    cards = "".join(f"<div class='card'><b>{esc(lbl)}</b><div class='date'>{esc(d)}</div><ul>{''.join(f'<li>{esc(c)}</li>' for c in ch)}</ul></div>"
                    for lbl, d, ch in steps)
    off = []
    for i, s in enumerate(systems, 1):
        off.append(f"<tr><td><label><input type='checkbox' data-off='{i}'><span>{esc(s.get('name', ''))}</span></label></td>"
                   f"<td>{esc(s.get('grant_via', 'where it was granted'))}</td><td data-when='{i}'></td></tr>")
    n = len(systems) + 1
    off.append(f"<tr><td><label><input type='checkbox' data-off='{n}'><span>Shared secrets the person could have seen</span></label></td>"
               f"<td>Rotate in the password manager</td><td data-when='{n}'></td></tr>")
    rules = ["Personal account on every system", "Least privilege for the first task", "Seller Central view-only until approved",
             "Password manager for every secret", "Two-factor authentication on every login", "Access grows with the responsibilities",
             "No credentials in chat or email"]
    body = f"""
<h1>Access plan: {esc(ctx['name'])}</h1>
<p class="sub">{esc(ctx['role'])} at {esc(ctx['brand'])}, starting {esc(ctx['start_date_long'])}. Week 1 is days 1 to 7, Month 1 is days 8 to 30, Month 3 is the full role from day 31. Each step is granted by {esc(approver)} after the checkpoint call, not before it. No real credentials on this page or anywhere in this folder.</p>
<div class="rules">{''.join(f'<span>{esc(r)}</span>' for r in rules)}</div>
<table class="acc"><colgroup><col style="width:17%"><col style="width:15%"><col style="width:18%"><col style="width:18%"><col style="width:18%"><col style="width:14%"></colgroup>
<thead><tr><th>System</th><th>Login</th>
<th>Week 1<span class="when">from {esc(dates['start_short'])}</span></th>
<th>Month 1<span class="when">after the day-7 call, {esc(dates['cp7_short'])}</span></th>
<th>Month 3<span class="when">after the day-30 check-in, {esc(dates['cp30_short'])}</span></th>
<th>Never</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>The ladder: access grows with the responsibilities</h2>
<div class="ladder">{cards}</div>
<h2>Why it is written this way</h2>
<div class="card"><ul class="why">
<li>The first task is mapping work, which needs reading, not changing. Edit rights arrive one system at a time, when the work needs them and {esc(approver)} has seen the checks work.</li>
<li>Every login is personal. Nobody uses the founder's login. Secrets live in the password manager; a one-off secret goes through an expiring share, never chat or email.</li>
<li>Seller Central: a secondary user on the hire's own work email, invited through Settings, User Permissions. Never Administrator, never banking, deposit, tax or account information. Two-step verification on an authenticator app, not SMS.</li>
<li>The documented takeover vector is a phishing email, so the first security conversation (phishing-talk.md) comes before the first login.</li>
<li>Access is reviewed at day 30 and day 90, then every six months; first six-month review {esc(ctx['review_6m_long'])}. Anything not used is removed.</li>
</ul></div>
<h2>Offboarding list: the same systems, inside 24 hours</h2>
<p class="note">Written on day one so it exists before it is needed. Ticks stay in this browser only. Revoke top to bottom in one sitting, then confirm deletion of local copies, collect the work, get written confirmation, and pay to the day.</p>
<table class="off"><thead><tr><th>Revoked</th><th>Where</th><th>When</th></tr></thead><tbody>{''.join(off)}</tbody></table>
<p class="foot">Built by the hire-first-month skill from first-month/config.json. Companion files: access-plan.md, onboarding.md, checkpoints.md, day-30.html, offboarding.md. Nothing on this page is sent, granted or stored anywhere.</p>
"""
    script = """var K=%s,S={};try{S=JSON.parse(localStorage.getItem(K)||"{}")}catch(e){}
function save(){try{localStorage.setItem(K,JSON.stringify(S))}catch(e){}}
function paint(){document.querySelectorAll("[data-off]").forEach(function(c){var k=c.getAttribute("data-off"),tr=c.closest("tr"),w=document.querySelector("[data-when='"+k+"']");
if(S[k]){c.checked=true;tr.classList.add("done");w.textContent="revoked "+S[k]}else{c.checked=false;tr.classList.remove("done");w.textContent=""}})}
document.querySelectorAll("[data-off]").forEach(function(c){c.onchange=function(){var k=c.getAttribute("data-off");if(c.checked){S[k]=new Date().toLocaleString()}else{delete S[k]}save();paint()}});
paint();""" % js_json(f"first-month-off-{ctx['slug']}")
    return page(f"Access plan: {ctx['name']}", f"{ctx['brand']} · First 30 days · Access plan", body, badge, ACCESS_CSS, script)


def build_day30_html(cfg, ctx, rows, badge):
    trs = []
    for i, (e, h) in enumerate(rows):
        trs.append(f"<tr><td class='exp'><b>{esc(e)}</b>" + (f"<span>Look for: {esc(h)}</span>" if h else "") + "</td>"
                   + "".join(f"<td class='fill'><div contenteditable='true' data-k='{i}-{c}' data-hint='{esc(hint)}'></div></td>"
                             for c, hint in (("ev", "what you saw, with the file or date"), ("tr", "what was never documented, taught or asked for"),
                                             ("nx", "one action, an owner, a date")))
                   + "</tr>")
    first = ctx["first_name"]
    body = f"""
<h1>Day-30 check-in: {esc(ctx['name'])}</h1>
<p class="sub">{esc(ctx['cp30_date'])}, one hour, both of you. The same scorecard that chose the person shows whether the role is working, for both of you. Fill the evidence before the call; fill the rest together.</p>
<div class="ask"><div>Did the work happen?</div><div>What still needs training?</div><div>Which expectations were unrealistic?</div></div>
<table class="d30"><colgroup><col class="e"><col><col><col></colgroup>
<thead><tr><th>Expected result<span>from the role scorecard</span></th><th>Actual evidence<span>what you saw, not how it felt</span></th><th>Missing training<span>documented, taught, asked for?</span></th><th>Next action<span>one step, an owner, a date</span></th></tr></thead>
<tbody>{''.join(trs)}</tbody></table>
<div class="row"><button class="p" id="copy">Copy as a table</button><span class="note">Typed text stays in this browser only. Paste the table into checkpoints.md after the call.</span></div>
<h2>Before any conclusion: three checks</h2>
<div class="checks">
<div class="card"><b>Were the expectations realistic?</b>Ramp to full speed takes about three months: weeks 1 and 2 orientation, weeks 3 and 4 steady quality, month 2 wider duties, month 3 full speed. A month-3 expectation is not a day-30 miss.</div>
<div class="card"><b>Was the training given?</b>For every gap: was it documented, taught or asked for in writing? If not, the gap is in the onboarding. Write the training into the third column.</div>
<div class="card"><b>Were the conditions there?</b>Access granted on time, the data available, replies inside the overlap window, the time not taken by other work. Ask {esc(first)}: what got in the way?</div>
</div>
<h2>What follows</h2>
<div class="card"><ul class="follow">
<li><b>On track:</b> say it on the call. Grant the Month 3 levels in access-plan.md. The raise schedule stays as written in the offer.</li>
<li><b>A gap with a cause you can fix</b> (training, access, data, an unclear expectation): fix it this week, write the next action with a date, check it at day 60.</li>
<li><b>A gap after the expectations were clear, the training was given and the conditions were there:</b> write it down with the evidence, tell {esc(first)} in plain words the same day, and agree what day 60 must show. Any decision about the role is yours, made at the review the agreement sets, with the evidence in front of you.</li>
</ul><p class="never">This check-in never ends with an automatic "end it".</p></div>
<h2>For your next hire, one line</h2>
<div class="card"><p>What you expected in the interview, next to what actually happened. Then one thing you would ask differently next time. Write it in checkpoints.md; it is how the hiring process gets better.</p></div>
<p class="foot">Built by the hire-first-month skill from criteria.md and first-month/config.json. Nothing on this page is sent anywhere.</p>
"""
    script = """var K=%s,S={};try{S=JSON.parse(localStorage.getItem(K)||"{}")}catch(e){}
document.querySelectorAll("[data-k]").forEach(function(d){var k=d.getAttribute("data-k");if(S[k])d.textContent=S[k];d.oninput=function(){S[k]=d.textContent;try{localStorage.setItem(K,JSON.stringify(S))}catch(e){}}});
document.getElementById("copy").onclick=function(){var t="| Expected result | Actual evidence | Missing training | Next action |\\n|---|---|---|---|\\n";
document.querySelectorAll("table.d30 tbody tr").forEach(function(tr){var c=tr.querySelectorAll("td");t+="| "+c[0].querySelector("b").textContent+" | "+[1,2,3].map(function(i){return c[i].textContent.replace(/\\|/g,"/").trim()}).join(" | ")+" |\\n"});
var b=this,d=function(){var x=b.textContent;b.textContent="Copied";setTimeout(function(){b.textContent=x},1400)};(navigator.clipboard?navigator.clipboard.writeText(t).then(d,d):d())};
""" % js_json(f"first-month-day30-{ctx['slug']}")
    return page(f"Day-30 check-in: {ctx['name']}", f"{ctx['brand']} · First 30 days · Day-30 check-in", body, badge, DAY30_CSS, script)


# ---------- main ----------

def check_and_report(written, out, root, notes):
    """No long dash and no local path in anything written; name leftover placeholders; print what was written."""
    for p in written:
        body = p.read_text(encoding="utf-8")
        for bad in ("\u2014", "\u2013"):
            if bad in body:
                raise SystemExit(f"long dash in {p.name}: fix the template or the config")
        for bad in ("/Users/", "/home/", "C:\\"):
            if bad in body:
                raise SystemExit(f"local path in {p.name}")
        left = sorted(set(re.findall(r"\{([a-z0-9_]+)\}", body)))
        if left and p.suffix == ".md":
            print(f"note: {p.name} still has placeholders: {', '.join(left)}")
    for p in written:
        print(f"wrote {out.relative_to(root) / p.name}")
    for n in notes:
        print(n if n.startswith("warning") else "note: " + n)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    ap.add_argument("--offer", action="store_true", help="write only the offer letter and the contract checklist")
    args = ap.parse_args()
    root = find_root(args.root)
    cfg_path = root / "first-month" / "config.json"
    if not cfg_path.is_file():
        raise SystemExit(f"no {cfg_path}: copy templates/config.example.json there and fill it")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    badge = demo_label(root, cfg)
    out = root / "out" / "first-month"
    out.mkdir(parents=True, exist_ok=True)

    hire, pay, ov, raise_cfg = cfg["hire"], cfg["pay"], cfg.get("overlap", {}), cfg.get("raise", {})
    start = parse_date(cfg["start_date"])
    offer = parse_date(cfg.get("offer_date") or cfg["start_date"])
    if start.weekday() != 0:
        print(f"note: the start date {long(start)} is not a Monday. A Monday start gives week one five full days.")
    cp_days = cfg.get("checkpoint_days") or [7, 14, 30]
    cps = {n: checkpoint(start, n) for n in sorted(set(cp_days) | {14, 30, 60, 90})}
    roll_note = "Every checkpoint is on a working day; one that falls on a weekend is held on the Monday after."
    wd = working_days(start, 10)

    weekly_weeks = int(pay.get("weekly_weeks", 8))
    monthly = float(pay["monthly"])
    weekly = round(monthly * 12 / 52)
    monthly_from = start + dt.timedelta(weeks=weekly_weeks)
    raise_6m = roll_to_workday(add_months(start, 6))[0]
    raise_12m = roll_to_workday(add_months(start, 12))[0]
    p6, p12 = raise_cfg.get("at_6_months_pct", 10), raise_cfg.get("at_12_months_pct", 10)

    f_window, computed_hours = founder_window(start, ov.get("hire_window_local", ""), ov.get("hire_tz", ""), ov.get("founder_tz", ""))
    overlap_hours = ov.get("hours") or (int(computed_hours) if computed_hours else 4)
    first = hire.get("first_name") or hire["name"].split()[0]
    ctx = {
        "name": hire["name"], "first_name": first, "slug": hire["slug"], "role": hire.get("role", "the role"),
        "hire_city": hire.get("city", "your city"), "hire_country": hire.get("country", "your country"),
        "brand": cfg.get("brand", "the company"), "signoff": cfg.get("signoff", ""),
        "offer_date_long": long(offer), "start_date": start.isoformat(), "start_date_long": long(start),
        "monthly_from_long": long(monthly_from),
        "cp7_date": long(cps[7][0]) if 7 in cps else "", "cp14_date": long(cps[14][0]),
        "cp30_date": long(cps[30][0]), "cp60_date": long(cps[60][0]), "cp90_date": long(cps[90][0]),
        "raise_6m_long": long(raise_6m), "raise_12m_long": long(raise_12m), "review_6m_long": long(raise_6m),
        "roll_note": roll_note, "currency": pay.get("currency", "USD"), "pay_monthly": f"{monthly:,.0f}",
        "pay_weekly": f"{weekly:,}", "weekly_weeks": weekly_weeks, "pay_day": pay.get("pay_day", "Friday"),
        "payment_rail": pay.get("rail", "a transfer service"), "rail_note": pay.get("rail_note", ""),
        "transfer_fee_line": FEE_LINES.get(str(pay.get("transfer_fee", "")).lower(), "[who pays the transfer fee: decide before you send]"),
        "overlap_hours": overlap_hours, "overlap_window_hire": ov.get("hire_window_local", "the agreed window"),
        "overlap_window_founder": f_window or "the same window, convert for your time zone",
        "probation_days": cfg.get("probation_days", 90), "probation_notice": cfg.get("probation_notice", "one week"),
        "notice_after": cfg.get("notice_after", "one month"), "agreement_when": cfg.get("agreement_when", "tomorrow"),
        "first_deliverable": cfg.get("first_deliverable", "one real piece of the role, small, finished by the end of week one."),
        "manual_name": cfg.get("manual_name", "Operations manual for this role"),
        "buddy": (cfg.get("buddy") or "").strip(),
    }
    ctx["raise_text"] = (f"{p6}% at six months ({long(raise_6m)}) and another {p12}% at twelve months ({long(raise_12m)}), each one confirmed "
                         f"at the review before it, if the work is where we both want it. I would rather write this down now than negotiate it in month five.")
    ctx["raise_text_short"] = f"{p6}% at six months, {p12}% at twelve"
    ctx["rate_text"] = (f"Reviewed at six months ({long(raise_6m)}) and at twelve ({long(raise_12m)}). If the work is where we both "
                        f"want it, I plan {p6}% more at the first review and {p12}% more at the second.")
    ctx["buddy_line"] = (f"The mid-week call is with {ctx['buddy']}, who is not the manager; the other two are with the founder." if ctx["buddy"]
                         else "All three with the founder, unless you can borrow a buddy who is not the manager (a freelancer you already work with, a past contractor) for the mid-week one.")
    for i, d in enumerate(wd, 1):
        ctx[f"d{i}"] = f"{d:%A}, {d:%B} {d.day}"
    ctx["structure_label"], ctx["structure_text"], ctx["structure_note"] = structure_bits(cfg, ctx)

    outcomes, o_src = read_outcomes(root, cfg)
    ctx["deliverables"] = "; ".join(f"by day {d}, {h[:1].lower() + h[1:].rstrip('.')}" for d, h, _ in outcomes)
    tasks, t_src = read_five_tasks(root, cfg)
    due_idx = [4, 6, 7, 8, 9]
    due_dates = [f"{wd[i]:%A}, {wd[i]:%B} {wd[i].day}" for i in due_idx[:len(tasks)]]
    cp_label = {14: f"the day-14 call ({ctx['cp14_date']})", 30: f"the day-30 check-in ({ctx['cp30_date']})",
                60: f"the day-60 review ({ctx['cp60_date']})", 90: f"the day-90 review ({ctx['cp90_date']})"}
    ctx["scorecard_table"] = scorecard_table(outcomes, cps, cp_label)
    ctx["scorecard_source"] = {"criteria.md": "the outcomes in `criteria.md`", "config.json": "the outcomes in `first-month/config.json`",
                               "defaults": "the default outcomes (write your own in `criteria.md`)"}[o_src]
    ctx["five_tasks_table"] = five_tasks_table(tasks, due_dates)
    ctx["five_tasks_source"] = {"config.json": "`five_tasks` in the config", "task-log.md": "the five candidates in `task-log.md`",
                                "placeholders": "placeholders (list five tasks from your task log in the config)"}[t_src]
    d30_rows = day30_expectations(cfg, outcomes, tasks, ctx)
    ctx["day30_table"] = day30_table(d30_rows)

    systems = cfg.get("systems", [])
    dates = {"start": long(start), "cp7": ctx["cp7_date"], "cp14": ctx["cp14_date"], "cp30": ctx["cp30_date"],
             "start_short": short(start), "cp7_short": short(cps[7][0]) if 7 in cps else "day 7", "cp30_short": short(cps[30][0])}
    steps = ladder_steps(systems, dates, ctx["signoff"] or "the founder")
    ctx["systems_table"] = systems_table(systems)
    ctx["system_details"] = system_details(systems)
    ctx["ladder_table"] = ladder_table(steps)
    ctx["offboarding_table"] = offboarding_table(systems)

    structure = str(cfg.get("structure") or "").lower()
    notes = []
    if structure not in STRUCTURES:
        msg = ("structure is not set in first-month/config.json. Ask the founder: contractor, eor (employer of record) or "
               "entity (a local company). It changes what the letter may promise; contract-checklist.md explains the three. "
               "There is no default.")
        if args.offer:
            raise SystemExit(msg + " No offer written.")
        notes.append(msg + " offer.md and contract-checklist.md are not written yet.")
    if ctx["transfer_fee_line"].startswith("["):
        notes.append("pay.transfer_fee is not set (founder, hire or split): the letter shows a blank to fill.")
    for s in cfg.get("systems", []):
        if "orders" in (str(s.get("week1", "")) + " " + str(s.get("month1", ""))).lower():
            notes.append(f"warning: {s.get('name', 'a system')} gives Orders before day 30. Orders shows buyer names and "
                         "addresses; move it to Month 3, after you approve it.")

    docs = []
    if structure in STRUCTURES:
        for doc in OFFER_DOCS:
            if not args.offer and (out / f"{doc}.md").exists():
                notes.append(f"kept your {doc}.md; rerun with --offer to rewrite it")
            else:
                docs.append((doc, "offer-contractor" if doc == "offer" and structure == "contractor" else doc))
    if not args.offer:
        docs += [(d, d) for d in PLAN_DOCS]
    written = []
    for doc, tpl in docs:
        text = fill((TEMPLATES / f"{tpl}.md").read_text(encoding="utf-8"), ctx)
        if badge and not text.startswith(badge):
            text = text.replace("\n", f"\n\n{badge}. Invented people and numbers, for the lesson.\n", 1)
        (out / f"{doc}.md").write_text(text, encoding="utf-8")
        written.append(out / f"{doc}.md")
    if args.offer:
        check_and_report(written, out, root, notes)
        print("Offer only. Read it on the call, send it after. The 30-day plan comes after the yes: run plan.py without --offer.")
        return

    events = [
        (7, cps[7][0], f"Day 7 with {first}: week one review",
         "Read the five daily reports in a row first. Did the first task map arrive? Has the manual started? "
         "Grant Month 1 access where the reports were clean and say what is held back and why. Say again that asking for help is never punished. "
         "Notes: out/first-month/checkpoints.md"),
        (14, cps[14][0], f"Day 14 with {first}: the five task maps",
         "Read one task map cold and try to follow it. Are all five there? Which one becomes the day-60 workflow? "
         "Is the overlap window kept on both sides? Notes: out/first-month/checkpoints.md"),
        (30, cps[30][0], f"Day 30 with {first}: expected result, actual evidence, missing training, next action",
         "Fill the evidence column before the call (out/first-month/day-30.html). Check expectations, training and conditions "
         "before any conclusion. Nothing here ends the role automatically. Notes: out/first-month/checkpoints.md"),
    ]
    (out / "checkpoints.ics").write_text(build_ics(hire["slug"], [e for e in events if e[0] in cp_days]), encoding="utf-8")
    written.append(out / "checkpoints.ics")
    (out / "access.html").write_text(build_access_html(cfg, ctx, steps, dates, badge), encoding="utf-8")
    written.append(out / "access.html")
    (out / "day-30.html").write_text(build_day30_html(cfg, ctx, d30_rows, badge), encoding="utf-8")
    written.append(out / "day-30.html")

    check_and_report(written, out, root, [])
    print(f"{hire['name']}, {ctx['role']}. Start {ctx['start_date_long']}.")
    print(f"Scorecard from {o_src}: " + "; ".join(f"day {d}: {h}" for d, h, _ in outcomes))
    print(f"Five tasks from {t_src}: " + "; ".join(tasks))
    print(f"Checkpoints: day 7 {ctx['cp7_date']}; day 14 {ctx['cp14_date']}; day 30 {ctx['cp30_date']}; day 60 {ctx['cp60_date']}; day 90 {ctx['cp90_date']}.")
    print(f"Pay: {ctx['currency']} {ctx['pay_monthly']} a month; weekly {ctx['currency']} {weekly:,} for {weekly_weeks} weeks, monthly from the week of {long(monthly_from)}.")
    if f_window:
        print(f"Overlap: {ctx['overlap_window_hire']} {ctx['hire_city']} time is {f_window} for you ({computed_hours:g} hours).")
    if computed_hours is not None and computed_hours < 4:
        print("warning: the overlap window is under four hours; four is the working minimum for a new hire.")
    for n in notes:
        print(n if n.startswith("warning") else "note: " + n)
    print("Nothing was sent, paid, granted or put in a calendar. Import checkpoints.ics yourself.")


if __name__ == "__main__":
    main()
