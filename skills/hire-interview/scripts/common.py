#!/usr/bin/env python3
"""Shared helpers for the hire-interview scripts. Standard library only, no network.

Not run on its own. The other scripts import it from the same folder.
"""
import html
import json
import os
import re
import sys

DASHES = ("\u2014", "\u2013")
WORD_SHARE_LABEL = ("WORD SHARE (share of transcript words), a coaching indicator, "
                    "not a target and not a candidate score")
SCORE_NOTE = ("Scores organise evidence. They are not validated predictions of who will do the job well, "
              "and a total is never a reason to stop thinking.")


def find_root(arg=None):
    """The hiring folder: the one that holds criteria.md. Accepts the folder itself or the one above it."""
    base = arg or "."
    for cand in (base, os.path.join(base, "hiring")):
        if os.path.isfile(os.path.join(cand, "criteria.md")):
            return os.path.normpath(cand)
    sys.exit(f"no criteria.md in {os.path.join(base, 'criteria.md')} or "
             f"{os.path.join(base, 'hiring', 'criteria.md')}. Run this from your hiring/ folder "
             "(the one that holds criteria.md) or from the folder above it, or pass --root path/to/hiring.")


def root_from_argv(argv):
    """Pull --root PATH out of argv. Returns (root, remaining args)."""
    args = list(argv)
    root = None
    if "--root" in args:
        k = args.index("--root")
        root = args[k + 1] if k + 1 < len(args) else None
        del args[k:k + 2]
    return find_root(root), args


def project_now(root, given=None):
    """The time to record: --now when given; else the date in today.txt (a demo, or a folder you are catching
    up on) with the clock's time; else the computer clock. Returns "YYYY-MM-DD HH:MM"."""
    import datetime as dt
    if given:
        return given
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    path = os.path.join(root, "today.txt")
    if not os.path.exists(path):
        return now
    first = (open(path, encoding="utf-8-sig").read().strip().splitlines() or [""])[0].strip()[:10]
    try:
        day = dt.date.fromisoformat(first)
    except ValueError:
        sys.exit(f"{path}: put one date like 2026-10-16 on the first line, or remove the file to use the computer's date.")
    print(f"date: {day.isoformat()} (from today.txt)")
    return f"{day.isoformat()} {now[11:]}"


def is_demo(root):
    """Demo mode (the FICTIONAL DEMO badge) is on when criteria.md says FICTIONAL DEMO."""
    try:
        return "FICTIONAL DEMO" in open(os.path.join(root, "criteria.md"), encoding="utf-8").read()
    except OSError:
        return False


def interviews_dir(root):
    return os.path.normpath(os.path.join(root, "out", "interviews"))


def slug_dir(root, slug):
    return os.path.join(interviews_dir(root), slug)


DEBRIEF = "CANDIDATE_DEBRIEF.md"


def stray_debriefs(d):
    """Other CANDIDATE_*.md files next to the debrief: copies under another name, which no script reads."""
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d) if re.fullmatch(r"candidate[_-]\w+\.md", n, re.I) and n != DEBRIEF)


def warn_strays(d, slug):
    for n in stray_debriefs(d):
        print(f"note: {slug}/{n} looks like a second copy of {DEBRIEF}. The ledger, the reference guide and the "
              f"decision table read {DEBRIEF}; move anything new into it, then remove {n} yourself.")


def load_prep(root):
    p = os.path.join(interviews_dir(root), "prep.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def prep_candidate(prep, slug):
    if not prep:
        return None
    return next((c for c in prep.get("candidates", []) if c.get("slug") == slug), None)


def core_questions(prep, slug):
    """The six questions for this candidate: five core ones plus their tailored follow-up (question 6).
    Returns a list of dicts {n, title, ask, anchors}. Empty list when prep.json is missing."""
    if not prep:
        return []
    out = [dict(q) for q in prep.get("core_questions", [])]
    c = prep_candidate(prep, slug)
    t = (c or {}).get("tailored") or {}
    q6 = dict(prep.get("tailored_question", {"n": 6, "title": "One tailored follow-up"}))
    q6["n"] = 6
    q6["ask"] = t.get("ask", "")
    q6["title"] = q6.get("title", "One tailored follow-up")
    q6.setdefault("anchors", {})
    out.append(q6)
    return out


def is_placeholder(value):
    """True for an unfilled template value such as "[one line of evidence]" or "[1]". A value that starts with
    a minute, "[03:10] showed the sheet", is evidence, not a placeholder, and so is a minute alone."""
    v = (value or "").strip()
    return bool(re.fullmatch(r"\[[^\]]*\]", v)) and not re.fullmatch(r"\[\d{1,2}:\d{2}(?::\d{2})?\]", v)


def md_section(text, heading_regex):
    """The body under the first '## <heading>' that matches, up to the next '## '. Empty when there is none."""
    m = re.search(r"^##\s+(?:\d+\.\s*)?" + heading_regex + r"[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def claim_check(root, slug):
    """The claim check for one candidate, out/verification/<slug>.md (written by claim_check.py).
    Returns {"file", "summary", "questions"} or None when it does not exist."""
    rel = f"out/verification/{slug}.md"
    p = os.path.join(root, *rel.split("/"))
    if not os.path.isfile(p):
        return None
    text = open(p, encoding="utf-8").read()
    summary = next((l.strip() for l in md_section(text, r"Summary").splitlines() if l.strip()), "")
    summary = summary.split(" No colour labels")[0].strip()
    qs = []
    for line in md_section(text, r"Questions for the call").splitlines():
        m = re.match(r"^\s*(?:\d+[.)]|[-*])\s+(.+)$", line)
        if m and not m.group(1).lower().startswith(("none", "(write")):
            qs.append(m.group(1).strip())
    return {"file": rel, "summary": summary, "questions": qs}


def coach_coverage(path):
    """The "Questions I covered" table of INTERVIEWER_COACH.md: [{n, asked}] with asked yes / partly / no, or None
    when the file or the table is missing. stats.py fills it from its word match; a person corrects it there,
    and the headline and the ledger read it."""
    if not os.path.isfile(path):
        return None
    rows = []
    for line in md_section(open(path, encoding="utf-8").read(), r"Questions I covered").splitlines():
        c = _row_cells(line) if line.strip().startswith("|") else []
        if len(c) >= 3 and c[0].isdigit():
            a = c[2].strip("* ").lower()
            asked = "partly" if a.startswith("part") else "yes" if a.startswith("yes") else "no" if a.startswith("no") else None
            if asked is None:
                return None
            rows.append({"n": int(c[0]), "asked": asked})
    return rows or None


def coverage_text(rows):
    """'5 of 6' or '5 of 6 (1 partly)' from coach_coverage rows."""
    n = sum(1 for r in rows if r["asked"] != "no")
    part = sum(1 for r in rows if r["asked"] == "partly")
    return f"{n} of {len(rows)}" + (f" ({part} partly)" if part else "")


EVIDENCE_MAP_COLS = ("requirement", "claim", "evidence", "missing", "question", "status")
QUOTE_RE = re.compile(r'^\s*["“](.+?)["”]\s*\(([^)]{1,40})\)\s*$')


def _row_cells(line):
    """One markdown table row split on pipes that are not escaped as \\|."""
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    cells, cur, i = [], [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if s[i] == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(s[i])
        i += 1
    cells.append("".join(cur).strip())
    return cells


def evidence_map(root, slug):
    """The dossier's Evidence Map, written by hire-applications in out/candidates/<slug>.md under "## Evidence Map":
    Requirement | Claim | Evidence (quoted) | Missing | Question | Status. Returns the rows as dicts with those
    six keys; [] when there is no dossier or no table."""
    p = os.path.join(root, "out", "candidates", f"{slug}.md")
    if not os.path.isfile(p):
        return []
    body = md_section(open(p, encoding="utf-8").read(), r"Evidence Map")
    rows, header = [], None
    for line in body.splitlines():
        if not line.strip().startswith("|"):
            if header and rows:
                break
            continue
        cells = _row_cells(line)
        if header is None:
            header = [c.lower().split("(")[0].strip() for c in cells]
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append({k: (cells[header.index(k)] if k in header and header.index(k) < len(cells) else "")
                     for k in EVIDENCE_MAP_COLS})
    return rows


def prep_from_evidence_map(rows):
    """Evidence / Missing / Questions for the prep card, from Evidence Map rows. Evidence: the quotes in rows marked
    Met or Ask (what the file shows). Missing and Questions: every row's Missing and Question cells that say
    something ("nothing" and "-" are skipped)."""
    split = lambda cell: [x.strip() for x in re.split(r"<br\s*/?>", cell or "", flags=re.I) if x.strip()]
    evidence, missing, questions = [], [], []
    for r in rows:
        if r.get("status", "").strip().lower().rstrip(".") in ("met", "ask"):
            for part in split(r.get("evidence")):
                m = QUOTE_RE.match(part)
                if m:
                    evidence.append({"text": m.group(1), "source": m.group(2)})
        missing += [x for x in split(r.get("missing")) if x.lower().rstrip(".") not in ("nothing", "none", "-")]
        q = " ".join(split(r.get("question")))
        if q and q.lower() not in ("-", "none", "no question needed"):
            questions.append(q)
    return {"evidence": evidence, "missing": missing, "questions": questions}


def no_dashes(text, where):
    for d in DASHES:
        if d in text:
            sys.exit(f"{where} contains a long dash (em or en dash). Replace it with a comma or a period and rerun.")
    return text


def write(path, text, where=None):
    no_dashes(text, where or path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {os.path.normpath(path)}")


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


# ---------- the page look shared by PREP.html, LEDGER.html and the .md views ----------

CSS = """
:root{--bg:#f5f3ee;--card:#fff;--ink:#1b1b1d;--mute:#5d5d63;--line:#dedad0;--acc:#1f3a5f;--acc2:#9a5b13;
--ok:#1d6b3d;--warn:#8a5300;--no:#9b1c1c;--soft:#eef2f7;--warm:#fdf4e6}
*{box-sizing:border-box}
html{font-size:22px}
body{margin:0;background:var(--bg);color:var(--ink);font:400 22px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
header.top{background:var(--acc);color:#fff;padding:26px 40px 22px;padding-right:330px;position:relative}
header.top h1{margin:0;font-size:40px;line-height:1.15;font-weight:700}
header.top .sub{margin-top:8px;font-size:22px;opacity:.88}
.badge{position:fixed;top:18px;right:22px;z-index:50;background:#b42318;color:#fff;font-weight:800;font-size:26px;
letter-spacing:.06em;padding:12px 20px;border-radius:10px;border:3px solid #fff;box-shadow:0 4px 14px rgba(0,0,0,.25)}
nav.tabs{display:flex;gap:10px;flex-wrap:wrap;padding:14px 40px;background:#fff;border-bottom:2px solid var(--line);position:sticky;top:0;z-index:20}
nav.tabs a{font-size:22px;padding:10px 20px;border-radius:999px;border:2px solid var(--line);color:var(--ink);text-decoration:none;background:#fff}
nav.tabs a.on{background:var(--acc);border-color:var(--acc);color:#fff}
nav.tabs a small{font-size:20px;opacity:.75;margin-left:8px}
main{max-width:1640px;margin:0 auto;padding:28px 40px 80px}
section.tab{display:block}
body.js section.tab{display:none}body.js section.tab.on{display:block}
.card{background:var(--card);border:2px solid var(--line);border-radius:16px;padding:26px 30px;margin:0 0 24px}
h2{font-size:32px;line-height:1.2;margin:0 0 16px}
h3{font-size:26px;margin:22px 0 10px}
p{margin:10px 0}
.mute{color:var(--mute)}
table{width:100%;border-collapse:collapse;font-size:21px}
th,td{text-align:left;vertical-align:top;padding:12px 14px;border-bottom:2px solid var(--line);overflow-wrap:break-word}
th{font-size:20px;color:var(--mute);font-weight:700;text-transform:uppercase;letter-spacing:.03em}
ul,ol{margin:8px 0 8px 30px;padding:0}li{margin:6px 0}
.cols3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}
.cols2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.col{border-radius:14px;padding:20px 22px;border:2px solid var(--line)}
.col h3{margin-top:0;font-size:28px}
.col.ev{background:#eef7f0;border-color:#b9dcc4}.col.mi{background:#fdf1e7;border-color:#efc9a6}.col.qu{background:#edf2fb;border-color:#bfcfea}
.src{display:inline-block;font-size:20px;color:var(--mute);margin-left:6px}
.q{border:2px solid var(--line);border-radius:14px;padding:18px 22px;margin:0 0 18px;background:#fbfaf7}
.q .n{display:inline-block;min-width:44px;height:44px;line-height:44px;text-align:center;border-radius:50%;background:var(--acc);color:#fff;font-weight:700;margin-right:12px}
.q .t{font-weight:700;font-size:26px}
.q .ask{font-size:23px;margin:10px 0 6px}
.anch{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-top:12px}
.anch div{background:#fff;border:2px solid var(--line);border-radius:10px;padding:12px 14px;font-size:21px}
.anch b{display:block;color:var(--acc2);font-size:21px;margin-bottom:4px}
.pill{display:inline-block;font-size:20px;padding:3px 14px;border-radius:999px;border:2px solid currentColor;margin:2px 6px 2px 0;white-space:nowrap}
.ok{color:var(--ok)}.warn{color:var(--warn)}.no{color:var(--no)}.grey{color:var(--mute)}
.box{border-radius:14px;padding:18px 22px;margin:14px 0}
.box.warm{background:var(--warm);border:2px solid #f0d3a3}.box.soft{background:var(--soft);border:2px solid #c9d5e6}
.big{font-size:56px;font-weight:800;line-height:1.05}
.bar{height:26px;background:#e6e1d6;border-radius:6px;position:relative;min-width:0}
.bar span{position:absolute;left:0;top:0;bottom:0;background:var(--acc);border-radius:6px}
.bar.hi span{background:#b45309}
.dots{white-space:nowrap;font-size:26px;letter-spacing:4px}
.dots .y{color:var(--acc)}.dots .n{color:#c9c3b6}
select,input[type=text],textarea{font:inherit;font-size:21px;border:2px solid var(--line);border-radius:8px;padding:8px 10px;background:#fff}
input[type=text]{width:100%}textarea{width:100%;min-height:140px}
.btn{display:inline-block;font:inherit;font-size:21px;border:2px solid var(--acc);background:var(--acc);color:#fff;border-radius:10px;padding:10px 18px;cursor:pointer}
.note{font-size:21px;color:var(--mute)}
blockquote{margin:12px 0;padding:12px 18px;border-left:6px solid var(--acc2);background:#fbf6ee;border-radius:0 10px 10px 0}
code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:20px;background:#f0ece3;padding:1px 6px;border-radius:5px}
pre{white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:20px;background:#f7f4ee;border:2px solid var(--line);border-radius:10px;padding:14px 16px}
.foot{margin-top:30px;font-size:20px;color:var(--mute)}
@media (max-width:1100px){.cols3,.cols2,.anch{grid-template-columns:1fr}header.top{padding-right:40px;padding-top:90px}}
@media print{nav.tabs,.btn,.badge{display:none}body.js section.tab{display:block}}
"""

TABS_JS = """
(function(){
 var tabs=[].slice.call(document.querySelectorAll('nav.tabs a'));
 if(!tabs.length)return;
 document.body.classList.add('js');
 function show(id){
  var el=document.getElementById('t-'+id);
  if(!el&&tabs.length){id=tabs[0].getAttribute('href').slice(1);el=document.getElementById('t-'+id);}
  [].forEach.call(document.querySelectorAll('section.tab'),function(s){s.classList.toggle('on',s===el);});
  tabs.forEach(function(a){a.classList.toggle('on',a.getAttribute('href')==='#'+id);});
  window.scrollTo(0,0);
 }
 window.addEventListener('hashchange',function(){show(location.hash.slice(1));});
 show(location.hash?location.hash.slice(1):'');
 window.addEventListener('load',function(){window.scrollTo(0,0);});
})();
"""


def page(title, sub, body, demo, extra_js=""):
    """A full HTML page. title and sub are escaped here; body must already be escaped HTML."""
    badge = '<div class="badge">FICTIONAL DEMO</div>' if demo else ""
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>{badge}"
            f"<header class=\"top\"><h1>{esc(title)}</h1><div class=\"sub\">{esc(sub)}</div></header>"
            f"{body}<script>{TABS_JS}{extra_js}</script></body></html>")


def bar(pct, hi=False):
    pct = max(0.0, min(100.0, float(pct)))
    return f'<div class="bar{" hi" if hi else ""}"><span style="width:{pct:.1f}%"></span></div>'


def dots(asked, of=6):
    return ('<span class="dots">' + "".join('<span class="y">&#9679;</span>' if i < asked else '<span class="n">&#9679;</span>'
                                            for i in range(of)) + "</span>")
