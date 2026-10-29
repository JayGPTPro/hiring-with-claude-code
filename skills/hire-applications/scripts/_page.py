"""Shared page shell for the hire-applications HTML pages (board.html, evidence/<slug>.html).

Every page escapes every piece of applicant text with html.escape before it is written. Nothing
from an application is ever passed through as HTML. Standard library only.

Type sizes are set for a page that may be recorded at 1920x1080 and watched on a phone:
body text 22px, table text 20px, headings larger, no label under 16px.
"""
import html
import os
import re

DEMO_MARK = re.compile(r"FICTIONAL DEMO", re.I)


def esc(value):
    """Escape any value for HTML text or an attribute. None becomes an empty string."""
    return html.escape("" if value is None else str(value), quote=True)


def is_demo(root, force=None):
    """True when criteria.md says FICTIONAL DEMO (or --demo was passed). Then every page shows the badge."""
    if force is not None:
        return force
    path = os.path.join(root, "criteria.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return bool(DEMO_MARK.search(f.read()))
    return False


BASE_CSS = """
:root{--ink:#17202a;--muted:#55606e;--line:#dfe3e8;--bg:#f7f6f2;--card:#ffffff;--soft:#f0f1f3;
 --met:#166534;--met-bg:#dcfce7;--ask:#1e40af;--ask-bg:#dbeafe;--not:#374151;--not-bg:#e5e7eb;
 --human:#9a3412;--human-bg:#ffedd5;--warn:#92400e;--warn-bg:#fef3c7;--alert:#9f1239;--alert-bg:#ffe4e6}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);
 font:22px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
a{color:inherit;text-decoration-color:#9aa3ad;text-underline-offset:3px}
header.top{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:24px;
 justify-content:space-between;background:var(--bg);padding:18px 32px 14px;border-bottom:1px solid var(--line)}
header.top h1{margin:0;font-size:34px;line-height:1.15;letter-spacing:-0.01em}
header.top .kicker{display:block;font-size:18px;font-weight:600;color:var(--muted);letter-spacing:.04em;
 text-transform:uppercase;margin-bottom:2px}
.badge-demo{flex:none;background:#111827;color:#fff;font-weight:800;font-size:26px;letter-spacing:.06em;
 padding:10px 20px;border-radius:10px;white-space:nowrap}
main{padding:20px 32px 64px}
.sub{color:var(--muted);margin:0 0 14px;max-width:1500px}
.tag{display:inline-block;font-size:18px;font-weight:700;padding:4px 12px;border-radius:999px;white-space:nowrap;line-height:1.3}
.tag.met{background:var(--met-bg);color:var(--met)}
.tag.ask{background:var(--ask-bg);color:var(--ask)}
.tag.not{background:var(--not-bg);color:var(--not)}
.tag.human{background:var(--human-bg);color:var(--human);white-space:normal;border-radius:10px}
.tag.plain{background:var(--soft);color:var(--muted)}
.foot{color:var(--muted);font-size:18px;margin-top:28px;max-width:1500px}
.foot p{margin:6px 0}
@media (max-width:900px){header.top{padding:12px 16px;flex-wrap:wrap}header.top h1{font-size:26px}
 .badge-demo{font-size:20px;padding:8px 12px}main{padding:14px 16px 40px}}
"""


def page(title, kicker, body, demo, extra_css="", script=""):
    """One full HTML document. `title` and `kicker` are plain text (escaped here); `body` is HTML
    that the caller already built from escaped parts."""
    badge = '<div class="badge-demo" aria-label="Fictional demo data">FICTIONAL DEMO</div>' if demo else ""
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<meta name=\"robots\" content=\"noindex\">\n"
            "<title>%s</title>\n<style>%s%s</style>\n</head>\n<body>\n"
            "<header class=\"top\"><div><span class=\"kicker\">%s</span><h1>%s</h1></div>%s</header>\n"
            "<main>\n%s\n</main>\n%s</body>\n</html>\n") % (
        esc(title), BASE_CSS, extra_css, esc(kicker), esc(title), badge, body,
        ("<script>\n%s\n</script>\n" % script) if script else "")


STATUS_TAGS = {
    "met": ("Met", "met"),
    "not shown": ("Not shown", "not"),
    "ask": ("Ask", "ask"),
    "human review required": ("Human review required", "human"),
}


def status_tag(text):
    """The four Evidence Map tags. Anything else is shown as written, in grey."""
    key = (text or "").strip().lower().rstrip(".")
    label, cls = STATUS_TAGS.get(key, ((text or "").strip() or "unknown", "plain"))
    return '<span class="tag %s">%s</span>' % (cls, esc(label))
