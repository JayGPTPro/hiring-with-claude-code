#!/usr/bin/env python3
"""Write the questionnaire as plain text you paste into a Google Form (or an email).

Reads   hiring/criteria.md   role, areas, budget, the "Hours:" line, and an optional "Situation question:" line
Writes  hiring/questionnaire/QUESTIONNAIRE.md

    python3 make_questionnaire.py --situation "A weekly PPC report has fewer rows than the Ads console. What would you check?"
    python3 make_questionnaire.py --force      overwrite an existing QUESTIONNAIRE.md

Run from your hiring/ folder or the folder above it (--root path/to/hiring overrides). The situation question is
one short case from the real job, answerable in about five minutes with no file to open. Standard library only.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import budget_line, find_root, read_criteria  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "QUESTIONNAIRE.md"
SITUATION_HINT = "About five minutes. A few lines are enough. This is a thinking sample, not a task: there is no file to open."


def situation_from(args, root):
    if args.situation:
        return args.situation.strip()
    m = re.search(r"(?im)^\s*(?:-\s*)?situation question:\s*(.+)$", (root / "criteria.md").read_text(encoding="utf-8"))
    return m.group(1).strip() if m else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    ap.add_argument("--situation", default=None, help="the one short situation question from this job")
    ap.add_argument("--force", action="store_true", help="overwrite QUESTIONNAIRE.md if it exists")
    args = ap.parse_args()
    root = find_root(args.root)
    c = read_criteria(root / "criteria.md")
    if len(c["areas"]) < 2:
        sys.exit("could not find the areas in criteria.md. Add a line like\n  Areas: Listings, PPC and reporting, SOPs\n"
                 "or a list under a line that says Areas:, one bullet per area.")
    sit = situation_from(args, root)
    n = 10
    sit_block = ""
    if sit:
        sit_block = ("Q10. One short situation, about five minutes: %s\n    Answer type: Paragraph. Required.\n"
                     "    Help text: %s" % (sit, SITUATION_HINT))
        n = 11
    fill = {"__ROLE__": c["role"], "__BUDGET_LINE__": budget_line(c), "__HOURS_LINE__": c["hours"],
            "__AREA_ROWS__": "\n".join("      %s" % a for a in c["areas"]), "__SITUATION_BLOCK__": sit_block,
            "__PART3_TITLE__": "One short situation, then practical fit" if sit else "Practical fit"}
    for i in range(5):
        fill["__N%d__" % (i + 1)] = str(n + i)
    text = TEMPLATE.read_text(encoding="utf-8")
    for k, v in fill.items():
        text = text.replace(k, v)
    text = re.sub(r"\n{3,}", "\n\n", text)
    left = sorted(set(re.findall(r"__[A-Z0-9_]+__", text)))
    if left:
        sys.exit("QUESTIONNAIRE.md: placeholders left unfilled: " + ", ".join(left))
    dst = root / "questionnaire" / "QUESTIONNAIRE.md"
    if dst.exists() and not args.force:
        print("kept    %s (use --force to overwrite)" % dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")
        print("wrote   %s" % dst)
    print("role:   %s\nareas:  %d: %s" % (c["role"], len(c["areas"]), ", ".join(c["areas"])))
    print("budget: target %s, hard max %s" % (c["target"], c["hard_max"]))
    print("situation question: %s" % (sit or "none (pass --situation \"...\")"))
    print("next: show QUESTIONNAIRE.md to the founder; nothing goes out until they say so.")


if __name__ == "__main__":
    main()
