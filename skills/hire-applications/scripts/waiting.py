#!/usr/bin/env python3
"""Who has been waiting on you for too long.

Run from the hiring project root (the folder that holds criteria.md and out/), or from the
folder above it:

    python3 path/to/waiting.py                 # list everyone waiting more than 5 days
    python3 path/to/waiting.py --days 3
    python3 path/to/waiting.py --today 2026-10-26

Reads  out/candidates/<slug>.md   the Card (Date) and the Log of each dossier
Prints the waiting list. Writes nothing; build_board.py puts the same list in SUMMARY.md and on
the board.

How the clock works, from the Log lines (keep the wording below and it just works):
  - The clock starts at the application date in the Card.
  - A Log line that says you sent something ("Invite sent", "Decline sent", "Replied with times")
    stops the clock: the candidate is no longer waiting on you. "Nothing sent" does not count.
  - A Log line where the ball comes back to you restarts the clock from that date:
    "candidate replied", "answers received", "interview held", "challenge received".
  - Status hired or closed takes the person off the list.

Standard library only. No network.
"""
import argparse
import glob
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _today  # noqa: E402  (same folder)

NOT_SENT = re.compile(r"\b(nothing|not|never|un)\s*sent\b|\bno reply sent\b", re.I)
SENT = re.compile(r"\b(sent|replied|reply went out|answered the candidate)\b", re.I)
BACK_TO_YOU = re.compile(
    r"\bcandidate (replied|answered|wrote|sent|asked)\b|\b(answers?|questionnaire|responses?|submission|challenge|cv) received\b"
    r"|\binterview(ed| held| done)\b|\bcall (held|done)\b|\bwaiting on (us|me|the founder)\b", re.I)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def find_root(start):
    root = os.path.abspath(start)
    if os.path.isdir(os.path.join(root, "out")) or os.path.exists(os.path.join(root, "criteria.md")):
        return root
    if os.path.isdir(os.path.join(root, "hiring")):
        return os.path.join(root, "hiring")
    return root


def parse_date(s):
    m = DATE_RE.search(s or "")
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def read_dossier(path):
    text = open(path, encoding="utf-8").read()
    sections, current = {}, "_top"
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip().lower()
            sections[current] = []
        else:
            sections.setdefault(current, []).append(line)

    def kv(section):
        d = {}
        for line in sections.get(section, []):
            m = re.match(r"^\s*[-*]\s*([^:]+):\s*(.*)$", line)
            if m:
                d[m.group(1).strip().lower()] = m.group(2).strip()
        return d

    card, status = kv("card"), kv("status")
    name = card.get("name") or text.splitlines()[0].lstrip("# ").strip()
    log = [l.strip() for l in sections.get("log", []) if l.strip().startswith(("-", "*"))]
    return {"slug": os.path.splitext(os.path.basename(path))[0], "name": name,
            "applied": parse_date(card.get("date", "")), "status": status.get("status", "").lower(),
            "log": log}


def waiting_since(d):
    """Return (since_date, last_line) if the candidate waits on you, else (None, reason)."""
    if d["status"] in ("hired", "closed"):
        return None, "status %s" % d["status"]
    since, last = d["applied"], "application"
    for line in d["log"]:
        when = parse_date(line) or since
        if BACK_TO_YOU.search(line):
            since, last = when, line.lstrip("-* ").strip()
            continue
        if SENT.search(line) and not NOT_SENT.search(line):
            since, last = None, line.lstrip("-* ").strip()
    if since is None:
        return None, last
    return since, last


def reply_sent(d):
    """True when the last Log line that moves the clock says you sent something: the candidate has an answer."""
    sent = False
    for line in d["log"]:
        if BACK_TO_YOU.search(line):
            sent = False
        elif SENT.search(line) and not NOT_SENT.search(line):
            sent = True
    return sent


def waiting_list(root, today, days):
    rows = []
    for path in sorted(glob.glob(os.path.join(root, "out", "candidates", "*.md"))):
        d = read_dossier(path)
        since, last = waiting_since(d)
        if since is None:
            continue
        waited = (today - since).days
        if waited > days:
            rows.append({"slug": d["slug"], "name": d["name"], "status": d["status"], "days": waited,
                         "since": since.isoformat(), "last": last})
    rows.sort(key=lambda r: -r["days"])
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="hiring project root, or the folder above it")
    ap.add_argument("--days", type=int, default=5, help="list people waiting more than this many days")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, default is today")
    args = ap.parse_args()
    root = find_root(args.root)
    if not glob.glob(os.path.join(root, "out", "candidates", "*.md")):
        sys.exit("no dossiers in %s/out/candidates/. Run hire-applications first." % root)
    today, source = _today.project_today(root, args.today)
    _today.say_source(today, source)
    rows = waiting_list(root, today, args.days)
    if not rows:
        print("nobody has waited on you for more than %d days. Good." % args.days)
        return
    print("waiting on you for more than %d days (%s):" % (args.days, today.isoformat()))
    for r in rows:
        print("  %2d days  %-22s %-14s since %s, last log: %s" % (r["days"], r["name"], r["status"] or "?", r["since"], r["last"][:70]))
    print("drafts for each status are in out/messages/. Read, edit, send; then add a Log line such as "
          "\"%s Decline sent.\" and the clock stops." % today.isoformat())
    print("nothing written; build_board.py puts this list in SUMMARY.md and on the board.")


if __name__ == "__main__":
    main()
