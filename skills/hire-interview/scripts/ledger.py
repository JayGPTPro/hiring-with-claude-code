#!/usr/bin/env python3
"""The interview ledger: one page that grows after each call. Standard library only, no network.

Usage (from your hiring/ folder or the folder above it):
  python3 <skill>/scripts/ledger.py [--root PATH]

Reads every out/interviews/<slug>/ folder:
  stats.json             word share, core questions covered, blocks over 75%, long stretches (stats.py)
  FOUNDER_SCORES.md      your total; CANDIDATE_DEBRIEF.md for Claude's total (through scoresheet.py)
  CANDIDATE_DEBRIEF.md   "## Ledger row": strongest_evidence, open_question, next_step; the speaker check status
  INTERVIEWER_COACH.md   "## Ledger row": call, date, time, one_thing_title, one_thing, previous_improved,
                         missed_follow_ups; and "## Questions I covered", the checked count of questions asked
                         (stats.json's word match only when that table is missing)
Writes out/interviews/LEDGER.html with two tabs, Candidate evidence (LEDGER.html#candidates) and
My interviewing (LEDGER.html#me), and out/interviews/LEDGER.md with the same two tables. Calls are listed in
the order they happened. Numbers come from the files above, never typed by hand. When candidates were asked
different numbers of questions, each total gets its average per question asked. Every string is escaped.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402
import scoresheet  # noqa: E402
from common import esc  # noqa: E402


def ledger_row(path):
    if not os.path.exists(path):
        return {}
    text = open(path, encoding="utf-8").read()
    m = re.search(r"^## Ledger row\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    out = {}
    for line in (m.group(1).splitlines() if m else []):
        km = re.match(r"^\s*-\s*([a-z_0-9]+)\s*:\s*(.*?)\s*$", line)
        if km and not common.is_placeholder(km.group(2)):
            out[km.group(1)] = km.group(2)
    return out


def speaker_status(path):
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf-8").read()
    body = scoresheet.block_body(text, "speaker")
    out = []
    for m in re.finditer(r"^### \[(\d\d:\d\d)\].*?\*\*Status: ([A-Z]+)(?: on (\d{4}-\d\d-\d\d))?", body, re.M | re.S):
        out.append({"time": m.group(1), "status": m.group(2), "date": m.group(3) or ""})
    return out


def collect(root):
    base = common.interviews_dir(root)
    prep = common.load_prep(root) or {}
    order = {c["slug"]: c for c in prep.get("candidates", [])}
    slugs = [n for n in sorted(os.listdir(base)) if os.path.isdir(os.path.join(base, n)) and n != "transcripts"]
    calls = []
    for slug in slugs:
        d = os.path.join(base, slug)
        st_path = os.path.join(d, "stats.json")
        if not os.path.exists(st_path):
            print(f"skipped {slug}: no stats.json (run stats.py)")
            continue
        st = json.load(open(st_path, encoding="utf-8"))
        common.warn_strays(d, slug)
        coach = ledger_row(os.path.join(d, "INTERVIEWER_COACH.md"))
        cov = common.coach_coverage(os.path.join(d, "INTERVIEWER_COACH.md"))
        deb = ledger_row(os.path.join(d, "CANDIDATE_DEBRIEF.md"))
        sm = scoresheet.summary(root, slug)
        pc = order.get(slug, {})
        call = coach.get("call") or str(pc.get("call", ""))
        day = f"{pc['day']}, {pc.get('time', '')}" if pc.get("day") else ""
        calls.append({
            "slug": slug, "day": day, "name": coach.get("candidate") or pc.get("name") or slug.replace("-", " ").title(),
            "call": int(call) if call.isdigit() else 999,
            "when": " ".join(x for x in (coach.get("date") or pc.get("date", ""), coach.get("time") or pc.get("time", "")) if x),
            "share": st["word_share_interviewer"],
            "covered": sum(1 for q in cov if q["asked"] != "no") if cov else sum(1 for q in st.get("core", []) if q["asked"]),
            "of": (len(cov) if cov else len(st.get("core", []))) or 6,
            "partly": sum(1 for q in cov if q["asked"] == "partly") if cov else 0, "blocks": len(st.get("blocks_over_75", [])),
            "long": len(st.get("long_turns", [])), "cut": len(st.get("cut_off", [])),
            "missed": coach.get("missed_follow_ups", "?"),
            "one_title": coach.get("one_thing_title", ""), "one": coach.get("one_thing", "not written yet"),
            "prev": coach.get("previous_improved", ""),
            "founder": sm["founder"], "claude": sm["claude"],
            "strongest": deb.get("strongest_evidence", ""), "open": deb.get("open_question", ""),
            "next": deb.get("next_step", "not decided"),
            "speaker": speaker_status(os.path.join(d, "CANDIDATE_DEBRIEF.md")),
        })
    calls.sort(key=lambda c: (c["call"], c["when"]))
    return calls


def plural(n, one, many):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    return "" if n == 0 else f"{n} {one if n == 1 else many}"


def score_text(t, avg=False):
    if not t:
        return "not saved"
    return f"{t['sum']} of {t['max']}" + (f", {t['avg']:.1f} a question" if avg and t.get("avg") is not None else "")


def uneven(calls):
    """True when candidates were asked different numbers of questions: then the totals are not comparable."""
    return len({c[k]["asked"] for c in calls for k in ("founder", "claude") if c[k]}) > 1


def asked_text(c):
    return f"{c['covered']} of {c['of']}" + (f" ({c['partly']} partly)" if c["partly"] else "")


def speaker_text(c):
    if not c["speaker"]:
        return "no line flagged"
    return "; ".join(f"[{s['time']}] {s['status'].lower()}" + (f" {s['date']}" if s["date"] else "") for s in c["speaker"])


def html_page(calls, demo):
    avg = uneven(calls)
    cand_rows = ""
    for c in calls:
        asked = c["founder"]["asked"] if c["founder"] else "?"
        pill = "ok" if not c["speaker"] or all(s["status"] == "CORRECTED" for s in c["speaker"]) else "warn"
        spk = (f'<span class="pill {pill}" style="white-space:normal">speaker check: {esc(speaker_text(c))}</span>'
               if c["speaker"] else '<span class="note">speaker check: no line flagged</span>')
        cand_rows += (
            f'<tr><td><b>{esc(c["call"] if c["call"] != 999 else "")}</b></td>'
            f'<td><b>{esc(c["name"])}</b><br><span class="note">{esc(c["day"] or c["when"])}</span><br>{spk}</td>'
            f'<td><b>You: {esc(score_text(c["founder"], avg))}</b><br>Claude: {esc(score_text(c["claude"], avg))}'
            f'<br><span class="note">{esc(asked)} of {esc(c["of"])} questions asked</span></td>'
            f'<td>{esc(c["strongest"])}</td><td>{esc(c["open"])}</td><td>{esc(c["next"])}</td></tr>')
    me_rows = ""
    for i, c in enumerate(calls):
        prev_title = calls[i - 1]["one_title"] if i else ""
        hi = c["share"] >= 40
        flags = [plural(c["blocks"], "5-minute block over 75%", "5-minute blocks over 75%"),
                 plural(c["long"], "long stretch", "long stretches"),
                 plural(c["missed"], "missed follow-up", "missed follow-ups"),
                 plural(c["cut"], "answer cut off", "answers cut off")]
        flags = [f for f in flags if f] or ["nothing flagged"]
        me_rows += (
            f'<tr><td style="white-space:nowrap"><b style="font-size:25px">{esc(c["call"] if c["call"] != 999 else "?")}. {esc(c["name"])}</b>'
            f'<br><span class="note">{esc(c["day"] or c["when"])}</span></td>'
            f'<td style="white-space:nowrap"><b style="font-size:28px">{c["share"]:.1f}%</b> '
            f'<span style="display:inline-block;width:140px;vertical-align:middle">{common.bar(c["share"], hi)}</span>'
            f'<div style="margin-top:6px">{common.dots(c["covered"], c["of"])} <b>{esc(asked_text(c))}</b></div></td>'
            f'<td>{"<br>".join(esc(f) for f in flags)}</td>'
            f'<td><b>{esc(c["one_title"])}.</b> {esc(c["one"])}</td>'
            f'<td>{("<b>" + esc(prev_title) + ":</b> ") if prev_title else ""}{esc(c["prev"])}</td></tr>')
    first, rest = (calls[0], calls[1:]) if calls else (None, [])
    trend = ""
    if first and rest:
        lo, hi_ = min(c["share"] for c in rest), max(c["share"] for c in rest)
        cov = sorted({c["covered"] for c in rest})
        trend = (f'<p style="font-size:24px">Call 1: <b>{first["share"]:.1f}%</b> of the words were mine, '
                 f'<b>{first["covered"]} of {first["of"]}</b> questions asked. Calls 2 to {len(calls)}: '
                 f'<b>{lo:.1f}% to {hi_:.1f}%</b>, <b>{" or ".join(str(x) for x in cov)} of {first["of"]}</b>. '
                 'That shows attention to what was missed. It does not prove a great interviewer.</p>')
    body = (
        '<nav class="tabs"><a href="#candidates">Candidate evidence</a><a href="#me">My interviewing</a></nav><main>'
        '<section class="tab" id="t-candidates"><div class="card"><h2>Candidate evidence</h2>'
        f'<p class="note">Your score was saved before Claude\'s analysis; both are shown. A question not asked is unknown and left '
        f'out of the total, so read each total with the number of questions it rests on. '
        + ('Candidates were asked different numbers of questions, so compare the averages, not the totals. ' if avg else '')
        + f'{esc(common.SCORE_NOTE)} '
        'The next step is yours, not Claude\'s.</p>'
        '<table style="table-layout:fixed"><colgroup><col style="width:80px"><col style="width:300px"><col style="width:240px">'
        '<col><col style="width:300px"><col style="width:260px"></colgroup><tr><th>Call</th><th>Candidate</th><th>Scores</th><th>Strongest evidence</th><th>Still open</th><th>Next step (yours)</th></tr>'
        f'{cand_rows}</table></div></section>'
        '<section class="tab" id="t-me"><div class="card"><h2>My interviewing</h2>'
        f'<p class="note">{esc(common.WORD_SHARE_LABEL)}. Questions: the six planned questions, matched in the transcript by '
        '<code>stats.py</code>. The coach observes behaviour only: what I asked, skipped, cut short or said at length. '
        'It never reads the candidate\'s personality.</p>'
        f'{trend}<table style="table-layout:fixed"><colgroup><col style="width:260px"><col style="width:300px">'
        '<col style="width:250px"><col><col style="width:270px"></colgroup><tr><th>Call</th><th>Word share / questions</th><th>Flagged</th>'
        f'<th>One thing to improve next call</th><th>Last call\'s one thing</th></tr>{me_rows}</table></div></section>'
        '</main>')
    return common.page("Interview ledger", f"{len(calls)} call(s), in the order they happened. Rebuilt by ledger.py after each debrief.",
                       body, demo)


def md_page(calls, demo):
    avg = uneven(calls)
    out = ["# Interview ledger", ""]
    if demo:
        out += ["FICTIONAL DEMO. Invented people and invented calls.", ""]
    out += ["Rebuilt by `ledger.py` from the files in each `out/interviews/<slug>/` folder. The HTML version is `LEDGER.html`.", "",
            "## Candidate evidence", "",
            "Your score was saved before Claude's analysis. A question not asked is left out of the total. "
            + ("Candidates were asked different numbers of questions, so compare the averages, not the totals. " if avg else "")
            + common.SCORE_NOTE, "",
            "| Call | Candidate | You | Claude | Asked | Strongest evidence | Still open | Speaker check | Next step (yours) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for c in calls:
        cell = lambda s: str(s).replace("|", "/")
        out.append(f"| {c['call']} | {cell(c['name'])} | {score_text(c['founder'], avg)} | {score_text(c['claude'], avg)} | "
                   f"{c['founder']['asked'] if c['founder'] else '?'} of {c['of']} | {cell(c['strongest'])} | {cell(c['open'])} | "
                   f"{cell(speaker_text(c))} | {cell(c['next'])} |")
    out += ["", "## My interviewing", "", common.WORD_SHARE_LABEL + ".", "",
            "| Call | Candidate | Word share | Questions | Blocks over 75% | Long stretches | Missed follow-ups | One thing to improve | Last call's one thing improved? |",
            "|---|---|---|---|---|---|---|---|---|"]
    for c in calls:
        cell = lambda s: str(s).replace("|", "/")
        out.append(f"| {c['call']} | {cell(c['name'])} | {c['share']:.1f}% | {asked_text(c)} | {c['blocks']} | {c['long']} | "
                   f"{cell(c['missed'])} | **{cell(c['one_title'])}** {cell(c['one'])} | {cell(c['prev'])} |")
    rules = os.path.join(HERE, "..", "templates", "LEDGER.md")
    if os.path.exists(rules):
        text = open(rules, encoding="utf-8").read()
        text = re.sub(r"^`ledger.py` adds.*?\n", "", text, flags=re.M)
        out += ["", re.sub(r"\n{3,}", "\n\n", text.strip())]
    return "\n".join(out) + "\n"


def main():
    root, _ = common.root_from_argv(sys.argv[1:])
    base = common.interviews_dir(root)
    if not os.path.isdir(base):
        sys.exit(f"no folder {base}")
    calls = collect(root)
    if not calls:
        sys.exit("no interviews with stats.json yet. Run stats.py first.")
    demo = common.is_demo(root)
    common.write(os.path.join(base, "LEDGER.html"), html_page(calls, demo), "LEDGER.html")
    common.write(os.path.join(base, "LEDGER.md"), md_page(calls, demo), "LEDGER.md")
    print(f"  {len(calls)} call(s). Open LEDGER.html#candidates or LEDGER.html#me.")


if __name__ == "__main__":
    main()
