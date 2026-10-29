#!/usr/bin/env python3
"""Render the interview markdown files as large, readable HTML pages. Standard library only, no network.

Usage (from your hiring/ folder or the folder above it):
  python3 <skill>/scripts/md_view.py                  every CANDIDATE_DEBRIEF.md, INTERVIEWER_COACH.md
                                                                       and FOUNDER_SCORES.md under out/interviews/
  python3 <skill>/scripts/md_view.py path/to/file.md  one file
  add --root PATH to point at the hiring folder

Writes <name>.html next to each <name>.md (for example INTERVIEWER_COACH.html). The markdown file stays the
record; the HTML is a view for reading on a screen or a phone. It handles what these files use: headings,
paragraphs, lists, tables, blockquotes, bold, code spans. Every character from the file is escaped first, so
nothing in a transcript quote can become HTML. HTML comments are dropped. A paragraph that is entirely bold
is shown large. Each heading gets an id, so CANDIDATE_DEBRIEF.html#speaker-check-and-disputed-quotes opens at that
section. The FICTIONAL DEMO badge shows when the file says FICTIONAL DEMO.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402
from common import esc  # noqa: E402

NAMES = ("CANDIDATE_DEBRIEF.md", "INTERVIEWER_COACH.md", "FOUNDER_SCORES.md")
EXTRA_CSS = """<style>
main.md{max-width:1500px}
main.md h2{margin-top:34px;padding-top:6px;border-top:3px solid var(--line)}
main.md p.lead{font-size:46px;font-weight:800;line-height:1.15;margin:8px 0 14px;color:var(--acc)}
main.md td{font-size:21px}
main.md .file{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:22px;background:#fff3;padding:2px 10px;border-radius:6px}
</style>"""


SHORT = re.compile(r"\[?\d{1,2}:\d{2}\]?|\d{4}-\d\d-\d\d|\d+")
NOWRAP = ' style="white-space:nowrap"'


def anchor(heading):
    """Heading text to an id: '6. Speaker check and disputed quotes' becomes 'speaker-check-and-disputed-quotes'."""
    words = re.sub(r"^\d+\.\s*", "", heading).lower()
    return re.sub(r"[^a-z0-9]+", "-", words).strip("-")


def inline(text):
    """Escape, then bold and code spans. Order matters: escape first, so input cannot inject tags."""
    t = esc(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])_([^_]+)_(?![\w*])", r"<i>\1</i>", t)
    return t


def render(md):
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.splitlines()
    out, i, title = [], 0, ""
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            level = len(m.group(1))
            if level == 1 and not title:
                title = m.group(2)
            else:
                tag = f"h{min(level + 1, 4) if level > 1 else 2}"
                out.append(f'<{tag} id="{anchor(m.group(2))}">{inline(m.group(2))}</{tag}>')
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
                body = "".join("<tr>" + "".join(
                    f'<td{NOWRAP if SHORT.fullmatch(c) else ""}>{inline(c)}</td>' for c in r) + "</tr>" for r in rows[1:])
                out.append(f"<table><tr>{head}</tr>{body}</table>")
            continue
        if s.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(inline(lines[i].strip()[1:].strip()))
                i += 1
            out.append("<blockquote>" + "<br>".join(quote) + "</blockquote>")
            continue
        if re.match(r"^([-*]|\d+\.)\s+", s):
            tag = "ol" if re.match(r"^\d+\.", s) else "ul"
            items = []
            while i < len(lines) and lines[i].strip() and (re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]) or lines[i].startswith("  ")):
                l = lines[i]
                if re.match(r"^\s*([-*]|\d+\.)\s+", l):
                    items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", l))
                else:
                    items[-1] += " " + l.strip()
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|\||>|[-*]\s|\d+\.\s)", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        text = " ".join(para)
        lead = re.fullmatch(r"\*\*[^*]+\*\*", text) is not None
        out.append(f'<p class="lead">{inline(text)}</p>' if lead else f"<p>{inline(text)}</p>")
    return title, "\n".join(out)


def view(path, root):
    md = open(path, encoding="utf-8").read()
    title, body = render(md)
    rel = os.path.relpath(path, root) if root else os.path.basename(path)
    sub = f"{os.path.basename(path)} · {os.path.dirname(rel)}"
    html_page = common.page(title or os.path.basename(path), sub,
                            EXTRA_CSS + '<main class="md"><div class="card">' + body + "</div></main>",
                            "FICTIONAL DEMO" in md)
    out = os.path.splitext(path)[0] + ".html"
    common.write(out, html_page, out)


def main():
    argv = sys.argv[1:]
    files = [a for a in argv if a.endswith(".md")]
    rest = [a for a in argv if not a.endswith(".md")]
    if files:
        root = None
        try:
            root, _ = common.root_from_argv(rest)
        except SystemExit:
            root = None
        for f in files:
            if not os.path.isfile(f):
                sys.exit(f"not found: {f}")
            view(f, root)
        return
    root, _ = common.root_from_argv(rest)
    base = common.interviews_dir(root)
    found = 0
    for d in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        for n in NAMES:
            p = os.path.join(base, d, n)
            if os.path.isfile(p):
                view(p, root)
                found += 1
    if not found:
        sys.exit(f"no {', '.join(NAMES)} under {base}")


if __name__ == "__main__":
    main()
