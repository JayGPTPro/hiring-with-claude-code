#!/usr/bin/env python3
"""Render the interview prep page. Standard library only, no network.

Usage (from your hiring/ folder or the folder above it):
  python3 <skill>/scripts/prep.py              reads out/interviews/prep.json
  python3 <skill>/scripts/prep.py path/to/prep.json
  add --root PATH to point at the hiring folder

Reads prep.json (written by Claude in prep mode, see SKILL.md and templates/prep.example.json) and
writes out/interviews/PREP.html next to it. The page has a Schedule tab and one tab per candidate.
PREP.html#<slug> opens a candidate's tab, PREP.html#schedule the schedule.

Also reads, per candidate, when the files exist:
  out/candidates/<slug>.md          the "## Evidence Map" table from hire-applications (Requirement | Claim |
                                    Evidence (quoted) | Missing | Question | Status). When prep.json leaves
                                    evidence, missing or questions out (or empty), they are filled from it.
  out/verification/<slug>.md        the claim check from claim_check.py ("## Summary", "## Questions for the call").
  out/evidence/<slug>.html          linked from the card when it exists.

Each candidate tab holds, in this order:
  - Evidence / Missing / Questions, from prep.json or the evidence map, and the claim-check questions;
  - the six core questions, each with "a 1 / a 3 / a 5 sounds like" anchors written before the call,
    question 6 being this candidate's tailored follow-up;
  - the practical-fit questions (work only);
  - the scoring sheet, your score first: a score and one line of evidence per question, kept in the
    browser, and a button that copies it as FOUNDER_SCORES.md. Claude's analysis is not on this page.

Every string from prep.json is escaped with html.escape; nothing is passed through as raw HTML. The
FICTIONAL DEMO badge shows when criteria.md says FICTIONAL DEMO. Prints what it wrote.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402
from common import esc  # noqa: E402

REQUIRED = ("core_questions", "candidates", "consent_line", "close", "practical_fit")
CAND_REQUIRED = ("slug", "name", "day", "time", "tailored")

SHEET_JS = r"""
(function(){
 function st(k,v){try{if(v===undefined)return localStorage.getItem(k);localStorage.setItem(k,v);}catch(e){return null;}}
 [].forEach.call(document.querySelectorAll('[data-k]'),function(el){var v=st(el.getAttribute('data-k'));if(v!==null&&v!==undefined)el.value=v;});
 document.addEventListener('input',function(e){var k=e.target.getAttribute&&e.target.getAttribute('data-k');if(k)st(k,e.target.value);});
 document.addEventListener('change',function(e){var k=e.target.getAttribute&&e.target.getAttribute('data-k');if(k)st(k,e.target.value);});
 function cell(s){return String(s||'').replace(/\|/g,'/').replace(/\s+/g,' ').trim();}
 document.addEventListener('click',function(e){
  var b=e.target.closest&&e.target.closest('[data-copy]');if(!b)return;
  var sec=b.closest('section');var name=sec.getAttribute('data-name');var when=sec.getAttribute('data-when');
  var t='# Your scoring sheet: '+name+'\n\n- Interview: '+when+'\n- Interviewer: '+(sec.getAttribute('data-interviewer')||'')+'\n- Written: '+new Date().toLocaleString()+', before reading any analysis\n\n## Your scoring sheet\n\n| # | Question | Your score | One line of evidence (what they said or showed, with the minute) |\n|---|---|---|---|\n';
  [].forEach.call(sec.querySelectorAll('tr[data-row]'),function(tr){
   t+='| '+tr.getAttribute('data-row')+' | '+cell(tr.getAttribute('data-title'))+' | '+cell(tr.querySelector('select').value)+' | '+cell(tr.querySelector('input').value)+' |\n';});
  if(navigator.clipboard)navigator.clipboard.writeText(t);
  var o=b.textContent;b.textContent='Copied. Paste it into out/interviews/'+sec.getAttribute('data-slug')+'/FOUNDER_SCORES.md';setTimeout(function(){b.textContent=o;},2500);
 });
})();
"""


def ul(items):
    return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>" if items else "<p class=\"mute\">none</p>"


def anchors_html(a):
    a = a or {}
    return ('<div class="anch">' + "".join(
        f'<div><b>A {k} sounds like</b>{esc(a.get(k, "not written yet"))}</div>' for k in ("1", "3", "5")) + "</div>")


def question_html(q, ask, why=None):
    setup = f'<p class="note">Set up: {esc(q["setup"])}</p>' if q.get("setup") else ""
    why_html = f'<p class="note">Why this one: {esc(why)}</p>' if why else ""
    return (f'<div class="q"><span class="n">{esc(q.get("n", ""))}</span><span class="t">{esc(q.get("title", ""))}</span>'
            f'<p class="ask">"{esc(ask)}"</p>{setup}{why_html}{anchors_html(q.get("anchors"))}</div>')


def when(c, tz):
    return f'{c["day"]}, {c["time"]} {tz}'


def schedule_tab(p, tz, demo):
    rows = "".join(
        f'<tr><td><b>{esc(c.get("call", ""))}</b></td><td><b>{esc(c["day"])}, {esc(c["time"])}</b></td>'
        f'<td>{esc(c.get("their_time", ""))}</td><td><a href="#{esc(c["slug"])}">{esc(c["name"])}</a></td>'
        f'<td>{esc(c.get("ask", ""))}</td><td>{esc((c.get("tailored") or {}).get("ask", ""))}</td></tr>'
        for c in p["candidates"])
    order = "".join(f'<li>{esc(q.get("title", ""))}</li>' for q in p["core_questions"])
    order += f'<li>{esc((p.get("tailored_question") or {}).get("title", "One tailored follow-up"))}, a different one for each person</li>'
    lesson = p.get("one_thing") or "First round of calls: no lesson from the ledger yet. After each call, INTERVIEWER_COACH.md gives one."
    return (
        '<section class="tab" id="t-schedule">'
        f'<div class="card"><h2>Schedule ({esc(tz)})</h2><table><tr><th>Call</th><th>When</th><th>Their time</th>'
        f'<th>Candidate</th><th>Ask</th><th>Their tailored follow-up</th></tr>{rows}</table></div>'
        '<div class="cols2">'
        f'<div class="card"><h2>Every call, the same way</h2><h3>Consent first</h3><blockquote>{esc(p["consent_line"])}</blockquote>'
        f'<p>{esc(p.get("warmup", ""))}</p><h3>The six questions</h3><ol>{order}</ol>'
        f'<h3>The close, the same for everyone</h3><blockquote>{esc(p["close"])}</blockquote></div>'
        f'<div class="card"><h2>Before every call</h2>{ul(p.get("checklist", []))}'
        f'<div class="box soft"><b>Your one thing to improve:</b> {esc(lesson)}</div>'
        f'<h2 style="margin-top:26px">Your score first</h2><p>Score each answer 1 to 5 against the anchors, with one line of evidence, '
        'before you read any analysis. Claude\'s analysis is written only after <code>scoresheet.py</code> has saved your sheet, '
        'so you compare two views instead of letting one become the other.</p>'
        f'<p class="note">{esc(common.SCORE_NOTE)}</p></div></div></section>')


def candidate_tab(p, c, tz, extra=None):
    extra = extra or {}
    ev = "".join(f'<li>"{esc(e.get("text", ""))}"<span class="src">({esc(e.get("source", ""))})</span></li>'
                 for e in c["evidence"]) or "<li class=\"mute\">no evidence quoted yet</li>"
    chips = [f'Ask: {c.get("ask", "")}' + (f' ({c["budget_fit"]})' if c.get("budget_fit") else ""),
             c.get("availability", ""), f'Source: {c.get("source", "")}' if c.get("source") else "",
             f'Strongest, in their words: {c["strongest"]}' if c.get("strongest") else ""]
    chips_html = "".join(f'<span class="pill grey">{esc(x)}</span>' for x in chips if x)
    claims = ""
    cc = extra.get("claim_check")
    if cc:
        claims = (f'<div class="box soft"><b>Claim check</b> <span class="note">({esc(cc["file"])})</span>'
                      + (f'<p>{esc(cc["summary"])}</p>' if cc["summary"] else "")
                      + (ul(cc["questions"]) if cc["questions"] else '<p class="note">No questions from the claim check.</p>')
                      + "</div>")
    links = []
    if extra.get("filled"):
        links.append(f'{esc(", ".join(extra["filled"]).capitalize())} filled from the Evidence Map in out/candidates/{esc(c["slug"])}.md.')
    if extra.get("evidence_page"):
        links.append(f'<a href="../evidence/{esc(c["slug"])}.html">Open the Evidence Map page</a>')
    links_html = f'<p class="note">{" ".join(links)}</p>' if links else ""
    t = c.get("tailored") or {}
    q6 = dict(p.get("tailored_question") or {"title": "One tailored follow-up"})
    q6["n"] = 6
    qs = "".join(question_html(q, q.get("ask", "")) for q in p["core_questions"])
    qs += question_html(q6, t.get("ask", "[no tailored follow-up written]"), t.get("why"))
    practical = ul(p["practical_fit"]) + (f'<h3>For {esc(c.get("first", c["name"]))}</h3>' + ul(c.get("practical", [])) if c.get("practical") else "")
    practical += f'<div class="box warm">{esc(p.get("never_ask", "Work questions only."))}</div>'
    titles = [q.get("title", "") for q in p["core_questions"]] + [q6.get("title", "One tailored follow-up")]
    opts = '<option value="">?</option>' + "".join(f"<option>{n}</option>" for n in (1, 2, 3, 4, 5)) + "<option>not asked</option>"
    sheet = "".join(
        f'<tr data-row="{i}" data-title="{esc(title)}"><td><b>{i}</b></td><td>{esc(title)}</td>'
        f'<td><select data-k="prep_score_{esc(c["slug"])}_{i}">{opts}</select></td>'
        f'<td><input type="text" data-k="prep_ev_{esc(c["slug"])}_{i}" placeholder="what they said or showed, with the minute"></td></tr>'
        for i, title in enumerate(titles, 1))
    head = f'Call {c.get("call", "")} · {when(c, tz)}' + (f' · {c["their_time"]}' if c.get("their_time") else "")
    return (
        f'<section class="tab" id="t-{esc(c["slug"])}" data-slug="{esc(c["slug"])}" data-name="{esc(c["name"])}" data-when="{esc(head)}" '
        f'data-interviewer="{esc(p.get("interviewer", ""))}">'
        f'<div class="card"><h2 style="font-size:40px;margin-bottom:6px">{esc(c["name"])}</h2>'
        f'<p style="font-size:24px;margin:4px 0 12px">{esc(head)} · {esc(c.get("location", ""))}</p>{chips_html}</div>'
        '<div class="card"><h2>Evidence / Missing / Questions</h2><div class="cols3">'
        f'<div class="col ev"><h3>Evidence</h3><p class="note">What they have actually shown, quoted.</p><ul>{ev}</ul></div>'
        f'<div class="col mi"><h3>Missing</h3><p class="note">What is not shown yet. Unknown, not weak.</p>{ul(c["missing"])}</div>'
        f'<div class="col qu"><h3>Questions</h3><p class="note">One question per gap, asked neutrally.</p>{ul(c["questions"])}</div>'
        f'</div>{links_html}{claims}</div>'
        '<div class="card"><h2>The six core questions, with anchors written before the call</h2>'
        '<p class="note">The same five questions for everyone, plus one tailored follow-up. Normal follow-ups are fine. '
        'A 2 and a 4 sit between the anchors.</p>'
        f'{qs}</div>'
        f'<div class="card"><h2>Practical fit (work only)</h2>{practical}</div>'
        '<div class="card"><h2>Your scoring sheet: your score first</h2>'
        '<p>Write your score and one line of evidence for each question before you read Claude\'s analysis. '
        'A question you did not ask is "not asked": unknown, not the candidate\'s weakness.</p>'
        '<table style="table-layout:fixed"><colgroup><col style="width:60px"><col style="width:400px"><col style="width:190px"><col></colgroup>'
        '<tr><th>#</th><th>Question</th><th>Your score</th><th>One line of evidence</th></tr>'
        f'{sheet}</table>'
        '<p style="margin-top:16px"><button class="btn" data-copy="1">Copy my sheet as FOUNDER_SCORES.md</button></p>'
        '<p class="note">Claude\'s analysis is not on this page. <code>scoresheet.py</code> creates CANDIDATE_DEBRIEF.md for it only '
        'after every row of your sheet has a score and a line of evidence. What you type here stays in this browser.</p></div>'
        '</section>')


def main():
    root, args = common.root_from_argv(sys.argv[1:])
    src = args[0] if args else os.path.join(common.interviews_dir(root), "prep.json")
    if not os.path.exists(src):
        sys.exit(f"not found: {src}. Write prep.json first (see templates/prep.example.json).")
    with open(src, encoding="utf-8") as f:
        p = json.load(f)
    for k in REQUIRED:
        if k not in p:
            sys.exit(f"prep.json is missing '{k}'")
    notes = []
    if len(p["core_questions"]) != 5:
        notes.append(f"core_questions has {len(p['core_questions'])} entries; the method uses five plus one tailored follow-up")
    for q in p["core_questions"]:
        a = q.get("anchors") or {}
        if not all(k in a for k in ("1", "3", "5")):
            notes.append(f"question {q.get('n')} has no full 1 / 3 / 5 anchors")
    extras = {}
    for c in p["candidates"]:
        for k in CAND_REQUIRED:
            if k not in c:
                sys.exit(f"candidate {c.get('name', '?')} is missing '{k}'")
        if not (c.get("tailored") or {}).get("ask"):
            notes.append(f"{c['name']}: no tailored follow-up (question 6)")
        ex = {"claim_check": common.claim_check(root, c["slug"]), "filled": [],
              "evidence_page": os.path.isfile(os.path.join(root, "out", "evidence", f"{c['slug']}.html"))}
        if not all(c.get(k) for k in ("evidence", "missing", "questions")):
            em = common.prep_from_evidence_map(common.evidence_map(root, c["slug"]))
            for k in ("evidence", "missing", "questions"):
                if not c.get(k) and em[k]:
                    c[k] = em[k]
                    ex["filled"].append(k)
                c.setdefault(k, [])
            if ex["filled"]:
                notes.append(f"{c['name']}: {', '.join(ex['filled'])} filled from the Evidence Map in out/candidates/{c['slug']}.md")
        extras[c["slug"]] = ex
    tz = p.get("timezone", "")
    demo = common.is_demo(root)
    nav = '<nav class="tabs"><a href="#schedule">Schedule</a>' + "".join(
        f'<a href="#{esc(c["slug"])}">{esc(c.get("first", c["name"]))}<small>call {esc(c.get("call", ""))}</small></a>'
        for c in p["candidates"]) + "</nav>"
    body = nav + "<main>" + schedule_tab(p, tz, demo) + "".join(candidate_tab(p, c, tz, extras[c["slug"]])
                                                                for c in p["candidates"]) + "</main>"
    html_page = common.page(p.get("title", "Interview prep"), p.get("subtitle", ""), body, demo, SHEET_JS)
    out = os.path.join(os.path.dirname(os.path.abspath(src)), "PREP.html")
    common.write(out, html_page, "PREP.html")
    print(f"  {len(p['candidates'])} candidate tab(s), FICTIONAL DEMO badge {'on' if demo else 'off'}. "
          "Open PREP.html#schedule or PREP.html#<slug>.")
    for n in notes:
        print("note: " + n)


if __name__ == "__main__":
    main()
