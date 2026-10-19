#!/usr/bin/env python3
"""Life Diary tool for Shittu AbdulQadir Adeshina.

Commands
  new [YYYY-MM-DD]        create a blank entry from templates/entry_template.md
  build [FILE ...]        build signed PDFs (no FILE: only entries missing a PDF)
  build --all             rebuild every PDF
  achievements            regenerate ACHIEVEMENTS.md from all entries

Entries live in entries/YYYY/MM/YYYY-MM-DD.md, PDFs in pdf/YYYY/MM/.
PDF engine: WeasyPrint if installed, otherwise wkhtmltopdf.
"""
import argparse
import base64
import datetime
import html
import io
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "Shittu AbdulQadir Adeshina"
SIGNATURE = "عبدالقادر"
PHOTO = ROOT / "assets" / "photo.jpg"
BACKGROUNDS = ROOT / "assets" / "backgrounds"  # faded photos; one is picked at random for each page
ACTIVITY_SECTIONS = ("Morning", "Afternoon", "Evening")

ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")


# ---------------------------------------------------------------- parsing
def all_entries():
    return sorted(ROOT.glob("entries/*/*/*.md"))


def pdf_path(entry):
    return ROOT / "pdf" / entry.parent.relative_to(ROOT / "entries") / (entry.stem + ".pdf")


def parse(path):
    """Return (date, meta, sections) where sections = [(title, [(kind, text)])]."""
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    meta, sections, cur = {}, [], None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.startswith("# "):
            continue
        if line.startswith("## "):
            cur = (line[3:].strip(), [])
            sections.append(cur)
            continue
        if cur is None:
            m = re.match(r"^([A-Za-z][\w ]*):\s*(.*)$", line)
            if m and m.group(2).strip():
                meta[m.group(1).strip()] = m.group(2).strip()
            continue
        m = re.match(r"^\s*[-*]\s*(.*)$", line)
        if m:
            if m.group(1).strip():
                cur[1].append(("li", m.group(1).strip()))
        else:
            cur[1].append(("p", line.strip()))
    date = datetime.date.fromisoformat(path.stem)
    return date, meta, [(t, items) for t, items in sections if items]


# ---------------------------------------------------------------- html
def is_rtl(text):
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(1 for c in letters if ARABIC.match(c)) / len(letters) > 0.5


def inline(text):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text))


def render_items(items, star=False):
    out, in_list = [], False
    for kind, text in items:
        d = ' dir="rtl" class="rtl"' if is_rtl(text) else ""
        if kind == "li":
            if not in_list:
                out.append('<ul class="star">' if star else "<ul>")
                in_list = True
            out.append(f"<li{d}>{inline(text)}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p{d}>{inline(text)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 14mm; }
html, body { background: transparent !important; }
body { font-family: 'DejaVu Serif', Georgia, serif; color: #1f2a2e; font-size: 11.5pt; line-height: 1.55; margin: 0; }
.band { background: #0f4c45; color: #fff; padding: 14px 18px; border-bottom: 4px solid #b8893b; }
.band table { width: 100%; border-collapse: collapse; }
.photo { width: 96px; height: 96px; border-radius: 48px; border: 3px solid #b8893b; }
.title { font-size: 9pt; letter-spacing: 3px; text-transform: uppercase; color: #e5c88a; }
.date { font-size: 21pt; font-weight: bold; margin: 2px 0; }
.who { font-size: 10.5pt; color: #d7ece8; }
.badge { text-align: right; vertical-align: top; font-size: 9pt; color: #e5c88a; }
.meta { margin: 10px 2px 0 2px; font-size: 10pt; color: #55656a; }
.meta b { color: #0f4c45; }
h2 { font-size: 13pt; color: #0f4c45; border-bottom: 1.5px solid #b8893b; padding-bottom: 2px; margin: 18px 0 6px 0; page-break-after: avoid; }
h3 { font-size: 11pt; color: #8a6420; margin: 10px 0 2px 0; page-break-after: avoid; }
ul { margin: 4px 0 4px 0; padding-left: 20px; }
li { margin-bottom: 3px; }
p { margin: 4px 0; }
.rtl { text-align: right; font-family: 'Amiri', 'Noto Naskh Arabic', 'DejaVu Sans', sans-serif; font-size: 13pt; }
ul.star { list-style: none; padding-left: 0; }
ul.star li { padding-left: 20px; position: relative; }
ul.star li:before { content: '\\2605'; color: #b8893b; position: absolute; left: 0; }
.achv { background: #fbf5e6; border: 1px solid #e5c88a; border-radius: 6px; padding: 4px 14px 8px 14px; margin-top: 14px; page-break-inside: avoid; }
.achv h2 { margin-top: 8px; }
.sign { margin-top: 34px; text-align: right; page-break-inside: avoid; }
.sig-ar { font-family: 'Amiri', 'Noto Naskh Arabic', 'DejaVu Sans', sans-serif; font-size: 34pt; color: #1d3a8a; line-height: 1.2; direction: rtl; }
.sig-name { font-size: 9.5pt; color: #55656a; margin-top: 2px; }
.foot { margin-top: 18px; text-align: center; font-size: 8pt; color: #8a9a9e; }
"""


def entry_html(path):
    date, meta, sections = parse(path)
    number = sum(1 for p in all_entries() if p.stem <= path.stem)
    photo = ""
    if PHOTO.exists():
        b64 = base64.b64encode(PHOTO.read_bytes()).decode()
        photo = f'<img class="photo" src="data:image/jpeg;base64,{b64}">'
    by_title = {t.lower(): (t, items) for t, items in sections}

    body = []
    meta_bits = [f"<b>{html.escape(k)}:</b> {html.escape(v)}" for k, v in meta.items()]
    if meta_bits:
        body.append(f'<div class="meta">{" &nbsp;&middot;&nbsp; ".join(meta_bits)}</div>')

    acts = [by_title[a.lower()] for a in ACTIVITY_SECTIONS if a.lower() in by_title]
    if acts:
        body.append("<h2>Daily Activities</h2>")
        for title, items in acts:
            body.append(f"<h3>{html.escape(title)}</h3>{render_items(items)}")

    achievements_html = ""
    for title, items in sections:
        low = title.lower()
        if low in {a.lower() for a in ACTIVITY_SECTIONS}:
            continue
        if low.startswith("achievement"):
            achievements_html = (
                f'<div class="achv"><h2>{html.escape(title)}</h2>{render_items(items, star=True)}</div>'
            )
            continue
        body.append(f"<h2>{html.escape(title)}</h2>{render_items(items)}")
    if achievements_html:
        body.append(achievements_html)

    signature = f"""
<div class="sign">
  <div class="sig-ar">{SIGNATURE}</div>
  <svg width="230" height="16" viewBox="0 0 230 16"><path d="M4 11 C 55 1, 120 16, 226 5" stroke="#1d3a8a" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
  <div class="sig-name">{NAME} &middot; {date:%d %b %Y}</div>
</div>"""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="band"><table><tr>
<td style="width:110px">{photo}</td>
<td><div class="title">My Life Diary</div><div class="date">{date:%A, %d %B %Y}</div><div class="who">{NAME}</div></td>
<td class="badge">Entry #{number}</td>
</tr></table></div>
{"".join(body)}
{signature}
<div class="foot">Personal &amp; private &middot; {NAME}</div>
</body></html>"""


# ---------------------------------------------------------------- pdf
def render_pdf(html_file, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from weasyprint import HTML  # type: ignore

        HTML(filename=str(html_file)).write_pdf(str(out))
        return
    except ImportError:
        pass
    exe = shutil.which("wkhtmltopdf")
    if not exe:
        sys.exit("Need WeasyPrint (pip install weasyprint) or wkhtmltopdf to build PDFs.")
    subprocess.run(
        [exe, "--quiet", "--enable-local-file-access", "--encoding", "utf-8", "-s", "A4",
         "-T", "14mm", "-B", "14mm", "-L", "14mm", "-R", "14mm", str(html_file), str(out)],
        check=False,
    )
    if not out.exists():
        sys.exit(f"PDF engine failed for {out}")


def add_backgrounds(pdf, seed):
    """Put a randomly chosen faded photo behind every page (random, but stable per date)."""
    images = sorted(BACKGROUNDS.glob("*.jpg"))
    if not images:
        return
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import DecodedStreamObject
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        print("pypdf/reportlab missing: skipping page backgrounds (pip install pypdf reportlab)")
        return
    rng = random.Random(seed)
    writer = PdfWriter()
    for page in PdfReader(str(pdf)).pages:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawImage(str(rng.choice(images)), 0, 0, width=A4[0], height=A4[1])
        c.save()
        bg = PdfReader(io.BytesIO(buf.getvalue())).pages[0]
        # wkhtmltopdf paints a white rectangle behind the text; drop it so the photo shows through.
        data = page.get_contents().get_data()
        data = re.sub(rb"/CSp cs 1 1 1 scn\n/GSa gs\nq\n[^\n]*cm\n0 0 [\d.]+ [\d.]+ re\nf\nQ\n", b"", data, count=1)
        cleaned = DecodedStreamObject()
        cleaned.set_data(data)
        page.replace_contents(cleaned)
        bg.merge_page(page)
        writer.add_page(bg)
    with open(pdf, "wb") as fh:
        writer.write(fh)


def cmd_build(args):
    if args.files:
        targets = [Path(f).resolve() for f in args.files]
    elif args.all:
        targets = all_entries()
    else:
        targets = [p for p in all_entries() if not pdf_path(p).exists()]
    with tempfile.TemporaryDirectory() as tmp:
        for p in targets:
            if not p.exists():
                continue
            h = Path(tmp) / (p.stem + ".html")
            h.write_text(entry_html(p), encoding="utf-8")
            out = pdf_path(p)
            render_pdf(h, out)
            add_backgrounds(out, p.stem)
            print("built", out.relative_to(ROOT))
    write_achievements()


# ---------------------------------------------------------------- achievements
def write_achievements():
    rows = []
    for p in all_entries():
        date, _, sections = parse(p)
        for title, items in sections:
            if title.lower().startswith("achievement"):
                rows += [(date, text, p.relative_to(ROOT)) for _, text in items]
    rows.sort(key=lambda r: r[0], reverse=True)
    lines = ["# Achievements", "",
             "Generated from the daily entries (newest first). Edit the entries, not this file.", "",
             "| Date | Achievement | Entry |", "|---|---|---|"]
    for d, text, rel in rows:
        lines.append(f"| {d} | {text.replace('|', '/')} | [{d}]({rel.as_posix()}) |")
    (ROOT / "ACHIEVEMENTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ACHIEVEMENTS.md: {len(rows)} achievement(s)")


def cmd_new(args):
    d = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    p = ROOT / "entries" / f"{d:%Y}" / f"{d:%m}" / f"{d}.md"
    if p.exists():
        sys.exit(f"{p.relative_to(ROOT)} already exists")
    p.parent.mkdir(parents=True, exist_ok=True)
    tpl = (ROOT / "templates" / "entry_template.md").read_text(encoding="utf-8")
    p.write_text(tpl.replace("{{date}}", str(d)), encoding="utf-8")
    print("created", p.relative_to(ROOT))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("date", nargs="?"); n.set_defaults(fn=cmd_new)
    b = sub.add_parser("build"); b.add_argument("files", nargs="*"); b.add_argument("--all", action="store_true"); b.set_defaults(fn=cmd_build)
    a = sub.add_parser("achievements"); a.set_defaults(fn=lambda _a: write_achievements())
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
