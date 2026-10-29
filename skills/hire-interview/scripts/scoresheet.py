#!/usr/bin/env python3
"""Your score first: the gate between your scoring sheet and Claude's analysis. Standard library only.

Usage (from your hiring/ folder or the folder above it):
  python3 <skill>/scripts/scoresheet.py              every candidate folder in out/interviews/
  python3 <skill>/scripts/scoresheet.py <slug> ...   one or more candidates
  options: --root PATH (the hiring folder), --now "YYYY-MM-DD HH:MM" (the time to record). Without --now the date
  comes from today.txt in the hiring folder when it exists, like every other script, else from the computer clock.

For each candidate, in out/interviews/<slug>/:
  1. FOUNDER_SCORES.md is your sheet. If it does not exist, it is created from templates/founder-scores.md
     with the six question titles from prep.json, and the script stops: fill it first.
  2. Every row needs a score (1 to 5, or "not asked") and, when scored, one line of evidence. Until then the
     script refuses, names the missing rows and exits 1. CANDIDATE_DEBRIEF.md is not created, so there is
     no analysis to read before your own score exists.
  3. When the sheet is complete, a fingerprint of it is saved in scores-saved.json, and CANDIDATE_DEBRIEF.md
     is created from templates/debrief.md: your sheet copied in first, a table for Claude's analysis with your
     scores in the last column, and the speaker check from stats.json (each flagged line starts as UNVERIFIED).
  4. On every later run your sheet is copied in again. If it changed after it was saved, the change is
     written into the debrief under "Score changes after the analysis". Changing a score is allowed; it is
     never silent.
  5. When Claude's column is filled, both totals are printed and every row where the two differ by two
     points or more is named.

A question that was not asked is unknown, not the candidate's weakness: it is left out of both totals, and
the total says on how many questions it rests. Scores organise evidence; they are not validated predictions.
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

TPL_SHEET = os.path.join(HERE, "..", "templates", "founder-scores.md")
TPL_DEBRIEF = os.path.join(HERE, "..", "templates", "debrief.md")
ROW = re.compile(r"^\|\s*(\d+)\s*\|(.*)\|\s*$")
MARK = {k: (f"<!-- {k}:start -->", f"<!-- {k}:end -->") for k in ("founder", "speaker", "changes")}
SHEET_LINE = re.compile(r"^- Your sheet: .*$", re.M)


def cells(line):
    m = ROW.match(line.strip())
    if not m:
        return None
    return [m.group(1)] + [c.strip() for c in m.group(2).split("|")]


def section_lines(text, heading_re):
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(heading_re, l, re.I)), None)
    if start is None:
        return None
    out = []
    for l in lines[start + 1:]:
        if l.startswith("## "):
            break
        out.append(l)
    return out


def parse_score(raw):
    r = raw.strip().strip("*").strip().lower()
    if re.fullmatch(r"[1-5]", r):
        return int(r)
    if r.startswith("not asked"):
        return "not asked"
    return None


def read_sheet(path):
    """Rows {n, question, score, evidence} under '## Your scoring sheet'. None when there is no such section."""
    text = open(path, encoding="utf-8").read()
    body = section_lines(text, r"^##\s.*scoring sheet")
    if body is None:
        return None
    rows = []
    for l in body:
        c = cells(l)
        if c and len(c) >= 4:
            rows.append({"n": int(c[0]), "question": c[1], "score": parse_score(c[2]), "raw": c[2],
                         "evidence": "" if common.is_placeholder(c[3]) else c[3]})
    return rows


def read_claude(path):
    """Rows of the table in '## 2. Claude's analysis': {n, question, score, evidence}."""
    if not os.path.exists(path):
        return None
    body = section_lines(open(path, encoding="utf-8").read(), r"^##\s.*claude's analysis")
    if body is None:
        return None
    rows = []
    for l in body:
        c = cells(l)
        if c and len(c) >= 4:
            rows.append({"n": int(c[0]), "question": c[1], "score": parse_score(c[2]), "raw": c[2],
                         "evidence": "" if common.is_placeholder(c[3]) else c[3]})
    return rows


def missing_rows(rows):
    out = []
    for r in rows:
        if r["score"] is None:
            out.append(f"row {r['n']} has no score")
        elif r["score"] != "not asked" and not r["evidence"]:
            out.append(f"row {r['n']} has a score but no line of evidence")
    return out


def total(rows):
    """{'sum', 'max', 'asked', 'of', 'text'}; questions not asked are left out."""
    scored = [r["score"] for r in rows if isinstance(r["score"], int)]
    s = sum(scored)
    n = len(scored)
    avg = round(s / n, 1) if n else None
    text = (f"{s} of {5 * n} on the {n} question{'s' if n != 1 else ''} asked"
            + (f" ({len(rows) - n} not asked)" if len(rows) - n else "") + f", {avg:.1f} a question") if n else "no question asked"
    return {"sum": s, "max": 5 * n, "asked": n, "of": len(rows), "avg": avg, "text": text}


def fingerprint(rows):
    norm = "\n".join(f"{r['n']}|{r['raw'].strip().lower()}|{r['evidence'].strip()}" for r in rows)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]


def founder_block(sheet_path, rows):
    text = open(sheet_path, encoding="utf-8").read()
    written = re.search(r"^- Written:\s*(.+)$", text, re.M)
    t = total(rows)
    out = ["Copied from `FOUNDER_SCORES.md` by `scoresheet.py`. Written " +
           (written.group(1).strip() if written else "at an unknown time") + ".", "",
           "| # | Question | Your score | Your one line of evidence |", "|---|---|---|---|"]
    out += [f"| {r['n']} | {r['question']} | {r['raw'] or '?'} | {r['evidence'] or ('not asked' if r['score'] == 'not asked' else '')} |"
            for r in rows]
    out += ["", f"Your total: **{t['text']}**."]
    return "\n".join(out)


def speaker_block(root, slug, now):
    p = os.path.join(common.slug_dir(root, slug), "stats.json")
    if not os.path.exists(p):
        return "_No stats.json yet. Run `stats.py` first; it checks the transcript for short lines with the wrong label._"
    flagged = json.load(open(p, encoding="utf-8")).get("speaker_check", [])
    if not flagged:
        return ("`stats.py` flagged no line in this transcript. Short lines can still carry the wrong label, "
                "so read the lines around any quote before you rely on it.")
    parts = []
    for s in flagged:
        ctx = "\n".join("> " + c for c in s.get("context", [f"[{s['time']}] {s['label']}: {s['text']}"]))
        parts.append(
            f"### [{s['time']}] \"{s['text']}\"\n\n"
            f"The transcript as it is (the file is never edited):\n\n{ctx}\n\n"
            f"Why it is disputed: {s['why']}.\n\n"
            "**Status: UNVERIFIED until checked against the recording.** Not used as evidence for either side. "
            "Your memory can say where to look in the recording; it does not change the evidence.\n\n"
            "| Step | Date | Status | What happened |\n|---|---|---|---|\n"
            f"| 1 | {now[:10]} | UNVERIFIED | Flagged by `stats.py`. Not used as evidence until a person listens to the recording. |\n\n"
            "Audit note: [empty until a person checks the recording. Then: who listened, which minutes, what the "
            "recording shows, and the date. If the recording is unclear or already deleted, set the status to "
            "UNRESOLVED and leave the quote out.]")
    return "\n\n".join(parts)


def replace_block(text, key, body):
    a, b = MARK[key]
    if a in text and b in text:
        return re.sub(re.escape(a) + r".*?" + re.escape(b), lambda _: f"{a}\n{body}\n{b}", text, flags=re.S)
    return text


def block_body(text, key):
    a, b = MARK[key]
    m = re.search(re.escape(a) + r"\n?(.*?)\n?" + re.escape(b), text, re.S)
    return m.group(1) if m else ""


def create_sheet(root, slug, path):
    prep = common.load_prep(root)
    c = common.prep_candidate(prep, slug) or {}
    qs = common.core_questions(prep, slug)
    titles = [q.get("title", "") for q in qs] or [f"Question {i}" for i in range(1, 7)]
    rows = "\n".join(f"| {i} | {t} | | |" for i, t in enumerate(titles, 1))
    when = f"{c.get('day', '')}, {c.get('time', '')} {(prep or {}).get('timezone', '')}".strip(", ") if c else "[day and time]"
    text = (open(TPL_SHEET, encoding="utf-8").read().replace("{name}", c.get("name", slug.replace("-", " ").title()))
            .replace("{when}", when).replace("{interviewer}", (prep or {}).get("interviewer", "[you]")).replace("{rows}", rows))
    if common.is_demo(root):
        text = text.replace("<!-- demo -->", "FICTIONAL DEMO. Invented people and an invented call.")
    common.write(path, text)


def create_debrief(root, slug, path, rows, saved, now):
    prep = common.load_prep(root)
    c = common.prep_candidate(prep, slug) or {}
    st = os.path.join(common.slug_dir(root, slug), "stats.json")
    sj = json.load(open(st, encoding="utf-8")) if os.path.exists(st) else {}
    minutes = sj.get("minutes", "?")
    est = (f" Minutes marked ~ are estimates ({sj['estimated_times']} of {sj.get('lines', '?')} lines): a quote with a ~ minute "
           "is approximate, so check the recording before you rely on its exact minute.") if sj.get("estimated_times") else ""
    when = (f"{c.get('day', '')}, {c.get('time', '')} {(prep or {}).get('timezone', '')}, call {c.get('call', '?')} of "
            f"{len((prep or {}).get('candidates', [])) or '?'}") if c else "[day and time]"
    claude_rows = "\n".join(f"| {r['n']} | {r['question']} | | | {r['raw']} |" for r in rows)
    text = open(TPL_DEBRIEF, encoding="utf-8").read()
    for k, v in (("{name}", c.get("name", slug.replace("-", " ").title())), ("{when}", when), ("{slug}", slug),
                 ("{minutes}", str(minutes)), ("{estimated}", est), ("{sheet_line}", sheet_line(saved)),
                 ("{founder}", founder_block(os.path.join(common.slug_dir(root, slug), "FOUNDER_SCORES.md"), rows)),
                 ("{score_note}", common.SCORE_NOTE), ("{claude_rows}", claude_rows),
                 ("{speaker}", speaker_block(root, slug, now))):
        text = text.replace(k, v)
    if common.is_demo(root):
        text = text.replace("<!-- demo -->", "FICTIONAL DEMO. Invented people and an invented call.")
    common.write(path, text)


def sheet_line(saved):
    return (f"saved {saved['first_saved']}, fingerprint {saved['fingerprint']}. "
            "Claude's analysis below was written after this.")


def refresh_debrief(root, slug, path, rows, saved, changed):
    text = open(path, encoding="utf-8").read()
    text = replace_block(text, "founder", founder_block(os.path.join(common.slug_dir(root, slug), "FOUNDER_SCORES.md"), rows))
    if changed:
        body = block_body(text, "changes")
        if body.strip().startswith("None."):
            body = ""
        body = (body.rstrip() + "\n" if body.strip() else "") + f"- {changed}"
        text = replace_block(text, "changes", body.strip())
        text = SHEET_LINE.sub(lambda _: "- Your sheet: " + sheet_line(saved) + " Changed afterwards: see section 7.", text, count=1)
    # keep the "Your score" column of Claude's table in step with the sheet
    by_n = {r["n"]: r["raw"] for r in rows}
    out, in_claude = [], False
    for l in text.splitlines():
        if l.startswith("## "):
            in_claude = bool(re.match(r"^##\s.*claude's analysis", l, re.I))
        c = cells(l) if in_claude else None
        if c and len(c) >= 5 and int(c[0]) in by_n:
            c[4] = by_n[int(c[0])]
            l = "| " + " | ".join(c[:5]) + " |"
        out.append(l)
    text = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    common.no_dashes(text, path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"refreshed {os.path.normpath(path)}")


def run(root, slug, now):
    d = common.slug_dir(root, slug)
    sheet = os.path.join(d, "FOUNDER_SCORES.md")
    if not os.path.exists(sheet):
        create_sheet(root, slug, sheet)
        print(f"  {slug}: fill your scores in FOUNDER_SCORES.md first. Claude's analysis stays closed until then.")
        return 1
    rows = read_sheet(sheet)
    if not rows:
        print(f"  {slug}: FOUNDER_SCORES.md has no '## Your scoring sheet' table. Refused.")
        return 1
    gaps = missing_rows(rows)
    if gaps:
        print(f"  {slug}: refused, your sheet is not complete: " + "; ".join(gaps) +
              ". Claude's analysis stays closed until every row has your score.")
        return 1
    fp = fingerprint(rows)
    saved_path = os.path.join(d, "scores-saved.json")
    saved = json.load(open(saved_path, encoding="utf-8")) if os.path.exists(saved_path) else None
    changed = None
    if saved is None:
        saved = {"first_saved": now, "fingerprint": fp, "history": [{"fingerprint": fp, "checked": now,
                 "rows": {str(r["n"]): r["raw"] for r in rows}}]}
        print(f"  {slug}: your sheet is complete. Saved fingerprint {fp} at {now}.")
    elif saved["history"][-1]["fingerprint"] != fp:
        old = saved["history"][-1]["rows"]
        diffs = [f"row {r['n']}: {old.get(str(r['n']), '?')} to {r['raw']}" for r in rows if old.get(str(r["n"])) != r["raw"]]
        changed = (f"{now}: your sheet changed after it was saved (fingerprint {saved['history'][-1]['fingerprint']} "
                   f"to {fp}). " + ("; ".join(diffs) if diffs else "evidence lines edited, scores the same") + ".")
        saved["history"].append({"fingerprint": fp, "checked": now, "rows": {str(r["n"]): r["raw"] for r in rows}})
        print(f"  {slug}: {changed} Recorded in the debrief, section 7.")
    common.write(saved_path, json.dumps(saved, indent=2) + "\n")
    debrief = os.path.join(d, "CANDIDATE_DEBRIEF.md")
    common.warn_strays(d, slug)
    if not os.path.exists(debrief):
        create_debrief(root, slug, debrief, rows, saved, now)
        print(f"  {slug}: CANDIDATE_DEBRIEF.md is open for Claude's analysis now.")
    else:
        refresh_debrief(root, slug, debrief, rows, saved, changed)
    t = total(rows)
    print(f"  {slug}: your total {t['text']}.")
    cl = read_claude(debrief)
    if cl and all(r["score"] is not None for r in cl) and any(r["evidence"] for r in cl):
        ct = total(cl)
        print(f"  {slug}: Claude's total {ct['text']}.")
        by_n = {r["n"]: r["score"] for r in rows}
        far = [f"row {r['n']} (you {by_n.get(r['n'])}, Claude {r['score']})" for r in cl
               if isinstance(r["score"], int) and isinstance(by_n.get(r["n"]), int) and abs(r["score"] - by_n[r["n"]]) >= 2]
        print(f"  {slug}: differ by two points or more: " + (", ".join(far) if far else "none") + ".")
    else:
        print(f"  {slug}: Claude's analysis not written yet (section 2 of CANDIDATE_DEBRIEF.md).")
    return 0


def summary(root, slug):
    """For ledger.py: your rows and total, Claude's rows and total, the saved fingerprint."""
    d = common.slug_dir(root, slug)
    sheet = os.path.join(d, "FOUNDER_SCORES.md")
    rows = read_sheet(sheet) if os.path.exists(sheet) else None
    cl = read_claude(os.path.join(d, "CANDIDATE_DEBRIEF.md"))
    complete = bool(rows) and not missing_rows(rows)
    cl_ok = bool(cl) and all(r["score"] is not None for r in cl) and any(r["evidence"] for r in cl)
    return {"founder_rows": rows, "founder": total(rows) if complete else None,
            "claude_rows": cl if cl_ok else None, "claude": total(cl) if cl_ok else None}


def main():
    argv = sys.argv[1:]
    now = None
    if "--now" in argv:
        k = argv.index("--now")
        now = argv[k + 1]
        del argv[k:k + 2]
    root, args = common.root_from_argv(argv)
    now = common.project_now(root, now)
    slugs = [a for a in args if not a.startswith("--")]
    base = common.interviews_dir(root)
    tdir = os.path.join(base, "transcripts")
    known = {os.path.splitext(f)[0] for f in os.listdir(tdir) if f.endswith(".txt")} if os.path.isdir(tdir) else set()
    if os.path.isdir(base):
        known |= {n for n in os.listdir(base) if os.path.isfile(os.path.join(base, n, "FOUNDER_SCORES.md"))}
    for s in slugs:
        if s not in known:
            sys.exit(f"no interview named {s!r}: no transcripts/{s}.txt and no {s}/FOUNDER_SCORES.md in {base}")
    if not slugs:
        slugs = sorted(known)
        if not slugs:
            sys.exit(f"no interviews found in {base}")
    codes = [run(root, s, now) for s in slugs]
    sys.exit(1 if any(codes) else 0)


if __name__ == "__main__":
    main()
