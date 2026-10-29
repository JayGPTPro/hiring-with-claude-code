#!/usr/bin/env python3
"""Build the candidate board, the Evidence Map pages and the morning list from the judged scores.

Run from the hiring project root (the folder that holds criteria.md, inbox/, out/), or from the
folder above it:

    python3 path/to/build_board.py
    python3 path/to/build_board.py --today 2026-10-12     # fix the date (waiting days, late-reply line)
    python3 path/to/build_board.py --close                # closing drafts, not for the hire or the runner-up

Reads, in this order of preference:
    out/scores.json            written by Claude after judging (format in SKILL.md)
    out/candidates/<slug>.md   the dossiers: Card / Evidence Map / Scores / Flags / Status / Log.
                               Fields scores.json leaves out are read from here.
    out/applications.json      from parse_inbox.py, fills in card fields
    out/blind/map.json         blind id per candidate (from redact.py)
    out/blind/hidden.json      hidden-text findings (from redact.py); adds the flag if missing
    control-cv.txt             the expected band of this role's control CV (hiring/control-cv.txt)

Writes:
    out/board.html             one row per application, sorted by SHARED + TRACK, with a status filter,
                               "Insufficient evidence. Follow-up required." where the evidence is too thin
                               for a number, and a row that opens to the source quote and what is missing
    out/board.csv              the same rows
    out/evidence/<slug>.html   the Evidence Map page per candidate (evidence_map.py)
    out/SUMMARY.md             who to talk to first, who is on hold, who is out and why
    out/MORNING.md             what changed since yesterday: new applications worth opening, decisions
                               waiting for you, people waiting more than --waiting-days for a reply
    out/board-state.json       what the board looked like, so tomorrow's run can say what changed
    out/messages/<slug>-<status>.md   one draft per candidate, from templates/messages.md

Nothing is sent. The drafts are files you read and send yourself.
Every piece of applicant text is escaped before it goes into HTML. Standard library only. No network.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import waiting  # noqa: E402  (same folder)
import parse_inbox  # noqa: E402
import _today  # noqa: E402
import evidence_map  # noqa: E402
from _page import esc, is_demo, page  # noqa: E402

STATUS_ORDER = ["call", "questionnaire", "hold", "no", "out of budget", "hired", "closed"]
CONTROL_SLUG = "control-cv"
CONTROL_ID = "C000"
HIDDEN_FLAG = "hidden text found, ignored"
INSUFFICIENT_TEXT = evidence_map.INSUFFICIENT_TEXT
PASS2_LIMIT = 5
BANDS = [(85, "top"), (70, "solid"), (55, "mixed"), (0, "thin")]
BAND_TEXT = "85 and up top, 70 to 84 solid, 55 to 69 mixed, under 55 thin"


def band(value100):
    for floor, label in BANDS:
        if value100 >= floor:
            return label
    return "thin"


STATUS_TEMPLATE = {"call": "invite-call", "questionnaire": "invite-questionnaire", "hold": "hold",
                   "no": "decline", "out of budget": "out-of-budget"}
STATUS_LABEL = {"call": "Invite to a call", "questionnaire": "Send the questionnaire", "hold": "On hold",
                "no": "No", "out of budget": "Out of budget", "hired": "Hired", "closed": "Closed"}
DEFAULT_ATTENTION = {"call": "Approve the invite", "questionnaire": "Approve the questionnaire",
                     "hold": "Revisit after the first calls", "no": "Decline draft ready",
                     "out of budget": "Card only, no research", "hired": "", "closed": ""}
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(os.path.dirname(HERE), "templates", "messages.md")


# ---------- loading ----------

def find_root(start):
    """Accept the hiring project root or the folder above it."""
    root = os.path.abspath(start)
    if os.path.isdir(os.path.join(root, "out")) or os.path.exists(os.path.join(root, "criteria.md")):
        return root
    if os.path.isdir(os.path.join(root, "hiring")):
        return os.path.join(root, "hiring")
    return root


def load_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def whole(v, default=0):
    """A score as a whole number, half up (40.5 is 41), from a number or a numeric string. The decision table
    in hire-test-task rounds the same way."""
    if isinstance(v, bool):
        return default
    try:
        f = float(v)
        return int(f + 0.5) if f >= 0 else -int(-f + 0.5)
    except (TypeError, ValueError, OverflowError):
        return default


def control_band(root):
    """Expected total band of this role's control CV, from the line 'Expected band: 55 to 69'."""
    path = os.path.join(root, "control-cv.txt")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        m = re.search(r"expected band:\s*(\d+)\s*to\s*(\d+)", f.read(), re.I)
    return (int(m.group(1)), int(m.group(2))) if m else None


def norm_flags(flags):
    out = []
    for fl in flags or []:
        if isinstance(fl, dict):
            colour = str(fl.get("color") or fl.get("colour") or "yellow").lower()
            text = str(fl.get("text", "")).strip()
        else:
            m = re.match(r"^\s*[-*]?\s*(green|yellow|red)\s*:\s*(.*)$", str(fl), re.I)
            if not m:
                continue
            colour, text = m.group(1).lower(), m.group(2).strip()
        if text and text.lower() not in ("none", "none."):
            out.append({"color": colour, "text": text})
    return out


def parse_dossier(path):
    """Pull the fields the board needs out of one dossier. Tolerant: missing parts stay empty."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    sec = evidence_map.sections(text)
    card, scores, status = (evidence_map.kv(sec.get("card", [])), evidence_map.kv(sec.get("scores", [])),
                            evidence_map.kv(sec.get("status", [])))
    ev = evidence_map.kv(sec.get("evidence", []))
    entry = {"slug": os.path.splitext(os.path.basename(path))[0],
             "name": card.get("name") or text.splitlines()[0].lstrip("# ").strip(),
             "location": card.get("location", ""), "ask_text": card.get("ask", ""),
             "availability": card.get("availability", ""), "source": card.get("source", ""),
             "date": card.get("date", ""), "cv": card.get("cv", ""),
             "blind_id": re.sub(r"\s*\(.*$", "", card.get("scored blind as", "")).strip()}
    m = re.search(r"second pass:\s*shared\s*(\d+)\D+track\s*(\d+)", "\n".join(sec.get("scores", [])), re.I)
    if m:
        entry["pass2"] = {"shared": int(m.group(1)), "track": int(m.group(2))}
    m = re.search(r"\d{3,6}", card.get("ask", "").replace(",", ""))
    entry["ask_usd"] = int(m.group(0)) if m else None
    for key in ("shared", "track"):
        m = re.match(r"\s*(\d+)", scores.get(key, ""))
        entry[key] = int(m.group(1)) if m else 0
    entry["insufficient_evidence"] = "insufficient" in scores.get("evidence level", "").lower()
    entry["budget_fit"] = re.sub(r"\s*\(.*$", "", scores.get("budget fit", "")).strip()
    entry["flags"] = norm_flags(sec.get("flags", []))
    entry["questions"] = [re.sub(r"^\s*\d+[.)]\s*", "", q).strip()
                          for q in sec.get("questions for the call", []) if re.match(r"^\s*\d+[.)]", q)]
    entry["status"] = status.get("status", "").lower()
    entry["reason"] = status.get("reason", "")
    if status.get("attention"):
        entry["attention"] = status["attention"]
    areas = (ev.get("track areas (from criteria.md)") or ev.get("track areas") or ev.get("strongest areas (their pick)")
             or ev.get("strongest areas", ""))
    areas = re.sub(r"\s*\(.*$", "", areas)
    entry["strongest_areas"] = [a.strip() for a in areas.split(",") if a.strip()]
    return entry


def from_map(rows):
    """The board's excerpt, missing list and first open question, read from Evidence Map rows."""
    excerpt, fallback, missing, question, counts = None, None, [], "", {}
    for r in rows:
        st = (r.get("status") or "").strip().lower()
        counts[st] = counts.get(st, 0) + 1
        side_row = re.match(r"\s*(clear written|communication|practical)", r.get("requirement", ""), re.I)
        for p in evidence_map.cell_lines(r.get("evidence", "")):
            m = evidence_map.QUOTE_RE.match(p)
            if m and not side_row:
                if excerpt is None and st == "met":
                    excerpt = {"quote": m.group(1), "source": m.group(2)}
                if fallback is None:
                    fallback = {"quote": m.group(1), "source": m.group(2)}
                break
        for p in evidence_map.cell_lines(r.get("missing", "")):
            if p.lower() not in ("nothing", "none", "-"):
                missing.append(p)
        if not question and st in ("ask", "not shown", "human review required") and r.get("question"):
            question = " ".join(evidence_map.cell_lines(r["question"]))
    return excerpt or fallback, missing, question, counts


def load_candidates(root):
    out_dir = os.path.join(root, "out")
    scores = load_json(os.path.join(out_dir, "scores.json"))
    source = "out/scores.json"
    files = sorted(glob.glob(os.path.join(out_dir, "candidates", "*.md")))
    dossiers = {os.path.splitext(os.path.basename(p))[0]: p for p in files}
    if scores and scores.get("candidates"):
        cands = scores["candidates"]
        criteria = scores.get("criteria") or {}
    else:
        if not files:
            sys.exit("found neither out/scores.json nor out/candidates/*.md under %s" % root)
        cands = [parse_dossier(p) for p in files]
        criteria = {}
        source = "out/candidates/*.md (no scores.json)"
    apps = load_json(os.path.join(out_dir, "applications.json")) or {}
    by_slug = {a["slug"]: a for a in apps.get("applications", [])}
    if not criteria:
        criteria = apps.get("criteria") or {}
    blind = (load_json(os.path.join(out_dir, "blind", "map.json")) or {}).get("ids", {})
    blind_by_slug = {v: k for k, v in blind.items()}
    hidden = (load_json(os.path.join(out_dir, "blind", "hidden.json")) or {}).get("candidates", {})
    warnings, control, kept = [], None, []
    for c in cands:
        a = by_slug.get(c.get("slug"), {})
        for key in ("name", "location", "ask_text", "ask_usd", "availability", "source", "date", "budget_fit"):
            if not c.get(key) and a.get(key) is not None:
                c[key] = a[key]
        if "cv" not in c or c["cv"] in ("", None):
            c["cv"] = "yes" if a.get("cv_text") else ("no" if a else "")
        c["flags"] = norm_flags(c.get("flags"))
        c["status"] = (c.get("status") or "").lower().strip()
        c["shared"] = whole(c.get("shared"))
        c["track"] = whole(c.get("track"))
        c["strongest_areas"] = list(c.get("strongest_areas") or [])[:2]
        c["questions"] = list(c.get("questions") or [])
        c["reason"] = c.get("reason") or ""
        c["blind_id"] = c.get("blind_id") or blind_by_slug.get(c["slug"], "")
        if c["slug"] == CONTROL_SLUG or c.get("control"):
            control = c
            continue
        # Evidence Map: the dossier is the record. scores.json may carry the same fields; it wins.
        rows = []
        if c["slug"] in dossiers:
            rows = evidence_map.read_dossier(dossiers[c["slug"]])["rows"]
            parsed = parse_dossier(dossiers[c["slug"]])
            if "insufficient_evidence" not in c:
                c["insufficient_evidence"] = parsed.get("insufficient_evidence", False)
            if not c.get("attention") and parsed.get("attention"):
                c["attention"] = parsed["attention"]
        excerpt, missing, question, counts = from_map(rows)
        c["excerpt"] = c.get("excerpt") or excerpt
        c["missing"] = c.get("missing") or missing
        if isinstance(c["missing"], str):
            c["missing"] = [c["missing"]]
        c["question"] = c.get("question") or question or (c["questions"][0] if c["questions"] else "")
        c["map_counts"] = counts
        c["has_map"] = bool(rows)
        c["insufficient_evidence"] = bool(c.get("insufficient_evidence")) and c["status"] != "out of budget"
        c["hidden"] = c["slug"] in hidden
        if c["hidden"] and not any(HIDDEN_FLAG in fl["text"].lower() for fl in c["flags"]):
            n = len(hidden[c["slug"]].get("findings", []))
            c["flags"].insert(0, {"color": "red", "text": "%s (%d finding%s, see out/blind/HIDDEN.md)." % (
                HIDDEN_FLAG.capitalize(), n, "" if n == 1 else "s")})
        p2 = c.get("pass2") or {}
        c["unstable"] = False
        if p2 and c["status"] != "out of budget":
            # the second pass repeats the screening, so it is compared with the screening numbers
            first = c.get("screening") if isinstance(c.get("screening"), dict) else {}
            s1, k1 = whole(first.get("shared"), c["shared"]), whole(first.get("track"), c["track"])
            s2, t2 = whole(p2.get("shared"), s1), whole(p2.get("track"), k1)
            t1, tot2 = s1 + k1, s2 + t2
            c["pass2_diff"] = abs(tot2 - t1)
            if c["pass2_diff"] > PASS2_LIMIT or band(t1) != band(tot2):
                c["unstable"] = True
                text = ("Second pass total %d, first pass %d (%s band, then %s band; SHARED %d then %d, TRACK %d then %d): "
                        "the two passes disagree, read the evidence yourself." % (
                            tot2, t1, band(t1), band(tot2), s1, s2, k1, t2))
                if not any("second pass" in fl["text"].lower() for fl in c["flags"]):
                    c["flags"].append({"color": "yellow", "text": text})
                warnings.append("%s: %s" % (c["name"], text))
        kept.append(c)
    lo_hi = control_band(root)
    if control is not None:
        control["total"] = control["shared"] + control["track"]
        control["band"] = lo_hi
        if lo_hi and not (lo_hi[0] <= control["total"] <= lo_hi[1]):
            warnings.append("Control CV scored %d (SHARED %d, TRACK %d), outside its expected band %d to %d. "
                            "The rubric drifted this batch: read the evidence lines before trusting any number near a line."
                            % (control["total"], control["shared"], control["track"], lo_hi[0], lo_hi[1]))
    else:
        warnings.append("No control CV in this batch. Write hiring/control-cv.txt for this role (templates/control-cv.txt), "
                        "run redact.py and score out/blind/%s.txt with the others, so drift shows." % CONTROL_ID)
    return kept, criteria, source, control, warnings, hidden


def read_role(root, criteria):
    if criteria.get("role"):
        return criteria["role"]
    path = os.path.join(root, "criteria.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            m = re.search(r"^#\s*(?:hiring criteria:\s*)?(.+)$", f.read(), re.I | re.M)
        if m:
            return m.group(1).strip()
    return "the role"


# ---------- ranking and attention ----------

def rank(cands):
    def key(c):
        scored = c["status"] != "out of budget"
        return (scored, not c.get("insufficient_evidence"), c["shared"] + c["track"], c["shared"], c["track"])
    ordered = sorted(cands, key=key, reverse=True)
    for i, c in enumerate(ordered, 1):
        scored = c["status"] != "out of budget"
        c["rank"] = i if scored else ""
        c["total"] = c["shared"] + c["track"] if scored else None
    return ordered


def attention_items(c, waiting_days):
    """What needs the founder's attention on this row, most urgent first. Short, plain words."""
    items = []
    wd = c.get("waiting_days")
    if wd is not None and wd > waiting_days and c["status"] not in ("hired", "closed"):
        items.append("Waiting %d days" % wd)
    own = (c.get("attention") or "").strip().rstrip(".")
    if c.get("hidden") and "hidden text" not in own.lower():
        items.append("Hidden text found, ignored")
    if c.get("unstable"):
        items.append("Two passes disagree: read the evidence")
    items.append(own or DEFAULT_ATTENTION.get(c["status"], ""))
    return [i for i in items if i]


# ---------- outputs ----------

def write_csv(path, cands):
    cols = ["rank", "name", "blind_id", "location", "ask", "budget_fit", "shared", "track", "total", "total_band",
            "evidence_level", "status", "attention", "reason", "excerpt", "missing", "question", "strongest_areas",
            "flags", "waiting_days", "source", "date", "slug"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for c in cands:
            scored = c["total"] is not None
            ex = c.get("excerpt") or {}
            w.writerow([c["rank"], c["name"], c.get("blind_id", ""), c["location"], c.get("ask_text", ""),
                        c.get("budget_fit", ""), c["shared"] if scored else "", c["track"] if scored else "",
                        c["total"] if scored else "", band(c["total"]) if scored else "",
                        ("insufficient" if c.get("insufficient_evidence") else "enough for a number") if scored else "not scored",
                        c["status"], " · ".join(c.get("attention_items", [])), c["reason"],
                        ('"%s" (%s)' % (ex.get("quote", ""), ex.get("source", ""))) if ex else "",
                        "; ".join(c.get("missing", [])), c.get("question", ""), "; ".join(c["strongest_areas"]),
                        "; ".join("%s: %s" % (fl["color"], fl["text"]) for fl in c["flags"]),
                        c.get("waiting_days", ""), c.get("source", ""), c.get("date", ""), c["slug"]])


BOARD_CSS = """
.lead{margin:0 0 6px;font-size:21px;color:var(--muted);max-width:1700px}
.lead b{color:var(--ink)}
.morning{margin:0 0 12px;font-size:21px}
.morning b{font-weight:700}
.morning a{font-weight:600}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 14px}
.bar button{font:inherit;font-size:19px;font-weight:600;color:var(--ink);background:var(--card);border:1px solid #c9ced5;
 border-radius:999px;padding:6px 16px;cursor:pointer}
.bar button.on{background:#111827;color:#fff;border-color:#111827}
.bar .count{font-weight:500;opacity:.75;margin-left:6px}
.warnline{background:var(--warn-bg);color:var(--warn);border-radius:10px;padding:8px 14px;margin:0 0 12px;font-size:20px;max-width:1700px}
table.board{border-collapse:separate;border-spacing:0;width:100%;background:var(--card);border:1px solid var(--line);border-radius:14px}
table.board thead th{position:sticky;top:var(--hdr,84px);z-index:10;background:#eef0f2;text-align:left;font-size:18px;font-weight:700;
 letter-spacing:.04em;text-transform:uppercase;color:#3d4753;padding:10px 12px;border-bottom:1px solid var(--line);
 cursor:pointer;user-select:none;white-space:nowrap;vertical-align:bottom}
table.board thead th.wrap{white-space:normal}
table.board thead th small{display:block;font-size:16px;font-weight:500;text-transform:none;letter-spacing:0;color:var(--muted)}
table.board thead th.num{text-align:right}
table.board thead th .arrow{font-size:14px;margin-left:4px;opacity:.6}
table.board tbody td{padding:11px 12px;border-bottom:1px solid var(--line);font-size:20px;line-height:1.35;vertical-align:middle}
tbody.cand{cursor:pointer}
tbody.cand:hover td{background:#fafbfc}
tbody.cand.open tr.main td{background:#f3f6fb}
td.name{font-weight:700;font-size:21px;white-space:nowrap}
table.board{table-layout:fixed}
col.c-name{width:220px}col.c-loc{width:235px}col.c-ask{width:105px}col.c-fit{width:245px}
col.c-sh{width:135px}col.c-tr{width:160px}col.c-st{width:250px}
td.name{overflow:hidden;text-overflow:ellipsis}
td.name a{text-decoration:none;border-bottom:2px solid #c9ced5}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.sc{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
td.sc b{font-size:24px}
td.sc .bd{display:inline-block;margin-left:8px;font-size:16px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;
 padding:2px 8px;border-radius:999px;vertical-align:2px}
.bd.top{background:var(--met-bg);color:var(--met)}.bd.solid{background:var(--ask-bg);color:var(--ask)}
.bd.mixed{background:var(--warn-bg);color:var(--warn)}.bd.thin{background:var(--not-bg);color:var(--not)}
td.insuff{color:var(--warn);font-weight:700;font-size:19px;line-height:1.25}
td.ns{color:var(--muted);font-size:19px}
.pill{display:inline-block;font-size:18px;font-weight:600;padding:3px 12px;border-radius:999px;white-space:nowrap}
.fit-in{background:var(--met-bg);color:var(--met)}.fit-above{background:var(--warn-bg);color:var(--warn)}
.fit-out{background:var(--alert-bg);color:var(--alert)}.fit-unknown{background:var(--not-bg);color:var(--not)}
.st-call{background:var(--ask-bg);color:var(--ask)}.st-questionnaire{background:#ede9fe;color:#5b21b6}
.st-hold{background:var(--warn-bg);color:var(--warn)}.st-no,.st-out{background:var(--not-bg);color:var(--not)}
.st-hired{background:var(--met-bg);color:var(--met)}
td.att{font-size:20px}
td.att .urgent{color:var(--alert);font-weight:700}
td.att .hid{color:var(--alert);font-weight:700}
tr.detail{display:none}
tbody.open tr.detail{display:table-row}
tr.detail td{background:#f3f6fb;padding:4px 18px 18px;font-size:20px;cursor:default}
.dgrid{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:12px 28px}
.dgrid .bd{display:inline-block;font-size:16px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:2px 8px;border-radius:999px}
.dgrid h4{margin:6px 0 4px;font-size:16px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.dgrid p{margin:0 0 6px}
.dgrid blockquote{margin:0;padding-left:12px;border-left:4px solid #c7cdd4}
.dgrid cite{font-style:normal;font-size:16px;font-weight:700;color:var(--muted);margin-left:6px;text-transform:uppercase}
.dgrid ul{margin:0;padding-left:22px}
.dlinks{margin-top:10px;font-size:19px}
.dlinks a{margin-right:22px;font-weight:600}
.dlinks span{color:var(--muted)}
.legend{margin-top:26px;color:var(--muted);font-size:19px;max-width:1700px}
.legend p{margin:6px 0}
.legend b{color:var(--ink)}
@media (max-width:1100px){.dgrid{grid-template-columns:1fr}}
@media (max-width:900px){table.board{display:block;overflow-x:auto}}
"""

BOARD_JS = r"""
(function(){
  var hdr = document.querySelector('header.top');
  function setHdr(){ document.documentElement.style.setProperty('--hdr', hdr.offsetHeight + 'px'); }
  setHdr(); window.addEventListener('resize', setHdr);
  var table = document.querySelector('table.board');
  var bodies = Array.prototype.slice.call(table.querySelectorAll('tbody.cand'));
  bodies.forEach(function(tb){
    tb.querySelector('tr.main').addEventListener('click', function(e){
      if (e.target.closest('a')) return;
      tb.classList.toggle('open');
    });
  });
  var ths = table.querySelectorAll('thead th[data-key]'), dir = {};
  ths.forEach(function(th){
    th.addEventListener('click', function(){
      var k = th.dataset.key, num = th.dataset.type === 'num';
      dir[k] = dir[k] === 'desc' ? 'asc' : 'desc';
      var m = dir[k] === 'asc' ? 1 : -1;
      bodies.sort(function(a, b){
        var x = a.dataset[k], y = b.dataset[k];
        if (num) { x = x === '' ? -1e9 : parseFloat(x); y = y === '' ? -1e9 : parseFloat(y); return (x - y) * m; }
        return x.localeCompare(y) * m;
      });
      bodies.forEach(function(tb){ table.appendChild(tb); });
      ths.forEach(function(t){ t.querySelector('.arrow').textContent = ''; });
      th.querySelector('.arrow').textContent = dir[k] === 'asc' ? '▲' : '▼';
    });
  });
  var btns = document.querySelectorAll('.bar button[data-filter]');
  btns.forEach(function(b){
    b.addEventListener('click', function(){
      var f = b.dataset.filter;
      btns.forEach(function(x){ x.classList.toggle('on', x === b); });
      bodies.forEach(function(tb){
        var show = f === 'all' || tb.dataset.status === f || (f === 'waiting' && tb.dataset.late === '1');
        tb.style.display = show ? '' : 'none';
      });
    });
  });
  function openHash(){
    var id = decodeURIComponent((location.hash || '').slice(1));
    if (!id) return;
    var tb = document.getElementById(id);
    if (!tb || !tb.classList.contains('cand')) return;
    tb.classList.add('open');
    var y = tb.getBoundingClientRect().top + window.scrollY - hdr.offsetHeight - 70;
    window.scrollTo(0, Math.max(0, y));
  }
  window.addEventListener('hashchange', openHash); openHash();
})();
"""


def fit_class(fit):
    fit = (fit or "").lower()
    if fit.startswith("in target"):
        return "fit-in"
    if fit.startswith("above") or fit.startswith("under"):
        return "fit-above"
    if fit.startswith("out"):
        return "fit-out"
    return "fit-unknown"


def status_class(status):
    return "st-out" if status == "out of budget" else "st-" + (status or "none").replace(" ", "-")


def score_td(value):
    return '<td class="sc"><b>%d</b></td>' % value


def detail_html(c):
    ex = c.get("excerpt")
    if c["status"] == "out of budget":
        left = "<h4>Card only</h4><p>The ask is above the hard maximum. No scoring, no research, no questions.</p>"
    elif ex:
        left = "<h4>Source behind the score</h4><blockquote>%s<cite>%s</cite></blockquote>" % (
            esc(ex.get("quote")), esc(ex.get("source")))
    else:
        left = "<h4>Source behind the score</h4><p>No quote recorded. Open the dossier.</p>"
    if c.get("insufficient_evidence"):
        left += ("<h4>Why there is no number here</h4><p>The file shows too little for a number to mean anything. "
                 "The provisional scores stay in the dossier; the follow-up decides.</p>")
    elif c["total"] is not None:
        b = band(c["total"])
        left += ('<h4>Total and band</h4><p>%d of 100, <span class="bd %s">%s</span> band. A 72 and a 76 are the same '
                 'thing.</p><h4>Track areas</h4><p>%s. Not directly comparable across tracks.</p>' % (
                     c["total"], b, b, esc(", ".join(c["strongest_areas"]) or "not named")))
    miss = "".join("<li>%s</li>" % esc(m) for m in c.get("missing", [])[:4]) or "<li>Nothing recorded</li>"
    mid = "<h4>Missing evidence</h4><ul>%s</ul>" % miss
    q = c.get("question") or ""
    flags = "".join("<li>%s</li>" % esc(fl["text"]) for fl in c["flags"][:3])
    right = ("<h4>Question that closes the gap</h4><p>%s</p>" % esc(q) if q else "") + (
        "<h4>Flags (questions, not verdicts)</h4><ul>%s</ul>" % flags if flags else "")
    links = []
    if c.get("has_map"):
        links.append('<a href="evidence/%s.html">Evidence Map</a>' % esc(c["slug"]))
    links.append('<a href="candidates/%s.md">Dossier</a>' % esc(c["slug"]))
    if c.get("draft"):
        links.append('<a href="messages/%s">Draft message (not sent)</a>' % esc(c["draft"]))
    if c.get("reason"):
        links.append('<span>%s</span>' % esc(c["reason"]))
    return ('<div class="dgrid"><div>%s</div><div>%s</div><div>%s</div></div><div class="dlinks">%s</div>'
            % (left, mid, right, "".join(links)))


def write_html(path, cands, role, today, demo, control, warnings, morning, waiting_days):
    total_n = len(cands)
    by_status = {}
    for c in cands:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    late_n = sum(1 for c in cands if c.get("late"))
    title = "%d applications%s" % (total_n, " · FICTIONAL DEMO" if demo else "")
    parts = []
    parts.append('<p class="lead">Sorted by <b>SHARED + TRACK</b>, each out of 50 and resting on a quote. A score organises '
                 'evidence; it does not predict who will do the job best. Click a row for the source.</p>')
    nd = len(morning["decisions"])
    parts.append('<p class="morning">Since yesterday: <b>%s</b> · <b>%d</b> decision%s waiting for you · <b>%d</b> '
                 'waiting more than %d days for a reply. <a href="MORNING.md">The list</a></p>' % (
                     esc(morning["new_text"]), nd, "" if nd == 1 else "s", len(morning["late"]), waiting_days))
    for w in warnings:
        if w.lower().startswith("control cv scored") or w.lower().startswith("no control cv"):
            parts.append('<div class="warnline">%s</div>' % esc(w))
    chips = ['<button type="button" class="on" data-filter="all">All<span class="count">%d</span></button>' % total_n]
    for s in STATUS_ORDER:
        if s in by_status:
            chips.append('<button type="button" data-filter="%s">%s<span class="count">%d</span></button>' % (
                esc(s), esc(STATUS_LABEL.get(s, s)), by_status[s]))
    if late_n:
        chips.append('<button type="button" data-filter="waiting">Waiting over %d days<span class="count">%d</span></button>'
                     % (waiting_days, late_n))
    parts.append('<div class="bar">%s</div>' % "".join(chips))
    parts.append('<table class="board"><colgroup><col class="c-name"><col class="c-loc"><col class="c-ask">'
                 '<col class="c-fit"><col class="c-sh"><col class="c-tr"><col class="c-st"><col></colgroup><thead><tr>'
                 '<th data-key="name">Name<span class="arrow"></span></th>'
                 '<th data-key="location">Location<span class="arrow"></span></th>'
                 '<th data-key="ask" data-type="num" class="num">Ask<span class="arrow"></span></th>'
                 '<th data-key="fit">Budget fit<span class="arrow"></span></th>'
                 '<th data-key="shared" data-type="num" class="num">SHARED<span class="arrow"></span><small>same for all</small></th>'
                 '<th data-key="track" data-type="num" class="num wrap">TRACK<span class="arrow"></span><small>not comparable across tracks</small></th>'
                 '<th data-key="status">Status<span class="arrow"></span></th>'
                 '<th data-key="att">What needs your attention<span class="arrow"></span></th>'
                 '</tr></thead>')
    for c in cands:
        scored = c["total"] is not None
        ins = c.get("insufficient_evidence")
        ask = c.get("ask_usd")
        ask_text = c.get("ask_text") or ""
        monthly = ask and (not ask_text or re.search(r"month|/mo|^\s*\$?[\d,]+\s*$", ask_text, re.I))
        ask_cell = ("$%s" % format(ask, ",")) if monthly else esc(ask_text or "not given")
        sort_total = c["total"] if (scored and not ins) else (c["total"] - 200 if scored else -999)
        att = c.get("attention_items", [])
        att_html = []
        for a in att:
            cls = "urgent" if a.startswith("Waiting ") else ("hid" if a.lower().startswith("hidden text") else "")
            att_html.append('<span class="%s">%s</span>' % (cls, esc(a)) if cls else esc(a))
        parts.append('<tbody class="cand" id="%s" data-name="%s" data-location="%s" data-ask="%s" data-fit="%s" '
                     'data-shared="%s" data-track="%s" data-total="%s" data-status="%s" data-att="%s" data-late="%s">' % (
                         esc(c["slug"]), esc(c["name"].lower()), esc((c.get("location") or "").lower()),
                         ask if ask else "", esc(c.get("budget_fit") or "unknown"),
                         (c["shared"] if not ins else c["shared"] - 100) if scored else "",
                         (c["track"] if not ins else c["track"] - 100) if scored else "",
                         sort_total, esc(c["status"]), esc(" ".join(att).lower()), "1" if c.get("late") else "0"))
        parts.append('<tr class="main">')
        name_link = ('<a href="evidence/%s.html">%s</a>' % (esc(c["slug"]), esc(c["name"]))) if c.get("has_map") else esc(c["name"])
        parts.append('<td class="name">%s</td>' % name_link)
        parts.append("<td>%s</td>" % esc(c.get("location", "")))
        parts.append('<td class="num">%s</td>' % ask_cell)
        parts.append('<td><span class="pill %s">%s</span></td>' % (fit_class(c.get("budget_fit")), esc(c.get("budget_fit") or "unknown")))
        if not scored:
            parts.append('<td class="ns" colspan="2">Not scored: out of budget</td>')
        elif ins:
            parts.append('<td class="insuff" colspan="2">%s</td>' % esc(INSUFFICIENT_TEXT))
        else:
            parts.append(score_td(c["shared"]) + score_td(c["track"]))
        parts.append('<td><span class="pill %s">%s</span></td>' % (status_class(c["status"]),
                                                                  esc(STATUS_LABEL.get(c["status"], c["status"] or "?"))))
        parts.append('<td class="att">%s</td>' % " · ".join(att_html))
        parts.append("</tr>")
        parts.append('<tr class="detail"><td colspan="8">%s</td></tr></tbody>' % detail_html(c))
    parts.append("</table>")
    legend = ['<div class="legend">',
              "<p><b>SHARED</b> (0 to 50): Amazon operations, AI in practice with checks, ownership, business sense, "
              "communication, 10 points each, the same for everyone. Compare people here.</p>",
              "<p><b>TRACK</b> (0 to 50): evidence in two of the role's areas from criteria.md, 25 points each: at screening the "
              "two the file shows best, after the questionnaire the two the person picked. A listing person and an automation "
              "builder can both score 40 for different things: not directly comparable across tracks.</p>",
              "<p><b>Not shown</b>: a part the file does not show is a question, left out of the number, never a 0.</p>",
              "<p><b>Bands</b>: %s, on the total. A 72 and a 76 are the same thing; read the evidence, not the point.</p>" % BAND_TEXT,
              "<p><b>Insufficient evidence. Follow-up required.</b> The file shows too little for a number to mean anything. "
              "Low means unknown, not weak. The next step is a question, not a no.</p>",
              "<p><b>Budget fit</b>: in target, above target but under the hard maximum, or out of budget (Card only, not scored).</p>",
              "<p><b>Scored blind</b>: the scoring read a copy with name, contact details, age, nationality and family status "
              "removed (out/blind/), one candidate per pass. The map from id to name stays on this machine.</p>"]
    if control is not None:
        lo_hi = control.get("band")
        inside = lo_hi and lo_hi[0] <= control["total"] <= lo_hi[1]
        legend.append("<p><b>Control CV</b> (%s): %d this batch (SHARED %d, TRACK %d), %s.</p>" % (
            CONTROL_ID, control["total"], control["shared"], control["track"],
            ("inside its band %d to %d, the rubric held" % lo_hi) if inside else
            ("outside its band %d to %d" % lo_hi if lo_hi else "no expected band in control-cv.txt")))
    for w in warnings:
        if not (w.lower().startswith("control cv scored") or w.lower().startswith("no control cv")):
            legend.append("<p>%s</p>" % esc(w))
    legend.append("<p>Built %s from out/scores.json and the dossiers. Every name opens its Evidence Map; every row opens to "
                  "the source quote. Drafts are in messages/, written, not sent.</p></div>" % esc(today))
    parts.append("".join(legend))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page(title, "Candidate board: %s" % role, "\n".join(parts), demo, BOARD_CSS, BOARD_JS))


def one_line(c):
    areas = ", ".join(c["strongest_areas"]) if c["strongest_areas"] else "no areas named"
    if c["total"] is None:
        score = "not scored"
    elif c.get("insufficient_evidence"):
        score = "insufficient evidence, follow-up required"
    else:
        score = "SHARED %d, TRACK %d, total %d: %s" % (c["shared"], c["track"], c["total"], band(c["total"]))
    bits = ["**%s** (%s, %s, %s)" % (c["name"], c.get("location") or "location unknown", c.get("ask_text") or "no ask", score)]
    bits.append(c["reason"].rstrip(". ") if c["reason"] else "strongest in %s" % areas)
    return ". ".join(bits) + "."


def write_summary(path, cands, role, today, drafts, source, control, warnings, waiting_rows, waiting_days):
    groups = {s: [c for c in cands if c["status"] == s] for s in STATUS_ORDER}
    unknown = [c for c in cands if c["status"] not in STATUS_ORDER]
    n_ins = sum(1 for c in cands if c.get("insufficient_evidence"))
    lines = ["# Screening summary: %s" % role, "",
             "%s. %d applications, %d scored blind, one candidate per pass; %d of them with too little evidence for a "
             "number (\"Insufficient evidence. Follow-up required.\"). Scores come from the examples, never from "
             "self-ratings, and organise evidence; they do not predict who will do the job best. Read the band (%s), "
             "not the rank. Budget fit is separate. Nothing here was sent to anyone."
             % (today, len(cands), len([c for c in cands if c["total"] is not None]), n_ins, BAND_TEXT), ""]
    lines.append("## Waiting on you for more than %d days" % waiting_days)
    if waiting_rows:
        for r in waiting_rows:
            lines.append("- **%s** (%s): %d days, since %s." % (r["name"], r["status"] or "no status", r["days"], r["since"]))
        lines.append("- Send the drafts in `out/messages/`, then add a Log line (\"%s Decline sent.\") and the clock stops." % today)
    else:
        lines.append("- Nobody. Keep it that way.")
    lines += ["", "## Batch checks"]
    if control is not None:
        lo_hi = control.get("band")
        inside = lo_hi and lo_hi[0] <= control["total"] <= lo_hi[1]
        lines.append("- Control CV (%s): %d (SHARED %d, TRACK %d), %s." % (
            CONTROL_ID, control["total"], control["shared"], control["track"],
            ("inside its band %d to %d, the rubric held" % lo_hi) if inside else
            ("OUTSIDE its band %d to %d, the rubric drifted this batch" % lo_hi if lo_hi else "no band set")))
    for w in warnings:
        if not w.lower().startswith("control cv scored"):
            lines.append("- %s" % w)
    lines.append("")

    def section(title, items, numbered=False):
        lines.append("## %s" % title)
        if not items:
            lines.append("- Nobody.")
        for i, c in enumerate(items, 1):
            lines.append(("%d. " % i if numbered else "- ") + one_line(c))
        lines.append("")

    section("Talk to first", groups["call"], numbered=True)
    section("Send the questionnaire", groups["questionnaire"])
    section("On hold", groups["hold"])
    section("Out", groups["no"] + groups["out of budget"])
    if groups["hired"] or groups["closed"]:
        section("Closed", groups["hired"] + groups["closed"])
    if unknown:
        section("Status not recognised (fix in scores.json)", unknown)
    red = [c for c in cands if any(f["color"] == "red" for f in c["flags"])]
    if red:
        lines.append("## Needs a direct answer before any next step")
        for c in red:
            for fl in c["flags"]:
                if fl["color"] == "red":
                    lines.append("- %s: %s" % (c["name"], fl["text"]))
        lines.append("")
    lines += ["## Files",
              "- Board: `out/board.html` and `out/board.csv` (built from %s)." % source,
              "- Evidence Maps: `out/evidence/<slug>.html`. Dossiers: `out/candidates/<slug>.md`.",
              "- Morning list: `out/MORNING.md`.",
              "- Drafts: %d files in `out/messages/`. Read, edit, and send them yourself. The assistant does not send." % drafts, ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------- the morning routine ----------

def morning_state(out_dir, cands, today):
    """Compare with the last board. Returns (new slugs, or None when there is no earlier board; changed; state; path)."""
    path = os.path.join(out_dir, "board-state.json")
    prev = load_json(path) or {}
    if prev.get("date") == today.isoformat():
        base = prev.get("before")           # a second run on the same day compares with the same yesterday
    else:
        base = {"date": prev.get("date"), "slugs": prev.get("slugs")} if prev.get("slugs") else None
    now = {c["slug"]: c["status"] for c in cands}
    if base and base.get("slugs"):
        new = [s for s in now if s not in base["slugs"]]
        changed = [(s, base["slugs"][s], now[s]) for s in now if s in base["slugs"] and base["slugs"][s] != now[s]]
    else:
        new, changed = None, []
    state = {"date": today.isoformat(), "slugs": now, "before": base}
    return new, changed, state, path


def unscored_in_inbox(root, cands):
    """Applications in inbox/ with no row on the board: not parsed, not blinded or not scored yet."""
    inbox = os.path.join(root, "inbox")
    if not os.path.isdir(inbox):
        return []
    on_board = {c["slug"] for c in cands} | {CONTROL_SLUG}
    rows = []
    for fname in parse_inbox.message_files(inbox):
        slug = re.sub(r"\.(md|txt)$", "", fname)
        if slug in on_board:
            continue
        fields = parse_inbox.parse_header(open(os.path.join(inbox, fname), encoding="utf-8", errors="replace").read())[0]
        rows.append({"slug": slug, "file": fname, "name": fields.get("name") or parse_inbox.slug_to_name(slug),
                     "date": fields.get("date", "")})
    return rows


def build_morning(cands, today, new, changed, base_date, unscored=()):
    by_slug = {c["slug"]: c for c in cands}
    if new is None:
        since = (today - timedelta(days=1)).isoformat()
        new = [c["slug"] for c in cands if (c.get("date") or "") >= since]
        new_basis = "applications dated %s or later (no earlier board to compare with)" % since
    else:
        new_basis = "applications not on the board of %s" % base_date
    worth = [by_slug[s] for s in new if by_slug[s]["status"] in ("call", "questionnaire", "hold")]
    worth.sort(key=lambda c: -(c["total"] or 0))
    decisions = [c for c in cands if c["status"] in ("call", "questionnaire", "hold") and c.get("waiting_days") is not None]
    # A flag (hidden text, two passes apart, a row for human review) waits on the founder until the Log says a
    # reply went out: after that the decision was made, and the flag stays on the board row.
    decisions += [c for c in cands if c not in decisions and (c.get("hidden") or c.get("unstable")
                                                              or c.get("map_counts", {}).get("human review required"))
                  and not c.get("answered")
                  and c["status"] not in ("out of budget", "hired", "closed")]
    late = sorted([c for c in cands if c.get("late")], key=lambda c: -c["waiting_days"])
    if not new:
        new_text = "no new scored applications" if unscored else "no new applications"
    else:
        new_text = "%d new application%s, %d worth opening" % (len(new), "" if len(new) == 1 else "s", len(worth))
    if unscored:
        new_text += "; %d in inbox/ not scored yet" % len(unscored)
    return {"new": new, "worth": worth, "decisions": decisions, "late": late, "changed": changed,
            "new_text": new_text, "new_basis": new_basis, "unscored": list(unscored)}


def write_morning(path, m, today, waiting_days, by_slug, date_source=""):
    lines = ["# Morning: what changed since yesterday", "",
             ("%s (date from today.txt: remove the file to use today's date)" % today.isoformat()
              if date_source == "today.txt" else today.isoformat()) + ". The prompt: \"What changed since yesterday? Update the board and show what needs my decision.\" "
             "Three lists, in the order to work them. Read only: nothing was sent.", ""]
    lines.append("## 1. New applications worth opening")
    lines.append("Counted from %s: %s." % (m["new_basis"], m["new_text"]))
    for c in m["worth"]:
        lines.append("- **%s**: %s. %s" % (c["name"], STATUS_LABEL.get(c["status"], c["status"]),
                                            " · ".join(c.get("attention_items", []))))
    for u in m.get("unscored", []):
        lines.append("- **%s** (`inbox/%s`%s): not scored yet, so it is on no list below. Run parse_inbox.py and "
                     "redact.py, score the new blind file, then rebuild the board." % (
                         u["name"], u["file"], (", dated %s" % u["date"]) if u["date"] else ""))
    if not m["worth"] and not m.get("unscored"):
        lines.append("- None to open today.")
    lines += ["", "## 2. Decisions waiting for you"]
    for c in m["decisions"]:
        own = [a for a in c.get("attention_items", [])
               if not a.startswith("Waiting ") and a != DEFAULT_ATTENTION.get(c["status"])]
        lines.append("- **%s**: %s.%s" % (c["name"], STATUS_LABEL.get(c["status"], c["status"]),
                                           (" " + " · ".join(own) + ".") if own else ""))
    if not m["decisions"]:
        lines.append("- None.")
    lines += ["", "## 3. Waiting more than %d days for a reply" % waiting_days]
    for c in m["late"]:
        lines.append("- **%s**: %d days since %s. Draft: `out/messages/%s`." % (
            c["name"], c["waiting_days"], c.get("date") or "the application", c.get("draft") or "none"))
    if not m["late"]:
        lines.append("- Nobody.")
    if m["changed"]:
        lines += ["", "## Status changes since the last board"]
        for s, a, b in m["changed"]:
            lines.append("- %s: %s to %s." % (by_slug[s]["name"], a or "none", b))
    lines += ["", "Send what you approve from your own account, then add a dated Log line to the dossier "
              "(\"%s Invite sent.\") so tomorrow's list is right." % today.isoformat(), ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------- messages ----------

def load_templates(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    sections, current = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+([a-z0-9-]+)\s*$", line)
        if m:
            current = m.group(1)
            sections[current] = []
        elif current:
            sections[current].append(line)
    return {k: "\n".join(v).strip() + "\n" for k, v in sections.items()}


def first_name(name):
    return (name or "").split()[0] if name else "there"


def days_between(iso, today):
    try:
        return (today - date.fromisoformat(iso[:10])).days
    except (ValueError, TypeError):
        return None


KEY_WORDS = {"invite-questionnaire": r"questionnaire", "invite-call": r"\bcall\b|interview", "hold": r"\bhold\b",
             "decline": r"declin|rejection", "out-of-budget": r"budget|declin", "closing": r"\bclos|filled"}


def sent_keys(log, status):
    """The drafts the dossier Log says went out: a Log line that says sent and names the kind of message
    ("Questionnaire invite sent", "Decline sent"). A bare "Invite sent" counts for the invite of the current status."""
    keys = set()
    for line in log:
        if not waiting.SENT.search(line) or waiting.NOT_SENT.search(line) or waiting.BACK_TO_YOU.search(line):
            continue
        hit = {k for k, rx in KEY_WORDS.items() if re.search(rx, line, re.I)}
        if not hit and re.search(r"\binvite\b", line, re.I) and STATUS_TEMPLATE.get(status, "").startswith("invite"):
            hit = {STATUS_TEMPLATE[status]}
        keys |= hit
    return keys


def what_they_sent(c):
    return "your message and your CV" if str(c.get("cv") or "").lower().startswith("yes") else "your message"


CLOSING_FILE = "%s-closing-board.md"  # hire-test-task writes <slug>-closing.md; a draft there wins
SIGNED_LINE = "Send after the hire has signed."


def challenge_decisions(out_dir):
    """{slug: decision} from challenge/review.json, as hire-test-task records it ("hire for this role", "runner-up")."""
    review = load_json(os.path.join(os.path.dirname(os.path.abspath(out_dir)), "challenge", "review.json")) or {}
    return {k: str(v.get("decision") or "").strip().lower() for k, v in review.items() if isinstance(v, dict)}


def gets_closing(c, decisions, msg_dir):
    """Not the hire, not the runner-up (hire-test-task writes theirs), and nobody hire-test-task already drafted for."""
    if c["status"] == "hired" or re.match(r"(hire|hired|runner)", decisions.get(c["slug"], "")):
        return False
    return not os.path.exists(os.path.join(msg_dir, "%s-closing.md" % c["slug"]))


def write_messages(out_dir, cands, role, today, templates, late_days, close):
    """One draft per candidate and status, written once. A draft already in out/messages/ is never rewritten (the
    founder may have edited it), and no draft is written for a message the Log says was sent."""
    msg_dir = os.path.join(out_dir, "messages")
    os.makedirs(msg_dir, exist_ok=True)
    written, kept = [], 0
    late_line = templates.get("late-reply-line", "").strip()
    decisions = challenge_decisions(out_dir) if close else {}
    for c in cands:
        keys = []
        if c["status"] in STATUS_TEMPLATE:
            keys.append(STATUS_TEMPLATE[c["status"]])
        if close and gets_closing(c, decisions, msg_dir):
            keys.append("closing")
        dossier = os.path.join(out_dir, "candidates", c["slug"] + ".md")
        sent = sent_keys(waiting.read_dossier(dossier)["log"], c["status"]) if os.path.exists(dossier) else set()
        for key in keys:
            body = templates.get(key)
            if not body:
                continue
            fname = CLOSING_FILE % c["slug"] if key == "closing" else "%s-%s.md" % (c["slug"], key)
            path = os.path.join(msg_dir, fname)
            if os.path.exists(path):
                kept += 1
                if key != "closing":
                    c["draft"] = fname
                continue
            if key in sent:
                continue
            text = (body.replace("[Name]", first_name(c["name"])).replace("[role]", role)
                    .replace("[what you sent]", what_they_sent(c)))
            age = days_between(c.get("date", ""), today)
            if late_line and age is not None and age > late_days and key != "closing":
                text = re.sub(r"^(Hi [^\n]*\n\n)", r"\1" + late_line + "\n\n", text, count=1)
            header = ("<!-- Draft for %s, status: %s, written %s by build_board.py. Not sent. "
                      "Read it, change what you want, send it yourself. -->\n\n" % (c["name"], c["status"], today.isoformat()))
            if key == "closing":  # "the role has been filled" is only true once the hire has signed
                header = SIGNED_LINE + "\n\n" + header
            with open(path, "w", encoding="utf-8") as f:
                f.write(header + text)
            written.append(path)
            if key != "closing":
                c["draft"] = fname
    if kept:
        print("kept %d drafts already in %s (a rebuild never rewrites a draft)" % (kept, msg_dir))
    return written


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="hiring project root (holds criteria.md, inbox/, out/)")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, default is today")
    ap.add_argument("--late-days", type=int, default=2, help="add the late-reply line when the application is older than this")
    ap.add_argument("--close", action="store_true", help="also write closing drafts (<slug>-closing-board.md) for everyone "
                    "but the hire and the runner-up in challenge/review.json; send them after the hire has signed")
    ap.add_argument("--no-messages", action="store_true", help="skip the drafts")
    ap.add_argument("--no-evidence", action="store_true", help="skip the out/evidence/ pages")
    ap.add_argument("--waiting-days", type=int, default=5, help="list people who have waited on you more than this many days")
    ap.add_argument("--demo", dest="demo", action="store_true", default=None, help="force the FICTIONAL DEMO badge on")
    ap.add_argument("--no-demo", dest="demo", action="store_false", help="force the badge off")
    args = ap.parse_args()

    root = find_root(args.root)
    out_dir = os.path.join(root, "out")
    today, date_source = _today.project_today(root, args.today)
    _today.say_source(today, date_source)
    demo = is_demo(root, args.demo)

    cands, criteria, source, control, warnings, hidden = load_candidates(root)
    role = read_role(root, criteria)
    cands = rank(cands)

    bad = [c["slug"] for c in cands if c["status"] not in STATUS_ORDER]
    if bad:
        print("warning: status not recognised for %s (use: %s)" % (", ".join(bad), ", ".join(STATUS_ORDER[:5])))

    waiting_rows = waiting.waiting_list(root, today, args.waiting_days)
    all_waiting = {r["slug"]: r["days"] for r in waiting.waiting_list(root, today, -1)}
    answered = {d["slug"] for d in (waiting.read_dossier(p) for p in glob.glob(os.path.join(out_dir, "candidates", "*.md")))
                if waiting.reply_sent(d)}
    for c in cands:
        c["waiting_days"] = all_waiting.get(c["slug"])
        c["answered"] = c["slug"] in answered
        c["late"] = c["waiting_days"] is not None and c["waiting_days"] > args.waiting_days

    drafts = []
    if not args.no_messages:
        drafts = write_messages(out_dir, cands, role, today, load_templates(TEMPLATES), args.late_days, args.close)
    for c in cands:
        c["attention_items"] = attention_items(c, args.waiting_days)

    unscored = unscored_in_inbox(root, cands)
    if unscored:
        warnings.append("%d application%s in inbox/ not scored yet, so not on this board: %s. Run parse_inbox.py and "
                        "redact.py, score the new blind files, then rebuild." % (
                            len(unscored), "" if len(unscored) == 1 else "s", ", ".join(u["slug"] for u in unscored)))
    new, changed, state, state_path = morning_state(out_dir, cands, today)
    morning = build_morning(cands, today, new, changed, (state.get("before") or {}).get("date"), unscored)

    html_path = os.path.join(out_dir, "board.html")
    csv_path = os.path.join(out_dir, "board.csv")
    sum_path = os.path.join(out_dir, "SUMMARY.md")
    morning_path = os.path.join(out_dir, "MORNING.md")
    write_html(html_path, cands, role, today.isoformat(), demo, control, warnings, morning, args.waiting_days)
    write_csv(csv_path, cands)
    write_summary(sum_path, cands, role, today.isoformat(), len(drafts), source, control, warnings, waiting_rows, args.waiting_days)
    write_morning(morning_path, morning, today, args.waiting_days, {c["slug"]: c for c in cands}, date_source)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)
    pages = [] if args.no_evidence else evidence_map.build_pages(root, cands, hidden, demo)

    n_ins = sum(1 for c in cands if c.get("insufficient_evidence"))
    print("built from %s: %d candidates (%d with insufficient evidence, %d out of budget)" % (
        source, len(cands), n_ins, sum(1 for c in cands if c["status"] == "out of budget")))
    for c in cands[:15]:
        if c["total"] is None:
            score = "not scored"
        elif c.get("insufficient_evidence"):
            score = "insufficient evidence"
        else:
            score = "%2d + %2d = %3d %s" % (c["shared"], c["track"], c["total"], band(c["total"]))
        print("  %-4s %-5s %-24s %-24s %s" % (c["rank"] or "-", c.get("blind_id") or "", c["name"], score, c["status"]))
    if len(cands) > 15:
        print("  ... %d more rows on the board" % (len(cands) - 15))
    if control is not None:
        print("  control %s: %d (SHARED %d, TRACK %d), expected band %s" % (
            CONTROL_ID, control["total"], control["shared"], control["track"],
            "%d to %d" % control["band"] if control.get("band") else "not set"))
    for w in warnings:
        print("warning: %s" % w)
    print("morning: %s; %d decisions waiting; %d waiting more than %d days" % (
        morning["new_text"], len(morning["decisions"]), len(morning["late"]), args.waiting_days))
    for p in (html_path, csv_path, sum_path, morning_path, state_path):
        print("wrote %s" % p)
    if pages:
        print("wrote %d Evidence Map pages to %s" % (len(pages), os.path.join(out_dir, "evidence")))
    if drafts:
        print("wrote %d drafts to %s (not sent)" % (len(drafts), os.path.join(out_dir, "messages")))


if __name__ == "__main__":
    main()
