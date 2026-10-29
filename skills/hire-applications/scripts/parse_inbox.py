#!/usr/bin/env python3
"""Read hiring/inbox/ into one JSON file of applications.

Run from the hiring project root (the folder that holds criteria.md, inbox/, out/), or from the
folder above it:

    python3 path/to/parse_inbox.py            # uses the current folder
    python3 path/to/parse_inbox.py --root .   # same

Then run redact.py: the scoring reads the blind copies in out/blind/, not this file.

Input, one application per file in inbox/:
    <slug>.md          the message as text, with a short header (see below)
    <slug>-cv.txt      the CV as plain text (optional; .pdf is noted but not read)

Header lines come first, one per line, then a blank line, then the message:
    Name: Ana Petrescu
    Location: Cluj-Napoca, Romania
    Ask: $2,000 a month
    Source: application form
    Date: 2026-10-12
    Availability: full time, 2 weeks notice

Output:
    out/applications.json   every application with its header, message, CV text and hints
    out/COVERAGE.md         what was read, what is missing, what to fix

Standard library only. No network. Nothing is sent anywhere.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _today  # noqa: E402  (same folder)
import _common  # noqa: E402

HEADER_KEYS = {"name", "location", "ask", "source", "date", "availability"}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

RANGE_RE = re.compile(
    r"(?:(?P<m1>[A-Za-z]{3,9})\.?\s+)?(?P<y1>(?:19|20)\d{2})\s*"
    r"(?:-|to|until|till)\s*"
    r"(?:(?P<m2>[A-Za-z]{3,9})\.?\s+)?(?P<y2>(?:19|20)\d{2}|present|now|current|today)",
    re.IGNORECASE)


def message_files(inbox):
    """The application messages in inbox/: <slug>.md or <slug>.txt, never the <slug>-cv files."""
    return [f for f in sorted(os.listdir(inbox)) if re.search(r"\.(md|txt)$", f) and not re.search(r"-cv\.(md|txt)$", f)]


def slug_to_name(slug):
    return " ".join(p.capitalize() for p in slug.split("-"))


def parse_header(text):
    """Split 'Key: value' lines from the body. Returns (fields, body, unknown_keys)."""
    lines = text.splitlines()
    fields, unknown = {}, []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            break
        m = re.match(r"^([A-Za-z][A-Za-z ]{0,30}):\s*(.*)$", line)
        if not m:
            break
        key = m.group(1).strip().lower()
        if key in HEADER_KEYS:
            fields[key] = m.group(2).strip()
        else:
            unknown.append(key)
            fields.setdefault("extra", {})[key] = m.group(2).strip()
        i += 1
    body = "\n".join(lines[i:]).strip()
    return fields, body, unknown


def parse_ask(text):
    """Return (amount, currency, period, note). Amount is the first number of 3+ digits."""
    if not text:
        return None, None, None, "no ask given"
    t = text.replace(",", "")
    currency = "USD"
    if "€" in text or re.search(r"\beur\b", text, re.I):
        currency = "EUR"
    elif "£" in text or re.search(r"\bgbp\b", text, re.I):
        currency = "GBP"
    period = "month"
    if re.search(r"\b(hour|hr|hourly)\b", text, re.I):
        period = "hour"
    elif re.search(r"\b(year|annual|yearly|pa)\b", text, re.I):
        period = "year"
    m = re.search(r"(\d+(?:\.\d+)?)\s*[kK]\b", t)
    if m:
        amount = int(float(m.group(1)) * 1000)
    else:
        nums = [int(n) for n in re.findall(r"\d{3,6}", t)]
        amount = nums[0] if nums else None
    note = ""
    if amount is None:
        note = "could not read a number from the ask"
    elif currency != "USD":
        note = "ask is in %s, convert to USD by hand before judging budget fit" % currency
    elif period != "month":
        note = "ask is per %s, convert to a monthly figure by hand" % period
    if len(re.findall(r"\d{3,6}", t)) > 1 and not note:
        note = "ask looks like a range; the first number was used"
    return amount, currency, period, note


def read_criteria(root):
    """Pull the budget numbers and the role name out of criteria.md. Missing parts are None."""
    path = os.path.join(root, "criteria.md")
    out = {"role": None, "target_usd": None, "hard_max_usd": None, "file": "criteria.md" if os.path.exists(path) else None}
    if not os.path.exists(path):
        return out
    text = open(path, encoding="utf-8").read()
    m = re.search(r"^#\s*(?:hiring criteria:\s*)?(.+)$", text, re.I | re.M)
    if m:
        out["role"] = m.group(1).strip()
    target, hard = _common.budget_numbers(text)
    out["hard_max_usd"] = hard
    out["target_usd"] = list(target) if target else None
    return out


def budget_fit(amount, currency, period, criteria):
    if amount is None or currency != "USD" or period != "month":
        return "unknown"
    hard = criteria.get("hard_max_usd")
    target = criteria.get("target_usd")
    if hard is None and target is None:
        return "unknown (no budget in criteria.md)"
    if hard is not None and amount > hard:
        return "out of budget"
    if target is not None:
        if amount <= target[1]:
            return "in target"
        if hard is not None:
            return "above target, under max"
    if hard is None:
        return "unknown (above target, and no hard maximum found in criteria.md)"
    return "under max"


def month_index(month_word, year, default_month):
    if month_word:
        key = month_word[:3].lower()
        if key in MONTHS:
            return int(year) * 12 + MONTHS[key] - 1
    return int(year) * 12 + default_month - 1


EDU_RE = re.compile(r"\b(university|universit|college|school|bsc|ba\b|ma\b|msc|mba|bba|degree|diploma|bachelor|master)", re.I)


def cv_date_ranges(cv_text, today):
    """Find 'Mar 2019 - Jun 2021' style ranges on job lines and flag overlaps of 2+ months.

    Bullet lines and education lines are skipped. A year-only range ('2015 - 2017') is read in
    its narrowest sense (Dec 2015 to Jan 2017) so two jobs that touch at a year boundary do not
    count as an overlap. This is a hint for a question, never a verdict.
    """
    ranges = []
    for line in cv_text.splitlines():
        s = line.strip()
        if not s or s[0] in "-*•" or EDU_RE.search(s):
            continue
        m = RANGE_RE.search(s)
        if not m:
            continue
        start = month_index(m.group("m1"), m.group("y1"), 12)
        y2 = m.group("y2")
        if y2.isdigit():
            end = month_index(m.group("m2"), y2, 1)
        else:
            end = today.year * 12 + today.month - 1
        if end < start:
            continue
        ranges.append({"line": s[:120], "start": start, "end": end})
    overlaps = []
    for i in range(len(ranges)):
        for j in range(i + 1, len(ranges)):
            a, b = ranges[i], ranges[j]
            months = min(a["end"], b["end"]) - max(a["start"], b["start"]) + 1
            if months >= 2:
                overlaps.append({"a": a["line"], "b": b["line"], "months": months})
    return [r["line"] for r in ranges], overlaps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="hiring project root (holds criteria.md, inbox/, out/)")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, used for 'present' in CV dates")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(os.path.join(root, "inbox")) and os.path.isdir(os.path.join(root, "hiring", "inbox")):
        root = os.path.join(root, "hiring")  # run from the folder above hiring/ works too
    inbox = os.path.join(root, "inbox")
    out_dir = os.path.join(root, "out")
    if not os.path.isdir(inbox):
        sys.exit("no inbox/ folder under %s. Run this from the hiring project root." % root)
    os.makedirs(out_dir, exist_ok=True)
    today, source = _today.project_today(root, args.today)
    _today.say_source(today, source)

    criteria = read_criteria(root)

    applications, coverage, problems = [], [], []
    if criteria.get("file") and criteria.get("hard_max_usd") is None:
        problems.append("criteria.md: no hard maximum found. Add a line such as \"Hard max: $3,000 a month\" under "
                        "## Budget; until then an ask above the target reads as budget fit unknown")
    for fname in message_files(inbox):
        slug = re.sub(r"\.(md|txt)$", "", fname)
        text = open(os.path.join(inbox, fname), encoding="utf-8", errors="replace").read()
        fields, body, unknown = parse_header(text)
        name = fields.get("name") or slug_to_name(slug)
        amount, currency, period, ask_note = parse_ask(fields.get("ask", ""))
        fit = budget_fit(amount, currency, period, criteria)

        cv_text, cv_file, cv_note = None, None, "no CV in inbox"
        for ext in ("txt", "md"):
            cand = os.path.join(inbox, "%s-cv.%s" % (slug, ext))
            if os.path.exists(cand):
                cv_text = open(cand, encoding="utf-8", errors="replace").read().strip()
                cv_file = os.path.basename(cand)
                cv_note = "read"
                break
        if cv_text is None:
            for ext in ("pdf", "docx", "doc"):
                cand = os.path.join(inbox, "%s-cv.%s" % (slug, ext))
                if os.path.exists(cand):
                    cv_file = os.path.basename(cand)
                    cv_note = "%s not read: convert it to %s-cv.txt first (pdftotext works) or read it in the session" % (cv_file, slug)
                    problems.append("%s: %s" % (slug, cv_note))
                    break

        cv_lines, overlaps = cv_date_ranges(cv_text, today) if cv_text else ([], [])
        missing = [k for k in ("name", "location", "ask", "source", "date") if not fields.get(k)]
        if missing:
            problems.append("%s: header is missing %s" % (slug, ", ".join(missing)))
        if ask_note:
            problems.append("%s: %s" % (slug, ask_note))
        if unknown:
            problems.append("%s: unknown header keys kept under extra: %s" % (slug, ", ".join(unknown)))

        app = {
            "slug": slug,
            "name": name,
            "location": fields.get("location", ""),
            "ask_text": fields.get("ask", ""),
            "ask_usd": amount if currency == "USD" and period == "month" else None,
            "ask_amount": amount,
            "ask_currency": currency,
            "ask_period": period,
            "budget_fit": fit,
            "source": fields.get("source", ""),
            "date": fields.get("date", ""),
            "availability": fields.get("availability", ""),
            "message_file": fname,
            "message": body,
            "message_words": len(body.split()),
            "cv_file": cv_file,
            "cv_text": cv_text,
            "cv_words": len(cv_text.split()) if cv_text else 0,
            "hints": {
                "cv_date_lines": cv_lines,
                "cv_date_overlaps": overlaps,
                "no_cv": cv_text is None,
                "ask_note": ask_note,
            },
        }
        if "extra" in fields:
            app["extra"] = fields["extra"]
        applications.append(app)
        coverage.append((slug, name, fields.get("date", ""), fields.get("source", ""),
                         fields.get("ask", "") or "(none)", fit, cv_note, len(overlaps)))

    result = {
        "generated": today.isoformat(),
        "inbox": "inbox/",
        "criteria": criteria,
        "count": len(applications),
        "applications": applications,
    }
    json_path = os.path.join(out_dir, "applications.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    cov_path = os.path.join(out_dir, "COVERAGE.md")
    with open(cov_path, "w", encoding="utf-8") as f:
        f.write("# Coverage: what parse_inbox.py read\n\n")
        f.write("Generated %s from `inbox/`. Read only. Nothing was sent to anyone.\n\n" % today.isoformat())
        f.write("Role: %s. Budget target: %s. Hard max: %s.\n\n" % (
            criteria.get("role") or "(not found in criteria.md)",
            ("$%s to $%s" % tuple(criteria["target_usd"])) if criteria.get("target_usd") else "(not found)",
            ("$%s" % criteria["hard_max_usd"]) if criteria.get("hard_max_usd") else "(not found)"))
        f.write("| Slug | Name | Date | Source | Ask | Budget fit | CV | CV date overlaps |\n|---|---|---|---|---|---|---|---|\n")
        for row in coverage:
            f.write("| " + " | ".join(str(c) for c in row) + " |\n")
        f.write("\n## To fix before judging\n")
        if problems:
            for p in problems:
                f.write("- %s\n" % p)
        else:
            f.write("- Nothing. Every file parsed.\n")
        f.write("\n## Not covered\n- Files that are not .md or .txt in inbox/ were ignored.\n")
        f.write("- A CV date overlap is a hint for a question, never a verdict. Two part-time roles can overlap.\n")

    print("read %d applications from %s" % (len(applications), inbox))
    for row in coverage:
        print("  %-22s ask %-14s %-26s CV: %s%s" % (row[0], row[4], row[5], row[6],
                                                   ("  date overlaps: %d" % row[7]) if row[7] else ""))
    print("wrote %s" % json_path)
    print("wrote %s" % cov_path)
    if problems:
        print("%d things to fix, listed in COVERAGE.md" % len(problems))


if __name__ == "__main__":
    main()
