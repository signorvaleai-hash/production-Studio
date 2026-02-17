from __future__ import annotations

import shutil
from pathlib import Path

from formatter.exporters import export_docx, export_epub, export_pdf
from formatter.kdp import build_kdp_compliance_report
from formatter.parser import parse_manuscript
from formatter.profiles import PROFILES


def create_production_package(
    manuscript_path: Path,
    output_dir: Path,
    title: str,
    author: str,
    profile_keys: list[str],
    front_cover: Path | None = None,
    back_cover: Path | None = None,
    extra_reports: dict[str, str] | None = None,
) -> Path:
    safe_stem = _safe_slug(title) or "book"
    build_dir = output_dir / f"{safe_stem}_production"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    selected = []
    for key in profile_keys:
        if key in PROFILES:
            selected.append(PROFILES[key])
    if not selected:
        selected.append(PROFILES["kindle_epub"])

    if manuscript_path.suffix.lower() == ".kpf":
        kpf_name = manuscript_path.name
        shutil.copy2(manuscript_path, build_dir / kpf_name)
        (build_dir / "README_FORMATTING.txt").write_text(
            "\n".join(
                [
                    f"Title: {title}",
                    f"Author: {author}",
                    "",
                    f"Detected source: {kpf_name}",
                    "KPF is already a KDP-native package.",
                    "No manuscript reflow conversion was applied.",
                    "",
                    "Next steps:",
                    "1) Open KPF in Kindle Create to verify layout.",
                    "2) Upload KPF directly to KDP if quality is approved.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (build_dir / "KDP_COMPLIANCE_REPORT.txt").write_text(
            build_kdp_compliance_report(manuscript_path, selected), encoding="utf-8"
        )
        if extra_reports:
            for file_name, content in extra_reports.items():
                (build_dir / file_name).write_text(content, encoding="utf-8")
        zip_base = output_dir / f"{safe_stem}_production_ready"
        archive_path = shutil.make_archive(str(zip_base), "zip", build_dir)
        return Path(archive_path)

    manuscript = parse_manuscript(manuscript_path, title=title, author=author)
    for profile in selected:
        if profile.output_type == "docx":
            out_path = build_dir / f"{safe_stem}_{profile.key}.docx"
            export_docx(manuscript, out_path, profile, front_cover, back_cover)
        elif profile.output_type == "epub":
            out_path = build_dir / f"{safe_stem}_{profile.key}.epub"
            export_epub(manuscript, out_path, profile, front_cover, back_cover)
        elif profile.output_type == "pdf":
            out_path = build_dir / f"{safe_stem}_{profile.key}.pdf"
            export_pdf(manuscript, out_path, profile, front_cover, back_cover)

    manifest = build_dir / "README_FORMATTING.txt"
    manifest.write_text(
        "\n".join(
            [
                f"Title: {manuscript.title}",
                f"Author: {manuscript.author}",
                "",
                "Generated formats:",
                *[f"- {profile.label} ({profile.key})" for profile in selected],
                "",
                "Final pre-publish checks:",
                "1) Open each output and verify chapter breaks, TOC, and images.",
                "2) Validate EPUB with your store previewer before publishing.",
                "3) Run a final typo/proof pass on generated files.",
            ]
        ),
        encoding="utf-8",
    )
    (build_dir / "KDP_COMPLIANCE_REPORT.txt").write_text(
        build_kdp_compliance_report(manuscript_path, selected), encoding="utf-8"
    )
    if extra_reports:
        for file_name, content in extra_reports.items():
            (build_dir / file_name).write_text(content, encoding="utf-8")

    zip_base = output_dir / f"{safe_stem}_production_ready"
    archive_path = shutil.make_archive(str(zip_base), "zip", build_dir)
    return Path(archive_path)


def _safe_slug(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")
