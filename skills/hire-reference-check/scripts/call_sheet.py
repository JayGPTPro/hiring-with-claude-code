#!/usr/bin/env python3
"""call_sheet.py: a 10 to 15 minute reference call guide per finalist. Standard library only, no network.

Usage, from your hiring/ folder (the one that holds criteria.md) or the folder above it:
  python3 <skill>/scripts/call_sheet.py            every finalist with out/references/<slug>-referees.md
  python3 <skill>/scripts/call_sheet.py <slug>     one finalist
  add --root PATH to point at the hiring folder, --date YYYY-MM-DD to set the date printed as written

Reads, in out/references/:
  <slug>-referees.md         the one or two referees the candidate approved (templates/referees.md). A row is used
                             only when "Approved by the candidate" starts with yes and "Current employer?" with no.
  <slug>-open-questions.md   the questions still open after the interviews and the work sample
                             (templates/open-questions.md).
When a file is missing, it is drafted and the script stops for that finalist:
  - the referees file from the template, to fill with the referees the user named in chat;
  - the open questions from the debrief (out/interviews/<slug>/CANDIDATE_DEBRIEF.md, "Open questions", bulleted
    or numbered), from any work-sample file that names the finalist (challenge/review.json "clarifying_questions"
    and "assumptions_stated", challenge/walkthroughs/<slug>.md) and from the claim check (out/verification/<slug>.md,
    "Questions for the call"), marked "candidate" until a person decides a referee can answer it. The draft says
    "Status: draft".
Approval: Claude shows the questions to the user in chat. When the user says yes, Claude sets the line to
"Status: approved in chat on YYYY-MM-DD". The guide is built only from a file with that line. It records the
user's yes; it is not a lock. After any edit to the questions, ask again and write the new date.
Writes:
  out/references/<slug>-call-sheet.md and <slug>-call-sheet.html: the guide, minute by minute, built around two
  core questions ("Would you hire this person again, and why?", "Tell me about a time they had to handle
  difficult feedback.") and the open questions marked "referee". Questions marked "candidate" are listed
  apart: they are for the candidate, not for a referee.
The tool never contacts anyone. Every string on the HTML page is escaped. Prints what it wrote.
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

TPL = HERE.parent / "templates"
CORE = [
    ("Would you hire this person again, and why?", "The why. A situation, not an adjective."),
    ("Tell me about a time they had to handle difficult feedback.", "What happened next, in their words."),
]
IF_TIME = [
    "One concrete example of their work that you remember.",
    "What advice would you give me for their first ninety days?",
]


def read(p):
    return p.read_text(encoding="utf-8") if p.exists() else ""


def parse_referees(text):
    name = re.search(r"^#\s+Referees:\s*(.+)$", text, re.M)
    meta = {}
    for k in ("Asked the candidate on", "Do not contact", "Delete raw notes on"):
        m = re.search(rf"^-\s*{k}:\s*(.+)$", text, re.M | re.I)
        meta[k] = m.group(1).strip() if m and not m.group(1).strip().startswith("[") else ""
    table = "| #" + text.split("| #", 1)[1] if "| #" in text else ""
    ok, refused = [], []
    for c in common.table_rows(table):
        if len(c) < 6 or c[1].startswith("["):
            continue
        r = {"n": c[0], "who": c[1], "relationship": c[2], "overlap": c[3], "approved": c[4], "current": c[5]}
        if not r["approved"].lower().startswith("yes"):
            refused.append((r, "not approved by the candidate"))
        elif not r["current"].lower().startswith("no"):
            refused.append((r, "works at the current employer; not before an offer"))
        else:
            ok.append(r)
    return (name.group(1).strip() if name else ""), meta, ok, refused


APPROVED = re.compile(r"^Status:\s*approved in chat on (\d{4}-\d{2}-\d{2})", re.M | re.I)


def parse_open(text):
    """(the date the user approved the questions in chat or "", the question rows, the placeholder row numbers)."""
    m = APPROVED.search(text)
    rows = common.open_question_rows(text)
    return (m.group(1) if m else ""), [r for r in rows if not r["placeholder"]], [r["n"] for r in rows if r["placeholder"]]


def placeholder_note(slug, name, numbers, approved):
    if not numbers:
        return ""
    rows = ("row " if len(numbers) == 1 else "rows ") + ", ".join(numbers)
    if approved:
        return (f"  note: {slug}: {rows} of {name} {'is' if len(numbers) == 1 else 'are'} still a placeholder ([...]) and "
                "left out of the guide and the summary. Fill or delete it, then ask the user to approve again.")
    return (f"  note: {slug}: {rows} of {name} {'is' if len(numbers) == 1 else 'are'} a placeholder ([...]). Fill or delete "
            "it before you show the questions for approval; a placeholder is never asked.")


def quoted(q):
    """The question in quotation marks once: as written when it already carries its own quotes."""
    q = q.strip()
    if len(q) > 1 and q[0] in "\"\u201c" and q[-1] in "\"\u201d" and '"' not in q[1:-1]:
        q = q[1:-1].strip()
    return q if '"' in q or "\u201c" in q else f"\"{q}\""


def draft_open(root, slug, name, path, demo):
    rows = []
    deb = read(root / "out" / "interviews" / slug / "CANDIDATE_DEBRIEF.md")
    body = common.section(deb, r"(?:\d+\.\s*)?Open questions")
    for l in body.splitlines():
        m = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$", l)
        q = m.group(1).strip() if m else ""
        if q and not q.startswith("["):
            rows.append((q, "Still open after the interview",
                         f"out/interviews/{slug}/CANDIDATE_DEBRIEF.md, Open questions", "referee"))
    rv = root / "challenge" / "review.json"
    if rv.exists():
        try:
            r = json.loads(rv.read_text(encoding="utf-8")).get(slug, {})
        except ValueError:
            r = {}
        if isinstance(r, dict):
            if not r.get("clarifying_questions"):
                rows.append(("How did they act when information was missing: ask, assume, or wait?",
                             "Asked no clarifying question during the work sample", "challenge/review.json", "referee"))
            for a in r.get("assumptions_stated", []) or []:
                rows.append((f"Assumption stated in the work sample: {a}", "Check how they handle assumptions at work",
                             "challenge/review.json", "referee"))
    wt = root / "challenge" / "walkthroughs" / f"{slug}.md"
    if wt.exists():
        rows.append(("[from the walkthrough notes: what is still open after it?]", "Read the walkthrough",
                     f"challenge/walkthroughs/{slug}.md", "referee"))
    cc = common.claim_check(root, slug)
    for q in (cc or {}).get("questions", []):
        rows.append((q, "From the claim check before the interview. Keep it only if the interviews did not settle it",
                     f"{cc['file']}, Questions for the call", "candidate"))
    text = read(TPL / "open-questions.md").replace("[Candidate name]", name)
    text = text.replace("<!-- demo -->", "FICTIONAL DEMO. Invented people." if demo else "")
    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")
    table = "\n".join(f"| {i} | {cell(q)} | {cell(w)} | {cell(s)} | {a} |" for i, (q, w, s, a) in enumerate(rows, 1)) or \
        "| 1 | [no open question found; write them from the debrief and the work sample] | | | referee |"
    text = re.sub(r"^\| 1 \| \[one question.*$", lambda _: table, text, flags=re.M)
    common.write(path, text)


def guide_rows(name, refs, open_ref):
    first = name.split()[0] if name else "them"
    rows = [("0 to 1", f"\"Thanks for taking the call. {first} gave me your name and knows I am calling. "
                       "It takes ten to fifteen minutes and my notes are only about the work.\"",
             "That they expected the call.")]
    rows.append(("1 to 2", "\"How did you work together, and for how long?\"", "The role and the dates match the CV."))
    rows.append(("2 to 5", f"\"{CORE[0][0]}\"", CORE[0][1]))
    rows.append(("5 to 8", f"\"{CORE[1][0]}\"", CORE[1][1]))
    if open_ref:
        n = len(open_ref)
        edges = [8 + round(5 * i / n) for i in range(n + 1)]
        for i, o in enumerate(open_ref):
            a, b = edges[i], edges[i + 1]
            when = f"{a} to {b}" if b > a else f"about {a}"
            rows.append((when, f"Open question {o['n']}: {quoted(o['q'])}", "A concrete example, not an opinion."))
    rows.append(("13 to 15", "\"Is there anything I should have asked? Who else saw their work?\" Thank them.",
                 "Names are offered, not chased. Ask the candidate before calling anyone new."))
    return rows


def build(root, slug, demo, written):
    refdir = root / "out" / "references"
    rp, op = refdir / f"{slug}-referees.md", refdir / f"{slug}-open-questions.md"
    cfg = root / "challenge" / "config.json"
    names = {}
    if cfg.exists():
        try:
            names = {f["slug"]: f.get("name", f["slug"]) for f in json.loads(cfg.read_text(encoding="utf-8")).get("finalists", [])}
        except (ValueError, KeyError):
            names = {}
    if not rp.exists():
        text = read(TPL / "referees.md").replace("[Candidate name]", names.get(slug, slug.replace("-", " ").title()))
        common.write(rp, text.replace("<!-- demo -->", "FICTIONAL DEMO. Invented people." if demo else ""))
        print(f"  {slug}: fill the referees the candidate approved, then rerun.")
        return 1
    name, meta, refs, refused = parse_referees(read(rp))
    name = name or names.get(slug, slug.replace("-", " ").title())
    if not refs:
        print(f"  {slug}: no approved referee in {rp.name}. Refused: " +
              ("; ".join(f"{r['who']} ({why})" for r, why in refused) or "no rows") + ".")
        return 1
    if not op.exists():
        draft_open(root, slug, name, op, demo)
        print(f"  {slug}: drafted the open questions in {op.name}. Show them to the user in chat; when they say yes, "
              "set its Status line to 'Status: approved in chat on <date>' and run this again.")
        note = placeholder_note(slug, op.name, parse_open(read(op))[2], False)
        if note:
            print(note)
        return 1
    approved, opens, holes = parse_open(read(op))
    note = placeholder_note(slug, op.name, holes, bool(approved))
    if not approved:
        print(f"  {slug}: {op.name} is not approved yet. Show the questions to the user in chat; when they say yes, "
              "set its Status line to 'Status: approved in chat on <date>' and run this again.")
        if note:
            print(note)
        return 1
    if note:
        print(note)
    open_ref = [o for o in opens if o["ask"].startswith("referee")]
    open_cand = [o for o in opens if o["ask"].startswith("candidate")]
    ref_lines = "\n".join(f"- Referee {r['n']}: {r['who']}. {r['relationship'][:1].upper() + r['relationship'][1:]} "
                          f"({r['overlap']}). Approved by the candidate: {r['approved']}." for r in refs)
    if refused:
        ref_lines += "\n" + "\n".join(f"- Not on this guide: {r['who']} ({why})." for r, why in refused)
    if len(refs) > 2:
        ref_lines += "\n- More than two referees listed. One or two is enough; call the ones who saw the work the open questions are about."
    rows = guide_rows(name, refs, open_ref)
    tpl = read(TPL / "call-sheet.md")
    cand_block = ("## Not for the referee: ask the candidate\n\n" + "\n".join(f"- {o['q']} ({o['why']})" for o in open_cand)) if open_cand else ""
    ref_lines += f"\n- Open questions approved in chat on {approved}."
    md = (tpl.replace("{name}", name).replace("{slug}", slug).replace("{role}", common.role(root)).replace("{written}", written)
          .replace("{demo}", "FICTIONAL DEMO. Invented people; a guide for a demo, not a real call.\n\n" if demo else "")
          .replace("{referee_lines}", ref_lines).replace("{do_not_contact}", meta["Do not contact"] or "[ask the candidate]")
          .replace("{delete_date}", meta["Delete raw notes on"] or "[date]")
          .replace("{guide_rows}", "\n".join(f"| {a} | {b} | {c} |" for a, b, c in rows))
          .replace("{open_rows}", "\n".join(f"| {o['n']} | {o['q']} | {o['why']} | {o['source']} |" for o in open_ref) or "| | none | | |")
          .replace("{candidate_block}", cand_block)
          .replace("{if_time}", "If there is time: " + " ".join(f"\"{q}\"" for q in IF_TIME)))
    md = re.sub(r"\n{3,}", "\n\n", md)
    common.write(refdir / f"{slug}-call-sheet.md", md)
    # the HTML view of the same guide
    ref_html = "".join(f"<li><b>{esc(r['who'])}</b>, {esc(r['relationship'])}, {esc(r['overlap'])}. "
                       f"<span class=\"pill ok\">approved: {esc(r['approved'])}</span></li>" for r in refs)
    ref_html += "".join(f"<li class=\"mute\">Not on this guide: {esc(r['who'])} ({esc(why)})</li>" for r, why in refused)
    guide_html = "".join(f"<tr><td style=\"white-space:nowrap\"><b>{esc(a)}</b></td><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in rows)
    open_html = "".join(f"<tr><td><b>{esc(o['n'])}</b></td><td>{esc(o['q'])}</td><td>{esc(o['why'])}</td><td class=\"note\">{esc(o['source'])}</td></tr>"
                        for o in open_ref)
    cand_html = ("<div class=\"card\"><h2>Not for the referee: ask the candidate</h2><ul>" +
                 "".join(f"<li>{esc(o['q'])} <span class=\"note\">({esc(o['why'])})</span></li>" for o in open_cand) + "</ul></div>") if open_cand else ""
    body = (
        "<main>"
        "<div class=\"card\"><div class=\"box warm\" style=\"margin-top:0\"><b>You make the call.</b> Voice, 10 to 15 minutes. "
        "This guide was written by the assistant, which never contacts a referee or the candidate.</div>"
        f"<h2>Approved by {esc(name.split()[0])}</h2><ul>{ref_html}</ul><p class=\"note\">Open questions approved in chat on {esc(approved)}.</p>"
        f"<p>Do not contact: {esc(meta['Do not contact'] or 'ask the candidate')}. Never the current employer before an offer. "
        f"Raw notes deleted on {esc(meta['Delete raw notes on'] or '[date]')}.</p>"
        f"<p class=\"lead-note\"><b>{esc(common.ONE_OPINION)}</b> Look for concrete examples and weigh them.</p></div>"
        "<div class=\"card\"><h2>The call, 10 to 15 minutes</h2><table style=\"table-layout:fixed\"><colgroup><col style=\"width:150px\">"
        "<col><col style=\"width:420px\"></colgroup><tr><th>Minutes</th><th>Ask</th><th>Listen for</th></tr>"
        f"{guide_html}</table><p class=\"note\">When an answer is an adjective, ask once: \"Can you give me an example?\" "
        "or \"What happened next?\" Then let them talk. If there is time: " + esc(" ".join(f'"{q}"' for q in IF_TIME)) + "</p></div>"
        "<div class=\"card\"><h2>Still open after the interviews and the work sample</h2><table style=\"table-layout:fixed\">"
        "<colgroup><col style=\"width:60px\"><col><col style=\"width:520px\"><col style=\"width:300px\"></colgroup>"
        f"<tr><th>#</th><th>Question for the referee</th><th>Why it is still open</th><th>Source</th></tr>{open_html}</table></div>"
        f"{cand_html}"
        "<div class=\"card\"><h2>After the call</h2><p>Notes the same day in <code>out/references/" + esc(slug) +
        "-notes-&lt;n&gt;.md</code>: every answer as <b>Concrete example</b> / <b>Vague opinion</b> / <b>Follow-up</b>. "
        "Nothing about family, health, age, origin, religion or relationship status. Do not share a referee's words with the candidate; "
        "if the candidate asks for their data under privacy law, follow your law.</p></div>"
        "</main>")
    page = common.page(f"Reference call guide: {name}", f"{common.role(root)} · {slug}-call-sheet.md · written {written}", body, demo)
    common.write(refdir / f"{slug}-call-sheet.html", page)
    print(f"  {slug}: {len(refs)} referee(s), {len(open_ref)} open question(s) for the referee, {len(open_cand)} for the candidate.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="write a 10 to 15 minute reference call guide per finalist")
    ap.add_argument("slugs", nargs="*", help="candidate slugs; default: every <slug>-referees.md in out/references/")
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    ap.add_argument("--date", default=None, help="the date to print as written (default: today.txt, else today)")
    a = ap.parse_args()
    root = common.find_root(a.root)
    written = common.project_today(root, a.date)[0].isoformat()
    demo = common.is_demo(root)
    refdir = root / "out" / "references"
    slugs = a.slugs or sorted(p.name[:-len("-referees.md")] for p in refdir.glob("*-referees.md"))
    if not slugs:
        sys.exit("no finalists: pass a slug (one or two finalists, after the work sample), "
                 "or add out/references/<slug>-referees.md from templates/referees.md")
    if len(slugs) > 2:
        print(f"note: {len(slugs)} finalists. References are for the one or two you are about to make an offer to.")
    codes = [build(root, s, demo, written) for s in slugs]
    sys.exit(1 if any(codes) else 0)


if __name__ == "__main__":
    main()
