# Book Production Formatter Portal

Web portal for ebook publishers to:
- Upload a manuscript (`.doc`, `.docx`, `.kpf`, `.epub`, `.html`, `.htm`, `.zip`, `.txt`, `.rtf`, `.pdf`, `.md`)
- Select production profiles for Kindle/KDP, other EPUB stores, DOCX master, and print PDF
- Add optional front and back cover images
- Preview corrected front/back cover before final package download
- Download a production-ready ZIP package

## What It Generates
- `Amazon KDP Kindle (EPUB)` output for Kindle upload workflows
- `Universal eBook Stores (EPUB)` for Apple Books / Kobo / Google Play Books
- `Formatted Master DOCX` for editorial source
- `Print-ready PDF (6x9)` draft for print pipeline

The ZIP also includes `README_FORMATTING.txt` with final QA checklist steps.
The ZIP includes `KDP_COMPLIANCE_REPORT.txt` based on [Amazon KDP manuscript guidance](https://kdp.amazon.com/en_US/help/topic/G200634390).
If covers are uploaded, ZIP includes `COVER_VALIDATION_REPORT.txt` based on [KDP cover requirements](https://kdp.amazon.com/en_US/help/topic/G200645690).
If source is `KPF`, the portal returns a pass-through production package (KPF + KDP report) because KPF is already a KDP-native format.

## Quick Start

```bash
cd "<your-project-folder>"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open: `http://127.0.0.1:5000`

## Go Live (Render)

This project now includes `render.yaml` for one-click Blueprint deploy.

1. Push this folder to GitHub/GitLab/Bitbucket
2. In Render Dashboard, click `New +` -> `Blueprint`
3. Select your repo and deploy
4. Render will run:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`

## Notes
- This tool applies broadly accepted formatting standards and chapter normalization.
- Always run a final visual check in each platform previewer (KDP preview, Apple Books preview, etc.) before publishing.
- KDP currently accepts EPUB for Kindle ebooks, which this tool outputs directly.
- Based on KDP guidance, MOBI is deprecated for fixed-layout submissions (March 2025 notice); this portal flags MOBI uploads.
- Cover validation is strict and hard-coded: JPEG/TIFF, RGB, 72 DPI, ratio >= 1.6:1, min 625x1000, max 10000x10000, and file size below 50MB.
- You can enable auto-correction to convert invalid covers into KDP-ready 1600x2560 RGB JPEG at 72 DPI.
