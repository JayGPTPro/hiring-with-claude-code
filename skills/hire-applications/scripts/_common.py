"""Shared helpers for the questionnaire step and the budget reader. Standard library only."""
import html
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _today  # noqa: E402  (same folder)

DEFAULT_HOURS = "Could you make time for regular overlap with the founder's working hours?"


def find_root(arg=None):
    """The hiring project root: the folder that holds criteria.md.

    Without --root: "." when ./criteria.md exists, "./hiring" when ./hiring/criteria.md exists,
    otherwise exit and name both. With --root: that folder, or its hiring/ child.
    """
    here = Path(arg) if arg else Path(".")
    for cand in (here, here / "hiring"):
        if (cand / "criteria.md").is_file():
            return cand
    sys.exit("no criteria.md in %s or %s. Run this from your hiring/ folder (the one that holds "
             "criteria.md) or from the folder above it, or pass --root path/to/hiring."
             % (here / "criteria.md", here / "hiring" / "criteria.md"))


def project_today(root, given=None):
    """The date to stamp: --today, else today.txt in the hiring folder, else the computer clock."""
    day, source = _today.project_today(str(root), given)
    _today.say_source(day, source)
    return day, source


# The hard maximum, in the words people use. "Target" lines are read separately.
MAX_RE = re.compile(r"(?:hard\s*max\w*|\bmaximum\b|\bmax\b|\bceiling\b|\bcap\b|\bupper limit\b|"
                    r"\bthe most (?:i|we) (?:will|would|can|could) (?:ever )?(?:pay|offer|go(?: up)?(?: to)?|spend)\b|"
                    r"\bno more than\b|\bnot (?:a cent|a dollar|anything) (?:more|above)\b)"
                    r"[^\d$\n]{0,40}\$?\s*([\d,]{3,7})", re.I)
TARGET_RE = re.compile(r"target[^\d$\n]{0,20}\$?\s*([\d,]{3,7})\s*(?:to|-|and)\s*\$?\s*([\d,]{3,7})", re.I)


def budget_numbers(text):
    """(target (low, high) or None, hard max or None) from the text of criteria.md. The "## Budget" section is
    read first, so a "maximum" elsewhere in the file (hours, units) is not taken for the pay ceiling."""
    budget = "\n".join(section(text.splitlines(), "budget"))
    out = []
    for rx in (TARGET_RE, MAX_RE):
        m = rx.search(budget) or rx.search(text)
        out.append(m)
    t, h = out
    return ((int(t.group(1).replace(",", "")), int(t.group(2).replace(",", ""))) if t else None,
            int(h.group(1).replace(",", "")) if h else None)


def area_list(text):
    """Split an areas line into areas: commas, with a last 'and' allowed ("A, B and C")."""
    parts = [a.strip(" .;") for a in re.split(r",|;", text)]
    if len(parts) > 1 and re.match(r"(?i)^and\s+", parts[-1]):
        parts[-1] = parts[-1][4:]
    return [a for a in parts if a]


def read_criteria(path):
    """Pull the role title, the areas, the budget and the hours line out of hiring/criteria.md.

      role    the first "# " heading (a "Hiring criteria:" prefix is dropped)
      areas   a line with "areas:" and a comma list, which may wrap onto the next lines; or "areas:" followed by
              a bulleted list; or a "## Areas" section with bullets
      budget  a target range ("Target: $1,500 to $2,500") and a hard maximum ("hard max", "maximum",
              "the most I will ever pay", "ceiling")
      hours   a line starting with "Hours:" or "Overlap:" (optional)
    """
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    out = {"role": "The role", "areas": [], "target": None, "hard_max": None, "hours": DEFAULT_HOURS}

    for ln in lines:
        if ln.startswith("# "):
            out["role"] = re.sub(r"(?i)^hiring criteria:\s*", "", ln[2:].strip())
            break

    for i, ln in enumerate(lines):
        m = re.match(r"(?i)^(?!\s*#).*?\bareas?\s*:[ \t]*(.*)$", ln)
        if not m:
            continue
        rest, j = m.group(1).strip(), i + 1
        if rest:  # a list that wraps: read on until the sentence ends, or a blank line, bullet, heading or "Key:"
            while (j < len(lines) and lines[j].strip() and not rest.rstrip().endswith((".", ":", "!", "?"))
                   and not re.match(r"^\s*([-*#]|\d+[.)]|[A-Za-z][\w ]{0,30}:)", lines[j])):
                rest += " " + lines[j].strip()
                j += 1
            out["areas"] = area_list(rest)
        else:  # "Areas:" then a bulleted list
            while j < len(lines) and (re.match(r"^\s*([-*]|\d+[.)])\s+\S", lines[j]) or (not lines[j].strip() and not out["areas"])):
                if lines[j].strip():
                    out["areas"].append(re.sub(r"^\s*([-*]|\d+[.)])\s+", "", lines[j]).strip(" ."))
                j += 1
        if out["areas"]:
            break
    if not out["areas"]:
        sec = section(lines, "areas")
        out["areas"] = [re.sub(r"^[-*\d.)\s]+", "", s).strip() for s in sec if re.match(r"^\s*[-*\d]", s)]

    out["target"], out["hard_max"] = budget_numbers(text)

    m = re.search(r"(?im)^\s*(?:-\s*)?(?:hours|overlap):\s*(.+)$", text)
    if m:
        out["hours"] = m.group(1).strip()
    return out


def section(lines, name):
    """Lines under the first '## <name>' heading (case-insensitive prefix match)."""
    grab, body = False, []
    for ln in lines:
        if ln.startswith("## "):
            if grab:
                break
            grab = ln[3:].strip().lower().startswith(name)
            continue
        if grab:
            body.append(ln)
    return body


def budget_line(c):
    if c["target"]:
        return ("The starting budget for this role is ${:,} to ${:,} a month. If you expect more, "
                "say so. I would rather know now than waste your time.").format(*c["target"])
    return "Give the number you would be happy with."


def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "candidate"


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def is_demo(root):
    """True when criteria.md says FICTIONAL DEMO. Every page then carries the demo badge."""
    p = Path(root) / "criteria.md"
    return p.is_file() and "FICTIONAL DEMO" in p.read_text(encoding="utf-8").upper()


BADGE_CSS = (".badge-demo{position:fixed;top:16px;right:16px;z-index:50;background:#111827;color:#fff;font-weight:800;"
             "font-size:26px;letter-spacing:.06em;padding:10px 20px;border-radius:10px;white-space:nowrap;"
             "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}"
             "@media (max-width:700px){.badge-demo{font-size:18px;padding:6px 10px;top:8px;right:8px}}")
BADGE_HTML = '<div class="badge-demo" aria-label="Fictional demo data">FICTIONAL DEMO</div>'
