from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

KDP_COVER_HELP_URL = "https://kdp.amazon.com/en_US/help/topic/G200645690"

KDP_ALLOWED_FORMATS = {"JPEG", "TIFF"}
KDP_IDEAL_WIDTH = 1600
KDP_IDEAL_HEIGHT = 2560
KDP_MIN_WIDTH = 625
KDP_MIN_HEIGHT = 1000
KDP_MAX_WIDTH = 10000
KDP_MAX_HEIGHT = 10000
KDP_MIN_RATIO = 1.6  # height / width
KDP_REQUIRED_DPI = 72
KDP_MAX_SIZE_MB = 50


@dataclass
class CoverValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]
    width: int | None = None
    height: int | None = None
    fmt: str | None = None
    mode: str | None = None
    dpi: tuple[float, float] | None = None
    size_mb: float | None = None


def validate_cover_image(path: Path, role: str = "cover") -> CoverValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        with Image.open(path) as img:
            fmt = (img.format or "").upper()
            mode = img.mode
            width, height = img.size
            dpi = img.info.get("dpi")
    except UnidentifiedImageError as exc:
        return CoverValidationResult(
            valid=False,
            errors=[f"{role.title()} image is unreadable: {exc}"],
            warnings=[],
        )

    size_mb = path.stat().st_size / (1024 * 1024)

    if fmt not in KDP_ALLOWED_FORMATS:
        errors.append(f"Format must be JPEG or TIFF. Uploaded format is {fmt or 'unknown'}.")

    if width < KDP_MIN_WIDTH or height < KDP_MIN_HEIGHT:
        errors.append(
            f"Dimensions are too small: {width}x{height}. Minimum is {KDP_MIN_WIDTH}x{KDP_MIN_HEIGHT} (W x H)."
        )

    if width > KDP_MAX_WIDTH or height > KDP_MAX_HEIGHT:
        errors.append(
            f"Dimensions are too large: {width}x{height}. Maximum is {KDP_MAX_WIDTH}x{KDP_MAX_HEIGHT} (W x H)."
        )

    ratio = (height / width) if width else 0.0
    if ratio < KDP_MIN_RATIO:
        errors.append(
            f"Height/width ratio must be at least {KDP_MIN_RATIO}:1. Current ratio is {ratio:.3f}:1."
        )

    if dpi is None:
        errors.append("DPI metadata is missing. KDP eBook cover spec requires 72 DPI.")
    else:
        x_dpi, y_dpi = float(dpi[0]), float(dpi[1])
        if abs(x_dpi - KDP_REQUIRED_DPI) > 1 or abs(y_dpi - KDP_REQUIRED_DPI) > 1:
            errors.append(f"DPI must be 72. Current DPI is approximately {x_dpi:.1f}x{y_dpi:.1f}.")

    if size_mb >= KDP_MAX_SIZE_MB:
        errors.append(f"File size must be below {KDP_MAX_SIZE_MB}MB. Current size is {size_mb:.2f}MB.")

    if mode != "RGB":
        errors.append(f"Color mode must be RGB. Current mode is {mode}.")

    if width != KDP_IDEAL_WIDTH or height != KDP_IDEAL_HEIGHT:
        warnings.append(
            f"Ideal dimensions are {KDP_IDEAL_WIDTH}x{KDP_IDEAL_HEIGHT} (W x H). Current is {width}x{height}."
        )
    if height < 2500:
        warnings.append("For best quality on HD devices, KDP recommends cover height of at least 2500px.")

    return CoverValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        width=width,
        height=height,
        fmt=fmt,
        mode=mode,
        dpi=(float(dpi[0]), float(dpi[1])) if dpi else None,
        size_mb=size_mb,
    )


def auto_correct_cover_to_kdp(path: Path, output_dir: Path, role: str) -> Path:
    with Image.open(path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        fitted = ImageOps.contain(img, (KDP_IDEAL_WIDTH, KDP_IDEAL_HEIGHT), method=Image.Resampling.LANCZOS)

    # Neutral canvas keeps full artwork without destructive cropping.
    canvas = Image.new("RGB", (KDP_IDEAL_WIDTH, KDP_IDEAL_HEIGHT), color=(248, 248, 248))
    x = (KDP_IDEAL_WIDTH - fitted.width) // 2
    y = (KDP_IDEAL_HEIGHT - fitted.height) // 2
    canvas.paste(fitted, (x, y))

    out_path = output_dir / f"{role}_cover_kdp_ready.jpg"
    canvas.save(out_path, format="JPEG", quality=95, optimize=True, dpi=(72, 72))
    return out_path


def render_cover_report(role: str, result: CoverValidationResult, auto_corrected: bool = False) -> str:
    lines = [
        f"{role.title()} cover:",
        f"- Status: {'PASS' if result.valid else 'FAIL'}",
        f"- Format: {result.fmt or 'unknown'}",
        f"- Dimensions: {result.width or '?'}x{result.height or '?'} (W x H)",
        f"- Color mode: {result.mode or 'unknown'}",
        f"- DPI: {f'{result.dpi[0]:.1f}x{result.dpi[1]:.1f}' if result.dpi else 'missing'}",
        f"- File size: {f'{result.size_mb:.2f}MB' if result.size_mb is not None else 'unknown'}",
        f"- Auto-corrected: {'Yes' if auto_corrected else 'No'}",
    ]
    if result.errors:
        lines.append("- Errors:")
        lines.extend([f"  * {err}" for err in result.errors])
    if result.warnings:
        lines.append("- Warnings:")
        lines.extend([f"  * {warn}" for warn in result.warnings])
    return "\n".join(lines)

