#!/usr/bin/env python3
"""summary.py: organises the reference notes and builds the board. Standard library only, no network.

Usage, from your hiring/ folder (the one that holds criteria.md) or the folder above it:
  python3 <skill>/scripts/summary.py            every finalist with notes in out/references/
  python3 <skill>/scripts/summary.py <slug>     one finalist
  add --root PATH to point at the hiring folder, --date YYYY-MM-DD to set the date printed as written

Reads, in out/references/:
  <slug>-notes-<n>.md          your notes after each call (templates/notes.md): per answer an Answer line and three
                               lines, Concrete example / Vague opinion / Follow-up, and an optional "Covers: open
                               question N" (several, comma separated, are fine)
  <slug>-open-questions.md     the reviewed open questions, to name each one
  <slug>-referees.md           the approved referees, for names when a notes file is missing
  <slug>-summary.md            an earlier summary, to keep Claude's read and your verdict
Writes:
  <slug>-summary.md            per finalist: the calls, every answer grouped by question (the two core questions, each
                               open question, other answers) as Concrete example / Vague opinion / Follow-up, the
                               follow-ups, neutral notes from the script, Claude's read (kept), your verdict (kept)
  REFERENCES.html              one board across finalists, with the same three columns

What the script decides: counts, grouping, and neutral notes (a referee not reached, only one referee reached,
an open question with no concrete example yet, a core question not answered). What it never decides: whether a
hesitant answer means no. There is no such rule here. Concrete examples are weighed; vague opinions are shown and
not weighed. One person's opinion is never a complete picture of a candidate. Every string on the HTML page is
escaped. Prints what it wrote.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
from common import esc  # noqa: E402

TEMPLATE = HERE.parent / "templates" / "summary.md"
READ_START, READ_END = "<!-- claude-read:start -->", "<!-- claude-read:end -->"
CORE = [("hire again", "Would you hire this person again, and why?"),
        ("difficult feedback", "Tell me about a time they had to handle difficult feedback.")]
FIELDS = ("Concrete example", "Vague opinion", "Follow-up")


def empty(v):
    v = (v or "").strip().lower()
    return not v or v.startswith("none") or v.startswith("not reached") or v.startswith("[")


def header(text):
    return {m.group(1).strip().lower(): m.group(2).strip()
            for m in re.finditer(r"^-\s+\*\*([^:*]+):\*\*\s*(.*)$", text, re.M)}


def groups_for(title, covers):
    t = title.lower()
    out = []
    if "hire this person again" in t or "hire them again" in t or "hire him again" in t or "hire her again" in t:
        out.append("hire again")
    if "difficult feedback" in t:
        out.append("difficult feedback")
    for c in covers:
        m = re.search(r"open question\s*(\d+)", c, re.I)
        if m:
            out.append(f"open question {m.group(1)}")
    m = re.match(r"(?:\d+\.\s*)?open question\s*(\d+)", title, re.I)
    if m and f"open question {m.group(1)}" not in out:
        out.append(f"open question {m.group(1)}")
    return out or ["other"]


def parse_notes(path):
    text = path.read_text(encoding="utf-8")
    h = header(text)
    answers = []
    for m in re.finditer(r"^###\s+([^\n]+)\n(.*?)(?=^###\s|^##\s|\Z)", text, re.M | re.S):
        title, body = m.group(1).strip(), m.group(2)

        def line(key):
            mm = re.search(rf"^{re.escape(key)}:\s*(.*?)\s*$", body, re.M)
            return mm.group(1) if mm else ""
        covers = [c.strip() for c in line("Covers").split(",") if c.strip()]
        a = {"title": re.sub(r"^\d+\.\s*", "", title), "answer": line("Answer"),
             "groups": groups_for(re.sub(r"^\d+\.\s*", "", title), covers)}
        for f in FIELDS:
            v = line(f)
            a[f] = "" if empty(v) else v
        a["unsorted"] = bool(a["answer"]) and not any(line(f) for f in FIELDS)
        answers.append(a)
    status = h.get("status", "").lower()
    status = "done" if status.startswith("done") else ("declined" if "declin" in status else
                                                       ("no reply" if status else ("done" if answers else "no reply")))
    referee = h.get("referee", "?")
    return {"file": path.name, "n": int(re.search(r"-notes-(\d+)", path.name).group(1)), "referee": referee,
            "short": referee.split(",")[0].strip(), "relationship": h.get("relationship", ""),
            "overlap": h.get("overlap", ""), "approved": h.get("approved by the candidate", ""),
            "call": h.get("call", ""), "status": status, "candidate": h.get("candidate", ""), "answers": answers,
            "counts": {f: sum(1 for a in answers if a[f]) for f in FIELDS}}


def open_questions(refdir, slug):
    p = refdir / f"{slug}-open-questions.md"
    out = {}
    if p.exists():
        for r in common.open_question_rows(p.read_text(encoding="utf-8")):
            if not r["placeholder"] and r["ask"].startswith("referee"):
                out[f"open question {r['n']}"] = r["q"]
    return out


def group_rows(refs, opens):
    """[(key, label, [(referee, answer)])] in reading order."""
    order = [(k, q) for k, q in CORE] + [(k, f"Open question {k.split()[-1]}: {q}") for k, q in opens.items()]
    seen = {k for k, _ in order}
    for r in refs:
        for a in r["answers"]:
            for g in a["groups"]:
                if g not in seen and g != "other":
                    order.append((g, g.capitalize()))
                    seen.add(g)
    order.append(("other", "Other answers"))
    rows = []
    for k, label in order:
        items = [(r, a) for r in refs if r["status"] == "done" for a in r["answers"] if k in a["groups"]]
        rows.append((k, label, items))
    return rows


def notes_from_script(refs, rows):
    out = []
    done = [r for r in refs if r["status"] == "done"]
    for r in refs:
        if r["status"] != "done":
            out.append(f"{r['short']}: {r['status']}. Ask the candidate for another name; silence is not a verdict.")
    if len(done) == 1:
        out.append(f"Only one referee reached. {common.ONE_OPINION}")
    if not done:
        out.append("No referee reached yet.")
    for k, label, items in rows:
        if k == "other":
            continue
        if done and not items:
            out.append(f"Not answered by any referee: \"{label}\"")
        elif items and not any(a["Concrete example"] for _, a in items):
            out.append(f"No concrete example yet for \"{label}\" (opinions only in this group).")
    unsorted = sum(1 for r in refs for a in r["answers"] if a["unsorted"])
    if unsorted:
        out.append(f"{unsorted} answer(s) not yet organised into Concrete example / Vague opinion / Follow-up.")
    return out


def keep_blocks(existing):
    read = None
    m = re.search(re.escape(READ_START) + r"\n?(.*?)\n?" + re.escape(READ_END), existing, re.S)
    if m and not m.group(1).strip().startswith("Not written yet"):
        read = m.group(1).strip()
    verdict = None
    m = re.search(r"^##\s+Founder's verdict[^\n]*\n(.*)\Z", existing, re.M | re.S)
    if m and not re.search(r"\*\*Founder's verdict:\*\*\s*open\s*$", m.group(1).strip().split("\n")[0]):
        verdict = m.group(1).strip()
    return read, verdict


def cell(s):
    return (s or "").replace("|", "/")


def write_summary(refdir, slug, name, refs, rows, flags, written, demo):
    out = refdir / f"{slug}-summary.md"
    read_kept, verdict_kept = keep_blocks(out.read_text(encoding="utf-8") if out.exists() else "")
    calls = "\n".join(f"| {r['n']} | {cell(r['referee'])} | {cell(r['relationship'])} | {cell(r['overlap'])} | {r['status']} | "
                      f"{r['counts']['Concrete example']} | {r['counts']['Vague opinion']} | {r['counts']['Follow-up']} |"
                      for r in refs) or "| | no notes files yet | | | | | | |"
    parts = []
    for k, label, items in rows:
        if not items and k == "other":
            continue
        parts.append(f"### {label}\n")
        if not items:
            parts.append("_Not answered by any referee._\n")
            continue
        parts.append("| Referee | Concrete example | Vague opinion | Follow-up |\n|---|---|---|---|")
        parts += [f"| {cell(r['short'])} | {cell(a['Concrete example']) or 'none'} | {cell(a['Vague opinion']) or 'none'} | "
                  f"{cell(a['Follow-up']) or 'none'} |" for r, a in items]
        parts.append("")
    fups = [f"- {r['short']}: {a['Follow-up']}" for r in refs for a in r["answers"] if a["Follow-up"]]
    tot = {f: sum(r["counts"][f] for r in refs) for f in FIELDS}
    done = sum(1 for r in refs if r["status"] == "done")
    page = TEMPLATE.read_text(encoding="utf-8").format(
        name=name, written=written, n_files=len(refs), calls_rows=calls,
        demo="FICTIONAL DEMO. Reconstructed demo notes, not real calls.\n\n" if demo else "",
        reached=f"{done} of {len(refs)}",
        organised=f"{tot['Concrete example']} concrete example(s), {tot['Vague opinion']} vague opinion(s), {tot['Follow-up']} follow-up(s)",
        by_question="\n".join(parts).strip() or "_No answers yet._",
        followups="\n".join(fups) or "- none",
        flags="\n".join(f"- {f}" for f in flags) or "- none")
    if read_kept:
        page = re.sub(re.escape(READ_START) + r".*?" + re.escape(READ_END),
                      lambda _: READ_START + "\n" + read_kept + "\n" + READ_END, page, flags=re.S)
    if verdict_kept:
        page = re.sub(r"(^##\s+Founder's verdict[^\n]*\n).*\Z", lambda m: m.group(1) + "\n" + verdict_kept + "\n", page, flags=re.M | re.S)
    common.write(out, page)
    return out


def read_and_verdict(path):
    read, verdict = keep_blocks(path.read_text(encoding="utf-8") if path.exists() else "")
    line = "open"
    if verdict:
        m = re.search(r"\*\*Founder's verdict:\*\*\s*(.*)", verdict)
        line = m.group(1).strip() if m else verdict.split("\n")[0]
    return read, line


def items_html(items, field):
    li = [f"<li><b>{esc(r['short'])}:</b> {esc(a[field])}</li>" for r, a in items if a[field]]
    return "<ul>" + "".join(li) + "</ul>" if li else '<span class="note">none</span>'


def board(finalists, refdir, written, demo):
    head_rows, cards = "", ""
    for slug, name, refs, rows, flags in finalists:
        done = [r for r in refs if r["status"] == "done"]
        tot = {f: sum(r["counts"][f] for r in refs) for f in FIELDS}
        oq = [(k, items) for k, _, items in rows if k.startswith("open question")]
        oq_ok = sum(1 for _, items in oq if any(a["Concrete example"] for _, a in items))
        read, verdict = read_and_verdict(refdir / f"{slug}-summary.md")
        one = '<br><span class="pill warn">one opinion only</span>' if len(done) == 1 else ""
        head_rows += (f'<tr><td><a href="#{esc(slug)}"><b>{esc(name)}</b></a></td><td>{len(done)} of {len(refs)}{one}</td>'
                      f'<td>{tot["Concrete example"]}</td><td>{tot["Vague opinion"]}</td><td>{tot["Follow-up"]}</td>'
                      f'<td>{oq_ok} of {len(oq)}</td><td>{esc(verdict)}</td></tr>')
        ref_list = "".join(f'<li><b>{esc(r["referee"])}</b>, {esc(r["relationship"])} ({esc(r["overlap"])}). '
                           f'<span class="note">{esc(r["call"])}. Approved: {esc(r["approved"])}</span></li>' for r in refs)
        trs = ""
        for k, label, items in rows:
            if k == "other" and not items:
                continue
            trs += (f'<tr><td><b>{esc(label)}</b></td><td class="ce">{items_html(items, "Concrete example")}</td>'
                    f'<td class="vo">{items_html(items, "Vague opinion")}</td><td class="fu">{items_html(items, "Follow-up")}</td></tr>')
        flag_html = "".join(f"<li>{esc(f)}</li>" for f in flags) or "<li class=\"note\">none</li>"
        read_html = "".join(f"<p>{esc(p)}</p>" for p in re.split(r"\n\s*\n", read or "") if p.strip()) or \
            '<p class="note">Claude\'s read not written yet.</p>'
        cards += (
            f'<div class="card" id="{esc(slug)}"><h2>{esc(name)}</h2><ul>{ref_list}</ul>'
            '<table class="ref" style="table-layout:fixed"><colgroup><col style="width:300px"><col><col style="width:330px"><col style="width:360px"></colgroup>'
            '<tr><th>Question</th><th>Concrete example</th><th>Vague opinion</th><th>Follow-up</th></tr>'
            f'{trs}</table><h3>Notes from the script</h3><ul>{flag_html}</ul>'
            f'<h3>Claude\'s read</h3><div class="box soft">{read_html}</div>'
            f'<div class="box warm"><b>Your verdict:</b> {esc(verdict)}</div></div>')
    css = ("<style>table.ref td.ce{background:#eef7f0}table.ref td.vo{background:#f6f3ec;color:#55555a}"
           "table.ref td.fu{background:#edf2fb}table.ref ul{margin:0 0 0 22px}table.ref li{margin:4px 0}</style>")
    body = (css + "<main><div class=\"card\"><p style=\"font-size:28px;margin-top:0\"><b>" + esc(common.ONE_OPINION) + "</b></p>"
            "<p>Every answer is organised as <b>Concrete example</b> (weighed), <b>Vague opinion</b> (shown, not weighed) and "
            "<b>Follow-up</b> (what to check next). There is no rule that a hesitant answer means no. You made every call; "
            "you decide. Nothing on this page was sent to anyone.</p>"
            "<table style=\"table-layout:fixed\"><colgroup><col style=\"width:240px\"><col style=\"width:200px\"><col style=\"width:150px\">"
            "<col style=\"width:150px\"><col style=\"width:150px\"><col style=\"width:220px\"><col></colgroup>"
            "<tr><th>Finalist</th><th>Referees reached</th><th>Concrete examples</th><th>Vague opinions</th>"
            f"<th>Follow-ups</th><th>Open questions with a concrete example</th><th>Your verdict</th></tr>{head_rows}</table></div>"
            f"{cards}</main>")
    return common.page("Reference calls", f"{len(finalists)} finalist(s), after the test task, before any offer. "
                       f"Built {written} from the notes in out/references/.", body, demo)


def main():
    ap = argparse.ArgumentParser(description="organise reference notes and build REFERENCES.html")
    ap.add_argument("slugs", nargs="*", help="candidate slugs; default: every finalist with notes files")
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    ap.add_argument("--date", default=None, help="the date to print as written (default: today.txt, else today)")
    a = ap.parse_args()
    root = common.find_root(a.root)
    refdir = root / "out" / "references"
    if not refdir.exists():
        sys.exit(f"no folder {refdir}; run call_sheet.py first and write the notes after each call")
    written = common.project_today(root, a.date)[0].isoformat()
    demo = common.is_demo(root)
    slugs = a.slugs or sorted({re.sub(r"-notes-\d+\.md$", "", p.name) for p in refdir.glob("*-notes-*.md")})
    if not slugs:
        sys.exit("no notes files yet: out/references/<slug>-notes-<n>.md, one per call (templates/notes.md)")
    names = {}
    cfg = root / "challenge" / "config.json"
    if cfg.exists():
        try:
            names = {f["slug"]: f.get("name", f["slug"]) for f in json.loads(cfg.read_text(encoding="utf-8")).get("finalists", [])}
        except (ValueError, KeyError):
            names = {}
    finalists = []
    for slug in slugs:
        files = sorted(refdir.glob(f"{slug}-notes-*.md"), key=lambda p: int(re.search(r"-notes-(\d+)", p.name).group(1)))
        refs = [parse_notes(p) for p in files]
        name = names.get(slug) or next((r["candidate"] for r in refs if r["candidate"]), slug.replace("-", " ").title())
        rows = group_rows(refs, open_questions(refdir, slug))
        flags = notes_from_script(refs, rows)
        write_summary(refdir, slug, name, refs, rows, flags, written, demo)
        print(f"  {slug}: {len(refs)} notes file(s), {sum(1 for r in refs if r['status'] == 'done')} reached, {len(flags)} note(s) from the script")
        finalists.append((slug, name, refs, rows, flags))
    common.write(refdir / "REFERENCES.html", board(finalists, refdir, written, demo))


if __name__ == "__main__":
    main()
