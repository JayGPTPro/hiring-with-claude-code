"""The date the hire-applications scripts stamp. Standard library only.

In order: the --today flag when given; else the one date in today.txt in the hiring folder (for a demo, or a
folder you are catching up on after the fact); else the computer clock.
"""
import os
import sys
from datetime import date


def project_today(root, given=None):
    """Return (date, where it came from)."""
    if given:
        try:
            return date.fromisoformat(given), "--today"
        except ValueError:
            sys.exit("--today must look like 2026-10-16")
    path = os.path.join(root, "today.txt")
    if os.path.exists(path):
        lines = open(path, encoding="utf-8-sig").read().strip().splitlines()
        first = lines[0].strip() if lines else ""
        try:
            return date.fromisoformat(first[:10]), "today.txt"
        except ValueError:
            sys.exit("%s: put one date like 2026-10-16 on the first line, or remove the file to use "
                     "the computer's date." % path)
    return date.today(), "the computer clock"


def say_source(day, source):
    """One line when the date is not the computer's, so a back-dated run is never a surprise."""
    if source == "today.txt":
        print("date: %s (from today.txt)" % day.isoformat())
