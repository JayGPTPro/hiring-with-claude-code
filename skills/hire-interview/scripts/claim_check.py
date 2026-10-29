#!/usr/bin/env python3
"""The claim check: one page per candidate and one summary page. Standard library only, no network.

Claude writes one file per candidate, hiring/out/verification/<slug>.json (shape in templates/claim-check.json):
each job-related claim, the sources looked at (the candidate's own documents, a source they supplied, or one
public company page), a status and one neutral question. This script renders them. It judges nothing and
contacts no one.

Run from your hiring/ folder (the one that holds criteria.md), or from the folder above it:

    python3 <skill>/scripts/claim_check.py            every out/verification/*.json
    python3 <skill>/scripts/claim_check.py --append   also write the "## Claim verification" section in each
                                                      dossier (a re-check replaces it)

Writes  out/verification/<slug>.md and .html, SUMMARY.md and SUMMARY.html; with --append the dossier section.

Statuses: Verified, Unverified, Clarification needed. Common synonyms are mapped ("Confirmed" is Verified,
"needs a question" is Clarification needed); anything else stops the run and names the claim. A result that
may not be this person is not used and not recorded, so a report with a "set_aside" field is refused.
Every value is escaped before it goes into HTML.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

STATUSES = ["Verified", "Unverified", "Clarification needed"]
SYNONYMS = {
    "verified": "Verified", "confirmed": "Verified", "yes": "Verified",
    "unverified": "Unverified", "not verified": "Unverified", "not confirmed": "Unverified",
    "unconfirmed": "Unverified", "no source": "Unverified", "no source found": "Unverified",
    "clarification needed": "Clarification needed", "needs clarification": "Clarification needed",
    "needs a question": "Clarification needed", "clarify": "Clarification needed",
    "conflict": "Clarification needed", "sources differ": "Clarification needed",
}
STATUS_CLS = {"Verified": "ver", "Unverified": "unv", "Clarification needed": "cla"}


def esc(v):
    return html.escape("" if v is None else str(v), quote=True)


def find_root(arg=None):
    here = Path(arg) if arg else Path(".")
    for cand in (here, here / "hiring"):
        if (cand / "criteria.md").is_file():
            return cand
    sys.exit("no criteria.md in %s or %s. Run this from your hiring/ folder (the one that holds criteria.md) "
             "or from the folder above it, or pass --root path/to/hiring." % (here / "criteria.md", here / "hiring" / "criteria.md"))


def criteria_info(root):
    text = (root / "criteria.md").read_text(encoding="utf-8")
    m = re.search(r"delete[^\n]{0,200}?(\d{4}-\d{2}-\d{2})", text, re.I)
    return {"retention": m.group(1) if m else "", "demo": "FICTIONAL DEMO" in text.upper()}


def norm_status(s, where):
    key = re.sub(r"[\s.!]+", " ", (s or "").strip().lower()).strip()
    if key in SYNONYMS:
        return SYNONYMS[key]
    sys.exit("%s: status %r is not one of Verified, Unverified, Clarification needed (or a known synonym such as "
             "Confirmed or needs a question). Fix the status and run again." % (where, s))


def load(path, info):
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("slug", path.stem)
    data.setdefault("candidate", path.stem.replace("-", " ").title())
    data["retention"] = data.get("retention") or info["retention"]
    if "set_aside" in data:
        sys.exit("%s: remove the \"set_aside\" field. A result that may not be this person is not used and not "
                 "written down anywhere, not even as set aside." % path.name)
    for c in data.get("claims", []):
        c["status"] = norm_status(c.get("status"), "%s, claim %r" % (path.name, c.get("claim", "")[:60]))
        c.setdefault("sources", [])
    return data


def counts(d):
    out = {s: 0 for s in STATUSES}
    for c in d.get("claims", []):
        out[c["status"]] += 1
    return out


def questions(d):
    seen, qs = set(), []
    for c in d.get("claims", []):
        q = (c.get("question") or "").strip()
        if q and c["status"] != "Verified" and q not in seen:
            seen.add(q)
            qs.append((q, c.get("context", "")))
    return qs


# ---------- markdown ----------

def write_md(d, path):
    n = counts(d)
    L = ["# %s: claim verification" % d["candidate"], "",
         "Checked %s. Job-related claims only, public or candidate-supplied sources. Nobody was contacted." % d.get("checked", "(date)"),
         "Retention: delete raw notes on %s. The statuses, the questions and the decision stay in the dossier." % (d["retention"] or "(set a date in criteria.md)"),
         "Purpose: %s" % d.get("purpose", "check what the candidate claimed about work, nothing else."), "",
         "## Summary", "",
         "Verified %d. Unverified %d. Clarification needed %d. No colour labels on the person: a difference between sources is a question, not a verdict."
         % (n["Verified"], n["Unverified"], n["Clarification needed"]), "",
         "## Claims", ""]
    for c in d.get("claims", []):
        L.append("### %s (%s)" % (c.get("claim", ""), c["status"]))
        L.append("- From: %s" % c.get("from", "the application"))
        for s in c["sources"]:
            L.append("- %s: %s%s" % (s.get("name", "source"), s.get("says", ""), (" (%s)" % s["detail"]) if s.get("detail") else ""))
        if c.get("note"):
            L.append("- Note: %s" % c["note"])
        if c.get("question") and c["status"] != "Verified":
            L.append("- Question: \"%s\"%s" % (c["question"], (" " + c["context"]) if c.get("context") else ""))
        L.append("")
    L += ["## Questions for the call", ""]
    qs = questions(d)
    L += ["%d. %s" % (i, q) for i, (q, _) in enumerate(qs, 1)] or ["None from the claim check."]
    L += ["", "## Not checked", ""] + (["- %s" % x for x in d.get("not_checked", [])] or ["- Nothing else."])
    L += ["", "## Not looked at", "", d.get("not_looked_at", "Family, relationships, religion, health, politics, age, origin, appearance, personal social media."), ""]
    path.write_text("\n".join(L), encoding="utf-8")


# ---------- html ----------

CSS = """
:root{--ink:#17202a;--muted:#55606e;--line:#dfe3e8;--bg:#f7f6f2;--card:#fff;--cla:#1e3a8a;--cla-bg:#dbeafe}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font:22px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
header.top{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:18px 32px 14px;border-bottom:1px solid var(--line)}
header.top .kicker{display:block;font-size:18px;font-weight:600;color:var(--muted);letter-spacing:.04em;text-transform:uppercase}
header.top h1{margin:0;font-size:34px;line-height:1.15}
.badge-demo{flex:none;background:#111827;color:#fff;font-weight:800;font-size:26px;letter-spacing:.06em;padding:10px 20px;border-radius:10px;white-space:nowrap}
main{padding:18px 32px 50px}
.info{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 22px;margin:0 0 16px}
.info p{margin:2px 0;font-size:20px;color:var(--muted)}.info b{color:var(--ink)}
.counts{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0 2px}
.st{display:inline-block;font-size:19px;font-weight:700;padding:4px 14px;border-radius:999px;white-space:nowrap}
.st.ver{background:#fff;color:var(--ink);border:2px solid var(--ink)}
.st.unv{background:#eceef1;color:#374151;border:2px solid #eceef1}
.st.cla{background:var(--cla-bg);color:var(--cla);border:2px solid var(--cla-bg)}
.conflict{background:var(--card);border:2px solid var(--cla);border-radius:16px;padding:18px 24px;margin:0 0 18px}
.conflict .lab{font-size:17px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.conflict h2{margin:4px 0 12px;font-size:28px;line-height:1.25}
.conflict h2 small{font-size:19px;font-weight:500;color:var(--muted)}
.sides{display:grid;gap:16px;margin:0 0 14px}
.side{border:1px solid var(--line);border-radius:12px;padding:12px 16px;background:#fbfbfa}
.side .src{font-size:17px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.side .says{font-size:24px;font-weight:600;line-height:1.3;margin-top:4px;white-space:pre-line}
.side .det{font-size:19px;color:var(--muted);margin-top:4px}
.ask{background:var(--cla-bg);border-radius:12px;padding:12px 18px}
.ask .lab{color:var(--cla)}
.ask p{margin:2px 0 0;font-size:30px;font-weight:800;color:var(--cla);line-height:1.25}
.ask small{display:block;font-size:19px;color:#334155;margin-top:4px}
.note{font-size:19px;color:var(--muted);margin:10px 0 0}
table{border-collapse:separate;border-spacing:0;width:100%;background:var(--card);border:1px solid var(--line);border-radius:14px}
th{background:#eef0f2;text-align:left;font-size:17px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);padding:10px 14px;border-bottom:1px solid var(--line)}
th:first-child{border-top-left-radius:14px}th:last-child{border-top-right-radius:14px}
td{vertical-align:top;padding:12px 14px;border-bottom:1px solid var(--line);font-size:20px;line-height:1.4}
tr:last-child td{border-bottom:0}
td .from{display:block;font-size:16px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
td.q{color:var(--cla);font-weight:600}
.srcline{margin:0 0 6px}.srcline b{font-size:17px;letter-spacing:.03em;text-transform:uppercase;color:var(--muted)}
.foot{color:var(--muted);font-size:18px;margin-top:20px}.foot p{margin:4px 0}
h2.sec{font-size:22px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);margin:22px 0 8px}
@media (max-width:900px){.sides{grid-template-columns:1fr!important}header.top{padding:12px 16px;flex-wrap:wrap}main{padding:14px 16px}
 .badge-demo{font-size:20px;padding:8px 12px}table thead{display:none}table,tbody,tr,td{display:block;width:auto!important}
 td{border-bottom:0;padding:6px 16px}tr{border-bottom:1px solid var(--line);padding:8px 0}}
"""


def page(title, kicker, body, demo):
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"robots\" content=\"noindex\">"
            "<title>%s</title><style>%s</style></head><body>"
            "<header class=\"top\"><div><span class=\"kicker\">%s</span><h1>%s</h1></div>%s</header>"
            "<main>%s</main></body></html>\n") % (
        esc(title), CSS, esc(kicker), esc(title),
        '<div class="badge-demo">FICTIONAL DEMO</div>' if demo else "", body)


def st_tag(status):
    return '<span class="st %s">%s</span>' % (STATUS_CLS.get(status, "unv"), esc(status))


def write_html(d, path, demo):
    n = counts(d)
    body = ['<section class="info"><p><b>Checked %s.</b> Job-related claims only, public or candidate-supplied sources. '
            'Nobody was contacted. <b>Delete raw notes on %s.</b></p><p>Purpose: %s</p><div class="counts">%s</div></section>' % (
                esc(d.get("checked", "")), esc(d["retention"] or "(no date: add one)"), esc(d.get("purpose", "")),
                "".join('<span class="st %s">%s: %d</span>' % (STATUS_CLS[s], esc(s), n[s]) for s in STATUSES))]
    side_by_side = [c for c in d.get("claims", []) if c["status"] == "Clarification needed" and len(c["sources"]) >= 2]
    rest = [c for c in d.get("claims", []) if c not in side_by_side]
    for c in side_by_side:
        k = len(c["sources"])
        sides = "".join('<div class="side"><div class="src">%s</div><div class="says">%s</div>%s</div>' % (
            esc(s.get("name", "")), esc(s.get("says", "")), ('<div class="det">%s</div>' % esc(s["detail"])) if s.get("detail") else "")
            for s in c["sources"])
        body.append('<section class="conflict"><div class="lab">%s · %s</div><h2>"%s" <small>from the %s</small></h2>'
                    '<div class="sides" style="grid-template-columns:repeat(%d,1fr)">%s</div>'
                    '<div class="ask"><div class="lab">Neutral question for the call</div><p>%s</p>%s</div>%s</section>' % (
                        esc(c["status"]), esc(c.get("kind_label", "Two sources, two versions")), esc(c.get("claim", "")),
                        esc(c.get("from", "application")), min(k, 3), sides, esc(c.get("question", "")),
                        ('<small>%s</small>' % esc(c["context"])) if c.get("context") else "",
                        ('<p class="note">%s</p>' % esc(c["note"])) if c.get("note") else ""))
    if rest:
        trs = []
        for c in rest:
            srcs = "".join('<div class="srcline"><b>%s</b><br>%s%s</div>' % (
                esc(s.get("name", "")), esc(s.get("says", "")), (" (%s)" % esc(s["detail"])) if s.get("detail") else "")
                for s in c["sources"]) or '<span style="color:#8a939e">no source found</span>'
            q = c.get("question", "") if c["status"] != "Verified" else ""
            trs.append('<tr><td><span class="from">From the %s</span>%s</td><td>%s%s</td><td>%s</td><td class="q">%s</td></tr>' % (
                esc(c.get("from", "application")), esc(c.get("claim", "")), srcs,
                ('<div class="srcline" style="color:#55606e">%s</div>' % esc(c["note"])) if c.get("note") else "",
                st_tag(c["status"]), esc(q) if q else '<span style="color:#8a939e;font-weight:400">none needed</span>'))
        body.append('<h2 class="sec">%s</h2><table><thead><tr><th style="width:24%%">Claim</th><th style="width:38%%">Source and what it shows</th>'
                    '<th style="width:14%%">Status</th><th>Neutral question</th></tr></thead><tbody>%s</tbody></table>' % (
                        "Every other claim checked" if side_by_side else "Claims checked", "".join(trs)))
    body.append('<div class="foot"><p><b>Not checked:</b> %s</p><p><b>Not looked at:</b> %s</p>'
                '<p>Built from out/verification/%s.json. A difference between sources is a question, never a verdict, and there '
                'are no red, yellow or green labels on the person. Read only: nothing was sent to anyone.</p></div>' % (
                    esc("; ".join(d.get("not_checked", [])) or "nothing else"),
                    esc(d.get("not_looked_at", "Family, relationships, religion, health, politics, age, origin, appearance, personal social media.")),
                    esc(d["slug"])))
    path.write_text(page(d["candidate"], "Claim verification", "".join(body), demo), encoding="utf-8")


def write_summary(reports, out_dir, demo):
    trs = []
    md = ["# Claim verification: summary", "",
          "One row per candidate checked. Verified / Unverified / Clarification needed, with the claims behind each count. "
          "No colour labels on people. Nobody was contacted.", "",
          "| Candidate | Verified | Unverified | Clarification needed | Questions | Delete raw notes on |",
          "|---|---|---|---|---|---|"]
    for d in reports:
        cells = []
        for s in STATUSES:
            items = [c.get("short") or c.get("claim", "") for c in d.get("claims", []) if c["status"] == s]
            cells.append('<td><div class="big">%d</div>%s</td>' % (len(items), "".join("<div class=\"it\">%s</div>" % esc(i) for i in items)))
        trs.append('<tr><td class="nm"><a href="%s.html">%s</a><span>checked %s</span></td>%s<td class="nq">%d</td><td>%s</td></tr>' % (
            esc(d["slug"]), esc(d["candidate"]), esc(d.get("checked", "")), "".join(cells),
            len(questions(d)), esc(d["retention"] or "no date")))
        n = counts(d)
        md.append("| %s | %d | %d | %d | %d | %s |" % (d["candidate"], n["Verified"], n["Unverified"], n["Clarification needed"],
                                                     len(questions(d)), d["retention"] or "no date"))
    css = ("td .big{font-size:28px;font-weight:800;line-height:1.1}td .it{font-size:18px;color:#374151;line-height:1.35;margin-top:3px}"
           "td.nm a{font-weight:700;font-size:22px;color:var(--ink)}td.nm span{display:block;font-size:17px;color:#55606e}td.nq{font-size:26px;font-weight:800}")
    body = ('<section class="info"><p>Each row is one candidate. The counts are claims, not people: a claim that cannot be confirmed '
            'is a question for the call, and a difference between sources is never a verdict. No red, yellow or green labels on '
            'anyone. Nobody was contacted.</p></section><table><thead><tr><th style="width:15%%">Candidate</th><th>%s</th><th>%s</th><th>%s</th>'
            '<th style="width:8%%">Questions</th><th style="width:10%%">Delete raw notes on</th>'
            '</tr></thead><tbody>%s</tbody></table><div class="foot"><p>Built from out/verification/*.json. Each name opens its report.</p></div>') % (
                st_tag("Verified"), st_tag("Unverified"), st_tag("Clarification needed"), "".join(trs))
    title = "%d candidates, claim by claim" % len(reports)
    doc = page(title, "Claim verification: summary", body, demo).replace("</style>", css + "</style>", 1)
    (out_dir / "SUMMARY.html").write_text(doc, encoding="utf-8")
    (out_dir / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def append_section(root, d):
    """Write the "## Claim verification" section in the dossier. A re-check replaces the old section."""
    dossier = root / "out" / "candidates" / ("%s.md" % d["slug"])
    if not dossier.is_file():
        return "no dossier"
    text = dossier.read_text(encoding="utf-8")
    n = counts(d)
    qs = questions(d)
    sec = ["## Claim verification", "",
           "Checked %s, job-related claims only, nobody contacted. Report: `out/verification/%s.html`. Delete raw notes on %s." % (
               d.get("checked", ""), d["slug"], d["retention"] or "(date)"),
           "- Verified %d, Unverified %d, Clarification needed %d." % (n["Verified"], n["Unverified"], n["Clarification needed"])]
    for c in d.get("claims", []):
        if c["status"] == "Clarification needed":
            sec.append("- Clarification needed: %s" % (c.get("short") or c.get("claim", "")))
    sec.append("- Questions carried to the call:" if qs else "- No questions from the claim check.")
    sec += ["  %d. %s" % (i, q) for i, (q, _) in enumerate(qs, 1)]
    block = "\n".join(sec) + "\n"
    old = re.search(r"^## Claim verification\s*\n.*?(?=^## |\Z)", text, re.M | re.S)
    if old:
        if old.group(0).strip() == block.strip():
            return "section up to date"
        text = text[:old.start()] + block + ("\n" if text[old.end():] else "") + text[old.end():]
        action, log = "section replaced", "re-checked"
    else:
        text = (text if text.endswith("\n") else text + "\n") + "\n" + block
        action, log = "section added", "added"
    text = re.sub(r"(^## Log\s*\n(?:.*\n)*?)(?=\n## |\Z)",
                  lambda m: m.group(1).rstrip("\n") + "\n- %s Claim verification %s (job-related sources only, nobody contacted).\n" % (
                      d.get("checked", ""), log), text, count=1, flags=re.M)
    dossier.write_text(text, encoding="utf-8")
    return action


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    ap.add_argument("--append", action="store_true", help="write the Claim verification section in each dossier (a re-check replaces it)")
    args = ap.parse_args()
    root = find_root(args.root)
    info = criteria_info(root)
    out_dir = root / "out" / "verification"
    files = sorted(p for p in out_dir.glob("*.json")) if out_dir.is_dir() else []
    if not files:
        sys.exit("no reports in %s. Write one <slug>.json per candidate first (templates/claim-check.json)." % out_dir)
    reports = [load(p, info) for p in files]
    for d in reports:
        write_md(d, out_dir / ("%s.md" % d["slug"]))
        write_html(d, out_dir / ("%s.html" % d["slug"]), info["demo"])
        n = counts(d)
        line = "%-22s verified %d, unverified %d, clarification needed %d, delete raw notes on %s" % (
            d["candidate"], n["Verified"], n["Unverified"], n["Clarification needed"], d["retention"] or "NO DATE")
        if args.append:
            line += "  [dossier: %s]" % append_section(root, d)
        print(line)
        if not d["retention"]:
            print("warning: %s has no deletion date; add \"retention\" or a delete date in criteria.md" % d["candidate"])
    reports.sort(key=lambda d: (-counts(d)["Clarification needed"], d["candidate"].lower()))
    write_summary(reports, out_dir, info["demo"])
    print("wrote %d reports (.md and .html) and SUMMARY.html, SUMMARY.md in %s" % (len(reports), out_dir))


if __name__ == "__main__":
    main()
