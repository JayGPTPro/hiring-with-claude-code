"""Optional. Builds hiring/out/DECISION.md: every stage's recorded result side by side, one row per finalist.

It reads only what each stage wrote, and every input is optional. A stage with no file says so and
drops out of the total; a finalist with no reference summary is named plainly. Nothing is typed in.

  screen         SHARED + TRACK out of 100 at screening, from out/scores.json ("screening" when the questionnaire
                 step changed them; or out/board.csv), rounded to whole numbers as the board does. "Insufficient
                 evidence" (in scores.json, or the dossier's "Evidence level:" line) stays text, never a number.
  questionnaire  the questionnaire TRACK out of 50, from the "TRACK: n/50" line under "## Questionnaire" in
                 out/candidates/<slug>.md. The writing anchors in questionnaire/writing.json (or
                 out/questionnaire/writing.json) are shown beside it and never scored.
  interview      YOUR scoring sheet total in out/interviews/<slug>/FOUNDER_SCORES.md (the first table under a
                 heading with "scor" in it). A "not asked" row is unknown, not a weakness, and is left out.
  references     out/references/<slug>-summary.md: the concrete examples, shown as text (weight 0 by default)
  challenge      your rating of the shared task, out of 20, from challenge/review.json
  specialist     your rating of the specialist part, shown beside the total and not in it (weight 0)

Weights: a "## Decision weights" section in criteria.md ("- stage: n"), else the defaults below. The total
stays hidden until every finalist has submitted (review.json "received", or any file for them in
challenge/submissions/) and you have rated every shared task. A score is never a reason to stop thinking.

Usage: run from your hiring/ folder, or from the folder above it:  python3 decision.py  (--root path/to/hiring overrides)
"""
import argparse
import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import (find_root, load_json, no_dashes, QUESTIONS, rating, part_complete,  # noqa: E402
                     submitted, reference_summary, dossier_section, dossier_insufficient, whole)

DEFAULT_WEIGHTS = {"screen": 15, "questionnaire": 10, "interview": 30, "references": 0, "challenge": 45, "specialist": 0}
STAGES = [("screen", "Screen"), ("questionnaire", "Questionnaire"), ("interview", "Interview"),
          ("references", "References"), ("challenge", "Test task, shared part"), ("specialist", "Test task, specialist part")]
SHEET_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|(.*)\|\s*$")
INSUFFICIENT = "Insufficient evidence. Follow-up required."


def num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    if isinstance(v, str) and re.fullmatch(r"\s*\d+(\.\d+)?\s*", v):
        return float(v)
    return None


def pct(x, mx):
    return round(100.0 * x / mx, 1) if mx else None


def load_weights(root):
    text = (root / "criteria.md").read_text(encoding="utf-8") if (root / "criteria.md").exists() else ""
    m = re.search(r"^##\s+Decision weights\s*$(.*?)(?=^## |\Z)", text, re.M | re.S | re.I)
    w = {}
    for line in (m.group(1).splitlines() if m else []):
        km = re.match(r"^\s*-\s*([a-z]+)\s*:\s*(\d+(?:\.\d+)?)", line, re.I)
        if km and km.group(1).lower() in DEFAULT_WEIGHTS:
            w[km.group(1).lower()] = float(km.group(2))
    if w:
        return {k: w.get(k, 0.0) for k in DEFAULT_WEIGHTS}, "criteria.md"
    return {k: float(v) for k, v in DEFAULT_WEIGHTS.items()}, "defaults"


def screen_cell(s, t, insufficient, out_of_budget):
    s, t = whole(s), whole(t)
    if insufficient:
        return {"text": INSUFFICIENT, "pct": None}
    if out_of_budget:
        return {"text": "not scored: out of budget", "pct": None}
    if s is not None and t is not None:
        return {"text": f"SHARED {s:g} + TRACK {t:g} = {s + t:g} of 100", "pct": pct(s + t, 100)}
    return None


def load_screen(root):
    out = {}
    sj, bc = root / "out" / "scores.json", root / "out" / "board.csv"
    if sj.exists():
        d = load_json(sj, {})
        rows = d.get("candidates", d) if isinstance(d, dict) else d
        if isinstance(rows, dict):
            rows = [dict(v, slug=k) for k, v in rows.items() if isinstance(v, dict)]
        for c in rows if isinstance(rows, list) else []:
            if isinstance(c, dict) and c.get("slug"):
                first = c.get("screening") if isinstance(c.get("screening"), dict) else c  # before the questionnaire
                ins = c["insufficient_evidence"] if "insufficient_evidence" in c else dossier_insufficient(root, c["slug"])
                cell = screen_cell(first.get("shared", c.get("shared")), first.get("track", c.get("track")), ins,
                                   str(c.get("status", "")).lower() == "out of budget")
                if cell:
                    out[c["slug"]] = cell
        if out:
            return out, "out/scores.json"
    if bc.exists():
        with bc.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
                cell = screen_cell(r.get("shared"), r.get("track"),
                                   r.get("evidence_level", "").lower().startswith("insufficient"),
                                   r.get("status", "").lower() == "out of budget")
                if r.get("slug") and cell:
                    out[r["slug"]] = cell
        return out, "out/board.csv"
    return out, None


QTRACK = re.compile(r"^\s*TRACK:\s*(\d+(?:\.\d+)?)\s*/\s*50", re.M)


def writing_anchors(root):
    """{slug: text} from writing.json: the yes count per anchor block, or a plain score. Shown, never scored."""
    for rel in ("questionnaire/writing.json", "out/questionnaire/writing.json"):
        d = load_json(root / rel, None)
        if not isinstance(d, dict):
            continue
        out = {}
        for slug, v in (d.get("scores", d)).items():
            if slug.startswith("_") or slug in ("max", "scores", "anchors"):
                continue
            blocks = [(n, v[n]) for n in ("writing", "situation") if isinstance(v, dict) and isinstance(v.get(n), dict)]
            if blocks:
                yes = [sum(1 for k in ("understood", "clear", "flagged") if str(b.get(k, "")).lower() == "yes") for _, b in blocks]
                out[slug] = "; ".join(f"{n} {y} of 3 yes" for (n, _), y in zip(blocks, yes))
                continue
            score = num(v) if num(v) is not None else (num(v.get("score")) if isinstance(v, dict) else None)
            mx = (num(v.get("max")) if isinstance(v, dict) else None) or num(d.get("max")) or 5
            if score is not None:
                out[slug] = f"writing {score:g} of {mx:g}"
        return out, rel
    return {}, None


def load_questionnaire(root, slugs):
    """The questionnaire TRACK (scored, out of 50) with the writing anchors beside it (shown, not scored)."""
    anchors, arel = writing_anchors(root)
    out, found = {}, False
    for slug in slugs:
        m = QTRACK.search(dossier_section(root, slug, "Questionnaire"))
        t = whole(m.group(1)) if m else None
        found = found or t is not None
        parts = ([f"questionnaire TRACK {t} of 50"] if t is not None else []) + \
                ([anchors[slug] + " (anchors not scored)"] if slug in anchors else [])
        if parts:
            out[slug] = {"text": "; ".join(parts), "pct": pct(t, 50) if t is not None else None}
    src = " and ".join(s for s in (("out/candidates/ (## Questionnaire TRACK)" if found else None), arel) if s)
    return out, (src or None)


def sheet_total(text):
    """('ok', total, max, not asked) or ('incomplete', rows, 0, 0) from the first table under a 'scor' heading."""
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if not re.match(r"^#{2,4}\s.*scor", l, re.I):
            continue
        rows, missing, skipped = [], [], 0
        for l2 in lines[i + 1:]:
            if re.match(r"^#{1,4}\s", l2):
                break
            m = SHEET_ROW.match(l2)
            if not m:
                continue
            raw = m.group(3).strip().strip("*")
            m5 = re.match(r"^([1-5])(\s*(/|of)\s*5)?\b", raw)
            if m5:
                rows.append(int(m5.group(1)))
            elif raw.lower().startswith("not asked"):
                skipped += 1
            else:
                missing.append(m.group(1))
        if rows or missing:
            return ("incomplete", missing, 0, 0) if missing else ("ok", sum(rows), 5 * len(rows), skipped)
    return None


def load_interview(root, slugs):
    out, found = {}, False
    for slug in slugs:
        folder = root / "out" / "interviews" / slug
        for p in [folder / "FOUNDER_SCORES.md"]:  # your sheet, never Claude's debrief
            r = sheet_total(p.read_text(encoding="utf-8")) if p.is_file() else None
            if not r:
                continue
            found = True
            if r[0] == "ok":
                note = f" ({r[2] // 5} asked, {r[3]} not asked)" if r[3] else ""
                out[slug] = {"text": f"your sheet {r[1]:g} of {r[2]}{note}", "pct": pct(r[1], r[2])}
            else:
                out[slug] = {"text": "sheet not totalled: rows " + ", ".join(r[1]) + " have no score", "pct": None}
            break
    return out, ("out/interviews/" if found else None)


def concrete_examples(text):
    """(concrete examples, calls done) from a calls table with a "Concrete examples" column, else a count in the text."""
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if l.strip().startswith("|") and re.search(r"concrete example", l, re.I):
            head = [c.strip().lower() for c in l.strip().strip("|").split("|")]
            ci = next(j for j, c in enumerate(head) if "concrete" in c)
            si = next((j for j, c in enumerate(head) if c == "status"), None)
            n = calls = 0
            for row in lines[i + 1:]:
                if not row.strip().startswith("|"):
                    break
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                if ci < len(cells) and re.fullmatch(r"\d+", cells[ci]):
                    n += int(cells[ci])
                if si is not None and si < len(cells) and re.match(r"(done|completed)", cells[si], re.I):
                    calls += 1
            return n, calls
    m = re.search(r"(\d+)\s+concrete example", text, re.I)
    return (int(m.group(1)) if m else 0), 0


def load_references(root, slugs):
    out, found = {}, False
    for slug in slugs:
        p = reference_summary(root, slug)
        if p:
            found = True
            n, calls = concrete_examples(p.read_text(encoding="utf-8"))
            out[slug] = {"text": f"{n} concrete example{'s' if n != 1 else ''}"
                         + (f" from {calls} call{'s' if calls != 1 else ''}" if calls else ""), "pct": pct(min(n, 5), 5)}
    return out, ("out/references/" if found else None)


def challenge_part(review, slug, part):
    r = review.get(slug) if isinstance(review.get(slug), dict) else {}
    block = (r.get("founder") or {}).get(part) if isinstance(r.get("founder"), dict) else None
    if not isinstance(block, dict) or not block:
        return None
    scores = [rating(block, k)[0] for k, _ in QUESTIONS]
    if part_complete(block):
        return {"text": f"your rating {sum(scores)} of 20", "pct": pct(sum(scores), 20)}
    return {"text": f"your rating not complete ({sum(1 for s in scores if s)} of 4)", "pct": None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    root = find_root(ap.parse_args().root)
    ch = root / "challenge"
    cfg = load_json(ch / "config.json", None)
    if cfg is None:
        raise SystemExit(f"no {ch / 'config.json'}: set up the test task first (copy templates/config.example.json there)")
    review = load_json(ch / "review.json", {})
    dc = load_json(ch / "decision-challenge.json", {})
    weights, wsrc = load_weights(root)
    finalists = cfg.get("finalists", [])
    slugs = [f["slug"] for f in finalists]
    readers = {"screen": load_screen(root), "questionnaire": load_questionnaire(root, slugs),
               "interview": load_interview(root, slugs), "references": load_references(root, slugs)}
    per = {s: {k: readers[k][0].get(s) for k in readers} for s in slugs}
    for s in slugs:
        per[s]["challenge"], per[s]["specialist"] = challenge_part(review, s, "core"), challenge_part(review, s, "specialist")
    srcs = {k: readers[k][1] for k in readers}
    srcs["challenge"] = "challenge/review.json" if any(per[s]["challenge"] for s in slugs) else None
    srcs["specialist"] = "challenge/review.json" if any(per[s]["specialist"] for s in slugs) else None

    active, dropped = [], []
    for k, lbl in STAGES:
        missing_for = [f["name"] for f in finalists if not (per[f["slug"]][k] and per[f["slug"]][k]["pct"] is not None)]
        if weights.get(k, 0) <= 0:
            dropped.append(f"{lbl} (weight 0)")
        elif not srcs.get(k):
            dropped.append(f"{lbl} (no file found)")
        elif missing_for:
            dropped.append(f"{lbl} (no figure for {', '.join(missing_for)})")
        else:
            active.append(k)
    wsum = sum(weights[k] for k in active) or 1.0
    eff = {k: round(100 * weights[k] / wsum, 1) for k in active}
    waiting = [f["name"] for f in finalists if not submitted(ch, f, review.get(f["slug"]) or {})]
    unrated = [f["name"] for f in finalists if not (per[f["slug"]]["challenge"] and per[f["slug"]]["challenge"]["pct"] is not None)]
    hide_total = bool(waiting or unrated or not active)
    total = {s: round(sum(per[s][k]["pct"] * eff[k] / 100 for k in active), 1) if active else None for s in slugs}

    notes = []
    if waiting:
        notes.append("Waiting for submissions from: " + ", ".join(waiting) + ". The total stays hidden until every finalist has submitted.")
    elif unrated:
        notes.append("Waiting for your rating of the shared task for: " + ", ".join(unrated) + ". The total stays hidden until you rated everyone.")
    for f in finalists:
        if not per[f["slug"]]["references"]:
            notes.append(f"No reference summary for {f['name']} (out/references/{f['slug']}-summary.md). "
                         "The decision runs without references; name the gap under Missing evidence.")
    missing_files = [lbl for k, lbl in STAGES if not srcs.get(k) and k not in ("specialist", "references")]
    if missing_files:
        notes.append("No file found yet for: " + ", ".join(missing_files) + ". Rerun this script when that stage has written its file.")
    if dropped:
        notes.append("Not in the total: " + "; ".join(dropped) + ". The other weights were rescaled to 100.")
    notes.append(f"Weights from {wsrc}: " + ", ".join(f"{lbl.lower()} {weights[k]:g}" for k, lbl in STAGES) + ".")

    md = ["# Decision table", "",
          "Recorded results only, each from the file its stage wrote. Scores organise evidence; they are not validated "
          "predictions. A score is never a reason to stop thinking.", ""]
    md += ["- " + n for n in notes]
    md += ["", "| Finalist | " + " | ".join(f"{lbl} ({eff[k]}%)" if k in active else lbl for k, lbl in STAGES) + " | Total (0 to 100) |",
           "|---|" + "---|" * len(STAGES) + "---|"]
    for f in finalists:
        s = f["slug"]
        cells = [(per[s][k]["text"] if per[s][k] else ("not run for this finalist" if srcs.get(k) else "not found")) for k, _ in STAGES]
        md.append(f"| {f['name']} | " + " | ".join(c.replace("|", "/") for c in cells) + " | "
                  + ("hidden" if hide_total or total[s] is None else f"**{total[s]}**") + " |")
    sealed = dc.get("sealed") if isinstance(dc.get("sealed"), dict) else None
    chal = dc.get("challenge") if isinstance(dc.get("challenge"), dict) else None
    names = {f["slug"]: f["name"] for f in finalists}
    md += ["", "## Sealed preference, then the Decision Challenge", ""]
    if sealed:
        md.append(f"- Sealed {sealed.get('written_at', '')} by {sealed.get('by') or 'the founder'}, before Claude's view: "
                  f"{names.get(sealed.get('prefer'), sealed.get('prefer', ''))}. Why: {sealed.get('why', '')}")
        if chal:
            md.append(f"- Challenge written {chal.get('written_at', '')}: " + ", ".join(
                f"{len(chal.get(k) or [])} {lbl}" for k, lbl in (("for", "for"), ("against", "against"),
                                                                 ("missing", "missing evidence"), ("next_check", "next checks")))
                      + ". See challenge/DECISION-CHALLENGE.html.")
    else:
        md.append("- Not sealed yet: python3 decision_challenge.py seal --prefer <slug> --why \"...\"")
    md += ["", "## Decision", ""] + [f"- {f['name']}: {(review.get(f['slug']) or {}).get('decision') or 'open'}" for f in finalists]
    text = "\n".join(md) + "\n"
    no_dashes(text, "DECISION.md")
    out = root / "out" / "DECISION.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}")
    for k, lbl in STAGES:
        print(f"  {lbl}: " + (srcs[k] or "no file found"))
    for n in notes:
        print("note: " + n)
    if not hide_total:
        for f in sorted(finalists, key=lambda f: -(total[f["slug"]] or 0)):
            print(f"  {f['name']}: {total[f['slug']]}")


if __name__ == "__main__":
    main()
