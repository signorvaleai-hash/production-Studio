from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import ebooklib
from docx import Document
from ebooklib import epub
from pypdf import PdfReader


@dataclass
class Block:
    kind: str  # chapter | paragraph
    text: str


@dataclass
class Manuscript:
    title: str
    author: str
    blocks: list[Block]


CHAPTER_RE = re.compile(r"^(chapter|book|part)\s+[\w\d]+", re.IGNORECASE)


def parse_manuscript(path: Path, title: str, author: str) -> Manuscript:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        lines = _parse_docx(path)
    elif suffix == ".doc":
        lines = _parse_doc(path)
    elif suffix in {".txt", ".md"}:
        lines = _parse_text(path)
    elif suffix in {".html", ".htm"}:
        lines = _parse_html(path)
    elif suffix == ".zip":
        lines = _parse_zip(path)
    elif suffix == ".rtf":
        lines = _parse_rtf(path)
    elif suffix == ".pdf":
        lines = _parse_pdf(path)
    elif suffix == ".epub":
        lines = _parse_epub(path)
    elif suffix == ".mobi":
        raise ValueError(
            "MOBI is deprecated for many KDP workflows. Upload DOCX/EPUB/KPF or another accepted source file."
        )
    elif suffix == ".kpf":
        raise ValueError("KPF is KDP-ready and is handled as a direct pass-through package.")
    else:
        raise ValueError(
            "Unsupported manuscript type. Use DOC/DOCX/KPF/EPUB/HTML/ZIP/TXT/RTF/PDF/MD sources."
        )

    blocks = _classify_blocks(lines)
    if not blocks:
        raise ValueError("The manuscript appears empty after parsing.")

    return Manuscript(title=title.strip(), author=author.strip(), blocks=blocks)


def _parse_docx(path: Path) -> list[str]:
    doc = Document(path)
    lines: list[str] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            lines.append(_normalize_space(text))
    return lines


def _parse_doc(path: Path) -> list[str]:
    soffice = shutil.which("soffice")
    if not soffice:
        raise ValueError(
            "DOC is accepted, but this server cannot parse .doc without LibreOffice. Upload DOCX or install soffice."
        )
    with tempfile.TemporaryDirectory(prefix="doc_convert_") as tmp:
        tmp_dir = Path(tmp)
        subprocess.run(
            [soffice, "--headless", "--convert-to", "docx", "--outdir", str(tmp_dir), str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        converted = list(tmp_dir.glob("*.docx"))
        if not converted:
            raise ValueError("DOC conversion failed. Please re-save the manuscript as DOCX and upload again.")
        return _parse_docx(converted[0])


def _parse_text(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    return _split_text_to_blocks(raw)


def _parse_html(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text = _html_to_text(raw)
    return _split_text_to_blocks(text)


def _parse_zip(path: Path) -> list[str]:
    blocks: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = sorted(zf.namelist())
        for name in names:
            if name.endswith("/"):
                continue
            ext = Path(name).suffix.lower()
            if ext in {".html", ".htm", ".txt", ".md", ".rtf"}:
                raw = zf.read(name).decode("utf-8", errors="ignore")
                if ext in {".html", ".htm"}:
                    blocks.extend(_split_text_to_blocks(_html_to_text(raw)))
                elif ext == ".rtf":
                    blocks.extend(_split_text_to_blocks(_rtf_to_text(raw)))
                else:
                    blocks.extend(_split_text_to_blocks(raw))
    if not blocks:
        raise ValueError("ZIP upload must contain at least one HTML, TXT, MD, or RTF manuscript file.")
    return blocks


def _parse_rtf(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    return _split_text_to_blocks(_rtf_to_text(raw))


def _parse_pdf(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    raw = "\n\n".join(pages).strip()
    if not raw:
        raise ValueError("PDF text extraction returned no text. Use DOCX or EPUB for best formatting quality.")
    return _split_text_to_blocks(raw)


def _parse_epub(path: Path) -> list[str]:
    book = epub.read_epub(str(path))
    blocks: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        raw = item.get_body_content().decode("utf-8", errors="ignore")
        blocks.extend(_split_text_to_blocks(_html_to_text(raw)))
    if not blocks:
        raise ValueError("Could not extract readable content from EPUB.")
    return blocks


def _split_text_to_blocks(raw: str) -> list[str]:
    chunks = re.split(r"\n\s*\n", raw)
    blocks: list[str] = []
    for chunk in chunks:
        lines = [_normalize_space(line) for line in chunk.splitlines() if _normalize_space(line)]
        if not lines:
            continue
        if _looks_like_chapter_heading(lines[0]):
            blocks.append(lines[0])
            if len(lines) > 1:
                blocks.append(_normalize_space(" ".join(lines[1:])))
        else:
            blocks.append(_normalize_space(" ".join(lines)))
    return blocks


def _html_to_text(raw: str) -> str:
    scrubbed = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    block_tags = r"(p|div|h1|h2|h3|h4|h5|h6|li|section|article|br|hr|tr)"
    scrubbed = re.sub(rf"(?is)</?{block_tags}[^>]*>", "\n", scrubbed)
    scrubbed = re.sub(r"(?is)<[^>]+>", " ", scrubbed)
    return html.unescape(scrubbed)


def _rtf_to_text(raw: str) -> str:
    text = raw.replace("\\par", "\n")
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    return text


def _classify_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    for line in lines:
        if _looks_like_chapter_heading(line):
            blocks.append(Block(kind="chapter", text=line))
        else:
            blocks.append(Block(kind="paragraph", text=line))
    return blocks


def _looks_like_chapter_heading(line: str) -> bool:
    if CHAPTER_RE.match(line):
        return True
    words = line.split()
    if len(words) > 9:
        return False
    if line.isupper() and len(line) <= 80:
        return True
    if re.match(r"^\d{1,3}[.: -]\s+\w+", line):
        return True
    return False


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
