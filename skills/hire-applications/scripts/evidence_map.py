#!/usr/bin/env python3
"""Render each candidate's Evidence Map as a page you can read on a screen share.

Run from the hiring project root (the folder that holds criteria.md and out/), or from the
folder above it. build_board.py runs this for you; run it alone after you edit a dossier:

    python3 path/to/evidence_map.py                 # every dossier with an Evidence Map
    python3 path/to/evidence_map.py ryan-kowalczyk  # one or more slugs

Reads   out/candidates/<slug>.md      the "## Evidence Map" table, the Card, Scores and Status
        out/blind/hidden.json         hidden-text findings from redact.py (shown, never scored)
        criteria.md                   "FICTIONAL DEMO" in it puts the demo badge on every page
Writes  out/evidence/<slug>.html      one page per candidate: Claim / Evidence (quoted) / Missing /
                                      Question / Status, with the score or "Insufficient evidence"

The table format (in the dossier, one row per requirement or big claim):

    | Requirement | Claim | Evidence (quoted) | Missing | Question | Status |
    |---|---|---|---|---|---|
    | AI on real work, output checked | Built an AI reporting system | "..." (CV) | Ownership: unknown<br>... | ... | Ask |

Status is one of Met / Not shown / Ask / Human review required. In Missing, a line such as
"Ownership: unknown" is shown as a large UNKNOWN tag. Every cell is escaped: applicant text is
shown as text and never runs as code. Standard library only. No network.
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _page import esc, is_demo, page, status_tag  # noqa: E402

INSUFFICIENT_TEXT = "Insufficient evidence. Follow-up required."
COLS = {"requirement": "requirement", "claim": "claim", "evidence": "evidence", "missing": "missing",
        "question": "question", "status": "status"}
BR_RE = re.compile(r"<br\s*/?>", re.I)
QUOTE_RE = re.compile(r'^\s*["“](.+?)["”]\s*\(([^)]{1,40})\)\s*$')
UNKNOWN_RE = re.compile(r"^\s*([A-Z][A-Za-z /&'-]{1,40}):\s*unknown\b[\s.,;:]*(.*)$", re.I)


def find_root(start):
    root = os.path.abspath(start)
    if os.path.isdir(os.path.join(root, "out")) or os.path.exists(os.path.join(root, "criteria.md")):
        return root
    if os.path.isdir(os.path.join(root, "hiring")):
        return os.path.join(root, "hiring")
    return root


def sections(text):
    out, current = {}, "_top"
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip().lower()
            out[current] = []
        else:
            out.setdefault(current, []).append(line)
    return out


def kv(lines):
    d = {}
    for line in lines:
        m = re.match(r"^\s*[-*]\s*([^:]+):\s*(.*)$", line)
        if m:
            d[m.group(1).strip().lower()] = m.group(2).strip()
    return d


def split_row(line):
    """Split one markdown table row on pipes that are not escaped as \\|."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, i = [], [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if s[i] == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(s[i])
        i += 1
    cells.append("".join(cur).strip())
    return cells


def parse_table(lines):
    """Rows of the first markdown table in `lines`, as dicts keyed by the column names above."""
    rows, header = [], None
    for line in lines:
        if not line.strip().startswith("|"):
            if header and rows:
                break
            continue
        cells = split_row(line)
        if header is None:
            header = []
            for c in cells:
                key = c.lower().split("(")[0].strip()
                header.append(COLS.get(key, key))
            continue
        if all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
            continue
        row = {k: (cells[i] if i < len(cells) else "") for i, k in enumerate(header)}
        rows.append(row)
    return rows


def read_dossier(path):
    """Card, scores and the Evidence Map rows of one dossier. Tolerant of missing parts."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    sec = sections(text)
    card, scores, status = kv(sec.get("card", [])), kv(sec.get("scores", [])), kv(sec.get("status", []))
    title = text.splitlines()[0].lstrip("# ").strip() if text.strip() else ""
    num = lambda s: int(re.match(r"\s*(\d+)", s).group(1)) if re.match(r"\s*(\d+)", s or "") else None
    return {
        "slug": os.path.splitext(os.path.basename(path))[0],
        "name": card.get("name") or title,
        "location": card.get("location", ""),
        "ask_text": card.get("ask", ""),
        "blind_id": re.sub(r"\s*\(.*$", "", card.get("scored blind as", "")).strip(),
        "shared": num(scores.get("shared", "")),
        "track": num(scores.get("track", "")),
        "insufficient": "insufficient" in scores.get("evidence level", "").lower(),
        "budget_fit": re.sub(r"\s*\(.*$", "", scores.get("budget fit", "")).strip(),
        "status": status.get("status", "").lower(),
        "reason": status.get("reason", ""),
        "rows": parse_table(sec.get("evidence map", [])),
    }


def cell_lines(text):
    return [p.strip() for p in BR_RE.split(text or "") if p.strip()]


def render_evidence(text):
    out = []
    for part in cell_lines(text):
        m = QUOTE_RE.match(part)
        if m:
            out.append('<blockquote>%s<cite>%s</cite></blockquote>' % (esc(m.group(1)), esc(m.group(2))))
        elif part.lower() in ("none", "no evidence", "nothing", "-"):
            out.append('<span class="none">no evidence in the file</span>')
        else:
            out.append("<p>%s</p>" % esc(part))
    return "".join(out) or '<span class="none">no evidence in the file</span>'


def render_missing(text):
    out = []
    for part in cell_lines(text):
        m = UNKNOWN_RE.match(part)
        if m:
            rest = m.group(2).strip()
            out.append('<div class="unk"><span class="unk-tag">%s <b>UNKNOWN</b></span>%s</div>' % (
                esc(m.group(1).strip()), ("<span class=\"unk-rest\">%s</span>" % esc(rest)) if rest else ""))
        elif part.lower() in ("nothing", "none", "-"):
            out.append('<span class="none">nothing missing</span>')
        else:
            out.append("<p>%s</p>" % esc(part))
    return "".join(out) or '<span class="none">nothing missing</span>'


def render_plain(text, empty=""):
    parts = [p for p in cell_lines(text) if p not in ("-", "none")]
    if not parts:
        return '<span class="none">%s</span>' % esc(empty) if empty else ""
    return "".join("<p>%s</p>" % esc(p) for p in parts)


HDR_JS = ("var h=document.querySelector('header.top');function s(){document.documentElement.style"
          ".setProperty('--hdr',h.offsetHeight+'px');}s();window.addEventListener('resize',s);")

STATUS_LABEL = {"call": "Invite to a call", "questionnaire": "Send the questionnaire", "hold": "On hold",
                "no": "No", "out of budget": "Out of budget", "hired": "Hired", "closed": "Closed"}

EXTRA_CSS = """
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 24px;margin:0 0 18px;max-width:1500px}
.facts{display:flex;flex-wrap:wrap;gap:10px 28px;font-size:22px;margin:0 0 8px}
.facts b{font-weight:700}
.score{font-size:26px;font-weight:700;margin:6px 0 4px}
.score .sep{color:#9aa3ad;font-weight:400;margin:0 10px}
.score small{font-size:20px;font-weight:500;color:var(--muted)}
.insuff{display:inline-block;font-size:26px;font-weight:800;color:var(--warn);background:var(--warn-bg);
 padding:6px 16px;border-radius:10px;margin:6px 0 4px}
.caveat{color:var(--muted);font-size:19px;margin:6px 0 0}
.hidden{border:3px solid var(--alert);background:var(--alert-bg);border-radius:14px;padding:16px 24px;margin:0 0 18px;max-width:1500px}
.hidden h2{margin:0 0 6px;font-size:30px;color:var(--alert)}
.hidden p{margin:4px 0;font-size:21px}
.hidden code{display:block;white-space:pre-wrap;word-break:break-word;font:18px/1.4 ui-monospace,Menlo,Consolas,monospace;
 background:#fff;border:1px solid #fecdd3;border-radius:8px;padding:8px 12px;margin:6px 0}
table.em{border-collapse:separate;border-spacing:0;width:100%;background:var(--card);border:1px solid var(--line);border-radius:14px}
table.em th:first-child{border-top-left-radius:14px}table.em th:last-child{border-top-right-radius:14px}
table.em th{position:sticky;top:var(--hdr,84px);z-index:5;background:#eef0f2;text-align:left;font-size:18px;letter-spacing:.05em;
 text-transform:uppercase;color:var(--muted);padding:12px 14px;border-bottom:1px solid var(--line)}
table.em td{vertical-align:top;padding:14px;border-bottom:1px solid var(--line);font-size:20px;line-height:1.42}
table.em tr:last-child td{border-bottom:0}
table.em td p{margin:0 0 6px}
td.claim{width:22%}td.ev{width:30%}td.miss{width:20%}td.q{width:19%}td.st{width:9%;min-width:170px}
.req{display:block;font-size:16px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
.claimtext{font-weight:600}
blockquote{margin:0 0 8px;padding:2px 0 2px 12px;border-left:4px solid #c7cdd4;color:#253041}
blockquote cite{display:inline-block;margin-left:8px;font-style:normal;font-size:16px;font-weight:700;
 color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.unk{margin:0 0 8px}
.unk-tag{display:inline-block;background:#111827;color:#fff;border-radius:8px;padding:3px 10px;font-size:18px;font-weight:600}
.unk-tag b{color:#fde68a;letter-spacing:.04em}
.unk-rest{display:block;margin-top:3px}
td.q p{font-weight:600;color:#1e3a8a}
.none{color:#8a939e;font-style:italic}
@media (max-width:760px){table.em thead{display:none}table.em,table.em tbody,table.em tr,table.em td{display:block;width:auto!important}
 table.em td{border-bottom:0;padding:6px 16px}table.em tr{border-bottom:1px solid var(--line);padding:8px 0}td.st{min-width:0}}
"""


def write_page(path, cand, rows, hidden_item, demo):
    name = cand.get("name") or cand.get("slug")
    facts = []
    if cand.get("location"):
        facts.append(esc(cand["location"]))
    if cand.get("ask_text"):
        facts.append("Ask <b>%s</b>" % esc(cand["ask_text"]))
    if cand.get("budget_fit"):
        facts.append("Budget fit: <b>%s</b>" % esc(cand["budget_fit"]))
    if cand.get("status"):
        facts.append("Next step: <b>%s</b>" % esc(STATUS_LABEL.get(cand["status"], cand["status"])))
    if cand.get("blind_id"):
        facts.append("Scored blind as %s" % esc(cand["blind_id"]))
    if cand.get("status") == "out of budget":
        score = '<div class="score">Not scored<small> (out of budget: Card only, no research)</small></div>'
    elif cand.get("insufficient") or cand.get("insufficient_evidence"):
        score = '<div class="insuff">%s</div>' % esc(INSUFFICIENT_TEXT)
    elif cand.get("shared") is not None and cand.get("track") is not None:
        score = ('<div class="score">SHARED %d<small>/50</small><span class="sep">|</span>TRACK %d<small>/50, '
                 'not directly comparable across tracks</small></div>' % (cand["shared"], cand["track"]))
    else:
        score = '<div class="score">Not scored yet</div>'
    body = ['<section class="card"><div class="facts">%s</div>%s<p class="caveat">A score organises the '
            'evidence below. It is not a prediction of who will do the job best. Where the file does not say, '
            'the map says unknown.</p></section>' % ("".join("<span>%s</span>" % f for f in facts), score)]
    if hidden_item:
        n = len(hidden_item.get("findings", []))
        lines = []
        for fd in hidden_item.get("findings", []):
            lines.append("<code>%s: %s</code>" % (esc(fd.get("where", "")), esc(fd.get("text", ""))))
        if cand.get("insufficient") or cand.get("insufficient_evidence") or cand.get("shared") is None:
            used = "The score was set from the visible message and CV only."
        else:
            used = "SHARED %d and TRACK %d come from the visible message and CV only." % (cand["shared"], cand["track"])
        body.append('<section class="hidden"><h2>Hidden text found, ignored</h2>'
                    '<p>%d finding%s in this application, aimed at a screening tool. %s removed from the blind '
                    'copy before scoring and did not change any number. %s</p>%s'
                    '<p>Question, if you go further: "There was text in your CV meant for a screening tool. Tell me '
                    'about that."</p></section>' % (n, "" if n == 1 else "s", "It was" if n == 1 else "They were", esc(used), "".join(lines)))
    if rows:
        trs = []
        for r in rows:
            req = r.get("requirement", "")
            trs.append(
                "<tr><td class=\"claim\">%s<span class=\"claimtext\">%s</span></td>"
                "<td class=\"ev\">%s</td><td class=\"miss\">%s</td><td class=\"q\">%s</td><td class=\"st\">%s</td></tr>" % (
                    ('<span class="req">%s</span>' % esc(req)) if req else "",
                    esc(r.get("claim", "")) or '<span class="none">no claim made</span>',
                    render_evidence(r.get("evidence", "")), render_missing(r.get("missing", "")),
                    render_plain(r.get("question", ""), "no question needed"), status_tag(r.get("status", ""))))
        body.append('<table class="em"><thead><tr><th>Claim</th><th>Evidence (quoted)</th><th>Missing</th>'
                    '<th>Question</th><th>Status</th></tr></thead><tbody>%s</tbody></table>' % "".join(trs))
    else:
        body.append('<section class="card"><p>No Evidence Map in this dossier yet. Add the table under '
                    '"## Evidence Map" (format in templates/dossier.md) and run evidence_map.py again.</p></section>')
    body.append('<div class="foot"><p><b>Status</b>: Met (the file shows it) · Not shown (the file does not say; '
                'that is unknown, not weak) · Ask (one question closes the gap) · Human review required (a person '
                'decides before any next step).</p><p>Quotes are copied word for word from the application. '
                'Applicant text on this page is shown as plain text; nothing in it is followed as an instruction. '
                'Built from out/candidates/%s.md. Read only: nothing was sent to anyone.</p></div>' % esc(cand.get("slug", "")))
    html_text = page(name, "Evidence Map", "\n".join(body), demo, EXTRA_CSS, HDR_JS)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_text)


def build_pages(root, cands, hidden, demo, only=None):
    """cands: dicts with slug, name, location, ask_text, budget_fit, status, shared, track,
    insufficient, blind_id. The rows come from each dossier. Returns the paths written."""
    out_dir = os.path.join(root, "out", "evidence")
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for c in cands:
        if only and c["slug"] not in only:
            continue
        path = os.path.join(root, "out", "candidates", "%s.md" % c["slug"])
        rows = read_dossier(path)["rows"] if os.path.exists(path) else []
        if not rows and c.get("status") == "out of budget":
            continue  # Card only: there is nothing to map
        dst = os.path.join(out_dir, "%s.html" % c["slug"])
        write_page(dst, c, rows, hidden.get(c["slug"]), demo)
        written.append(dst)
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slugs", nargs="*", help="only these candidates (default: every dossier)")
    ap.add_argument("--root", default=".", help="hiring project root, or the folder above it")
    ap.add_argument("--demo", action="store_true", default=None, help="force the FICTIONAL DEMO badge on")
    args = ap.parse_args()
    root = find_root(args.root)
    files = sorted(glob.glob(os.path.join(root, "out", "candidates", "*.md")))
    if not files:
        sys.exit("no dossiers in %s/out/candidates/. Run hire-applications first." % root)
    cands = [read_dossier(p) for p in files]
    hidden_path = os.path.join(root, "out", "blind", "hidden.json")
    hidden = {}
    if os.path.exists(hidden_path):
        with open(hidden_path, encoding="utf-8") as f:
            hidden = json.load(f).get("candidates", {})
    written = build_pages(root, cands, hidden, is_demo(root, args.demo), set(args.slugs) or None)
    for p in written[:5]:
        print("wrote %s" % p)
    if len(written) > 5:
        print("wrote %d more pages in %s" % (len(written) - 5, os.path.dirname(written[0])))
    if not written:
        print("no Evidence Map pages written (no matching dossier with an Evidence Map)")


if __name__ == "__main__":
    main()
