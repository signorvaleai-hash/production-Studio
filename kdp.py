from __future__ import annotations

from pathlib import Path

from formatter.profiles import FormatProfile

KDP_TOPIC_URL = "https://kdp.amazon.com/en_US/help/topic/G200634390"
KDP_RECOMMENDED_SOURCE_EXTS = {".doc", ".docx", ".kpf", ".epub"}
KDP_ACCEPTED_SOURCE_EXTS = {".html", ".htm", ".zip", ".txt", ".rtf", ".pdf"}
KDP_DEPRECATED_NOTICE = "As of March 2025, KDP no longer supports MOBI for fixed-layout content."


def build_kdp_compliance_report(source_path: Path, selected_profiles: list[FormatProfile]) -> str:
    source_ext = source_path.suffix.lower()
    lines: list[str] = [
        "KDP Submission Compliance Report",
        f"Reference: {KDP_TOPIC_URL}",
        "",
        f"Source file: {source_path.name}",
        f"Source extension: {source_ext or '(none)'}",
        "",
    ]

    if source_ext in KDP_RECOMMENDED_SOURCE_EXTS:
        lines.append("Source format status: PASS (recommended by KDP)")
    elif source_ext in KDP_ACCEPTED_SOURCE_EXTS:
        lines.append("Source format status: PASS (accepted by KDP, but not in recommended list)")
    elif source_ext == ".mobi":
        lines.append("Source format status: FAIL (MOBI deprecation for fixed-layout workflows)")
    else:
        lines.append("Source format status: WARN (not listed in KDP accepted/recommended source formats)")

    lines.extend(
        [
            "",
            "KDP recommended source formats: DOC, DOCX, KPF, EPUB",
            "KDP accepted additional source formats: HTML, HTM, ZIP, TXT, RTF, PDF",
            KDP_DEPRECATED_NOTICE,
            "",
            "Generated outputs in this package:",
            *[f"- {profile.label} ({profile.output_type.upper()})" for profile in selected_profiles],
            "",
            "Final KDP readiness checks:",
            "1) Upload EPUB to KDP previewer and review TOC/chapter breaks.",
            "2) Confirm cover rendering, fonts, spacing, and scene breaks.",
            "3) Run a final proofread after conversion preview.",
        ]
    )
    return "\n".join(lines) + "\n"

