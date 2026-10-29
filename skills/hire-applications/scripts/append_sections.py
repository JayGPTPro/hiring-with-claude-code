#!/usr/bin/env python3
"""Append each filled "Questionnaire" section to the candidate's dossier.

Reads   hiring/out/questionnaire/<slug>-section.md   (written by compare.py, filled by Claude)
Writes  hiring/out/candidates/<slug>.md               appends the section; creates a stub dossier if missing
        hiring/out/scores.json                        the questionnaire TRACK ("TRACK: n/50"), the two areas they
                                                      picked, and SHARED when the section says "revised to n/50".
                                                      The screening numbers are kept under "screening", so the
                                                      second pass and the decision table still compare like with like.

A section that still contains a "__" placeholder is skipped and listed, so an unscored draft never
lands in a dossier. A dossier that already has a "## Questionnaire" heading is skipped too
(delete that part of the dossier by hand if you want it replaced).

Run from your hiring/ folder (the one that holds criteria.md), or from the folder above it:
  python3 path/to/append_sections.py            (--root path/to/hiring overrides)
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_root, project_today  # noqa: E402

STUB = """# {name}

## Card
- Name: {name}
- Location: {location}
- Ask: {ask}
- Availability: {availability}
- Source: questionnaire (not screened yet)
- Date: {today}

## Evidence
(no screening notes yet; see Questionnaire below)

## Scores
- SHARED: not scored yet
- TRACK: see Questionnaire

## Flags
(none recorded yet)

## Questions for the call
(see Questionnaire)

## Status
- Status: questionnaire
- Reason: questionnaire received before screening
- Attention: Screen the application before the next step

## Log
- {today}: dossier created by append_sections.py from the questionnaire

"""


def field(text, label):
    m = re.search(r"^Received .*?$", text, re.M)
    head = m.group(0) if m else ""
    m = re.search(label + r"\s*([^.]*)", head)
    return m.group(1).strip() if m else ""


def section_scores(text):
    """(TRACK, revised SHARED or None, [the two picked areas]) from a filled section."""
    num = lambda m: int(float(m.group(1)) + 0.5) if m else None
    track = num(re.search(r"^TRACK:\s*(\d+(?:\.\d+)?)\s*/\s*50", text, re.M))
    shared = num(re.search(r"SHARED:\s*revised to\s*(\d+(?:\.\d+)?)\s*/\s*50", text))
    areas = re.findall(r"^\d+\.\s+\*\*(.+?)\*\*", text, re.M)[:2]
    return track, shared, areas


def update_scores(scores, slug, text):
    """Write the questionnaire TRACK into this candidate's scores.json entry. Returns the Log text, or a reason."""
    track, shared, areas = section_scores(text)
    if track is None:
        return None, "no 'TRACK: n/50' line, scores.json left as it was"
    c = next((c for c in (scores or {}).get("candidates", []) if isinstance(c, dict) and c.get("slug") == slug), None)
    if c is None:
        return None, "not in out/scores.json, add it there after screening"
    c.setdefault("screening", {"shared": c.get("shared"), "track": c.get("track"),
                               "strongest_areas": list(c.get("strongest_areas") or [])})
    said = ["TRACK %s to %s" % (c.get("track"), track)]
    c["track"] = track
    if shared is not None:
        said.append("SHARED %s to %s" % (c.get("shared"), shared))
        c["shared"] = shared
    if len(areas) == 2:
        c["strongest_areas"] = areas
        said.append("areas " + ", ".join(areas))
    return "scores.json " + "; ".join(said), None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD for the Log lines (default: today.txt, else today)")
    args = ap.parse_args()
    root = find_root(args.root)
    src_dir = root / "out" / "questionnaire"
    dst_dir = root / "out" / "candidates"
    today = project_today(root, args.today)[0].isoformat()
    sections = sorted(src_dir.glob("*-section.md"))
    if not sections:
        sys.exit(f"no *-section.md files in {src_dir}. Run compare.py first.")
    dst_dir.mkdir(parents=True, exist_ok=True)  # only after the inputs checked out
    scores_path = root / "out" / "scores.json"
    scores = json.loads(scores_path.read_text(encoding="utf-8")) if scores_path.exists() else None
    done, skipped, changed = 0, [], False
    for p in sections:
        text = p.read_text(encoding="utf-8")
        slug = p.name[: -len("-section.md")]
        if "__" in text:
            skipped.append(f"{p.name}: still has __ placeholders")
            continue
        dossier = dst_dir / f"{slug}.md"
        if dossier.exists():
            body = dossier.read_text(encoding="utf-8")
            if re.search(r"^## Questionnaire\s*$", body, re.M):
                skipped.append(f"{p.name}: {dossier.name} already has a Questionnaire section")
                continue
            if not body.endswith("\n"):
                body += "\n"
            body += "\n" + text.rstrip() + "\n"
            said, why_not = update_scores(scores, slug, text)
            log = f"- {today}: questionnaire section appended" + (f"; {said}" if said else "")
            body = re.sub(r"(^## Log\s*\n(?:.*\n)*?)(?=\n## |\Z)",
                          lambda m: m.group(1).rstrip("\n") + "\n" + log + "\n", body, count=1, flags=re.M)
            dossier.write_text(body, encoding="utf-8")
            print(f"appended  {dossier}")
            print(f"          {said}" if said else f"          {slug}: {why_not}")
            changed = changed or bool(said)
        else:
            name = slug.replace("-", " ").title()
            stub = STUB.format(name=name, location=field(text, "Location:") or "see questionnaire",
                               ask=field(text, "Ask") or "see questionnaire",
                               availability=field(text, "Availability:") or "see questionnaire", today=today)
            dossier.write_text(stub + text.rstrip() + "\n", encoding="utf-8")
            print(f"created   {dossier} (stub + section)")
        done += 1
    if changed:
        scores_path.write_text(json.dumps(scores, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote     {scores_path} (questionnaire TRACK; screening numbers kept under \"screening\")")
    print(f"\n{done} dossiers updated")
    for s in skipped:
        print("skipped   " + s)


if __name__ == "__main__":
    main()
