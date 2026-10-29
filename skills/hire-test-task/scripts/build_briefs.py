"""Renders each challenge/briefs/<slug>.md into challenge/briefs/<slug>.html (and a PDF with --pdf).

Needs challenge/SCORING-GUIDE.md first (templates/scoring-guide.md): the guide is written with the briefs.
--lock-guide [YYYY-MM-DD] locks it before the first submission: it writes rubric_locked_at and a fingerprint
(scoring_guide_sha256) into challenge/review.json. A second lock after the guide changed is refused, and
review_board.py warns when the guide no longer matches its fingerprint.

The .md is written by Claude from templates/brief.md. The layout is the method, one section each:
  Goal / Context / Task (part 1, the shared core task, and part 2, the specialist part) /
  What I will look at / Expected effort / Pay / Deadline / How to send / How the work may be used.
The script fills placeholders, checks the brief and renders it. It never sends anything.

Pay is optional. fee_usd above 0: one fee for everyone, and the founder may use the work. fee_usd null or 0:
the task is unpaid, no fee line appears anywhere, and the work is never used. An unpaid task over about an
hour, or on the founder's real material (real_material: true), prints a recommendation to pay; the founder
decides.

--terms drafts out/messages/<slug>-terms-before-trial.md for each finalist whose terms_sent is still null
(role pay, hours and start from "role" in config.json; the task's fee or "unpaid"). It keeps a draft that
is already there, and needs no scoring guide yet.

Placeholders (unknown braces are left alone):
  {name} {first_name} {brand} {signoff} {fee} {payment} {due} {submit_to}
  {pay_line} {use_line}  the Pay and How the work may be used lines, for a paid or an unpaid task
  {effort}               "two hours", "one hour" (from expected_hours)
  {days} {days_words}    from "days" in config.json (the return window), "5" and "five"
  {hours} {hours_words}  from "expected_hours" (default 2), "2" and "two"
  {track}                the finalist's specialist track ("track" in config.json, else review.json)
  {core_items}           the table of the shared core task, read from challenge/core-task.md (or the file
                         named by "core_task" in config.json), so every finalist gets the same part 1 text

Checks, per brief: terms_sent holds a date (pay, hours and start date went out in writing first);
every section of the layout is there; the effort line says about N hours and how to ask for more time;
the brief names no other finalist; no long dashes. The shared task keeps the information that is
naturally missing, and review.json records the questions each finalist asked about it.

Markdown subset: # ## ### headings, **bold**, *italic*, `code`, lists, tables. A table whose header
cells are all empty (| | |) renders as the essentials box; any other table renders as a table.
Front matter at the top: name, title.

Usage: run from your hiring/ folder, or from the folder above it:
  python3 build_briefs.py --terms                                the terms messages, before any brief
  python3 build_briefs.py [--lock-guide [YYYY-MM-DD]] [--pdf]  (--root path/to/hiring overrides)
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import (esc, find_root, load_json, demo_label, words, no_dashes, page, table_cells,  # noqa: E402
                     read_core_items, read_core_header, task_terms, pay_advice)

HERE = pathlib.Path(__file__).resolve().parent
SECTIONS = ["Goal", "Context", "Task", "Expected effort", "Pay", "Deadline", "How to send"]

CHROME_CANDIDATES = [
    os.environ.get("CHROME", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]

CSS = """
.wrap{display:grid;grid-template-columns:330px minmax(0,1fr);gap:40px;align-items:start}
nav.index{position:sticky;top:84px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
nav.index b{display:block;font-size:20px;color:var(--mute);margin-bottom:6px}
nav.index ol{margin:0 0 14px;padding-left:30px;font-size:21px;line-height:1.55}
nav.index a{color:var(--ink);text-decoration:none}
nav.index .glance{border-top:1px solid var(--line);padding-top:12px;font-size:20px}
nav.index .glance div{margin:5px 0}
nav.index .glance span{color:var(--mute)}
.sheet{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:30px 40px 36px;max-width:1180px}
.sheet h1{font-size:40px}
.intro{font-size:23px}
.sheet h2{display:flex;align-items:center;gap:14px;font-size:30px;margin:34px 0 10px;padding-top:18px;border-top:2px solid var(--line);scroll-margin-top:90px}
.sheet h2 .n{flex:none;width:44px;height:44px;border-radius:50%;background:var(--ink);color:#fff;font-size:22px;line-height:44px;text-align:center}
.sheet h3{font-size:25px;margin:20px 0 8px}
.goal{font-weight:700}
.sheet ul,.sheet ol{margin:0 0 12px;padding-left:30px}.sheet li{margin:4px 0}
code{font-family:Menlo,Consolas,monospace;font-size:19px;background:var(--acc-bg);padding:1px 6px;border-radius:5px}
table.box{background:var(--soft);border:1px solid var(--line);margin:8px 0 14px}
table.box td{border-bottom:1px solid var(--line)}table.box td:first-child{width:24%;font-weight:700}
table.items{margin:8px 0 14px}table.items td:first-child,table.items th:first-child{width:56px;text-align:center}
table.items td:nth-child(2){width:190px;font-weight:600}
@media (max-width:1100px){.wrap{grid-template-columns:1fr}nav.index{position:static}}
@media (max-width:760px){.sheet{padding:20px 16px}}
@media print{
 body{font-size:9.5pt;line-height:1.38;background:#fff}.bar{position:static;padding:5px 10px;font-size:9pt}.badge{font-size:10pt;padding:2px 8px}
 nav.index{display:none}.wrap{display:block}main{padding:0;max-width:none}.sheet{border:0;padding:0;max-width:none}
 .sheet h1{font-size:16pt;margin:6px 0 4px}.intro{font-size:9.5pt}p{margin:0 0 5px}
 .sheet h2{font-size:12pt;margin:8px 0 3px;padding-top:5px;break-after:avoid}
 .sheet h2 .n{width:20px;height:20px;line-height:20px;font-size:9pt}.sheet h3{font-size:10.5pt;margin:6px 0 3px}
 table,th{font-size:8.5pt;line-height:1.3}th,td{padding:3px 6px}code{font-size:8pt}
 table.items td:nth-child(2){width:95px}table.items td:first-child,table.items th:first-child{width:24px}
 .sheet ul,.sheet ol{margin:0 0 5px}.sheet li{margin:1px 0}
 @page{size:A4;margin:10mm 13mm}
}
"""

INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<b>\1</b>"),
    (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])"), r"<i>\1</i>"),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
]


def inline(text: str) -> str:
    """Escape first, then the three inline marks. No raw HTML from the file survives."""
    out = esc(text)
    for rx, rep in INLINE:
        out = rx.sub(rep, out)
    return out


def fill(text: str, ctx: dict) -> str:
    return re.sub(r"\{([a-z_]+)\}", lambda m: str(ctx[m.group(1)]) if m.group(1) in ctx else m.group(0), text)


def split_front_matter(text: str):
    meta = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = text[end + 4:]
    return meta, text.lstrip("\n")


def core_items_md(items, header=None) -> str:
    """The core task table, with the core task's own header when it has one cell per column."""
    if not items:
        return ""
    width = max(2 + len(t.split(" | ")) for _, _, t in items)
    head = list(header or [])
    if len(head) != width:
        head = ["#", "Area", "What is waiting"] + [""] * (width - 3)
    head[0] = "#"   # the page styles a table as the core task by this first header cell
    rows = ["| " + " | ".join(head) + " |", "|" + "---|" * width]
    rows += [f"| {n} | {a} | {t} |" for n, a, t in items]
    return "\n".join(rows)


def render_md(md: str):
    """Tiny markdown subset to HTML. Returns (html, [(anchor, h2 text)])."""
    out, para, table = [], [], []
    lst = None
    heads = []

    def flush_para():
        if para:
            text = " ".join(s.strip() for s in para)
            cls = ' class="goal"' if re.match(r"\*\*(The goal|Goal)\b", text) else ""
            out.append(f"<p{cls}>{inline(text)}</p>")
            para.clear()

    def flush_list():
        nonlocal lst
        if lst:
            tag, items = lst
            out.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{tag}>")
            lst = None

    def flush_table():
        if not table:
            return
        rows = [r for r in table if not all(c and set(c) <= set("-: ") for c in r)]
        has_sep = len(rows) != len(table)
        head = rows[0] if has_sep and rows else None
        body = rows[1:] if head is not None else rows
        if head is None or all(not c for c in head):
            out.append('<table class="box">' + "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</table>")
        else:
            cls = ' class="items"' if head[0] == "#" else ""
            out.append(f"<table{cls}><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</tbody></table>")
        table.clear()

    def flush_all():
        flush_para(); flush_list(); flush_table()

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_all(); continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            flush_all()
            level = len(m.group(1)); text = m.group(2).strip()
            if level == 2:
                anchor = "s%d" % (len(heads) + 1)
                heads.append((anchor, text))
                out.append(f'<h2 id="{anchor}"><span class="n">{len(heads)}</span>{inline(text)}</h2>')
            else:
                out.append(f"<h3>{inline(text)}</h3>")
            continue
        if line.strip().startswith("|"):
            flush_para(); flush_list()
            table.append(table_cells(line)); continue
        m = re.match(r"^(?:[-*]|\d+[.)])\s+(.*)$", line)
        if m:
            flush_para(); flush_table()
            tag = "ol" if line.lstrip()[0].isdigit() else "ul"
            if lst and lst[0] == tag:
                lst[1].append(m.group(1))
            else:
                flush_list(); lst = (tag, [m.group(1)])
            continue
        if lst and raw.startswith(("  ", "\t")):
            lst[1][-1] += " " + line.strip(); continue
        flush_list(); flush_table()
        para.append(line)
    flush_all()
    return "\n".join(out), heads


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and pathlib.Path(c).exists():
            return c
    return ""


def section_check(heads) -> list:
    names = [h.lower() for _, h in heads]
    return [s for s in SECTIONS if not any(n == s.lower() or n.startswith(s.lower()) for n in names)]


def write_terms(root, cfg) -> None:
    """Draft the terms message for every finalist whose terms_sent is null. A draft already there is kept."""
    tpl = (HERE.parent / "templates" / "messages" / "terms-before-trial.md").read_text(encoding="utf-8")
    parts = tpl.split("\n---\n")
    body = parts[1].strip() + "\n" if len(parts) >= 3 else tpl
    role = cfg.get("role") if isinstance(cfg.get("role"), dict) else {}
    terms = task_terms(cfg)
    ctx = {"role_pay": role.get("pay") or "[monthly pay]", "role_hours": role.get("hours") or "[hours]",
           "start": role.get("start") or "[start date]", "signoff": cfg.get("signoff", ""),
           "task_line": terms["task_line"]}
    if not any(role.get(k) for k in ("pay", "hours", "start")):      # no role terms: the message is about the task only
        body = "\n".join(l for l in body.split("\n") if "{role_pay}" not in l).replace("\n\n\n", "\n\n")
    elif not all(role.get(k) for k in ("pay", "hours", "start")):
        print('note: "role" in config.json is missing pay, hours or start; the draft shows a blank in brackets to fill.')
    out_dir = root / "out" / "messages"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in cfg.get("finalists", []):
        if f.get("terms_sent"):
            continue
        dst = out_dir / f"{f['slug']}-terms-before-trial.md"
        if dst.exists():
            print(f"kept {dst} (already drafted; your edits stay)")
            continue
        text = ("<!-- Draft. Not sent. Send it yourself, then put the date in terms_sent in challenge/config.json. -->\n\n"
                + fill(body, dict(ctx, first_name=f["name"].split()[0])))
        no_dashes(text, f"{f['slug']} terms message")
        dst.write_text(text, encoding="utf-8")
        print(f"wrote {dst}")


def lock_guide(ch, guide, when):
    """Write rubric_locked_at and the guide's fingerprint into review.json. Refused once the guide changed."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", when or ""):
        raise SystemExit("--lock-guide takes a date like 2026-10-21, or nothing for today")
    sha = hashlib.sha256(guide.read_bytes()).hexdigest()
    path = ch / "review.json"
    review = load_json(path, {})
    old = review.get("scoring_guide_sha256")
    if old and old != sha:
        raise SystemExit(f"SCORING-GUIDE.md changed after it was locked on {review.get('rubric_locked_at', '')}. "
                         "The lock stays. Put the locked text back, or tell every finalist the guide changed and rate everyone again.")
    if old:
        print(f"note: the scoring guide was already locked on {review.get('rubric_locked_at', '')}; nothing changed")
        return
    review = {"rubric_locked_at": when, "scoring_guide_sha256": sha, **{k: v for k, v in review.items()
                                                                     if k not in ("rubric_locked_at", "scoring_guide_sha256")}}
    path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path}  (scoring guide locked {when}; it does not change after this)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    ap.add_argument("--pdf", action="store_true", help="also run Chrome headless to make <slug>.pdf")
    ap.add_argument("--terms", action="store_true", help="draft the terms message for each finalist whose terms_sent is null")
    ap.add_argument("--lock-guide", nargs="?", const=dt.date.today().isoformat(), default=None, metavar="YYYY-MM-DD",
                    help="lock SCORING-GUIDE.md before the first submission (default date: today)")
    args = ap.parse_args()
    root = find_root(args.root)
    ch = root / "challenge"
    if not (ch / "config.json").is_file():
        raise SystemExit(f"no {ch / 'config.json'}: copy templates/config.example.json there and fill it")
    if args.terms:
        cfg = load_json(ch / "config.json", {})
        for line in pay_advice(cfg):
            print(line)
        write_terms(root, cfg)
        return
    guide = ch / "SCORING-GUIDE.md"
    if not guide.is_file():
        raise SystemExit(f"no {guide}: write the scoring guide with the briefs (templates/scoring-guide.md). "
                         "It is what you and Claude rate the submissions against.")
    no_dashes(guide.read_text(encoding="utf-8"), "SCORING-GUIDE.md")
    if args.lock_guide:
        lock_guide(ch, guide, args.lock_guide)
    cfg = load_json(ch / "config.json", {})
    review = load_json(ch / "review.json", {})
    badge = demo_label(root, cfg)

    core_path = root / cfg.get("core_task", "challenge/core-task.md")
    items = read_core_items(core_path)
    if not items:
        print(f"note: no numbered table found in {core_path}; {{core_items}} stays empty.")

    brand = cfg.get("brand", "Your brand")
    doc_label = cfg.get("doc_label", "Test task")
    terms = task_terms(cfg)
    for line in pay_advice(cfg):
        print(line)
    hours = cfg.get("expected_hours", 2)
    days = cfg.get("days", 5)
    common = {
        "brand": brand, "fee": terms["fee"], "effort": terms["effort"], "days": str(days), "days_words": words(days),
        "hours": str(hours), "hours_words": words(hours), "due": cfg.get("due", ""),
        "submit_to": cfg.get("submit_to", ""), "payment": cfg.get("payment", ""), "signoff": cfg.get("signoff", ""),
        "core_items": core_items_md(items, read_core_header(core_path)),
    }

    briefs = ch / "briefs"
    agreement_tpl = HERE.parent / "templates" / "trial-agreement.md"
    finalists = cfg.get("finalists", [])
    written = []
    for f in finalists:
        slug = f["slug"]
        src = briefs / f"{slug}.md"
        if not src.exists():
            print(f"skip {slug}: no {src}. Claude writes it from templates/brief.md.")
            continue
        if not f.get("terms_sent"):
            print(f"refused {slug}: terms_sent is null in config.json. Send pay, hours and start date in writing first "
                  f"(build_briefs.py --terms drafts it), then put the date in terms_sent. No brief until then.")
            continue
        raw_text = src.read_text(encoding="utf-8")
        meta, md = split_front_matter(raw_text)
        md = re.sub(r"<!--.*?-->", "", md, flags=re.S)  # notes left from templates/brief.md
        name = meta.get("name") if meta.get("name") and "{" not in meta["name"] else f["name"]
        r = review.get(slug) if isinstance(review.get(slug), dict) else {}
        track = f.get("track") or r.get("track") or ""
        ctx = dict(common, name=name, first_name=name.split()[0], track=track)
        ctx.update({k: fill(terms[k], ctx) for k in ("pay_line", "use_line", "fee_terms", "use_terms", "stop_terms")})
        md = fill(md, ctx)
        title = fill(meta.get("title") or f.get("task_title", doc_label), ctx)
        body, heads = render_md(md)

        problems = []
        missing = section_check(heads)
        if missing:
            problems.append("sections missing from the layout: " + ", ".join(missing))
        if not re.search(r"\babout\s+(?:\w+\s+){1,2}?hours?\b", md, re.I):
            problems.append('the effort section does not say "about N hours"')
        if not re.search(r"more time|adjust", md, re.I):
            problems.append('no way to ask for an adjustment ("If you need more time, tell me")')
        if not terms["paid"] and re.search(r"\{fee\}|\bfee\b|\$\d", md):
            problems.append("the task is unpaid but the brief still names a fee: use {pay_line} and {use_line}")
        if "{core_items}" in raw_text and not items:
            problems.append("the shared core task table is empty")
        for other in finalists:
            if other["slug"] != slug and re.search(r"\b%s\b" % re.escape(other["name"].split()[0]), md):
                raise SystemExit(f"{slug}: the brief mentions another finalist ({other['name']}). Each brief reads as the only one.")
        no_dashes(md + title, f"{slug} brief")

        nav = "".join(f'<li><a href="#{a}">{esc(h)}</a></li>' for a, h in heads)
        glance = (f'<div class="glance"><div><span>Return within</span> {esc(words(days))} days</div>'
                  f'<div><span>Expected work:</span> about {esc(terms["effort"])}</div>'
                  f'<div><span>Pay:</span> {esc(terms["glance_pay"])}</div>'
                  f'<div><span>Due:</span> {esc(cfg.get("due", ""))}</div></div>')
        parts = body.split("<h2", 1)
        intro = parts[0].replace("<p>", '<p class="intro">', 1)
        rest = ("<h2" + parts[1]) if len(parts) > 1 else ""
        sheet = (f'<div class="wrap"><nav class="index"><b>This brief</b><ol>{nav}</ol>{glance}</nav>'
                 f'<article class="sheet"><h1>{esc(title)}</h1>{intro}{rest}</article></div>')
        out_html = page(f"{brand} | {doc_label} | {name}", f"{brand} · {doc_label} · for {name}", sheet, badge, CSS)
        no_dashes(out_html, f"{slug} brief page")
        dst = briefs / f"{slug}.html"
        dst.write_text(out_html, encoding="utf-8")
        written.append(dst)
        print(f"wrote {dst}")
        for p in problems:
            print(f"  check {slug}: {p}")
        if agreement_tpl.exists():
            body_t = agreement_tpl.read_text(encoding="utf-8")
            body_t = body_t[body_t.index("---"):] if "---" in body_t else body_t
            agreement = fill(body_t, dict(ctx, title=title, date=cfg.get("sent") or f["terms_sent"]))
            adst = briefs / f"{slug}-trial-agreement.md"
            adst.write_text(f"# Test task agreement: {name}\n\nA checklist in one paragraph, not legal advice. "
                            f"Send it with the brief; both sign.\n\n" + agreement, encoding="utf-8")
            print(f"wrote {adst}")

    chrome = find_chrome()
    if written:
        print("\nPDF per brief (Chrome headless):")
    for dst in written:
        pdf = dst.with_suffix(".pdf")
        shown = chrome or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        print(f'  "{shown}" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="{pdf}" {dst.as_uri()}')
        if args.pdf:
            if not chrome:
                print("  Chrome not found. Set CHROME=/path/to/chrome and rerun with --pdf.")
                break
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={pdf}", dst.as_uri()], check=True, capture_output=True)
            print(f"  wrote {pdf} ({pdf.stat().st_size} bytes)")
    if not written:
        print("no brief written. Claude writes challenge/briefs/<slug>.md first (templates/brief.md).")


if __name__ == "__main__":
    main()
