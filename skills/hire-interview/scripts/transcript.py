#!/usr/bin/env python3
"""Turn a call transcript into the format the other scripts read. Standard library only, no network.

Usage (from your hiring/ folder or the folder above it):
  python3 <skill>/scripts/transcript.py SOURCE SLUG [--candidate NAME] [--interviewer NAME ...] [--root PATH]

SOURCE is the file you downloaded: a Google Meet transcript (.docx or .txt), a Zoom .vtt, an .sbv, or plain
text with "Name: text" lines. It is read, never changed. The result is out/interviews/transcripts/<SLUG>.txt,
one turn per line:
  [MM:SS] INTERVIEWER: text
  [MM:SS] CANDIDATE: text
The candidate is the speaker whose name matches --candidate, or the candidate's name in prep.json. A full
name is matched first; a first name only when one speaker has it. Every other speaker is INTERVIEWER. When the
file has more than one other speaker, name each interviewer with --interviewer "Name" (once per person). If
the speakers do not map to one CANDIDATE and the named interviewers, nothing is written and the script lists
the speaker names it saw.
Long dashes (em and en dash) in the text become a comma, or a hyphen between two numbers (2019-2021), so the
transcript passes the no-dash rule. The source file keeps them.

Minutes:
  - Zoom .vtt and .sbv carry a time on every line: those minutes are real.
  - Google Meet prints a time only every few minutes. Between two of them the minute of each turn is
    estimated from the words spoken, and written with a ~ ([~06:23]). Plain text with no times is estimated
    at 150 words a minute. A quote with a ~ minute is approximate: check the recording before relying on it.
Each turn stays on one line. A turn that Meet splits at one of its timestamps, or Zoom splits over several
cues, is joined back, so the speaker check in stats.py does not flag lines that were never two turns. Two
lines in a row from the same speaker are kept apart only when the first asks a question and the second is a
short answer: that is the line a person should check against the recording.
An existing transcript is never overwritten. Prints what it wrote.
"""
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

WPM = 150
SHORT = 12
CUE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})[.,]\d{1,3}\s*(?:-->|,)\s*(?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3}")
STAMP = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$")
ENDED = re.compile(r"^Meeting ended after (\d{1,2}):(\d{2}):(\d{2})", re.I)
TIMED = re.compile(r"^\[?(~)?(?:(\d+):)?(\d{1,2}):(\d{2})\]?\s+(.+)$")
SPEAKER = re.compile(r"^([^\s:][^:]{0,60}?):\s+(.*)$")
VOICE = re.compile(r"^<v(?:\.[^ >]*)?\s+([^>]+)>(.*?)(?:</v>)?$")


def docx_lines(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    out = []
    for p in re.findall(r"<w:p[ >].*?</w:p>|<w:p/>", xml, re.S):
        p = re.sub(r"<w:(?:br|tab)\b[^>]*/>", " ", p)
        text = "".join(re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", p, re.S))
        out.append(text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&"))
    return out


def secs(h, m, s):
    return (int(h) if h else 0) * 3600 + int(m) * 60 + int(s)


def speaker_text(line, last):
    v = VOICE.match(line)
    if v:
        return v.group(1).strip(), v.group(2).strip()
    m = SPEAKER.match(line)
    if m and not re.fullmatch(r"https?|\d+", m.group(1).strip()):
        return m.group(1).strip(), m.group(2).strip()
    return last, line


def parse_cues(lines):
    """VTT and SBV: a time line, then the text. Every entry has a real time."""
    out, t, who = [], None, None
    for raw in lines:
        line = raw.strip()
        m = CUE.match(line)
        if m:
            t = secs(*m.groups())
            continue
        if t is None or not line or line.upper().startswith(("WEBVTT", "NOTE")) or line.isdigit():
            continue
        who, text = speaker_text(line, who)
        if out and out[-1]["t"] == t and out[-1]["who"] == who:
            out[-1]["text"] += " " + text
        else:
            out.append({"t": t, "who": who, "text": text, "est": False, "cut": "cue"})
    return out


def parse_meet(lines):
    """Google Meet: a time only every few minutes. Turns between two times are spread by their words."""
    blocks, end, started = [], None, False
    for raw in lines:
        line = raw.strip()
        m = STAMP.match(line)
        if m:
            started = True
            blocks.append({"t": secs(*m.groups()), "turns": []})
            continue
        m = ENDED.match(line)
        if m:
            end = secs(*m.groups())
            continue
        if not started or not line:
            continue
        who, text = speaker_text(line, None)
        if who is None and blocks[-1]["turns"]:
            blocks[-1]["turns"][-1]["text"] += " " + line
        elif who is not None:
            blocks[-1]["turns"].append({"who": who, "text": text})
    out = []
    for i, b in enumerate(blocks):
        words = [len(x["text"].split()) for x in b["turns"]]
        total = sum(words) or 1
        stop = blocks[i + 1]["t"] if i + 1 < len(blocks) else (end or b["t"] + round(total * 60 / WPM))
        done = 0
        for k, (x, n) in enumerate(zip(b["turns"], words)):
            out.append({"t": b["t"] + round((stop - b["t"]) * done / total), "who": x["who"], "text": x["text"],
                        "est": done > 0, "cut": "stamp" if k == 0 else None})
            done += n
    return out


def parse_plain(lines):
    """Plain text: "Name: text", with or without a time in front. No time means estimated by words."""
    out, t, who = [], 0, None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = TIMED.match(line)
        if m and (m.group(2) or m.group(3)):
            t_line, est, rest = secs(m.group(2), m.group(3), m.group(4)), bool(m.group(1)), m.group(5)
        else:
            t_line, est, rest = None, True, line
        who2, text = speaker_text(rest, None)
        if who2 is None:
            if out:
                out[-1]["text"] += " " + rest
            continue
        if t_line is not None:
            t = t_line
        out.append({"t": t, "who": who2, "text": text, "est": est, "cut": None})
        t += round(len(text.split()) * 60 / WPM)
    return out


def detect(lines):
    head = [l.strip() for l in lines if l.strip()][:400]
    if any(l.upper().startswith("WEBVTT") for l in head[:2]) or any(CUE.match(l) for l in head):
        return "cues", parse_cues
    if any(STAMP.match(l) for l in head):
        return "meet", parse_meet
    return "plain", parse_plain


def merge(entries):
    """Join a turn that the source split: always at a Meet timestamp (Meet repeats the name after it), and over
    Zoom cues unless a question is followed by a short line, the line the speaker check asks a person to verify."""
    out = []
    for e in entries:
        p = out[-1] if out else None
        if p and p["who"] == e["who"] and e["cut"] and not p.get("hold"):
            asks_then_short = p["text"].rstrip().endswith("?") and len(e["text"].split()) <= SHORT and "?" not in e["text"]
            if e["cut"] == "stamp" or not asks_then_short:
                p["text"] += " " + e["text"]
                continue
            e = dict(e, hold=True)
        out.append(dict(e))
    return out


def norm(name):
    return re.sub(r"\s*[(\[].*?[)\]]\s*", " ", name or "").strip().lower()


def matches(name, speakers):
    """The speakers this name means: the full name first, a first name only when one speaker has it."""
    n = norm(name)
    if not n:
        return []
    full = [s for s in speakers if norm(s) == n]
    if full:
        return full
    first = [s for s in speakers if norm(s).split()[:1] == n.split()[:1]]
    return first if len(first) == 1 else []


def no_long_dashes(text):
    """An em or en dash becomes a comma, or a hyphen between two numbers. Returns (text, how many)."""
    n = sum(text.count(d) for d in common.DASHES)
    text = re.sub(r"(\d)\s*[\u2013\u2014]\s*(?=\d)", r"\1-", text)
    text = re.sub(r"\s*[\u2013\u2014]+\s*", ", ", text)
    text = re.sub(r",\s*([,.;:?!])", r"\1", text)
    return re.sub(r"^,\s*", "", text), n


def main():
    root, args = common.root_from_argv(sys.argv[1:])
    cand, inter_names = None, []
    while "--candidate" in args or "--interviewer" in args:
        flag = "--candidate" if "--candidate" in args else "--interviewer"
        k = args.index(flag)
        value = args[k + 1] if k + 1 < len(args) else None
        del args[k:k + 2]
        if flag == "--candidate":
            cand = value
        elif value:
            inter_names.append(value)
    if len(args) != 2:
        sys.exit("usage: transcript.py SOURCE SLUG [--candidate NAME] [--interviewer NAME ...]. SOURCE is the Meet, Zoom "
                 "or text file; SLUG is the candidate's slug, as in prep.json.")
    src, slug = args
    if not os.path.isfile(src):
        sys.exit(f"no file {src}")
    dst = os.path.join(common.interviews_dir(root), "transcripts", f"{slug}.txt")
    if os.path.abspath(dst) == os.path.abspath(src):
        sys.exit(f"{src} is already the transcript for {slug}.")
    if os.path.exists(dst):
        sys.exit(f"{dst} exists already. A transcript is never overwritten; remove it yourself if you want to convert again.")
    if not cand:
        c = common.prep_candidate(common.load_prep(root), slug) or {}
        cand = c.get("name") or c.get("first")
    if not cand:
        sys.exit(f"which speaker is the candidate? {slug} is not in prep.json; pass --candidate \"Their name\".")
    if src.lower().endswith(".docx"):
        lines = docx_lines(src)
    else:
        with open(src, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    kind, parse = detect(lines)
    entries = [e for e in parse(lines) if e["who"] and e["text"].strip()]
    if not entries:
        sys.exit(f"{src}: no lines like \"Name: text\" found. Expected a Meet transcript, a Zoom .vtt, an .sbv or plain text.")
    speakers = sorted({e["who"] for e in entries})
    if set(speakers) <= {"INTERVIEWER", "CANDIDATE"}:
        cand, inter_names = "CANDIDATE", ["INTERVIEWER"]
    cands = matches(cand, speakers)
    if inter_names:
        inter = [s for n in inter_names for s in matches(n, speakers)]
        unnamed = [n for n in inter_names if not matches(n, speakers)]
    else:
        inter, unnamed = [s for s in speakers if s not in cands], []
    left = [s for s in speakers if s not in cands and s not in inter]
    same_first = [s for s in speakers if norm(s).split()[:1] == norm(cand).split()[:1]]
    problem = ("the candidate %r could be any of %d speakers with that first name" % (cand, len(same_first))
               if not cands and len(same_first) > 1 else
               "no speaker matches the candidate %r" % cand if not cands else
               "the candidate %r matches %d speakers" % (cand, len(cands)) if len(cands) > 1 else
               "no speaker matches the interviewer %s" % ", ".join(repr(n) for n in unnamed) if unnamed else
               "%s is both the candidate and an interviewer" % cands[0] if set(cands) & set(inter) else
               "no other speaker to label INTERVIEWER" if not inter else
               "%d speakers would be INTERVIEWER" % len(inter) if len(inter) > 1 and not inter_names else
               "%s is neither the candidate nor a named interviewer" % ", ".join(left) if left else "")
    if problem:
        sys.exit(f"{problem}, so nothing was written. Speakers in the file: {'; '.join(speakers)}. Pass the full names "
                 f"as they appear there: --candidate \"<name>\" once, and --interviewer \"<name>\" once for each interviewer.")
    for e in entries:
        e["who"] = "CANDIDATE" if e["who"] in cands else "INTERVIEWER"
        e["text"], e["dashes"] = no_long_dashes(e["text"])
    dashes = sum(e["dashes"] for e in entries)
    rows = merge(entries)
    text = "\n".join(f"[{'~' if r['est'] else ''}{r['t'] // 60:02d}:{r['t'] % 60:02d}] {r['who']}: {' '.join(r['text'].split())}"
                     for r in rows) + "\n"
    common.write(dst, text)
    est = sum(1 for r in rows if r["est"])
    print(f"  {len(rows)} turns from a {kind} file. CANDIDATE: {cands[0]}; INTERVIEWER: {', '.join(inter)}.")
    if est:
        print(f"  {est} of {len(rows)} minutes are estimated and marked ~. Quotes with a ~ minute are approximate.")
    if dashes:
        print(f"  {dashes} long dash{'es' if dashes != 1 else ''} became a comma or a hyphen. The source file is unchanged.")


if __name__ == "__main__":
    main()
