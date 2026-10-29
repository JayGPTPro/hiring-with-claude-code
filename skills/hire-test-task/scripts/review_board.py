"""Builds challenge/REVIEW.html (the founder's board for the test task) and challenge/walkthroughs/<slug>.md.

The page, top to bottom:
  1. The submissions, one card each as Submission A, B, C: what came, when, Claude's summary,
     the questions asked before submitting and the assumptions stated.
  2. Part 1, the shared task: the four questions (understood the goal / relevant work / reasoning
     visible / would I use it). Per finalist, YOUR rating first, then Claude's note. Claude's note
     for a part stays hidden until your four ratings for that part are in, in review.json or typed
     on the page.
  3. Part 2, the specialist part: the same four questions, judged against each track's own
     requirements. A listings score and a reporting score are not directly comparable.
  4. The walkthrough: one decision from each submission, highlighted, and three short questions
     (walk me through this one choice / what trade-off did you make / what would you change with
     another hour), with the notes from the call.
  5. Per finalist: the full submission text, Claude's read, your notes, the decision.
There is no click column and no click count anywhere. A personal link, if you use one, is optional
and is never read as motivation.

Names stay hidden (Submission A, B, C) until you have rated every part of every finalist.

Reads:
  challenge/config.json             finalists, fee, days, due, expected_hours
  challenge/SCORING-GUIDE.md        the guide you rate against; the page warns when it changed after the lock
  challenge/submissions/            what each finalist sent, under any name (a file with their slug or name)
  challenge/review.json             per slug: summary, what_came, received, track, clarifying_questions,
                                    assumptions_stated, founder {rated_at, core, specialist},
                                    claude {written_at, core, specialist, read}, walkthrough, decision
                                    (templates/review.example.json)
Writes:
  challenge/REVIEW.html, challenge/walkthroughs/<slug>.md (the call sheet and notes, one per finalist)

Usage: run from your hiring/ folder, or from the folder above it:  python3 review_board.py  (--root path/to/hiring overrides)
"""
import argparse
import hashlib
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import (esc, find_root, load_json, demo_label, no_dashes, page, letter, words, js_json, task_terms,  # noqa: E402
                     QUESTIONS, ANCHORS, rating, part_complete, parts_for, track_of, names_visible,
                     submission_files, submitted)

WALK_QUESTIONS = ["Walk me through this one choice.", "What trade-off did you make?",
                  "What would you change with another hour?"]
PART_TITLE = {"core": "Part 1, the shared task", "specialist": "Part 2, the specialist part"}

CSS = """
.subs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
.subs .card{margin:0;display:flex;flex-direction:column}
.big{display:flex;align-items:center;gap:14px;margin-bottom:8px}
.big .L{flex:none;width:58px;height:58px;border-radius:14px;background:var(--ink);color:#fff;font-size:34px;font-weight:800;text-align:center;line-height:58px}
.big .t{font-size:24px;font-weight:700;line-height:1.2}.big .t span{display:block;font-size:20px;font-weight:500;color:var(--mute)}
.kv{font-size:20px;margin:4px 0}.kv b{color:var(--mute);font-weight:600}
.summary{font-size:21px;margin:10px 0 8px}
table.rub{table-layout:fixed;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
table.rub col.q{width:22%}
table.rub thead th{background:var(--ink);color:#fff;font-size:22px}
table.rub thead th span{display:block;font-size:19px;font-weight:500;opacity:.85}
td.qn b{display:block;font-size:21px}
td.qn span{display:block;font-size:20px;color:var(--mute);line-height:1.35;margin-top:4px}
.you{border-left:6px solid var(--ink);padding:4px 10px;margin-bottom:8px}
.cl{border-left:6px solid var(--acc);background:var(--acc-bg);padding:6px 10px;border-radius:0 6px 6px 0}
.lab{font-size:19px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--mute);margin-right:6px}
.cl .lab{color:var(--acc)}
.sc{font-size:24px;font-weight:800}
.line{font-size:20px;line-height:1.38;margin-top:2px}
.cl .line{font-size:20px}
.wait{font-size:20px;color:var(--mute);font-style:italic;border-left:6px dashed var(--line);padding:6px 10px}
.diff{display:inline-block;font-size:19px;font-weight:700;color:var(--warn);margin-left:6px}
tr.tot td{background:var(--soft);font-weight:700}
.walks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
.walks .card{margin:0}
.hl{background:#fff3b0;border-left:6px solid #e0b400;padding:10px 12px;border-radius:0 6px 6px 0;font-size:20px;margin:8px 0 12px}
.hl b{display:block;font-size:18px;text-transform:uppercase;letter-spacing:.05em;color:#7a5d00}
ol.wq{margin:0 0 8px;padding-left:28px;font-size:21px}ol.wq li{margin:6px 0}
ol.wq li .ans{display:block;font-size:20px;color:var(--ink);margin-top:2px;padding-left:2px;border-left:3px solid var(--line);padding-left:8px}
.subtext{white-space:pre-wrap;font-size:20px;background:var(--soft);border-radius:10px;padding:14px;max-height:none}
.internal{font-size:20px;background:var(--warn-bg);border-left:6px solid var(--warn);padding:8px 12px;border-radius:4px;margin-top:10px}
select.r{font-size:20px;padding:4px 8px}input.l{width:100%;margin-top:6px;font-size:19px}
@media (max-width:1100px){.subs,.walks{grid-template-columns:1fr}}
"""

SCRIPT = """
var D=%s,K="hire-test-task-review-v3",S={};try{S=JSON.parse(localStorage.getItem(K)||"{}")}catch(e){}
function save(){try{localStorage.setItem(K,JSON.stringify(S))}catch(e){}}
function g(k){var p=k.split("|");S[p[0]]=S[p[0]]||{};S[p[0]][p[1]]=S[p[0]][p[1]]||{};return S[p[0]][p[1]]}
function gate(sp){var sel=document.querySelectorAll("select[data-r^='"+sp+"|']"),done=sel.length>0;sel.forEach(function(s){if(!s.value)done=false});
document.querySelectorAll("[data-gate='"+sp+"']").forEach(function(e){e.hidden=!done});document.querySelectorAll("[data-wait='"+sp+"']").forEach(function(e){e.hidden=done})}
document.querySelectorAll("select[data-r]").forEach(function(s){var k=s.getAttribute("data-r"),p=k.split("|"),b=g(k);if(b[p[2]]&&b[p[2]][0])s.value=b[p[2]][0];
s.onchange=function(){var b=g(k);b[p[2]]=[parseInt(s.value,10)||null,(b[p[2]]||[])[1]||""];save();gate(p[0]+"|"+p[1])};gate(p[0]+"|"+p[1])});
document.querySelectorAll("input[data-l]").forEach(function(i){var k=i.getAttribute("data-l"),p=k.split("|"),b=g(k);if(b[p[2]]&&b[p[2]][1])i.value=b[p[2]][1];
i.oninput=function(){var b=g(k);b[p[2]]=[(b[p[2]]||[])[0]||null,i.value];save()}});
document.querySelectorAll("[data-notes]").forEach(function(t){var k=t.getAttribute("data-notes");S[k]=S[k]||{};if(S[k].founder_notes!=null)t.value=S[k].founder_notes;t.oninput=function(){S[k].founder_notes=t.value;save()}});
document.querySelectorAll("[data-decision]").forEach(function(s){var k=s.getAttribute("data-decision");S[k]=S[k]||{};if(S[k].decision)s.value=S[k].decision;s.onchange=function(){S[k].decision=s.value;save()}});
document.getElementById("copy").onclick=function(){var out=JSON.parse(JSON.stringify(D.review));D.slugs.forEach(function(k){var s=S[k];if(!s)return;out[k]=out[k]||{};
["core","specialist"].forEach(function(p){if(s[p]){out[k].founder=out[k].founder||{};out[k].founder[p]=Object.assign({},out[k].founder[p]||{},s[p]);out[k].founder.rated_at=out[k].founder.rated_at||new Date().toISOString().slice(0,16).replace("T"," ")}});
if(s.founder_notes!=null)out[k].founder_notes=s.founder_notes;if(s.decision)out[k].decision=s.decision});
var t=JSON.stringify(out,null,2),b=this,d=function(){var x=b.textContent;b.textContent="Copied";setTimeout(function(){b.textContent=x},1400)};(navigator.clipboard?navigator.clipboard.writeText(t).then(d,d):d())};
"""


def rget(review, slug):
    r = review.get(slug)
    return r if isinstance(r, dict) else {}


def part_cell(slug, part, key, founder_block, claude_block, rated):
    """One cell: your rating (or the inputs), then Claude's note (gated)."""
    ys, yl = rating(founder_block, key)
    cs, cl = rating(claude_block, key)
    gate_id = f"{slug}|{part}"
    if rated:
        you = f'<div class="you"><span class="lab">You</span><span class="sc">{ys}</span>/5<div class="line">{esc(yl)}</div></div>'
    else:
        opts = "".join(f'<option value="{i}"{" selected" if ys == i else ""}>{i}</option>' for i in range(1, 6))
        you = (f'<div class="you"><span class="lab">You</span><select class="r" data-r="{esc(gate_id)}|{key}">'
               f'<option value="">rate</option>{opts}</select>'
               f'<input class="l" data-l="{esc(gate_id)}|{key}" placeholder="one line of evidence" value="{esc(yl)}"></div>')
    if cs is None and not cl:
        note = '<div class="cl"><span class="lab">Claude</span><span class="line">no note yet</span></div>'
    else:
        diff = f'<span class="diff">differs by {abs(ys - cs)}: read it again</span>' if (ys and cs and abs(ys - cs) >= 2) else ""
        note = (f'<div class="cl"><span class="lab">Claude</span><span class="sc">{cs if cs else "?"}</span>/5{diff}'
                f'<div class="line">{esc(cl)}</div></div>')
    if rated:
        return f"<td>{you}{note}</td>"
    return (f'<td>{you}<div class="wait" data-wait="{esc(gate_id)}">Claude\'s note appears after your four ratings for this part.</div>'
            f'<div data-gate="{esc(gate_id)}" hidden>{note}</div></td>')


def walk_md(name_or_letter, w, brand, badge):
    lines = [f"# Walkthrough: {name_or_letter}", ""]
    if badge:
        lines += [badge + ". Notes reconstructed for the lesson, not a real call.", ""]
    lines += [f"Thirty minutes, after the work is rated and before the decision. {brand}. The person explains one choice; nobody defends everything.", ""]
    if isinstance(w, str):
        return "\n".join(lines + [w, ""])
    lines += [f"- Date: {w.get('date', '')}", f"- The one decision: {w.get('decision', '')}", ""]
    if w.get("quote"):
        lines += ["> " + w["quote"], ""]
    qs = w.get("questions") or WALK_QUESTIONS
    notes = w.get("notes") or []
    lines += ["## Three short questions", ""]
    for i, q in enumerate(qs):
        ans = notes[i][1] if i < len(notes) and isinstance(notes[i], list) and len(notes[i]) > 1 else (notes[i] if i < len(notes) and isinstance(notes[i], str) else "")
        lines += [f"{i + 1}. {q}", f"   Notes: {ans}", ""]
    if w.get("held"):
        lines += ["## What held, what did not", "", w["held"], ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    args = ap.parse_args()
    root = find_root(args.root)
    ch = root / "challenge"
    cfg = load_json(ch / "config.json", None)
    if cfg is None:
        raise SystemExit(f"no {ch / 'config.json'}: copy templates/config.example.json there and fill it")
    review = load_json(ch / "review.json", {})
    finalists = cfg.get("finalists", [])
    badge = demo_label(root, cfg)
    brand = cfg.get("brand", "")
    locked_at = review.get("rubric_locked_at") or ""
    show_names = names_visible(review, finalists)
    terms, days, due = task_terms(cfg), cfg.get("days", 5), cfg.get("due", "")

    def label(i, f):
        return f["name"] if show_names else f"Submission {letter(i)}"

    warnings = []
    any_score = any(rating((rget(review, f["slug"]).get("founder") or {}).get(p), k)[0]
                    for f in finalists for p in ("core", "specialist") for k, _ in QUESTIONS)
    guide = ch / "SCORING-GUIDE.md"
    if not guide.is_file():
        warnings.append("No challenge/SCORING-GUIDE.md. Write it with the briefs and lock it before the first submission.")
    elif review.get("scoring_guide_sha256") and hashlib.sha256(guide.read_bytes()).hexdigest() != review["scoring_guide_sha256"]:
        warnings.append(f"SCORING-GUIDE.md changed after it was locked on {locked_at}. Put the locked text back, or rate everyone again against the new one.")
    if any_score and not locked_at:
        warnings.append("A rating exists but the scoring guide was never locked (build_briefs.py --lock-guide). Lock it before the first submission arrives.")
    got = {f["slug"]: re.search(r"\d{4}-\d{2}-\d{2}", str(rget(review, f["slug"]).get("received", ""))) for f in finalists}
    early = [f["name"] for f in finalists if locked_at and got[f["slug"]] and got[f["slug"]].group(0) < locked_at[:10]]
    if early:
        warnings.append("Received before the scoring guide was locked: " + ", ".join(early) + ". The guide must come first.")
    if not show_names:
        warnings.append("Names are hidden until you have rated every part of every submission. Rate the work before you remember the person.")

    # 1. submissions
    sub_cards = []
    for i, f in enumerate(finalists):
        slug = f["slug"]
        r = rget(review, slug)
        received = submitted(ch, f, r)
        qs = r.get("clarifying_questions")
        if qs is None:
            q_txt = "not recorded yet"
        elif not qs:
            q_txt = "none"
        else:
            q_txt = "; ".join((q.get("question", "") + (f" ({q['about']})" if q.get("about") else "")) if isinstance(q, dict) else str(q) for q in qs)
        a = r.get("assumptions_stated")
        a_txt = "not recorded yet" if a is None else ("none" if not a else "; ".join(str(x) for x in a))
        track = track_of(f, r)
        sub_cards.append(
            f'<div class="card"><div class="big"><span class="L">{letter(i)}</span><span class="t">{esc(label(i, f))}'
            f'<span>{esc(track or "shared task only")}</span></span></div>'
            f'<div class="kv"><b>Received:</b> {esc(r.get("received", "") or ("yes" if received else "not yet"))}</div>'
            f'<div class="kv"><b>What came:</b> {esc(r.get("what_came", "") or ("see the file" if received else ""))}</div>'
            f'<p class="summary">{esc(r.get("summary", "")) or "<span class=note>Claude has not summarised it yet.</span>"}</p>'
            f'<div class="kv"><b>Questions asked before submitting:</b> {esc(q_txt)}</div>'
            f'<div class="kv"><b>Assumption stated:</b> {esc(a_txt)}</div></div>')

    # 2 and 3. the rubric tables
    part_keys = ["core"] + (["specialist"] if any("specialist" in parts_for(f, rget(review, f["slug"])) for f in finalists) else [])
    tables = []
    for part in part_keys:
        head = ['<th>Question<span>5 looks like / 2 looks like</span></th>']
        for i, f in enumerate(finalists):
            r = rget(review, f["slug"])
            sub = track_of(f, r) if part == "specialist" else "same task for everyone"
            head.append(f"<th>{esc(label(i, f)) if show_names else 'Submission ' + letter(i)}<span>{esc(sub)}</span></th>")
        body_rows = []
        for key, qlabel in QUESTIONS:
            five, two = ANCHORS[key]
            cells = [f'<td class="qn"><b>{esc(qlabel)}</b><span>5: {esc(five)}</span><span>2: {esc(two)}</span></td>']
            for f in finalists:
                r = rget(review, f["slug"])
                if part not in parts_for(f, r):
                    cells.append('<td class="note">no specialist part</td>')
                    continue
                fb = (r.get("founder") or {}).get(part) or {}
                cb = (r.get("claude") or {}).get(part) or {}
                cells.append(part_cell(f["slug"], part, key, fb, cb, part_complete(fb)))
            body_rows.append("<tr>" + "".join(cells) + "</tr>")
        tot = ['<td><b>Total</b></td>']
        for f in finalists:
            r = rget(review, f["slug"])
            if part not in parts_for(f, r):
                tot.append("<td></td>")
                continue
            fb = (r.get("founder") or {}).get(part) or {}
            cb = (r.get("claude") or {}).get(part) or {}
            ys = sum(rating(fb, k)[0] or 0 for k, _ in QUESTIONS)
            cs = sum(rating(cb, k)[0] or 0 for k, _ in QUESTIONS)
            if part_complete(fb):
                tot.append(f"<td>You {ys} of 20 · Claude {cs if part_complete(cb) else '?'} of 20</td>")
            else:
                tot.append("<td>You: rate all four first</td>")
        body_rows.append('<tr class="tot">' + "".join(tot) + "</tr>")
        cols = '<colgroup><col class="q">' + "".join("<col>" for _ in finalists) + "</colgroup>"
        extra = ("<p class='note'>Judged against each track's own requirements. A listings score and a reporting score are not directly comparable; compare people on part 1.</p>"
                 if part == "specialist" else
                 "<p class='note'>The fair comparison: everyone answered the same items.</p>")
        tables.append(f'<h2 id="{part}">{esc(PART_TITLE[part])}: four questions</h2>{extra}'
                      f'<table class="rub">{cols}<thead><tr>{"".join(head)}</tr></thead><tbody>{"".join(body_rows)}</tbody></table>')

    # 4. walkthroughs
    walks = []
    wdir = ch / "walkthroughs"
    for i, f in enumerate(finalists):
        r = rget(review, f["slug"])
        w = r.get("walkthrough")
        if not w:
            walks.append(f'<div class="card"><div class="big"><span class="L">{letter(i)}</span><span class="t">{esc(label(i, f))}</span></div>'
                         f'<p class="note">Not held yet. Pick one decision from the submission, then ask the three questions.</p></div>')
            continue
        if isinstance(w, str):
            walks.append(f'<div class="card"><div class="big"><span class="L">{letter(i)}</span><span class="t">{esc(label(i, f))}</span></div><p>{esc(w)}</p></div>')
        else:
            qs = w.get("questions") or WALK_QUESTIONS
            notes = w.get("notes") or []
            lis = []
            for j, q in enumerate(qs):
                n = notes[j] if j < len(notes) else ""
                ans = n[1] if isinstance(n, list) and len(n) > 1 else (n if isinstance(n, str) else "")
                lis.append(f"<li>{esc(q)}" + (f'<span class="ans">{esc(ans)}</span>' if ans else "") + "</li>")
            walks.append(
                f'<div class="card"><div class="big"><span class="L">{letter(i)}</span><span class="t">{esc(label(i, f))}'
                f'<span>{esc(w.get("date", ""))}</span></span></div>'
                f'<div class="hl"><b>The one decision</b>{esc(w.get("decision", ""))}'
                + (f'<div style="margin-top:6px;font-style:italic">"{esc(w["quote"])}"</div>' if w.get("quote") else "")
                + f'</div><ol class="wq">{"".join(lis)}</ol>'
                + (f'<p class="note"><b>What held:</b> {esc(w["held"])}</p>' if w.get("held") else "") + "</div>")
        wdir.mkdir(parents=True, exist_ok=True)
        text = walk_md(label(i, f), w, brand, badge)
        no_dashes(text, f"walkthrough {f['slug']}")
        (wdir / f"{f['slug']}.md").write_text(text, encoding="utf-8")

    # 5. details per finalist
    details = []
    opts = ["open", "hire for this role", "runner-up", "no, close with thanks"]
    for i, f in enumerate(finalists):
        slug = f["slug"]
        r = rget(review, slug)
        files = submission_files(ch, f)
        texts = [p for p in files if p.is_file() and p.suffix.lower() in (".md", ".txt")]
        text = texts[0].read_text(encoding="utf-8").strip() if texts else ""
        others = [p.name for p in files if p not in texts[:1]]
        if not show_names:
            others = [f"{len(others)} more file(s); open them yourself"] if others else []
        claude = r.get("claude") or {}
        founder_ok = all(part_complete(((r.get("founder") or {}).get(p)) or {}) for p in parts_for(f, r))
        read = claude.get("read", "")
        d = r.get("decision", "")
        details.append(
            f'<details class="card"><summary>{letter(i)}. {esc(label(i, f))}: the full submission, Claude\'s read, your notes</summary>'
            + (f'<p class="kv"><b>Also sent:</b> {esc(", ".join(others))}</p>' if others else "")
            + (f'<p class="kv"><b>Paid:</b> {esc(r.get("paid", "") or "not yet")} ({esc(terms["board_pay"].rstrip("."))})</p>' if terms["paid"] else "")
            + (f'<p class="kv"><b>Claude\'s read:</b> {esc(read)}</p>' if read and founder_ok else ("<p class='note'>Claude's read appears after your ratings.</p>" if read else ""))
            + (f'<div class="internal"><b>Internal only:</b> {esc(r["internal_note"])}</div>' if r.get("internal_note") and show_names else "")
            + f'<div class="subtext">{esc(text) if text else ("No text file to show; open what they sent." if files else "Nothing in challenge/submissions/ yet.")}</div>'
            f'<div class="row"><b>Your notes</b></div><textarea data-notes="{esc(slug)}" placeholder="What the rubric misses.">{esc(r.get("founder_notes", ""))}</textarea>'
            f'<div class="row"><span class="note">Decision:</span><select data-decision="{esc(slug)}">'
            + "".join(f'<option{" selected" if d == o else ""}>{esc(o)}</option>' for o in opts + ([d] if d and d not in opts else []))
            + '</select><span class="note">You decide after the Decision Challenge.</span></div></details>')

    banners = "".join(f'<div class="banner">{esc(w)}</div>' for w in warnings)
    lock_line = f"Scoring guide locked {locked_at}." if locked_at else "Scoring guide not locked yet."
    sub_line = (f"{words(len(finalists)).capitalize()} finalists. One shared task plus one specialist part each, rated separately. "
                f"{terms['board_pay']} About {terms['effort']}. "
                f"Return within {words(days)} days, due {due}. {lock_line}")
    body = f"""
<h1>Test task review</h1>
<p class="sub">{esc(sub_line)}</p>
<p class="note">Your rating comes first; Claude's note is shown after it. Scores organise evidence; they are not validated predictions of who will do the job best.</p>
{banners}
<h2>The submissions</h2>
<div class="subs">{''.join(sub_cards)}</div>
{''.join(tables)}
<h2 id="walkthrough">The walkthrough: one decision each</h2>
<p class="note">Thirty minutes after the rating, before the decision. Not to defend everything: one choice, the trade-off, and what another hour would change.</p>
<div class="walks">{''.join(walks)}</div>
<h2>Each submission in full</h2>
{''.join(details)}
<div class="card"><div class="row" style="margin:0"><button class="p" id="copy">Copy review.json</button><span class="note">Merges the ratings, notes and decisions typed here. Paste over challenge/review.json and rerun.</span></div></div>
<p class="foot">Nothing on this page is sent anywhere. A person rates, decides and sends.</p>
"""
    review_out = {k: v for k, v in review.items() if not k.startswith("_")}
    data = js_json({"review": review_out, "slugs": [f["slug"] for f in finalists]})
    html_text = page("Test task review", f"{brand} · Test task · Review", body, badge, CSS, SCRIPT % data)
    no_dashes(html_text, "REVIEW.html")
    out = ch / "REVIEW.html"
    out.write_text(html_text, encoding="utf-8")
    print(f"wrote {out}" + (" (names shown, every part rated)" if show_names else " (names hidden)"))
    for f in finalists:
        if (wdir / f"{f['slug']}.md").exists() and rget(review, f["slug"]).get("walkthrough"):
            print(f"wrote {wdir / (f['slug'] + '.md')}")
    for w in warnings:
        print("note: " + w)
    missing = [f["slug"] for f in finalists if not rget(review, f["slug"])]
    if missing:
        print("nothing in review.json yet for: " + ", ".join(missing))


if __name__ == "__main__":
    main()
