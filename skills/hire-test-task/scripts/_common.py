"""Shared helpers for the hire-test-task scripts. Python 3 standard library only, no network.

Not a command. The other scripts import it:
  find_root(arg)        the hiring/ folder (the one that holds criteria.md), from it or the folder above
  load_json(path, d)    a JSON file or the default when it does not exist
  demo_label(root, cfg) "FICTIONAL DEMO" when criteria.md says so (or config.json sets demo_badge)
  esc(value)            html.escape for every string that came from a file
  page(...)             the page shell: a sticky top bar with the badge, legible type for video and phone
  no_dashes(text, what) refuses long dashes in anything a script writes
  submission_files(ch, f), submitted(ch, f, r)   what a finalist sent, under any file name or type
  evidence(root, f)     the files each earlier stage wrote for one finalist, or None where a stage has none
"""
import html
import json
import pathlib
import re

NUM_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
             8: "eight", 9: "nine", 10: "ten", 12: "twelve", 14: "fourteen"}


def find_root(arg=None):
    """The hiring project root: the folder that holds criteria.md.

    Without --root: "." when ./criteria.md exists, "./hiring" when ./hiring/criteria.md exists,
    otherwise exit and name both. With --root: that folder, or its hiring/ child.
    """
    here = pathlib.Path(arg) if arg else pathlib.Path(".")
    for cand in (here, here / "hiring"):
        if (cand / "criteria.md").is_file():
            return cand.resolve()
    raise SystemExit("no criteria.md in %s or %s. Run this from your hiring/ folder (the one that holds "
                     "criteria.md) or from the folder above it, or pass --root path/to/hiring."
                     % (here / "criteria.md", here / "hiring" / "criteria.md"))


def load_json(p, default):
    p = pathlib.Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"{p} is not valid JSON: {e}")


def demo_label(root, cfg=None) -> str:
    """The badge text. config.json "demo_badge" wins (an empty string turns it off); otherwise the
    badge shows when the first lines of criteria.md say FICTIONAL DEMO. A real search shows none."""
    if isinstance(cfg, dict) and "demo_badge" in cfg:
        return str(cfg.get("demo_badge") or "")
    crit = pathlib.Path(root) / "criteria.md"
    try:
        head = crit.read_text(encoding="utf-8")[:4000]
    except OSError:
        return ""
    return "FICTIONAL DEMO" if "FICTIONAL DEMO" in head.upper() else ""


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def js_json(obj) -> str:
    """JSON for an inline <script>: no "<", ">" or "&" survives, so nothing from a file can open or close a tag."""
    return json.dumps(obj).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def words(n) -> str:
    try:
        f = float(n)
    except (TypeError, ValueError):
        return str(n)
    return NUM_WORDS.get(int(f), str(n)) if f.is_integer() else str(n)


def _num(v, default=0.0) -> float:
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def effort(hours) -> str:
    """'one hour', 'two hours', 'half an hour', '1.5 hours'."""
    h = _num(hours, 2.0)
    if h == 0.5:
        return "half an hour"
    return f"{words(hours)} hour" if h == 1 else f"{words(hours)} hours"


def task_terms(cfg: dict) -> dict:
    """What the brief, the agreement, the terms message and the review board say about pay and use.

    fee_usd above 0 is a paid task: one fee for everyone, and the founder may use the work.
    fee_usd null, 0 or missing is an unpaid task: no fee line anywhere, and the work is never used.
    The strings may hold {brand}, {name} and {signoff}; fill them like any other placeholder.
    """
    fee = _num(cfg.get("fee_usd"), 0.0)
    paid = fee > 0
    shown = "$%s" % (int(fee) if fee.is_integer() else fee) if paid else ""
    hours = cfg.get("expected_hours", 2)
    t = {"paid": paid, "fee": shown, "effort": effort(hours)}
    if paid:
        t.update(
            pay_line=f"{shown} for both parts, {cfg.get('payment', '')}, whether or not this leads to the role.",
            use_line=("This task is paid because I may use what you create. Once it is paid, {brand} may use it in its "
                      "own business. I will not publish or share it outside the business without asking you first. "
                      "The one-paragraph agreement that comes with this brief says the same."),
            glance_pay=f"{shown}, one fee",
            board_pay=f"One fee for everyone: {shown}.",
            fee_terms=("{brand} pays {name} %s for the task, whether or not it leads to a role, within a week of "
                       "receiving the work." % shown),
            use_terms=("Because the task is paid, {brand} may use what {name} creates for it in its own business. "
                       "{brand} makes no claim on anything {name} has made before, makes elsewhere, or makes after this "
                       "task; only the work delivered for this task is covered. {brand} will not publish, share or "
                       "present the work outside its own business without asking {name} first."),
            stop_terms="Either side can stop the task at any point; the full fee is paid for any submission made in good faith, finished or not.",
            task_line=f"The task is paid separately ({shown}) and should take about {t['effort']}.")
    else:
        t.update(
            pay_line="This task is unpaid.",
            use_line=("This task is unpaid, so {brand} will not use what you make, in the business or anywhere else. "
                      "Only I read it, to decide on the role. The one-paragraph agreement that comes with this brief "
                      "says the same."),
            glance_pay="Unpaid",
            board_pay="Unpaid, the same for everyone.",
            fee_terms="The task is unpaid.",
            use_terms=("{brand} will not use what {name} creates for it, in its business or anywhere else, and makes "
                       "no claim on it or on anything else {name} makes. Only {signoff} reads "
                       "it, to decide on the role, and it is not shared."),
            stop_terms="Either side can stop the task at any point.",
            task_line=f"The task is unpaid and should take about {t['effort']}. I will not use what you make.")
    return t


def pay_advice(cfg: dict) -> list:
    """Lines to print when the task has no fee. A fee is recommended for a task over about an hour or on the
    founder's real material (a real list, a real file, work the founder might use). The founder decides."""
    if task_terms(cfg)["paid"]:
        return []
    why = []
    if _num(cfg.get("expected_hours", 2), 2.0) > 1:
        why.append(f"it takes about {effort(cfg.get('expected_hours', 2))}")
    if cfg.get("real_material"):
        why.append("it uses your real business material")
    out = []
    if cfg.get("real_material") is None:
        out.append("note: real_material is not set in config.json. Ask the founder whether the task uses real business "
                   "material (a real list, a real file, work they might use), then set true or false.")
    if why:
        out.append("recommend a fee: " + " and ".join(why) + ". That is real work, and strong candidates skip long "
                   "unpaid tasks. You decide: set fee_usd, or keep it unpaid and never use the work.")
    return out


def no_dashes(text: str, what: str) -> None:
    for bad in ("\u2014", "\u2013"):
        if bad in text:
            raise SystemExit(f"{what}: remove the long dash ({ascii(bad)}); use a period or a comma")


# ---------- what a finalist sent, and what each stage wrote about them ----------

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def submission_files(ch, f: dict):
    """Files (or folders) in challenge/submissions/ named after this finalist: the slug, or the full or first
    name, in any form ("Ava - Brimfold test task.pdf", "ava.md", "Cara_Monday.pdf"). Sorted, text files first."""
    folder = pathlib.Path(ch) / "submissions"
    if not folder.is_dir():
        return []
    slug, name = _norm(f.get("slug", "")), _norm(f.get("name", ""))
    first = name.split("-")[0] if name else ""
    keys = [k for k in (slug, name) if k] + ([first] if len(first) > 1 else [])
    out = []
    for p in folder.iterdir():
        if p.name.startswith("."):
            continue
        stem = "-" + _norm(p.stem if p.is_file() else p.name) + "-"
        if any("-" + k + "-" in stem for k in keys):
            out.append(p)
    return sorted(out, key=lambda p: (p.suffix.lower() not in (".md", ".txt"), p.name))


def submitted(ch, f: dict, r: dict) -> bool:
    """Counted as submitted when review.json has a "received" value or any file for the finalist is in submissions/."""
    return bool((r or {}).get("received")) or bool(submission_files(ch, f))


def reference_summary(root, slug: str):
    """The reference summary for one finalist, or None: out/references/<slug>-summary.md, else any .md under out/
    whose name has the slug and "reference" in it."""
    root = pathlib.Path(root)
    first = root / "out" / "references" / f"{slug}-summary.md"
    if first.is_file():
        return first
    for p in sorted((root / "out").rglob("*.md")) if (root / "out").is_dir() else []:
        n = p.name.lower()
        if slug in n and "reference" in n and "question" not in n and "notes" not in n:
            return p
    return None


def dossier_section(root, slug: str, heading: str) -> str:
    """The text under "## <heading>" in out/candidates/<slug>.md, the screening dossier, or ""."""
    p = pathlib.Path(root) / "out" / "candidates" / f"{slug}.md"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    m = re.search(r"^##\s+" + re.escape(heading) + r"\s*$(.*?)(?=^## |\Z)", text, re.M | re.S | re.I)
    return m.group(1) if m else ""


def dossier_insufficient(root, slug: str) -> bool:
    """The dossier's "Evidence level:" line under ## Scores says insufficient (the rule build_board.py uses)."""
    m = re.search(r"^\s*[-*]\s*Evidence level:\s*(.*)$", dossier_section(root, slug, "Scores"), re.M | re.I)
    return bool(m) and "insufficient" in m.group(1).lower()


def whole(v):
    """A score as a whole number, half up (40.5 is 41), from a number or a numeric string; None otherwise."""
    if isinstance(v, bool):
        return None
    try:
        return int(float(v) + 0.5) if float(v) >= 0 else -int(-float(v) + 0.5)
    except (TypeError, ValueError, OverflowError):
        return None


def evidence(root, f: dict, review: dict):
    """[(stage, relative path or None)] for one finalist, in the order of the search."""
    root, slug = pathlib.Path(root), f["slug"]
    r = review.get(slug) if isinstance(review.get(slug), dict) else {}

    def rel(p):
        return str(p.relative_to(root)) if p and p.exists() else None
    ch = root / "challenge"
    founder = r.get("founder") if isinstance(r.get("founder"), dict) else {}
    return [
        ("Screen and questionnaire (the dossier)", rel(root / "out" / "candidates" / f"{slug}.md")),
        ("Claim check", rel(root / "out" / "verification" / f"{slug}.md")),
        ("Interview review", rel(root / "out" / "interviews" / slug / "CANDIDATE_DEBRIEF.md")),
        ("Your interview scores", rel(root / "out" / "interviews" / slug / "FOUNDER_SCORES.md")),
        ("Test task, what they sent", ", ".join(str(p.relative_to(root)) for p in submission_files(ch, f))
         or ("challenge/review.json (received)" if r.get("received") else None)),
        ("Test task, your rating", "challenge/review.json" if founder.get("core") else None),
        ("References", rel(reference_summary(root, slug))),
    ]


# ---------- the review rubric: four questions, the same for every finalist and both parts ----------

QUESTIONS = [
    ("understood_goal", "Did they get the goal?"),
    ("relevant_work", "Is it about my business?"),
    ("reasoning_visible", "Can I see why they chose it?"),
    ("would_use_it", "Would I use it on Monday?"),
]
PARTS = [("core", "Part 1, the shared task"), ("specialist", "Part 2, the specialist part")]
ANCHORS = {
    "understood_goal": ("Built for the goal in the brief; made a choice the ask did not spell out.",
                        "Did the ask literally, or solved a different problem."),
    "relevant_work": ("Uses this business's numbers, dates, people and limits.",
                      "Could be sent to any business, or needs systems the business does not have."),
    "reasoning_visible": ("Says why, what was left out, what is missing, and where a person checks.",
                          "Conclusions without reasons; \"a human in the loop\" with no place named."),
    "would_use_it": ("You could act on it on Monday morning, maybe after one small fix.",
                     "You would rebuild it before using it."),
}


def rating(block, key):
    """(score or None, line) from {"key": [score, "line"]} or {"key": score}."""
    v = (block or {}).get(key) if isinstance(block, dict) else None
    line = ""
    if isinstance(v, list):
        v, line = (list(v) + [None, ""])[:2]
    if isinstance(v, dict):
        v, line = v.get("score"), v.get("line", v.get("note", ""))
    return (v if isinstance(v, int) and 1 <= v <= 5 else None), ("" if line is None else str(line))


def part_scores(block):
    return [s for s, _ in (rating(block, k) for k, _ in QUESTIONS) if s is not None]


def part_complete(block) -> bool:
    return len(part_scores(block)) == len(QUESTIONS)


def track_of(f: dict, r: dict) -> str:
    """The specialist track: config.json "track", else review.json "track", else "(listings track)" in the task text."""
    t = (f or {}).get("track") or (r or {}).get("track") or ""
    if not t:
        m = re.search(r"\(([^()]*track)\)", (f or {}).get("task", ""), re.I)
        t = m.group(1) if m else ""
    return t.strip()


def parts_for(f: dict, r: dict):
    """Part keys this finalist is rated on: core always, specialist when a track exists or was rated."""
    founder = (r or {}).get("founder", {}) if isinstance(r, dict) else {}
    claude = (r or {}).get("claude", {}) if isinstance(r, dict) else {}
    has_spec = bool(track_of(f, r)) or "specialist" in founder or "specialist" in claude
    return ["core", "specialist"] if has_spec else ["core"]


def founder_done(f: dict, r: dict) -> bool:
    founder = (r or {}).get("founder", {}) if isinstance(r, dict) else {}
    return all(part_complete(founder.get(p)) for p in parts_for(f, r))


def names_visible(review: dict, finalists) -> bool:
    """Names show only when the founder has rated every part of every finalist."""
    return bool(finalists) and all(
        founder_done(f, review.get(f["slug"]) if isinstance(review.get(f["slug"]), dict) else {}) for f in finalists)


def letter(i: int) -> str:
    return chr(65 + i) if i < 26 else str(i + 1)


def table_cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]



def read_core_items(path):
    """[(n, area, text)] from the first table in the core task whose first column is a number."""
    path = pathlib.Path(path)
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("|"):
            cells = table_cells(line)
            if len(cells) >= 3 and re.fullmatch(r"\d+", cells[0]):
                items.append((int(cells[0]), cells[1], " | ".join(cells[2:])))
            elif items:
                break
        elif items:
            break
    return items



def read_core_header(path):
    """The header cells of the table read_core_items reads (the row above its |---| line), or []."""
    path = pathlib.Path(path)
    if not path.exists():
        return []
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
    for i, line in enumerate(lines):
        cells = table_cells(line) if line.startswith("|") else []
        if len(cells) >= 3 and re.fullmatch(r"\d+", cells[0]):
            if i >= 2 and set(lines[i - 1].replace("|", "").strip()) <= set("-: ") and lines[i - 2].startswith("|"):
                return table_cells(lines[i - 2])
            return []
    return []


# Type sizes are set for a 1920x1080 screen recording watched on a phone:
# body 22px or more, tables 20px or more, no label under 18px.
BASE_CSS = """
:root{--bg:#f5f4ef;--card:#fff;--ink:#1c1c1e;--mute:#55555c;--line:#dedbd2;--acc:#2a55c9;--acc-bg:#e7edfb;
--ok:#17713f;--ok-bg:#dcf2e4;--warn:#8a5300;--warn-bg:#fdefd3;--no:#a3241b;--no-bg:#fbe1de;--soft:#efede6}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:22px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.bar{position:sticky;top:0;z-index:20;display:flex;justify-content:space-between;align-items:center;gap:16px;
padding:12px 40px;background:var(--ink);color:#fff;font-size:20px}
.bar .where{opacity:.85;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar .where b{opacity:1;color:#fff;letter-spacing:.02em}
.badge{flex:none;background:#ffd84d;color:#1c1c1e;font-weight:800;font-size:24px;letter-spacing:.08em;
padding:8px 16px;border-radius:8px;white-space:nowrap}
main{max-width:1640px;margin:0 auto;padding:28px 40px 90px}
h1{font-size:42px;line-height:1.15;margin:6px 0 8px;letter-spacing:-.01em}
h2{font-size:30px;line-height:1.2;margin:40px 0 12px}
h3{font-size:25px;margin:22px 0 8px}
p{margin:0 0 12px}
.sub{color:var(--mute);margin:0 0 16px;max-width:1300px}
.note{font-size:20px;color:var(--mute)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 24px;margin:14px 0}
table{width:100%;border-collapse:collapse;font-size:20px;line-height:1.4}
th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;overflow-wrap:anywhere}
th{font-size:20px;font-weight:700;color:var(--ink);background:var(--soft)}
.pill{display:inline-block;font-size:20px;font-weight:600;padding:2px 12px;border-radius:999px;margin:2px 6px 2px 0;
white-space:nowrap;border:1.5px solid transparent;line-height:1.35}
.p-ok{background:var(--ok-bg);color:var(--ok)}.p-warn{background:var(--warn-bg);color:var(--warn)}
.p-no{background:var(--no-bg);color:var(--no)}.p-acc{background:var(--acc-bg);color:var(--acc)}
.p-mute{background:var(--soft);color:var(--mute)}.p-line{border-color:var(--mute);color:var(--mute);background:transparent}
.banner{background:var(--warn-bg);border-left:6px solid var(--warn);padding:12px 16px;border-radius:6px;margin:12px 0;font-size:20px}
.info{background:var(--acc-bg);border-left:6px solid var(--acc);padding:12px 16px;border-radius:6px;margin:12px 0;font-size:20px}
a{color:var(--acc)}
textarea,input,select,button{font:inherit;font-size:20px;color:var(--ink)}
textarea{width:100%;border:1px solid var(--line);border-radius:10px;padding:12px;background:#fff;min-height:110px}
select,button,input{border:1px solid var(--line);border-radius:10px;padding:6px 12px;background:#fff}
button{cursor:pointer}button.p{background:var(--acc);color:#fff;border-color:var(--acc)}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:12px}
.foot{color:var(--mute);font-size:20px;margin-top:36px;max-width:1300px}
details>summary{cursor:pointer;font-weight:600}
@media (max-width:760px){
 .bar{padding:10px 16px;font-size:18px}.badge{font-size:19px;padding:6px 10px}
 main{padding:18px 16px 60px}h1{font-size:32px}h2{font-size:26px}
 th,td{padding:8px 6px}
}
@media print{.bar{position:static}body{background:#fff}}
"""


def page(title: str, where: str, body: str, badge: str, css: str = "", script: str = "") -> str:
    """A full HTML page. Every argument except body, css and script is plain text and is escaped here;
    body must already be built from escaped parts."""
    badge_html = f'<span class="badge">{esc(badge)}</span>' if badge else ""
    title_full = f"{title} | {badge}" if badge else title
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{esc(title_full)}</title>\n<style>{BASE_CSS}{css}</style></head><body>\n"
        f"<header class=\"bar\"><span class=\"where\">{esc(where)}</span>{badge_html}</header>\n"
        f"<main>\n{body}\n</main>\n"
        + (f"<script>{script}</script>\n" if script else "")
        + "</body></html>\n"
    )


if __name__ == "__main__":
    print("_common.py holds helpers for the other hire-test-task scripts; it writes nothing.")
