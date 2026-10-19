# My Life Diary

Personal diary of **Shittu AbdulQadir Adeshina**: daily activities, achievements and reflections, with a signed PDF (عبدالقادر) for every day.

> Keep this repository **private**. It holds personal writing and a personal photo.

## How it works

| Folder / file | Purpose |
|---|---|
| `entries/YYYY/MM/YYYY-MM-DD.md` | One Markdown entry per day: this is what you write |
| `pdf/YYYY/MM/YYYY-MM-DD.pdf` | The signed PDF of that day (built automatically) |
| `ACHIEVEMENTS.md` | Running list of every achievement, newest first (built automatically) |
| `assets/photo.jpg` | Your photo, shown in each PDF header |
| `templates/entry_template.md` | Blank daily entry |
| `scripts/diary.py` | Builds PDFs and the achievements list |

## Add a day

1. Copy `templates/entry_template.md` to `entries/YYYY/MM/YYYY-MM-DD.md` (the file name must be the date).
2. Fill in what you want. Empty sections are left out of the PDF. Arabic text is supported.
3. Commit. The **Build diary PDFs** GitHub Action creates the day's PDF and updates `ACHIEVEMENTS.md`.

Or just tell Claude what you did today and ask it to log the day.

## Build on your own computer

```bash
pip install weasyprint          # or install wkhtmltopdf
python scripts/diary.py new     # blank entry for today
python scripts/diary.py build   # PDFs for entries that have none yet
python scripts/diary.py build --all
```
