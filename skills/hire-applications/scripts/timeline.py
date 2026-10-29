#!/usr/bin/env python3
"""Draft the "what happens next, and when" message for a shortlisted candidate.

Candidates who know the next steps and the dates wait better and drop out less. This writes one
draft per slug with four steps (questionnaire, interview, test task, decision) and their
dates. It never sends anything: you read the draft and send it from your own account.

Reads   hiring/questionnaire/timeline.json   the dates and your name (format below; written for you
                                              on the first run if it is missing)
        hiring/out/applications.json or the dossiers, for the first name (optional)
        hiring/criteria.md                    the role title
Writes  hiring/out/messages/<slug>-timeline.md

Run from your hiring/ folder (the one that holds criteria.md), or from the folder above it:
  python3 path/to/timeline.py ana-petrescu [more slugs]   (--root path/to/hiring overrides)

timeline.json:
  {"sign": "Sam",
   "questionnaire_due": "2026-10-16",
   "interviews": ["2026-10-19", "2026-10-20"],
   "work_sample_sent": "2026-10-21", "work_sample_due": "2026-10-26", "work_sample_hours": "about two hours",
   "work_sample_paid": true,
   "decision_by": "2026-10-29"}
  work_sample_paid: true says the task is paid, one fee for everyone; false says it is unpaid and the
  work is not used; left out, the line says neither.

Standard library only. No network.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_root, project_today, read_criteria  # noqa: E402

EXAMPLE = {"_note": "Dates for the candidate timeline message. Change them, then run timeline.py again.",
           "sign": "[your name]", "questionnaire_due": "YYYY-MM-DD", "interviews": ["YYYY-MM-DD", "YYYY-MM-DD"],
           "work_sample_sent": "YYYY-MM-DD", "work_sample_due": "YYYY-MM-DD", "work_sample_hours": "about two hours",
           "work_sample_paid": None, "decision_by": "YYYY-MM-DD"}


PAY_PART = {True: ", paid, one fee for everyone", False: ", unpaid, and I will not use what you make"}


def day(iso):
    d = dt.date.fromisoformat(iso)
    return "%s %d %s" % (d.strftime("%A"), d.day, d.strftime("%B"))


def first_name(root, slug):
    apps = root / "out" / "applications.json"
    if apps.is_file():
        for a in json.loads(apps.read_text(encoding="utf-8")).get("applications", []):
            if a.get("slug") == slug and a.get("name"):
                return a["name"].split()[0]
    dossier = root / "out" / "candidates" / f"{slug}.md"
    if dossier.is_file():
        m = re.search(r"^- Name:\s*(\S+)", dossier.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    return slug.split("-")[0].capitalize()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slugs", nargs="+", help="the shortlisted candidates, by slug")
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD for the draft header (default: today.txt, else today)")
    args = ap.parse_args()
    root = find_root(args.root)
    cfg_path = root / "questionnaire" / "timeline.json"
    if not cfg_path.is_file():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(EXAMPLE, indent=2) + "\n", encoding="utf-8")
        sys.exit(f"wrote {cfg_path} with placeholders. Fill in the dates, your name and work_sample_paid (true or false), then run timeline.py again.")
    t = json.loads(cfg_path.read_text(encoding="utf-8"))
    try:
        q_due, ws_sent, ws_due, decision = (day(t["questionnaire_due"]), day(t["work_sample_sent"]),
                                            day(t["work_sample_due"]), day(t["decision_by"]))
        interviews = [day(d) for d in t["interviews"]]
    except (KeyError, ValueError) as e:
        sys.exit(f"timeline.json: a date is missing or not YYYY-MM-DD ({e}).")
    role = read_criteria(root / "criteria.md")["role"]
    iv = interviews[0] if len(interviews) == 1 else ", ".join(interviews[:-1]) + " or " + interviews[-1]
    out_dir = root / "out" / "messages"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = project_today(root, args.today)[0].isoformat()
    for s in args.slugs:
        name = first_name(root, s)
        text = (
            f"<!-- Draft for {s}, written {today} by timeline.py. Not sent. Read it, change what you want, send it yourself. -->\n\n"
            f"Hi {name},\n\n"
            f"Thank you for applying for the {role} role. Here is the rest of the process, so you know what comes next and when.\n\n"
            f"1. **Questionnaire.** About 20 minutes, the same questions for everyone. Please send it back by {q_due}.\n"
            f"2. **Interview.** A video call of about 45 minutes on {iv}. I will send times once your answers are in.\n"
            f"3. **Test task.** {t.get('work_sample_hours', 'A short task').capitalize()}, the same task for everyone"
            f"{PAY_PART.get(t.get('work_sample_paid'), '')}. I send it on {ws_sent} and it is due {ws_due}.\n"
            f"4. **Decision.** You will hear from me by {decision}, whatever the answer.\n\n"
            "If a date does not work for you, tell me and we will find another one.\n\n"
            "An AI assistant helps me organise the applications. A person makes every decision, and if you would like a human "
            "re-read of anything you sent, just say so.\n\n"
            f"{t.get('sign', '[your name]')}\n")
        if re.search("[\\u2013\\u2014]", text):
            sys.exit("a dash slipped into the draft; fix timeline.json")
        p = out_dir / f"{s}-timeline.md"
        p.write_text(text, encoding="utf-8")
        print(f"wrote   {p} (draft, not sent)")


if __name__ == "__main__":
    main()
