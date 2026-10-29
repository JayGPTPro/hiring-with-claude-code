"""Shared helpers for the hire-first-month scripts. Python 3 standard library only, no network.

Not a command. plan.py imports it:
  demo_label(root, cfg)  "FICTIONAL DEMO" when criteria.md says so (or config.json sets demo_badge)
  esc(value)             html.escape for every string that came from a file
  js_json(obj)           JSON safe to put inside an inline <script>
  page(...)              the page shell: a sticky top bar with the badge, legible type for video and phone
"""
import html
import json
import pathlib


def demo_label(root, cfg=None) -> str:
    """The badge text. config.json "demo_badge" wins (an empty string turns it off); otherwise the
    badge shows when the first lines of criteria.md say FICTIONAL DEMO. A real hire shows none."""
    if isinstance(cfg, dict) and "demo_badge" in cfg:
        return str(cfg.get("demo_badge") or "")
    try:
        head = (pathlib.Path(root) / "criteria.md").read_text(encoding="utf-8")[:4000]
    except OSError:
        return ""
    return "FICTIONAL DEMO" if "FICTIONAL DEMO" in head.upper() else ""


def js_json(obj) -> str:
    """JSON for an inline <script>: no "<", ">" or "&" survives, so nothing from a file can open or close a tag."""
    return json.dumps(obj).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


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
    print("_common.py holds helpers for plan.py; it writes nothing.")
