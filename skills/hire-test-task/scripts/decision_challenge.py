"""The Decision Challenge, inside the decision step: your preference first, sealed; then Claude challenges it.

Step 1, you, before you ask Claude for a recommendation:
  python3 decision_challenge.py seal --prefer <slug> --why "who you prefer and why, in your words" [--by Sam] [--at "YYYY-MM-DD HH:MM"]
  Writes challenge/decision-challenge.json with the text, the time and a fingerprint (SHA-256 of the text).
  A sealed preference is never edited: a second seal is refused. If you change your mind, write it in
  "after" once the challenge is in, so the record shows both.

Step 2, Claude, after the seal: adds a "challenge" block to the same file (templates/decision-challenge.example.json):
  for / against / missing / next_check, each a list of {"point", "source"}, plus "recommendation" and "written_at".
  The strongest evidence for your choice, the strongest against it, the evidence still missing, and the
  next check that would close the biggest gap. Not to be negative. To find what is missing.
  Against and Missing evidence are never empty: if either is, the page refuses to show the challenge and
  the script exits 1. A thin file is said to be thin.

Step 3, the page:
  python3 decision_challenge.py
  Writes challenge/DECISION-CHALLENGE.html: the sealed preference first, then the four columns, then Claude's
  recommendation and your decision after the challenge. Claude's block is not shown when there is no seal,
  when it is dated before the seal, or when the sealed text no longer matches its fingerprint. Above it,
  what is on file for each finalist, stage by stage; a finalist with no reference summary is named plainly.

A score is never a reason to stop thinking. Nothing here is sent anywhere.

Usage: run from your hiring/ folder, or from the folder above it.  (--root path/to/hiring overrides)
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import esc, find_root, load_json, demo_label, no_dashes, page, evidence  # noqa: E402

COLS = [("for", "For", "The strongest evidence for your choice", "ok"),
        ("against", "Against", "The strongest evidence against it", "no"),
        ("missing", "Missing evidence", "What the file does not show yet", "warn"),
        ("next_check", "Next check", "What would close the biggest gap", "acc")]

CSS = """
.step{display:flex;align-items:center;gap:14px;margin:34px 0 10px}
.step .n{flex:none;width:46px;height:46px;border-radius:50%;background:var(--ink);color:#fff;font-size:23px;font-weight:800;text-align:center;line-height:46px}
.step h2{margin:0}
.sealed{border:3px solid var(--ink);border-radius:16px;background:var(--card);padding:22px 26px}
.sealed .who{font-size:30px;font-weight:800;margin:4px 0 8px}
.sealed .why{font-size:23px;line-height:1.5}
.sealed .meta{font-size:20px;color:var(--mute);margin-top:12px}
.lock{display:inline-block;background:var(--ink);color:#fff;font-size:18px;font-weight:700;letter-spacing:.06em;padding:4px 12px;border-radius:6px;text-transform:uppercase}
.matrix{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.col{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.col h3{margin:0;padding:12px 16px;font-size:26px;color:#fff}
.col h3 span{display:block;font-size:19px;font-weight:500;opacity:.9}
.col.ok h3{background:var(--ok)}.col.no h3{background:var(--no)}.col.warn h3{background:var(--warn)}.col.acc h3{background:var(--acc)}
.col ul{list-style:none;margin:0;padding:6px 16px 12px}
.col li{padding:10px 0;border-bottom:1px solid var(--line);font-size:20px;line-height:1.4}
.col li:last-child{border-bottom:0}
.col li .src{display:block;font-size:19px;color:var(--mute);margin-top:4px}
.rec{font-size:22px;line-height:1.5}
.stop{font-size:24px;font-weight:800;margin-top:14px}
td.miss{color:var(--no);font-weight:600}
@media (max-width:1200px){.matrix{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:760px){.matrix{grid-template-columns:1fr}}
"""


def fingerprint(prefer: str, why: str) -> str:
    return hashlib.sha256(f"{prefer}\n{why}".encode("utf-8")).hexdigest()


def parse_time(s):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(str(s)[:19], fmt)
        except ValueError:
            continue
    return None


def seal(root, args):
    ch = root / "challenge"
    cfg = load_json(ch / "config.json", {})
    slugs = {f["slug"]: f["name"] for f in cfg.get("finalists", [])}
    if slugs and args.prefer not in slugs:
        raise SystemExit(f"--prefer must be one of: {', '.join(slugs)}")
    why = (args.why or "").strip()
    if len(why) < 20:
        raise SystemExit("--why needs your reasons in a sentence or two, in your own words, before Claude says anything.")
    no_dashes(why, "--why")
    path = ch / "decision-challenge.json"
    d = load_json(path, {})
    if isinstance(d.get("sealed"), dict):
        raise SystemExit(f"already sealed on {d['sealed'].get('written_at', '')} ({slugs.get(d['sealed'].get('prefer'), d['sealed'].get('prefer'))}). "
                         "A sealed preference is not edited. If you changed your mind, write it under \"after\" once the challenge is in.")
    at = args.at or dt.datetime.now().strftime("%Y-%m-%d %H:%M")   # the real clock: Claude's challenge is compared with it
    if not parse_time(at):
        raise SystemExit("--at must look like 2026-10-29 08:40")
    d = {"_how": "Sealed by decision_challenge.py seal. Claude adds the challenge block after the seal; you add after.",
         "sealed": {"prefer": args.prefer, "why": why, "by": args.by or cfg.get("signoff", ""), "written_at": at,
                    "sha256": fingerprint(args.prefer, why)},
         **{k: v for k, v in d.items() if k not in ("sealed", "_how")}}
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path}  (sealed {at}: {slugs.get(args.prefer, args.prefer)}). Now ask Claude to challenge it.")


def build(root):
    ch = root / "challenge"
    cfg = load_json(ch / "config.json", {})
    names = {f["slug"]: f["name"] for f in cfg.get("finalists", [])}
    badge = demo_label(root, cfg)
    d = load_json(ch / "decision-challenge.json", {})
    sealed = d.get("sealed") if isinstance(d.get("sealed"), dict) else None
    chal = d.get("challenge") if isinstance(d.get("challenge"), dict) else None
    after = d.get("after")
    problems, refused = [], False
    show_chal = bool(chal)
    intact = False
    if sealed:
        intact = fingerprint(sealed.get("prefer", ""), sealed.get("why", "")) == sealed.get("sha256")
        if not intact:
            problems.append("The sealed text no longer matches its fingerprint: it was edited after sealing. Claude's challenge is not shown.")
            show_chal = False
        if chal:
            ts, tc = parse_time(sealed.get("written_at")), parse_time(chal.get("written_at"))
            if not tc or (ts and tc < ts):
                problems.append("Claude's challenge is dated before your seal, or has no date. It must come after. Not shown.")
                show_chal = False
            for key, title in (("against", "Against"), ("missing", "Missing evidence")):
                if not [x for x in (chal.get(key) or []) if (x.get("point") if isinstance(x, dict) else str(x)).strip()]:
                    problems.append(f"{title} is empty. It never is: name the strongest evidence against the choice and what the "
                                    "file does not show yet, or say the file is thin. The challenge is not shown until then.")
                    show_chal = False
                    refused = True
    else:
        if chal:
            problems.append("There is a challenge block but no sealed preference. Seal yours first; the challenge stays hidden until then.")
        show_chal = False

    parts = ["<h1>Decision Challenge</h1>",
             "<p class='sub'>You write who you prefer and why, before Claude says anything. Then Claude challenges that choice: "
             "the strongest evidence for it, the strongest evidence against it, the evidence still missing, and the next check. "
             "Not to be negative. To find the missing information.</p>"]
    parts += [f"<div class='banner'>{esc(p)}</div>" for p in problems]
    parts.append("<div class='step'><span class='n'>1</span><h2>Your preference, sealed first</h2></div>")
    if sealed:
        parts.append(
            f"<div class='sealed'><span class='lock'>Sealed before Claude's view</span>"
            f"<div class='who'>{esc(names.get(sealed.get('prefer'), sealed.get('prefer', '')))}</div>"
            f"<div class='why'>{esc(sealed.get('why', ''))}</div>"
            f"<div class='meta'>Written {esc(sealed.get('written_at', ''))} by {esc(sealed.get('by', ''))}. "
            f"Fingerprint {esc(str(sealed.get('sha256', ''))[:12])}, {'unchanged' if intact else 'CHANGED after sealing'}.</div></div>")
    else:
        parts.append("<div class='card'><p>Not sealed yet. Before you ask Claude for its recommendation, write who you prefer and why:</p>"
                     "<p><code>python3 decision_challenge.py seal --prefer &lt;slug&gt; --why \"...\"</code></p></div>")
    review = load_json(ch / "review.json", {})
    rows, gaps = [], []
    finalists = cfg.get("finalists", [])
    ev = {f["slug"]: evidence(root, f, review) for f in finalists}
    for i, (stage, _) in enumerate(ev[finalists[0]["slug"]] if finalists else []):
        cells = "".join(f"<td>{esc(ev[f['slug']][i][1])}</td>" if ev[f["slug"]][i][1] else "<td class='miss'>none on file</td>"
                        for f in finalists)
        rows.append(f"<tr><td>{esc(stage)}</td>{cells}</tr>")
    for f in finalists:
        if not ev[f["slug"]][-1][1]:
            gaps.append(f"No reference summary for {f['name']} (out/references/{f['slug']}-summary.md). The challenge must say so under Missing evidence.")
    if finalists:
        heads = "".join(f"<th>{esc(f['name'])}</th>" for f in finalists)
        parts.append("<h2>What is on file</h2><p class='note'>The files each stage wrote, per finalist. Claude reads these, and only these.</p>"
                     f"<table><thead><tr><th>Stage</th>{heads}</tr></thead>"
                     f"<tbody>{''.join(rows)}</tbody></table>" + "".join(f"<div class='info'>{esc(g)}</div>" for g in gaps))
    parts.append("<div class='step'><span class='n'>2</span><h2>The challenge</h2></div>")
    if show_chal:
        parts.append(f"<p class='note'>Written by Claude {esc(chal.get('written_at', ''))}, after the seal, from the files in this folder. Each point names its source.</p>")
        cols = []
        for key, title, sub, cls in COLS:
            items = chal.get(key) or []
            lis = []
            for it in items:
                if isinstance(it, dict):
                    lis.append(f"<li>{esc(it.get('point', ''))}" + (f"<span class='src'>{esc(it.get('source', ''))}</span>" if it.get("source") else "") + "</li>")
                else:
                    lis.append(f"<li>{esc(it)}</li>")
            cols.append(f"<div class='col {cls}'><h3>{esc(title)}<span>{esc(sub)}</span></h3><ul>{''.join(lis) or '<li>nothing written</li>'}</ul></div>")
        parts.append(f"<div class='matrix'>{''.join(cols)}</div>")
        parts.append("<div class='step'><span class='n'>3</span><h2>Claude's recommendation, after the challenge</h2></div>")
        parts.append(f"<div class='card'><p class='rec'>{esc(chal.get('recommendation', ''))}</p>"
                     "<p class='stop'>A score is never a reason to stop thinking.</p></div>")
    else:
        parts.append("<div class='card'><p class='note'>Shown after your preference is sealed and Claude has written the challenge.</p></div>")
    parts.append("<div class='step'><span class='n'>4</span><h2>Your decision after the challenge</h2></div>")
    if isinstance(after, dict) and after:
        parts.append(f"<div class='card'><p class='rec'>{esc(after.get('decision', ''))}</p>"
                     f"<p class='note'>Written {esc(after.get('written_at', ''))} by {esc(after.get('by', ''))}.</p></div>")
    elif isinstance(after, str) and after.strip():
        parts.append(f"<div class='card'><p class='rec'>{esc(after)}</p></div>")
    else:
        parts.append("<div class='card'><p class='note'>Not written yet. Write what you decided and whether the challenge changed anything, in \"after\".</p></div>")
    parts.append("<p class='foot'>The person decides. Claude organises the evidence and asks what is missing. Nothing on this page is sent anywhere.</p>")
    html_text = page("Decision Challenge", f"{cfg.get('brand', '')} · Hiring · Decision Challenge", "\n".join(parts), badge, CSS)
    no_dashes(html_text, "DECISION-CHALLENGE.html")
    out = ch / "DECISION-CHALLENGE.html"
    out.write_text(html_text, encoding="utf-8")
    print(f"wrote {out}" + ("" if sealed else "  (no seal yet: only step 1 instructions shown)"))
    for g in gaps:
        print("note: " + g)
    for p in problems:
        print("note: " + p)
    if refused:
        raise SystemExit("refused: the challenge has an empty Against or Missing evidence column. Fill it and rerun.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="your hiring/ folder (default: . or ./hiring, whichever holds criteria.md)")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("seal", help="write and seal your preference before Claude's view")
    s.add_argument("--prefer", required=True, help="the slug of the finalist you prefer")
    s.add_argument("--why", required=True, help="why, in your own words")
    s.add_argument("--by", default="", help="your name (default: signoff in config.json)")
    s.add_argument("--at", default="", help='the time to record, "YYYY-MM-DD HH:MM" (default: now)')
    s.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    args = ap.parse_args()
    root = find_root(args.root)
    if args.cmd == "seal":
        seal(root, args)
    build(root)


if __name__ == "__main__":
    main()
