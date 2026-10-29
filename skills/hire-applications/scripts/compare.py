#!/usr/bin/env python3
"""Put the questionnaire answers side by side.

Reads   hiring/questionnaire/responses.csv   the Google Forms export as downloaded ("Download responses (.csv)":
                                              question titles as headers, a Timestamp column, the rating grid as
                                              "Rate ... [Area]" columns, checkbox answers joined with ";"), or the
                                              older fixed columns (name, r1..rN, strong_1, example_1, ...)
        hiring/questionnaire/writing.json    optional: Claude's three writing anchors per slug
        hiring/criteria.md                   the areas and the budget
        hiring/out/candidates/*.md, out/applications.json, inbox/   to match each form name to a dossier
Writes  hiring/out/questionnaire/COMPARE.html         SELF-RATINGS, NOT PERFORMANCE, each example beside its number
        hiring/out/questionnaire/<slug>-section.md    a draft Questionnaire section per person, "__" left to fill

    python3 compare.py [--csv "path/to/Form Responses.csv"] [--sort received|name|ask]

--csv copies a downloaded file to questionnaire/responses.csv first (an older responses.csv is kept as
responses-previous.csv). When one person sent the form twice, the later answers are used. Every answer is
escaped on the page. Standard library only. No network.
"""
import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BADGE_CSS, BADGE_HTML, esc, find_root, is_demo, project_today, read_criteria, slug  # noqa: E402
import parse_inbox  # noqa: E402

FIXED = ["timestamp", "name", "email", "location", "ask", "availability", "hours", "side_work"]
TAIL = ["strong_1", "example_1", "strong_2", "example_2", "avoid", "cv_link"]
OPTIONAL = ["monday"]  # an older responses.csv without it still renders, with a note
ANCHORS = [("understood", "Understood the request"), ("clear", "Answered clearly"), ("flagged", "Flagged what was missing")]
SHORT_ANCHOR = {"understood": "Understood", "clear": "Clear", "flagged": "Flagged gaps"}
THIN_WORDS = 30


def shade(v):
    """1 -> near white, 6 -> sand, 10 -> deep clay. Returns (background, text colour)."""
    stops = [(1, (244, 243, 239)), (6, (243, 217, 173)), (10, (201, 105, 63))]
    v = max(1, min(10, v))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if a <= v <= b:
            t = (v - a) / (b - a)
            rgb = tuple(round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
            return "#%02x%02x%02x" % rgb, ("#fff" if v >= 9 else "#1d1d1b")
    return "#f4f3ef", "#1d1d1b"


def short_labels(areas):
    """One-word column headers, made unique: 'Seller Central operations' -> 'Seller'."""
    out, seen = [], set()
    for a in areas:
        lab = a.replace("&", " ").split()[0]
        k, n = lab, 2
        while k in seen:
            k, n = f"{lab} {n}", n + 1
        seen.add(k)
        out.append(k)
    return out


def norm(s):
    s = re.sub(r"^\s*q?\d+[.)]\s*", "", str(s or ""), flags=re.I)
    return re.sub(r"\s+", " ", s).strip().lower()


def map_headers(fields, areas, hours_q):
    """Which column holds what. Old fixed names first, then Google Forms question titles by their key words."""
    col, used = {}, set()
    low = {f: norm(f) for f in fields if f}
    old = {"timestamp", "name", "email", "location", "ask", "availability", "hours", "side_work", "monday",
           "strong_1", "example_1", "strong_2", "example_2", "avoid", "cv_link"}
    for f, n in low.items():
        if n in old:
            col[n] = f
            used.add(f)
    ratings = [None] * len(areas)
    for i in range(len(areas)):
        if f"r{i + 1}" in low.values():
            ratings[i] = next(f for f, n in low.items() if n == f"r{i + 1}")
    for f, n in low.items():
        m = re.search(r"\[(.+)\]\s*$", n)
        if m and "rate" in n:
            hit = [i for i, a in enumerate(areas) if norm(a) == m.group(1).strip()]
            hit = hit or [i for i, a in enumerate(areas) if norm(a).startswith(m.group(1).strip()) or m.group(1).strip().startswith(norm(a))]
            if hit and ratings[hit[0]] is None:
                ratings[hit[0]] = f
                used.add(f)
    hq = norm(hours_q)[:30]
    rules = [("timestamp", lambda n: n == "timestamp"), ("name", lambda n: n in ("full name", "your name", "name")),
             ("email", lambda n: "email" in n), ("location", lambda n: n.startswith("city") or "location" in n),
             ("cv_link", lambda n: n.startswith("cv") or "résumé" in n or "resume" in n),
             ("situation", lambda n: "situation" in n),
             ("examples", lambda n: n.startswith("example") or ("example" in n and "strongest" in n)),
             ("picks", lambda n: "strongest" in n and ("two" in n or "pick" in n)),
             ("avoid", lambda n: "rather not lead" in n), ("ask", lambda n: "compensation" in n or "expected monthly" in n),
             ("availability", lambda n: "when could you start" in n or n.startswith("start date")),
             ("side_work", lambda n: "commitments" in n or "alongside" in n),
             ("monday", lambda n: "monday" in n),
             ("hours", lambda n: (hq and n.startswith(hq)) or "overlap" in n or "hours a day" in n or "time zone" in n)]
    examples = []
    for key, test in rules:
        for f, n in low.items():
            if f in used or not test(n):
                continue
            if key == "examples":
                examples.append(f)
                used.add(f)
                continue
            if key not in col:
                col[key] = f
                used.add(f)
    for i, f in enumerate(sorted(examples, key=lambda f: re.findall(r"\d+", f)[-1:] or ["9"])[:2], 1):
        col.setdefault(f"example_{i}", f)
    return col, ratings, [f for f in fields if f and f not in used and f not in ratings]


def known_people(root):
    """slug -> (name, text to look for an email in), from the dossiers, applications.json and inbox/."""
    people = {}
    apps = root / "out" / "applications.json"
    if apps.is_file():
        for a in json.loads(apps.read_text(encoding="utf-8")).get("applications", []):
            people[a["slug"]] = [a.get("name") or "", (a.get("message") or "") + "\n" + (a.get("cv_text") or "")]
    for d in sorted((root / "out" / "candidates").glob("*.md")):
        m = re.search(r"^- Name:\s*(.+)$", d.read_text(encoding="utf-8"), re.M)
        people.setdefault(d.stem, ["", ""])[0] = people.get(d.stem, ["", ""])[0] or (m.group(1).strip() if m else d.stem)
    for f in sorted((root / "inbox").glob("*.md")) if (root / "inbox").is_dir() else []:
        if f.stem in people and not f.stem.endswith("-cv"):
            people[f.stem][1] += "\n" + f.read_text(encoding="utf-8", errors="replace")
    return people


def match_slug(name, email, people):
    """(slug, how). Exact name first, then the email in their application, then a unique first-name match."""
    s = slug(name)
    if s in people:
        return s, ""
    if email:
        hits = [k for k, (_, txt) in people.items() if email.lower() in txt.lower()]
        if len(hits) == 1:
            return hits[0], "email"
    toks = s.split("-")
    hits = [k for k in people if k.split("-")[:len(toks)] == toks or slug(people[k][0]).split("-")[:len(toks)] == toks]
    if len(set(hits)) == 1:
        return hits[0], "name"
    return s, None


def load(path, areas, hours_q, people):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        fields = rd.fieldnames or []
        col, rating_cols, unread = map_headers(fields, areas, hours_q)
        if "name" not in col:
            sys.exit("responses.csv: no name column. A Google Forms export has 'Full name'; the old format has 'name'.")
        miss = [a for a, c in zip(areas, rating_cols) if c is None]
        if miss:
            print("note: no rating column for %s; those cells show '-'" % ", ".join(miss))
        for k in ("picks", "example_1", "example_2", "ask", "situation", "monday"):
            if k not in col and not (k == "picks" and "strong_1" in col):
                print(f"note: responses.csv has no column for {k}; that part stays empty")
        if unread:
            print("note: columns not used: " + "; ".join(u[:60] for u in unread))
        by_slug, order = {}, []
        for raw in rd:
            raw = {k: (v or "").strip() for k, v in raw.items() if k}
            g = lambda k: raw.get(col[k], "") if k in col else ""
            name = g("name")
            if not name:
                continue
            r = {k: g(k) for k in ("timestamp", "email", "location", "ask", "availability", "hours", "side_work",
                                   "monday", "example_1", "example_2", "cv_link", "situation")}
            r["name"] = name
            if "picks" in col:
                picks = [x.strip() for x in g("picks").split(";") if x.strip()]
                canon = {norm(a): a for a in areas}
                picks = [canon.get(norm(x), x) for x in picks]
            else:
                picks = [g("strong_1"), g("strong_2")]
            r["strong_1"], r["strong_2"] = (picks + ["", ""])[:2]
            r["avoid_list"] = [a.strip() for a in g("avoid").split(";") if a.strip() and a.strip().lower() != "none"]
            r["avoid"] = "; ".join(r["avoid_list"])
            r["ratings"] = []
            for c in rating_cols:
                try:
                    r["ratings"].append(int(float(raw.get(c, "") or 0)) if c else 0)
                except ValueError:
                    r["ratings"].append(0)
            r["ask_n"] = parse_inbox.parse_ask(r["ask"])[0] or 0
            r["slug"], how = match_slug(name, r["email"], people)
            r["match"] = how
            if r["slug"] in by_slug:
                print(f"note: {name} sent the form twice; the later answers ({r['timestamp'] or 'last row'}) are used")
            else:
                order.append(r["slug"])
            by_slug[r["slug"]] = r
    q = col.get("situation", "")
    q = re.sub(r"(?i)^\s*(q?\d+[.)]\s*)?one short situation[^:]*:\s*", "", q).strip() if q else ""
    sit = {"present": "situation" in col, "column_label": "Situation",
           "question": q if q and norm(q) != "situation" else "the situation question"}
    return [by_slug[s] for s in order], sit


def example_kind(text):
    """Blank, thin, no number, or detailed. Thin: under THIN_WORDS words. A label for the reader, not a score."""
    words = len(text.split())
    if not words:
        return "blank", "No example given"
    has_num = bool(re.search(r"\d", text))
    if words < THIN_WORDS:
        return "thin", "Thin example: %d words, %s" % (words, "a number" if has_num else "no number")
    if not has_num:
        return "nonum", "Example: %d words, no number" % words
    return "detailed", "Detailed example: %d words, with numbers" % words


def notes_for(r, areas, c):
    """Deterministic observations. Questions for the call, never verdicts."""
    out = []
    rs = [x for x in r["ratings"] if x]
    if rs and max(rs) - min(rs) == 0:
        out.append(f"flat self-ratings (every area {rs[0]}); the examples have to carry it")
    elif rs and max(rs) - min(rs) <= 1:
        out.append("self-ratings all within one point; the examples have to carry it")
    picks = [r["strong_1"], r["strong_2"]]
    pick_r = [r["ratings"][areas.index(p)] for p in picks if p in areas]
    if pick_r:
        higher = [f"{a} ({r['ratings'][i]})" for i, a in enumerate(areas) if a not in picks and r["ratings"][i] > max(pick_r)]
        if higher:
            out.append("rated " + ", ".join(higher) + " above both picks; ask why those are not the strongest")
    for i, p in enumerate(picks, 1):
        if p and p in r["avoid_list"]:
            out.append(f"{p} is both a strongest pick and on the rather-not list")
        kind, _ = example_kind(r[f"example_{i}"])
        ri = r["ratings"][areas.index(p)] if p in areas else 0
        if p and kind == "blank":
            out.append(f"no example for {p}")
        elif p and kind == "thin" and ri >= 8:
            out.append(f"rated {p} {ri} with a thin example; ask to see the work")
    if c["hard_max"] and r["ask_n"] > c["hard_max"]:
        out.append(f"ask ${r['ask_n']:,} is above the hard max ${c['hard_max']:,}: out, no more work on this candidate")
    elif c["target"] and r["ask_n"] > c["target"][1]:
        out.append(f"ask ${r['ask_n']:,} is above the target range (${c['target'][0]:,} to ${c['target'][1]:,})")
    if not r["cv_link"]:
        out.append("no CV link")
    if r["hours"].lower().startswith("i would need"):
        out.append("hours overlap needs a conversation")
    if r["side_work"] and r["side_work"].strip().lower() not in ("none", "none.", "no", "nothing"):
        out.append("keeps side work: " + r["side_work"][:80] + ("..." if len(r["side_work"]) > 80 else ""))
    return out


def norm_anchor_block(v):
    if not isinstance(v, dict):
        return None
    out = {}
    for k, _ in ANCHORS:
        val = str(v.get(k, "")).strip().lower()
        out[k] = val if val in ("yes", "partly", "no") else ""
    out["reason"] = str(v.get("reason", "")).strip()
    return out if any(out[k] for k, _ in ANCHORS) else None


def load_writing(path):
    """Claude's writing judgment per slug against the three anchors.

    New format: {"slug": {"writing": {"understood": "yes|partly|no", "clear": ..., "flagged": ..., "reason": ...},
                          "situation": {... same keys, for the situation answer ...}}}
    Older format still read: {"slug": {"score": 1 to 5, "reason": "..."}}."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for k, v in data.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        entry = {"writing": norm_anchor_block(v.get("writing")), "situation": norm_anchor_block(v.get("situation"))}
        if entry["writing"] is None and "score" in v:
            try:
                entry["old"] = {"score": max(1, min(5, int(v["score"]))), "reason": str(v.get("reason", "")).strip()}
            except (TypeError, ValueError):
                print(f"note: writing.json entry for {k} is not readable; skipped")
        out[k] = entry
    return out


def anchors_html(block, empty="not scored yet"):
    """The total out of three, then only the anchors that were not a clear yes."""
    if not block:
        return '<span class="dim">%s</span>' % esc(empty)
    n = sum(1 for k, _ in ANCHORS if block.get(k) == "yes")
    lines = ['<div class="an-total">%d<span>/3</span></div>' % n]
    misses = [k for k, _ in ANCHORS if block.get(k) != "yes"]
    if not misses:
        lines.append('<div class="an yes"><i></i><b>all three yes</b></div>')
    for k in misses:
        v = block.get(k) or "?"
        lines.append('<div class="an %s"><i></i>%s: <b>%s</b></div>' % (esc(v), esc(SHORT_ANCHOR[k]), esc(v)))
    return "".join(lines)


def snippet(text, chars=36, whole=62):
    """The example as written when it is short; otherwise its first words, cut at a word boundary."""
    t = " ".join(text.split())
    if len(t) <= whole:
        return t
    cut = t[:chars].rsplit(" ", 1)[0]
    return cut + " ..."


CSS = """
:root{--ink:#1d1d1b;--muted:#5f5d57;--line:#e2ded6;--bg:#faf9f6;--yes:#1f6b45;--partly:#9a6b1c;--no:#8a8780}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font:22px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header.top{position:sticky;top:0;z-index:20;background:var(--bg);padding:16px 28px 12px;border-bottom:1px solid var(--line);
 display:flex;justify-content:space-between;align-items:center;gap:20px}
header.top .kicker{display:block;font-size:18px;font-weight:600;color:var(--muted);letter-spacing:.04em;text-transform:uppercase}
header.top h1{margin:0;font-size:32px;line-height:1.15}
header.top .badge-demo{position:static}
.wrap{padding:14px 28px 60px}
.legend{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;margin:0 0 8px}
.sr{display:inline-block;border:3px solid var(--ink);border-radius:10px;padding:4px 14px;font-weight:800;font-size:24px;letter-spacing:.05em}
.legend .txt{font-size:20px;color:var(--muted);max-width:760px;line-height:1.3}
.chips{display:flex;gap:4px;align-items:center}
.chip{display:inline-grid;place-items:center;width:34px;height:30px;border-radius:6px;font-size:17px;font-weight:700}
.key{display:flex;gap:22px;color:var(--muted);font-size:18px;margin:0 0 4px;flex-wrap:nowrap;white-space:nowrap}
.key i{display:inline-block;width:20px;height:20px;border-radius:5px;vertical-align:-3px;margin-right:6px;background:#f3d9ad}
.key i.p{box-shadow:inset 0 0 0 3px var(--ink)}.key i.a{background:repeating-linear-gradient(135deg,#f3d9ad 0 4px,#fff 4px 7px)}
.map{color:var(--muted);font-size:16px;margin:0 0 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.map b{color:var(--ink)}
table{border-collapse:separate;border-spacing:0;width:100%;background:#fff;border:1px solid var(--line);border-radius:14px;table-layout:fixed}
th{position:sticky;top:var(--hdr,74px);z-index:5;background:#f2f0eb;text-align:left;font-size:17px;letter-spacing:.04em;text-transform:uppercase;
 color:var(--muted);padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:bottom}
th.h{text-align:center;padding:10px 0;font-size:15px;letter-spacing:-.01em;text-transform:none;font-weight:700;color:var(--ink)}
col.c-who{width:215px}col.c-h{width:72px}col.c-wr{width:180px}col.c-si{width:180px}
td{vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}
tbody.r{cursor:pointer}tbody.r:hover td{background:#fcfbf8}tbody.r.open tr.main td{background:#f7f4ee}
td.who b{display:block;font-size:21px;line-height:1.2}td.who span{display:block;font-size:18px;color:var(--muted);line-height:1.3}
td.c{text-align:center;font-weight:800;font-size:23px;padding:0;vertical-align:middle;border-left:2px solid #fff}
td.c.pick{box-shadow:inset 0 0 0 4px var(--ink)}
td.c.avoid{background-image:repeating-linear-gradient(135deg,rgba(255,255,255,.6) 0 5px,transparent 5px 10px)!important}
td.ex .area{font-size:18px;font-weight:700;line-height:1.25}
td.ex .self{display:inline-block;margin-left:6px;font-size:17px;font-weight:800;background:#f3d9ad;border-radius:6px;padding:0 7px}
td.ex .kind{display:inline-block;margin:2px 0 1px;font-size:16px;font-weight:700;letter-spacing:.02em;border-radius:6px;padding:1px 8px}
.kind.thin{background:#fde2dc;color:#a3341c}.kind.blank{background:#fde2dc;color:#a3341c}.kind.nonum{background:#fbefd5;color:#8a5a12}.kind.detailed{background:#e3f1e8;color:#1f6b45}
td.ex p{margin:1px 0 0;font-size:19px;line-height:1.3;color:#2c2b28}
.an-total{font-size:24px;font-weight:800;line-height:1.15}.an-total span{font-size:16px;color:var(--muted);font-weight:600}
.an{font-size:17px;line-height:1.35;white-space:nowrap}.an i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;background:var(--no)}
.an.yes i{background:var(--yes)}.an.partly i{background:var(--partly)}.an.yes b{color:var(--yes)}.an.partly b{color:var(--partly)}.an.no b{color:var(--no)}
tr.detail{display:none}tbody.open tr.detail{display:table-row}
tr.detail td{background:#f7f4ee;padding:6px 16px 18px;cursor:default}
.dg{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px 26px}
.dg h4{margin:8px 0 4px;font-size:16px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.dg p{margin:0 0 6px;font-size:19px;line-height:1.4}.dg ul{margin:0;padding-left:20px;font-size:19px}
.tag{display:inline-block;background:#fff;border:1px solid var(--line);border-radius:999px;padding:1px 10px;font-size:17px;margin:0 4px 4px 0}
.dim{color:#9a978f}.foot{color:var(--muted);font-size:18px;margin-top:18px}
a{color:var(--ink)}
@media (max-width:900px){.dg{grid-template-columns:1fr}header.top{flex-wrap:wrap}header.top h1{font-size:24px}
 table{display:block;overflow-x:auto}.key{flex-wrap:wrap;white-space:normal}}
"""

JS = r"""
(function(){
  var h=document.querySelector('header.top');
  function s(){document.documentElement.style.setProperty('--hdr',h.offsetHeight+'px');}
  s();window.addEventListener('resize',s);
  document.querySelectorAll('tbody.r').forEach(function(tb){
    tb.querySelector('tr.main').addEventListener('click',function(e){ if(e.target.closest('a'))return; tb.classList.toggle('open'); });
  });
  function openHash(){ var id=decodeURIComponent((location.hash||'').slice(1)); var tb=id&&document.getElementById(id);
    if(tb&&tb.classList.contains('r')){ tb.classList.add('open');
      window.scrollTo(0, Math.max(0, tb.getBoundingClientRect().top + window.scrollY - h.offsetHeight - 70)); } }
  window.addEventListener('hashchange',openHash); openHash();
})();
"""


def render(rows, areas, c, dossier_dir, writing, sit, demo, today):
    labels = short_labels(areas)
    legend = "".join(f'<span class="chip" style="background:{shade(v)[0]};color:{shade(v)[1]}">{v}</span>' for v in range(1, 11))
    sit_label = sit["column_label"] if sit["present"] else ""
    cols = '<col class="c-who">' + '<col class="c-h">' * len(areas) + "<col><col>" + '<col class="c-wr">' + (
        '<col class="c-si">' if sit_label else "")
    head = ("<th>Candidate</th>" + "".join(f'<th class="h" title="{esc(a)}">{esc(l)}</th>' for a, l in zip(areas, labels))
            + "<th>Strongest area 1: their example</th><th>Strongest area 2: their example</th><th>Writing</th>"
            + (f"<th>{esc(sit_label)}</th>" if sit_label else ""))
    body = []
    for r in rows:
        cells = []
        for i, a in enumerate(areas):
            v = r["ratings"][i]
            bg, fg = shade(v) if v else ("#fff", "#999")
            cls = ["c"] + (["pick"] if a in (r["strong_1"], r["strong_2"]) else []) + (["avoid"] if a in r["avoid_list"] else [])
            cells.append(f'<td class="{" ".join(cls)}" style="background:{bg};color:{fg}" title="{esc(a)}: {v or "-"}">{v or "-"}</td>')
        ex_cells = []
        for i in (1, 2):
            s_area, e = r[f"strong_{i}"], r[f"example_{i}"]
            ri = r["ratings"][areas.index(s_area)] if s_area in areas else None
            kind, label = example_kind(e)
            ex_cells.append(
                '<td class="ex"><div class="area">%s%s</div><span class="kind %s">%s</span>%s</td>' % (
                    esc(s_area) or '<span class="dim">no area picked</span>',
                    (' <span class="self">self %d</span>' % ri) if ri else "", kind, esc(label),
                    ('<p>"%s"</p>' % esc(snippet(e))) if e else ""))
        fit = ""
        if c["hard_max"] and r["ask_n"] > c["hard_max"]:
            fit = "over the hard max"
        elif c["target"] and r["ask_n"] > c["target"][1]:
            fit = "above target"
        elif c["target"]:
            fit = "in target"
        w = writing.get(r["slug"], {})
        if w.get("writing"):
            wcell = anchors_html(w["writing"])
        elif w.get("old"):
            wcell = '<div class="an-total">%d<span>/5 (older scale)</span></div>' % w["old"]["score"]
        else:
            wcell = '<span class="dim">not scored yet</span>'
        dossier = dossier_dir / f"{r['slug']}.md"
        links = []
        if dossier.exists():
            links.append(f'<a href="../candidates/{esc(r["slug"])}.md">dossier</a>')
        if re.match(r"^(https?://|\.\./|\./)", r["cv_link"]) or re.match(r"^[\w./-]+$", r["cv_link"] or "-"):
            links.append(f'<a href="{esc(r["cv_link"])}">CV</a>')  # web links and relative file paths only
        elif r["cv_link"]:
            links.append(f'CV link not opened: {esc(r["cv_link"][:60])}')
        avoid = "".join(f'<span class="tag">{esc(a)}</span>' for a in r["avoid_list"]) or '<span class="dim">none</span>'
        notes = "".join(f"<li>{esc(n)}</li>" for n in notes_for(r, areas, c)) or '<li class="dim">nothing to flag</li>'
        reasons = ""
        if w.get("writing", {}) and w["writing"].get("reason"):
            reasons += "<h4>Writing, why</h4><p>%s</p>" % esc(w["writing"]["reason"])
        if w.get("situation", {}) and w["situation"].get("reason"):
            reasons += "<h4>%s answer, why</h4><p>%s</p>" % (esc(sit_label), esc(w["situation"]["reason"]))
        detail = ('<div class="dg"><div><h4>%s, in full (%s)</h4><p>%s</p><h4>%s, in full (%s)</h4><p>%s</p></div>'
                  '<div><h4>If they started Monday</h4><p>%s</p>%s</div>'
                  '<div><h4>Would rather not lead</h4><p>%s</p><h4>Notes for the call</h4><ul>%s</ul>%s<p>%s</p></div></div>') % (
            esc(r["strong_1"]), esc(example_kind(r["example_1"])[1]), esc(r["example_1"]) or '<span class="dim">blank</span>',
            esc(r["strong_2"]), esc(example_kind(r["example_2"])[1]), esc(r["example_2"]) or '<span class="dim">blank</span>',
            esc(r["monday"]) or '<span class="dim">no answer</span>',
            ("<h4>%s</h4><p>%s</p>" % (esc(sit["question"]), esc(r["situation"]) or '<span class="dim">no answer</span>')) if sit_label else "",
            avoid, notes, reasons, " · ".join(links))
        body.append(
            f'<tbody class="r" id="{esc(r["slug"])}"><tr class="main"><td class="who"><b>{esc(r["name"])}</b>'
            f'<span>{esc(r["location"])}</span><span>${r["ask_n"]:,}/mo{(" · " + fit) if fit else ""}</span></td>'
            + "".join(cells) + "".join(ex_cells) + f"<td>{wcell}</td>"
            + (f"<td>{anchors_html(w.get('situation'))}</td>" if sit_label else "")
            + f'</tr><tr class="detail"><td colspan="{4 + len(areas) + (1 if sit_label else 0)}">{detail}</td></tr></tbody>')
    mapping = " · ".join(f"<b>{esc(l)}</b> {esc(a)}" for a, l in zip(areas, labels))
    badge = BADGE_HTML if demo else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Questionnaire answers: {esc(c['role'])}</title>
<style>{CSS}{BADGE_CSS if demo else ""}</style></head><body>
<header class="top"><div><span class="kicker">Questionnaire answers: {esc(c['role'])}</span><h1>{len(rows)} answers side by side</h1></div>{badge}</header>
<div class="wrap">
<div class="legend"><span class="sr">SELF-RATINGS, NOT PERFORMANCE</span><span class="chips">{legend}</span>
<span class="txt">How they rate themselves, 1 to 10. The evidence is the example beside the number.</span></div>
<div class="key"><span><i class="p"></i>one of their two strongest picks</span><span><i class="a"></i>would rather not lead</span>
<span><b>Writing</b> and <b>{esc(sit_label or "situation")}</b>: three anchors, understood / clear / flagged what was missing. Never accent or fancy words.</span></div>
<p class="map">{mapping}</p>
<table><colgroup>{cols}</colgroup><thead><tr>{head}</tr></thead>
{''.join(body)}</table>
<p class="foot">{len(rows)} people from hiring/questionnaire/responses.csv, rendered {today}. The writing anchors are Claude's judgment from hiring/questionnaire/writing.json; a person checks them. The heatmap is a map for the conversation, never a ranking. Click a row for the full answers, the Monday answer, the situation answer and the notes for the call. Candidate text on this page is shown as plain text. Nothing was sent to anyone.</p>
</div><script>{JS}</script></body></html>
"""


def anchor_line(block):
    if not block:
        return "__ (understood the request: yes/partly/no; answered clearly: yes/partly/no; flagged what was missing: yes/partly/no; why)"
    return "%d of 3. Understood the request: %s. Answered clearly: %s. Flagged what was missing: %s. Why: %s" % (
        sum(1 for k, _ in ANCHORS if block.get(k) == "yes"), block.get("understood") or "?", block.get("clear") or "?",
        block.get("flagged") or "?", block.get("reason") or "__")


def section_draft(r, areas, c, writing, sit):
    rows = "\n".join(f"| {a} | {r['ratings'][i] or '-'} |" for i, a in enumerate(areas))
    notes = notes_for(r, areas, c)
    w = writing.get(r["slug"], {})
    lines = [
        "## Questionnaire", "",
        f"Received {r['timestamp']}. Location: {r['location']}. Ask ${r['ask_n']:,}/month. Availability: {r['availability'].rstrip('.')}. "
        f"Hours overlap: {r['hours']}. Side work: {(r['side_work'] or 'none stated').rstrip('.')}. CV: {r['cv_link'] or 'none'}.",
        "", "Self-ratings (how they see themselves, not evidence):", "", "| Area | 1-10 |", "|---|---|", rows, "",
        "Strongest two, in their words:", ""]
    for i in (1, 2):
        s_area = r[f"strong_{i}"]
        ri = r["ratings"][areas.index(s_area)] if s_area in areas else "-"
        lines += [f"{i}. **{s_area}** (self {ri}/10, {example_kind(r[f'example_{i}'])[1].lower()}): \"{r[f'example_{i}'] or 'no example given'}\"",
                  "   Evidence: __/25. Why: __", ""]
    lines += ["Would rather not lead: " + (", ".join(r["avoid_list"]) or "none") + ".", "",
              "If they started Monday: \"" + (r["monday"] or "no answer") + "\"", ""]
    if sit["present"]:
        lines += ["Situation (%s): \"%s\"" % (sit["question"], r["situation"] or "no answer"), "",
                  "Situation, writing anchors: " + anchor_line(w.get("situation")), ""]
    lines += ["Notes from compare.py: " + ("; ".join(notes) if notes else "nothing to flag") + ".", "",
              "Writing, anchors on the whole response: " + anchor_line(w.get("writing")), "",
              "TRACK: __/50 (sum of the two evidence lines). SHARED: unchanged at __/50, or revised to __/50 because __.", "",
              "Questions for the call: __", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    ap.add_argument("--sort", default="received", choices=["received", "name", "ask"])
    ap.add_argument("--csv", default=None, help="a downloaded responses file to copy into questionnaire/responses.csv")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD for the page (default: today.txt, else today)")
    args = ap.parse_args()
    root = find_root(args.root)
    today = project_today(root, args.today)[0].isoformat()
    c = read_criteria(root / "criteria.md")
    if len(c["areas"]) < 2:
        sys.exit("could not read the areas from criteria.md (see make_questionnaire.py)")
    src = root / "questionnaire" / "responses.csv"
    if args.csv:
        given = Path(args.csv)
        if not given.is_file():
            sys.exit(f"--csv: no file at {given}")
        src.parent.mkdir(parents=True, exist_ok=True)
        if src.exists() and src.resolve() != given.resolve():
            if src.read_bytes() != given.read_bytes():
                shutil.copyfile(src, src.with_name("responses-previous.csv"))
                print(f"kept    the older {src.name} as responses-previous.csv")
        if not src.exists() or src.resolve() != given.resolve():
            shutil.copyfile(given, src)
            print(f"copied  {given} to {src}")
    if not src.exists():
        sys.exit(f"missing {src}. In Google Forms: Responses, Download responses (.csv); save it there, or pass --csv.")
    people = known_people(root)
    rows, sit = load(src, c["areas"], c["hours"], people)
    for r in rows:
        if r["match"]:
            print(f"matched {r['name']} to {r['slug']} (by {r['match']}): check it is the same person")
        elif r["match"] is None:
            print(f"note: {r['name']}: no dossier with this name, so the section is drafted as {r['slug']}. If it is someone "
                  "you screened, rename the file to their slug before append_sections.py.")
    if args.sort == "name":
        rows.sort(key=lambda r: r["name"].lower())
    elif args.sort == "ask":
        rows.sort(key=lambda r: r["ask_n"])

    writing = load_writing(root / "questionnaire" / "writing.json")
    unscored = [r["name"] for r in rows if not (writing.get(r["slug"], {}).get("writing") or writing.get(r["slug"], {}).get("old"))]
    out_dir = root / "out" / "questionnaire"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "COMPARE.html"
    html_path.write_text(render(rows, c["areas"], c, root / "out" / "candidates", writing, sit, is_demo(root), today), encoding="utf-8")
    thin = [r["name"] for r in rows for i in (1, 2) if example_kind(r[f"example_{i}"])[0] in ("thin", "blank")]
    print(f"wrote   {html_path}  ({len(rows)} candidates, {len(rows) - len(unscored)} with writing anchors)")
    if thin:
        print(f"marked  thin or blank examples: {', '.join(sorted(set(thin)))}")
    kept = 0
    for r in rows:
        p = out_dir / f"{r['slug']}-section.md"
        if p.exists():
            kept += 1
            continue
        p.write_text(section_draft(r, c["areas"], c, writing, sit), encoding="utf-8")
        print(f"wrote   {p}")
    if kept:
        print(f"kept    {kept} existing *-section.md files (delete one to regenerate it)")
    if unscored:
        print(f"writing anchors missing for: {', '.join(unscored)}. Judge them with the anchors in SKILL.md into "
              "hiring/questionnaire/writing.json and run compare.py again.")
    print("\nnext: fill the __ lines in each *-section.md (the rubric is in SKILL.md), then run append_sections.py")


if __name__ == "__main__":
    main()
