#!/usr/bin/env python3
"""Shared helpers for the hire-reference-check scripts. Standard library only, no network.

Not run on its own. call_sheet.py and summary.py import it from the same folder.
"""
import datetime as dt
import html
import os
import re
import sys
from pathlib import Path

DASHES = ("\u2014", "\u2013")
ONE_OPINION = "One person's opinion is never a complete picture of a candidate."


def find_root(arg=None):
    """The hiring folder: the one that holds criteria.md. Accepts the folder itself or the one above it."""
    here = Path(arg) if arg else Path(".")
    for cand in (here, here / "hiring"):
        if (cand / "criteria.md").is_file():
            return cand
    sys.exit(f"no criteria.md in {here / 'criteria.md'} or {here / 'hiring' / 'criteria.md'}. Run this from your "
             "hiring/ folder (the one that holds criteria.md) or from the folder above it, or pass --root path/to/hiring.")


def project_today(root, given=None):
    """The date to print: --date when given; else the one date in today.txt in the hiring folder (a demo, or a
    folder you are catching up on); else the computer clock. Returns (date, where it came from)."""
    if given:
        try:
            return dt.date.fromisoformat(given), "--date"
        except ValueError:
            sys.exit("--date must look like 2026-10-16")
    path = Path(root) / "today.txt"
    if path.exists():
        lines = path.read_text(encoding="utf-8-sig").strip().splitlines()
        try:
            day = dt.date.fromisoformat((lines[0].strip() if lines else "")[:10])
        except ValueError:
            sys.exit(f"{path}: put one date like 2026-10-16 on the first line, or remove the file to use the computer's date.")
        print(f"date: {day.isoformat()} (from today.txt)")
        return day, "today.txt"
    return dt.date.today(), "the computer clock"


def is_demo(root):
    """Demo mode (the FICTIONAL DEMO badge) is on when criteria.md says FICTIONAL DEMO."""
    try:
        return "FICTIONAL DEMO" in (Path(root) / "criteria.md").read_text(encoding="utf-8")
    except OSError:
        return False


def role(root):
    m = re.match(r"#\s+(?:Hiring criteria:\s*)?([^\n]+)", (Path(root) / "criteria.md").read_text(encoding="utf-8"))
    return m.group(1).strip() if m else "the role in criteria.md"


def no_dashes(text, where):
    for d in DASHES:
        if d in text:
            sys.exit(f"{where} contains a long dash (em or en dash). Replace it with a comma or a period and rerun.")
    return text


def write(path, text):
    no_dashes(text, str(path))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    print(f"wrote {os.path.normpath(str(path))}")


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def table_rows(body):
    """Rows of the first markdown table in body, without the header and the separator."""
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def open_question_rows(text):
    """The rows of an open-questions file, call_sheet.py and summary.py alike: {n, q, why, source, ask,
    placeholder}. A question that starts with "[" is a placeholder Claude left to fill: both scripts skip it."""
    rows = []
    if "| #" in text:
        for c in table_rows("| #" + text.split("| #", 1)[1]):
            if len(c) >= 2 and c[0].isdigit():
                rows.append({"n": c[0], "q": c[1], "why": c[2] if len(c) > 2 else "", "source": c[3] if len(c) > 3 else "",
                             "ask": (c[4] if len(c) > 4 and c[4] else "referee").lower(), "placeholder": c[1].startswith("[")})
    return rows


def section(text, heading_regex):
    m = re.search(r"^##\s+" + heading_regex + r"[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def claim_check(root, slug):
    """The claim check for one candidate, out/verification/<slug>.md (hire-interview's claim_check.py).
    Returns {"file", "questions"} or None when it does not exist. Only the questions are read."""
    rel = f"out/verification/{slug}.md"
    p = Path(root) / rel
    if not p.is_file():
        return None
    qs = []
    for line in section(p.read_text(encoding="utf-8"), r"Questions for the call").splitlines():
        m = re.match(r"^\s*(?:\d+[.)]|[-*])\s+(.+)$", line)
        if m and not m.group(1).lower().startswith(("none", "(write")):
            qs.append(m.group(1).strip())
    return {"file": rel, "questions": qs}


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
