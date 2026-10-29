#!/usr/bin/env python3
"""Interview transcript numbers for the coach file. Standard library only, no network.

Usage (from your hiring/ folder or the folder above it):
  python3 <skill>/scripts/stats.py                     every transcript in out/interviews/transcripts/
  python3 <skill>/scripts/stats.py <slug>              one transcript
  python3 <skill>/scripts/stats.py path/to/<slug>.txt  one transcript by path
  add --json to print the numbers as JSON, --root PATH to point at the hiring folder

Transcript format, one turn per line:
  [MM:SS] INTERVIEWER: text
  [MM:SS] CANDIDATE: text
[H:MM:SS], ranges [MM:SS-MM:SS] and estimated minutes [~MM:SS] (from transcript.py) also work. The CANDIDATE
label is the candidate; the other label is the interviewer.

What it measures, all about the interviewer's behaviour, never about the candidate:
  - WORD SHARE: the interviewer's share of the transcript's words (not speaking time). A coaching
    indicator, not a target and not a candidate score.
  - 5-minute blocks where the interviewer had more than 75 percent of the words.
  - Long stretches: interviewer turns of LONG_TURN_WORDS words or more, with their opening words.
  - Core questions covered, n of 6: the five core questions and the candidate's tailored follow-up from
    out/interviews/prep.json, matched against the interviewer's questions by the words they share (each
    question's own words, its title and, at a quarter weight, its anchors; a word shared by several questions
    counts less), so a question asked in your own words is still found. The first run writes the result into
    the "Questions I covered" table of INTERVIEWER_COACH.md; a person checks it there, and that table is what
    the headline and the ledger show from then on.
  - Answers cut off: candidate lines that end in "..." with the interviewer speaking next.
  - Numbers with no follow-up question: a candidate turn with a number or a result word, followed by an
    interviewer turn with no question in it. Claude decides which of these was a missed follow-up.
  - The candidate's own questions, for the debrief.
  - Speaker check: two lines in a row with the same label where the first asks a question and the second
    is a short line with no question. Transcription often puts a short answer under the wrong speaker.
    Such a line is unverified until a person checks it against the recording. The transcript is never
    edited by this script.

Writes out/interviews/<slug>/stats.json (with the number of ~ minutes) and refreshes two blocks in out/interviews/<slug>/INTERVIEWER_COACH.md:
the headline at the top (word share and questions covered) and the numbers section at the end. It creates the
file from templates/coach.md the first time. Everything outside those two blocks is left as it is.
"""
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

LONG_TURN_WORDS = 120
HEAVY_BLOCK = 0.75
MATCH_AT = 0.4          # weighted share of a core question's words found around one interviewer question
MATCH_WORDS = 5.0       # ... out of at most this much weight, so a long planned question is not harder to find
SHORT_LINE_WORDS = 12   # a line this short right after a same-label question is checked for a speaker swap
NUM_START, NUM_END = "<!-- numbers:start -->", "<!-- numbers:end -->"
HEAD_START, HEAD_END = "<!-- headline:start -->", "<!-- headline:end -->"
TEMPLATE = os.path.join(HERE, "..", "templates", "coach.md")

LINE = re.compile(
    r"^\[(~)?(?:(\d+):)?(\d{1,2}):(\d{2})(?:\s*-\s*(?:(\d+):)?(\d{1,2}):(\d{2}))?\]\s*([A-Z][A-Z _-]*?):\s?(.*)$")
STOP = set("""the a an and or of to in on for with you your me my i we it is are was were do did does what how when
where who which tell show walk about one that this not from have has had be at as by if then them they their there
here would could can will so any some more most like just okay yes also than been into only very really""".split())
PROMPTS = ("tell me", "show me", "walk me", "share your", "pick one", "describe", "talk me")
LEADS = ("okay, so ", "okay. ", "okay ", "so ", "and ", "next question. ", "right, ")
MIN_ANSWER_WORDS = 25   # shorter candidate turns (a count said aloud) are not checked for a missed follow-up
MIN_MOVE_ON_WORDS = 6   # "Okay." lets them go on; a longer turn with no question moves the call on
RESULT = re.compile(r"\d|\b(doubled|doubling|tripled|halved|percent|twice as)\b", re.I)


def secs(h, m, s):
    return (int(h) if h else 0) * 3600 + int(m) * 60 + int(s)


def clock(t, est=False):
    return (("~" if est else "") + f"{t // 60:02d}:{t % 60:02d}") if t is not None else ""


def rclock(r):
    return clock(r["t"], r.get("est"))


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s.strip()]


def is_prompt(sent):
    """A sentence that asks: it ends with ?, or it opens with an ask such as 'tell me' or 'show me'."""
    s = sent.lower().lstrip("\"' ")
    for lead in LEADS:
        if s.startswith(lead):
            s = s[len(lead):]
    return s.endswith("?") or s.startswith(PROMPTS) or any(f" {x} " in f" {s} " for x in PROMPTS)


def stem(w):
    w = w.lower().strip("'")
    if w.endswith("'s"):
        w = w[:-2]
    if w.endswith(("ses", "xes", "zes", "ches", "shes")) and len(w) >= 5:
        return w[:-2]
    for suf, mn in (("ing", 6), ("ed", 5), ("s", 4)):
        if w.endswith(suf) and len(w) >= mn and not w.endswith("ss"):
            return w[:-len(suf)]
    return w


# A few everyday swaps an interviewer makes when asking a planned question in their own words.
SAME = {"made": "built", "build": "built", "create": "built", "creat": "built", "lately": "recently", "recent": "recently",
        "broke": "wrong", "mistake": "wrong", "error": "wrong", "fail": "wrong", "fix": "wrong", "own": "yourself", "personally": "yourself",
        "commit": "hour", "conflict": "other"}


def content(text):
    """The words that carry meaning: longer than three letters and not a stop word, or a short acronym
    such as AI, PPC, VA or SOP. Stemmed, with the everyday swaps above."""
    out = set()
    for w in re.findall(r"[A-Za-z']+", text):
        s = stem(w)
        if s in SAME or (len(w) > 3 and w.lower() not in STOP) or (w.isupper() and len(w) >= 2):
            out.add(SAME.get(s, s))
    return out


def parse(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            m = LINE.match(raw.rstrip("\n"))
            if m:
                rows.append({"t": secs(m.group(2), m.group(3), m.group(4)), "est": bool(m.group(1)),
                             "label": m.group(8).strip(), "text": m.group(9).strip()})
    return rows


def turns(rows):
    """Consecutive lines with the same label merged into one turn."""
    out = []
    for r in rows:
        if out and out[-1]["label"] == r["label"]:
            out[-1]["text"] += " " + r["text"]
            out[-1]["lines"].append(r)
        else:
            out.append({"t": r["t"], "est": r["est"], "label": r["label"], "text": r["text"], "lines": [r]})
    return out


def excerpt(text, n=26):
    w = text.split()
    return " ".join(w[:n]) + (" ..." if len(w) > n else "")


def tail(text, n=22):
    w = text.split()
    return ("... " if len(w) > n else "") + " ".join(w[-n:])


def same_word(a, b):
    return a == b or (a[:4] == b[:4] and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)


def found(word, words):
    return word in words or any(same_word(word, w) for w in words)


def match_core(rows, inter, questions):
    """For each question {n, title, ask, anchors}: the interviewer question where it was asked, or not asked.
    Every interviewer question (a sentence ending in ? or opening with "tell me", "show me"...) is read with up
    to three sentences around it in the same turn, across transcript lines. Its score for a core question is
    the weight of that question's words it contains (the ask and the title at full weight, the anchors at a quarter,
    a word that several core questions share counts less), out of the question's total or MATCH_WORDS, whichever
    is smaller. Each interviewer question counts for one
    core question at most, the best match first."""
    keys = []
    for q in questions:
        title = q.get("title", "") if q.get("n") != 6 else ""   # question 6's title is the same for everyone
        k = content(q.get("ask", "")) | content(title) if q.get("ask") else set()
        a = content(" ".join((q.get("anchors") or {}).values())) - k if k else set()
        keys.append((k, a))
    df = {}
    for k, a in keys:
        for w in k | a:
            df[w] = df.get(w, 0) + 1
    prompts = []
    for t in turns(rows):
        if t["label"] != inter:
            continue
        ss = [(s, r) for r in t["lines"] for s in sentences(r["text"])]
        for i, (s, r) in enumerate(ss):
            if is_prompt(s):
                window = content(" ".join(x for x, _ in ss[max(0, i - 3):i + 4]))
                lead = ss[i - 1][0] + " " if i > 0 and len(s.split()) < 8 else ""
                prompts.append({"r": r, "line": lead + s, "words": window})
    cands = []
    for qi, (k, a) in enumerate(keys):
        total = sum(1.0 / df[w] for w in k)
        if not total:
            continue
        for pi, pr in enumerate(prompts):
            hit = sum(1.0 / df[w] for w in k if found(w, pr["words"]))
            hit += 0.25 * sum(1.0 / df[w] for w in a if found(w, pr["words"]))
            cands.append((min(1.0, hit / min(total, MATCH_WORDS)), qi, pi))
    best, used = {}, set()
    for score, qi, pi in sorted(cands, key=lambda c: (-c[0], c[1], c[2])):
        if score < MATCH_AT:
            break
        if qi in best or pi in used:
            continue
        best[qi] = (score, pi)
        used.add(pi)
    top = {}
    for score, qi, _ in cands:
        top[qi] = max(top.get(qi, 0.0), score)
    res = []
    for qi, q in enumerate(questions):
        hit = best.get(qi)
        pr = prompts[hit[1]] if hit else None
        res.append({"n": q.get("n"), "title": q.get("title", ""), "asked": bool(hit),
                    "time": rclock(pr["r"]) if pr else "", "line": excerpt(pr["line"], 30) if pr else "",
                    "match": round(hit[0] if hit else top.get(qi, 0.0), 2)})
    return res


def compute(rows, questions):
    labels = sorted({r["label"] for r in rows})
    if "CANDIDATE" not in labels or len(labels) != 2:
        sys.exit(f"expected exactly two labels, one of them CANDIDATE. Found: {labels}")
    inter = [l for l in labels if l != "CANDIDATE"][0]
    words = {inter: 0, "CANDIDATE": 0}
    for r in rows:
        words[r["label"]] += len(r["text"].split())
    total = sum(words.values()) or 1
    share = round(100.0 * words[inter] / total, 1)

    blocks = {}
    for r in rows:
        blocks.setdefault(r["t"] // 300, {inter: 0, "CANDIDATE": 0})[r["label"]] += len(r["text"].split())
    heavy = []
    for b, w in sorted(blocks.items()):
        bt = w[inter] + w["CANDIDATE"]
        if bt and w[inter] > HEAVY_BLOCK * bt:
            heavy.append({"block": f"{b * 5:02d} to {b * 5 + 5:02d} min", "interviewer_pct": round(100 * w[inter] / bt)})

    tt = turns(rows)
    long_turns = [{"time": clock(t["t"], t["est"]), "words": len(t["text"].split()), "opening": excerpt(t["text"], 16)}
                  for t in tt if t["label"] == inter and len(t["text"].split()) >= LONG_TURN_WORDS]

    cut_off, no_follow = [], []
    for i, t in enumerate(tt[:-1]):
        nxt = tt[i + 1]
        if t["label"] != "CANDIDATE" or nxt["label"] != inter:
            continue
        last = t["lines"][-1]["text"].rstrip()
        if last.endswith("...") or last.endswith("…"):
            cut_off.append({"time": rclock(t["lines"][-1]), "ends": tail(last, 14), "next_time": clock(nxt["t"], nxt["est"])})
        if (RESULT.search(t["text"]) and len(t["text"].split()) >= MIN_ANSWER_WORDS and not last.endswith("?")
                and len(nxt["text"].split()) >= MIN_MOVE_ON_WORDS
                and not any(is_prompt(s) for s in sentences(nxt["text"]))):
            num_sents = [s for s in sentences(t["text"]) if RESULT.search(s)]
            no_follow.append({"time": clock(t["t"], t["est"]), "number": excerpt(num_sents[-1], 30) if num_sents else "",
                              "ends": tail(last, 12), "next_time": clock(nxt["t"], nxt["est"]), "next": excerpt(nxt["text"], 18)})

    cand_q = [{"time": rclock(r), "text": s} for r in rows if r["label"] == "CANDIDATE"
              for s in sentences(r["text"]) if s.endswith("?")]

    speaker = []
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if a["label"] != b["label"]:
            continue
        ss = sentences(a["text"])
        if not ss or not ss[-1].endswith("?"):
            continue
        if len(b["text"].split()) > SHORT_LINE_WORDS or "?" in b["text"]:
            continue
        other = "CANDIDATE" if a["label"] == inter else inter
        moved = len(b["text"].split()) * (1 if a["label"] == inter else -1)
        speaker.append({
            "time": rclock(b), "label": b["label"], "text": b["text"],
            "after_time": rclock(a), "after": excerpt(ss[-1], 24),
            "next_time": rclock(rows[i + 2]) if i + 2 < len(rows) else "",
            "next": excerpt(rows[i + 2]["text"], 18) if i + 2 < len(rows) else "",
            "maybe": other,
            "context": [f"[{rclock(x)}] {x['label']}: {x['text']}" for x in rows[i:i + 3]],
            "why": (f"two {a['label']} lines in a row; the question at [{rclock(a)}] has no {other} line after it, "
                    f"and the short line at [{rclock(b)}] reads like the answer to it"),
            "share_if_moved": round(100.0 * (words[inter] - moved) / total, 1),
        })

    return {
        "interviewer_label": inter,
        "start": rclock(rows[0]), "end": rclock(rows[-1]),
        "minutes": (rows[-1]["t"] - rows[0]["t"]) // 60, "lines": len(rows),
        "estimated_times": sum(1 for r in rows if r["est"]),
        "words": {"interviewer": words[inter], "candidate": words["CANDIDATE"]},
        "word_share_interviewer": share, "word_share_label": common.WORD_SHARE_LABEL,
        "blocks_over_75": heavy, "long_turns": long_turns,
        "core": match_core(rows, inter, questions), "cut_off": cut_off,
        "numbers_no_question": no_follow, "candidate_questions": cand_q, "speaker_check": speaker,
    }


def coverage_table(r):
    out = ["| # | Question | Asked | Where |", "|---|---|---|---|"]
    for q in r["core"]:
        where = f"[{q['time']}] \"{q['line']}\"" if q["asked"] else "not found in the interviewer's questions"
        out.append(f"| {q['n']} | {q['title']} | {'yes' if q['asked'] else 'no'} | {where} |")
    return "\n".join(out)


def numbers_md(slug, r, has_prep):
    covered = sum(1 for q in r["core"] if q["asked"])
    est = r.get("estimated_times", 0)
    out = [NUM_START,
           f"_Written by `stats.py` from `transcripts/{slug}.txt`. Rerun it to refresh this block; do not edit it by hand._",
           "",
           f"**{common.WORD_SHARE_LABEL}:** the interviewer had **{r['word_share_interviewer']}%** of the words "
           f"({r['words']['interviewer']:,} of {r['words']['interviewer'] + r['words']['candidate']:,}).",
           "",
           f"- Call: [{r['start']}] to [{r['end']}], about {r['minutes']} minutes, {r['lines']} transcript lines.",
           f"- Estimated minutes: {est} of {r['lines']} lines carry a ~ minute, so quotes with a ~ minute are approximate."
           if est else "- Every minute comes from the transcript itself.",
           "- 5-minute blocks where the interviewer had over 75% of the words: " +
           (", ".join(f"{b['block']} ({b['interviewer_pct']}%)" for b in r["blocks_over_75"]) or "none") + ".",
           f"- Long stretches by the interviewer ({LONG_TURN_WORDS} words or more in one turn): " +
           (str(len(r["long_turns"])) if r["long_turns"] else "none") + ("" if not r["long_turns"] else ":")]
    for t in r["long_turns"]:
        out.append(f"  - [{t['time']}] {t['words']} words: \"{t['opening']}\"")
    if has_prep:
        out += ["", f"**Core questions, word match: {covered} of {len(r['core'])}.** The checked count is the "
                "\"Questions I covered\" table above.", "", coverage_table(r)]
    else:
        out += ["", "**Core questions covered:** not counted, no `out/interviews/prep.json`."]
    out += ["", "**Answers cut off** (a candidate line that ends in \"...\" with the interviewer speaking next): " +
            (str(len(r["cut_off"])) if r["cut_off"] else "none")]
    for c in r["cut_off"]:
        out.append(f"- [{c['time']}] \"{c['ends']}\" then the interviewer at [{c['next_time']}]")
    out += ["", "**Numbers with no follow-up question** (for Claude to judge which were missed follow-ups): " +
            (str(len(r["numbers_no_question"])) if r["numbers_no_question"] else "none")]
    for n in r["numbers_no_question"]:
        out.append(f"- [{n['time']}] \"{n['number']}\" then [{n['next_time']}] \"{n['next']}\"")
    out += ["", "**Speaker check** (a short line that may carry the wrong label is unverified until checked against the recording): " +
            (str(len(r["speaker_check"])) if r["speaker_check"] else "no line flagged")]
    for s in r["speaker_check"]:
        out.append(f"- [{s['time']}] labelled {s['label']}: \"{s['text']}\" Why: {s['why']}. "
                   f"If it is the {s['maybe']}'s line, the word share is {s['share_if_moved']}%.")
    out += ["", f"**The candidate's own questions:** {len(r['candidate_questions'])}"]
    for q in r["candidate_questions"]:
        out.append(f"- [{q['time']}] \"{q['text']}\"")
    out.append(NUM_END)
    return "\n".join(out)


def headline_md(r, cov):
    """cov: the coach table rows (checked by a person), or None to use the word match."""
    if cov:
        asked = f" · {common.coverage_text(cov)} core questions asked**"
    elif r["core"]:
        asked = f" · {sum(1 for q in r['core'] if q['asked'])} of {len(r['core'])} core questions asked**"
    else:
        asked = "**"
    return "\n".join([HEAD_START, f"**{r['word_share_interviewer']}% of the words were mine" + asked, "",
                       f"{common.WORD_SHARE_LABEL}. Counted by `stats.py` from the transcript; questions asked come from the "
                       "\"Questions I covered\" table; the details are in the last section.", HEAD_END])


def put_block(text, start, end, block):
    if start in text and end in text:
        return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, text, flags=re.S), True
    return text, False


def refresh_coach(root, slug, r, block, name):
    path = os.path.join(common.slug_dir(root, slug), "INTERVIEWER_COACH.md")
    if os.path.exists(path):
        text = open(path, encoding="utf-8").read()
        text, ok = put_block(text, NUM_START, NUM_END, block)
        if not ok:
            text = text.rstrip() + "\n\n## The numbers from stats.py\n\n" + block + "\n"
        action = "refreshed the numbers in"
    else:
        tpl = open(TEMPLATE, encoding="utf-8").read()
        text = (tpl.replace("{name}", name).replace("{slug}", slug).replace("{numbers}", block)
                .replace("{coverage}", coverage_table(r) if r["core"] else "Not counted: no `out/interviews/prep.json`."))
        if common.is_demo(root):
            text = text.replace("<!-- demo -->", "FICTIONAL DEMO. Invented people and an invented call.")
        action = "created"
    common.no_dashes(text, path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    text, _ = put_block(text, HEAD_START, HEAD_END, headline_md(r, common.coach_coverage(path)))
    text = text.replace("{headline}", headline_md(r, common.coach_coverage(path)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{action} {path}")


def run_one(root, path, as_json):
    slug = os.path.splitext(os.path.basename(path))[0]
    rows = parse(path)
    if not rows:
        sys.exit(f"{path}: no transcript lines found. Expected lines like: [03:20] INTERVIEWER: text")
    prep = common.load_prep(root)
    questions = common.core_questions(prep, slug)
    r = compute(rows, questions)
    r["slug"] = slug
    r["transcript"] = os.path.relpath(path, root)
    if as_json:
        print(json.dumps(r, indent=2))
        return r
    d = common.slug_dir(root, slug)
    os.makedirs(d, exist_ok=True)
    common.write(os.path.join(d, "stats.json"), json.dumps(r, indent=2, ensure_ascii=False) + "\n")
    c = common.prep_candidate(prep, slug) or {}
    refresh_coach(root, slug, r, numbers_md(slug, r, bool(questions)), c.get("name", slug.replace("-", " ").title()))
    covered = sum(1 for q in r["core"] if q["asked"])
    print(f"  {slug}: word share {r['word_share_interviewer']}% (interviewer), "
          f"core questions {covered} of {len(r['core']) if r['core'] else '?'}, "
          f"blocks over 75%: {len(r['blocks_over_75'])}, long stretches: {len(r['long_turns'])}, "
          f"cut off: {len(r['cut_off'])}, numbers with no question: {len(r['numbers_no_question'])}, "
          f"speaker check: {len(r['speaker_check'])} line(s)")
    return r


def main():
    root, args = common.root_from_argv(sys.argv[1:])
    as_json = "--json" in args
    args = [a for a in args if not a.startswith("--")]
    tdir = os.path.join(common.interviews_dir(root), "transcripts")
    if args:
        paths = []
        for a in args:
            if os.path.isfile(a):
                paths.append(a)
            elif os.path.isfile(os.path.join(tdir, a + ".txt")):
                paths.append(os.path.join(tdir, a + ".txt"))
            else:
                sys.exit(f"no transcript {a} (looked for {a} and {os.path.join(tdir, a + '.txt')})")
    else:
        if not os.path.isdir(tdir):
            sys.exit(f"no folder {tdir}. Put one transcript per call there as <slug>.txt.")
        paths = sorted(os.path.join(tdir, f) for f in os.listdir(tdir) if f.endswith(".txt"))
        if not paths:
            sys.exit(f"no .txt transcripts in {tdir}")
    if common.load_prep(root) is None:
        print("note: no out/interviews/prep.json, so core questions are not counted. Run prep mode first.")
    for p in paths:
        run_one(root, p, as_json)


if __name__ == "__main__":
    main()
