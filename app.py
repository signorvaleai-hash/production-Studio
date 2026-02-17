from __future__ import annotations

import base64
import tempfile
from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from formatter.cover_validator import (
    KDP_COVER_HELP_URL,
    auto_correct_cover_to_kdp,
    render_cover_report,
    validate_cover_image,
)
from formatter.pipeline import create_production_package
from formatter.profiles import PROFILES

ALLOWED_MANUSCRIPT_EXT = {
    ".doc",
    ".docx",
    ".kpf",
    ".epub",
    ".html",
    ".htm",
    ".zip",
    ".txt",
    ".rtf",
    ".pdf",
    ".md",
}
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB


@app.get("/")
def index():
    return render_template("index.html", profiles=PROFILES.values())


@app.get("/api/profiles")
def list_profiles():
    return jsonify(
        [
            {
                "key": profile.key,
                "label": profile.label,
                "description": profile.description,
                "output_type": profile.output_type,
            }
            for profile in PROFILES.values()
        ]
    )


@app.post("/api/format")
def format_manuscript():
    manuscript = request.files.get("manuscript")
    if not manuscript or not manuscript.filename:
        return jsonify({"error": "Please upload a manuscript file."}), 400

    manuscript_name = secure_filename(manuscript.filename)
    manuscript_ext = Path(manuscript_name).suffix.lower()
    if manuscript_ext == ".mobi":
        return (
            jsonify(
                {
                    "error": "MOBI is deprecated for fixed-layout on KDP (March 2025). Upload DOCX, EPUB, or other accepted source formats."
                }
            ),
            400,
        )
    if manuscript_ext not in ALLOWED_MANUSCRIPT_EXT:
        return (
            jsonify(
                {
                    "error": "Unsupported manuscript type. Use DOC/DOCX/KPF/EPUB/HTML/ZIP/TXT/RTF/PDF/MD."
                }
            ),
            400,
        )

    title = (request.form.get("title") or Path(manuscript_name).stem).strip()
    author = (request.form.get("author") or "Unknown Author").strip()
    profile_keys = request.form.getlist("profiles")
    auto_fix_covers = (request.form.get("auto_fix_covers") or "on").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    front_cover = request.files.get("front_cover")
    back_cover = request.files.get("back_cover")

    try:
        with tempfile.TemporaryDirectory(prefix="ebook_format_") as tmp:
            tmp_dir = Path(tmp)
            manuscript_path = tmp_dir / manuscript_name
            manuscript.save(manuscript_path)

            cover_report_sections: list[str] = []
            front_cover_path, front_report = _save_optional_image(
                front_cover, tmp_dir, "front", auto_fix_covers
            )
            back_cover_path, back_report = _save_optional_image(
                back_cover, tmp_dir, "back", auto_fix_covers
            )
            if front_report:
                cover_report_sections.append(front_report)
            if back_report:
                cover_report_sections.append(back_report)

            extra_reports = {}
            if cover_report_sections:
                extra_reports["COVER_VALIDATION_REPORT.txt"] = (
                    "KDP Cover Validation Report\n"
                    f"Reference: {KDP_COVER_HELP_URL}\n\n"
                    + "\n\n".join(cover_report_sections)
                    + "\n"
                )

            archive_path = create_production_package(
                manuscript_path=manuscript_path,
                output_dir=tmp_dir,
                title=title,
                author=author,
                profile_keys=profile_keys,
                front_cover=front_cover_path,
                back_cover=back_cover_path,
                extra_reports=extra_reports,
            )
            data = archive_path.read_bytes()

        download_name = f"{_safe_download_name(title)}_production_ready.zip"
        return send_file(
            BytesIO(data),
            mimetype="application/zip",
            as_attachment=True,
            download_name=download_name,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Formatting failed: {str(exc)}"}), 500


@app.post("/api/preview-cover")
def preview_cover():
    upload = request.files.get("cover")
    if not upload or not upload.filename:
        return jsonify({"error": "Please upload a cover image first."}), 400

    role = (request.form.get("role") or "front").strip().lower()
    if role not in {"front", "back"}:
        role = "front"

    auto_fix_covers = (request.form.get("auto_fix_covers") or "on").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    name = secure_filename(upload.filename)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return jsonify({"error": "Cover must be JPG, JPEG, PNG, WEBP, TIF, or TIFF."}), 400

    with tempfile.TemporaryDirectory(prefix="cover_preview_") as tmp:
        tmp_dir = Path(tmp)
        original_path = tmp_dir / f"{role}_cover_original{ext}"
        upload.save(original_path)

        original_validation = validate_cover_image(original_path, role=role)
        final_path = original_path
        final_validation = original_validation
        auto_corrected = False

        if not original_validation.valid and auto_fix_covers:
            corrected_path = auto_correct_cover_to_kdp(original_path, tmp_dir, role=role)
            corrected_validation = validate_cover_image(corrected_path, role=role)
            if not corrected_validation.valid:
                return (
                    jsonify(
                        {
                            "error": f"{role.title()} cover auto-correction failed.",
                            "original": _validation_to_dict(original_validation),
                            "corrected": _validation_to_dict(corrected_validation),
                        }
                    ),
                    400,
                )
            final_path = corrected_path
            final_validation = corrected_validation
            auto_corrected = True

        preview_bytes = final_path.read_bytes()
        mime = _guess_preview_mime(final_path)
        preview_data_url = f"data:{mime};base64,{base64.b64encode(preview_bytes).decode('ascii')}"

    return jsonify(
        {
            "role": role,
            "auto_fix_enabled": auto_fix_covers,
            "auto_corrected": auto_corrected,
            "can_proceed": final_validation.valid,
            "original": _validation_to_dict(original_validation),
            "final": _validation_to_dict(final_validation),
            "preview_data_url": preview_data_url,
            "preview_mime": mime,
            "message": _build_preview_message(role, original_validation.valid, auto_corrected, auto_fix_covers),
        }
    )


def _save_optional_image(upload, tmp_dir: Path, prefix: str, auto_fix_covers: bool) -> tuple[Path | None, str | None]:
    if not upload or not upload.filename:
        return None, None
    name = secure_filename(upload.filename)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError(f"{prefix.title()} cover must be JPG, JPEG, PNG, WEBP, TIF, or TIFF.")
    original_out = tmp_dir / f"{prefix}_cover_original{ext}"
    upload.save(original_out)

    validation = validate_cover_image(original_out, role=prefix)
    if validation.valid:
        return original_out, render_cover_report(prefix, validation, auto_corrected=False)

    if not auto_fix_covers:
        error_lines = "\n".join([f"- {e}" for e in validation.errors])
        raise ValueError(
            f"{prefix.title()} cover does not meet KDP specs.\n"
            f"{error_lines}\n"
            "Enable 'Auto-correct covers to KDP spec' to fix automatically."
        )

    corrected_out = auto_correct_cover_to_kdp(original_out, tmp_dir, role=prefix)
    corrected_validation = validate_cover_image(corrected_out, role=prefix)
    if not corrected_validation.valid:
        corrected_errors = "\n".join([f"- {e}" for e in corrected_validation.errors])
        raise ValueError(
            f"{prefix.title()} cover auto-correction failed to meet KDP specs.\n{corrected_errors}"
        )

    combined_report = "\n".join(
        [
            render_cover_report(prefix, validation, auto_corrected=False),
            "",
            f"{prefix.title()} cover auto-corrected output:",
            render_cover_report(prefix, corrected_validation, auto_corrected=True),
        ]
    )
    return corrected_out, combined_report


def _safe_download_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")
    return cleaned[:80] or "book"


def _validation_to_dict(result) -> dict:
    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "width": result.width,
        "height": result.height,
        "format": result.fmt,
        "mode": result.mode,
        "dpi": [result.dpi[0], result.dpi[1]] if result.dpi else None,
        "size_mb": result.size_mb,
    }


def _guess_preview_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext in {".tif", ".tiff"}:
        return "image/tiff"
    if ext == ".webp":
        return "image/webp"
    if ext == ".png":
        return "image/png"
    return "application/octet-stream"


def _build_preview_message(role: str, original_valid: bool, auto_corrected: bool, auto_fix_enabled: bool) -> str:
    if original_valid:
        return f"{role.title()} cover already meets KDP rules. Preview is the original image."
    if auto_corrected:
        return f"{role.title()} cover did not meet KDP rules. Preview shows the auto-corrected image that will be used."
    if auto_fix_enabled:
        return f"{role.title()} cover failed KDP checks and no corrected preview is available."
    return (
        f"{role.title()} cover does not meet KDP rules. Enable 'Auto-correct covers to KDP spec' to preview corrected output."
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
