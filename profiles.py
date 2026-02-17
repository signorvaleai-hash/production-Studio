from dataclasses import dataclass


@dataclass(frozen=True)
class FormatProfile:
    key: str
    label: str
    description: str
    output_type: str  # epub, docx, pdf
    body_font: str = "Times New Roman"
    body_size_pt: int = 12
    line_spacing: float = 1.15
    first_line_indent_in: float = 0.25
    page_width_in: float = 6.0
    page_height_in: float = 9.0
    margin_in: float = 0.75


PROFILES = {
    "kindle_epub": FormatProfile(
        key="kindle_epub",
        label="Amazon KDP Kindle (EPUB)",
        description="KDP-optimized reflowable EPUB for Kindle publishing.",
        output_type="epub",
        body_font="Bookerly",
        body_size_pt=12,
        line_spacing=1.2,
        first_line_indent_in=0.2,
    ),
    "universal_epub": FormatProfile(
        key="universal_epub",
        label="Universal eBook Stores (EPUB)",
        description="EPUB for Apple Books, Kobo, Google Play Books and others.",
        output_type="epub",
        body_font="Georgia",
        body_size_pt=12,
        line_spacing=1.3,
        first_line_indent_in=0.2,
    ),
    "docx_master": FormatProfile(
        key="docx_master",
        label="Formatted Master DOCX",
        description="Clean master DOCX source suitable for editorial updates.",
        output_type="docx",
        body_font="Garamond",
        body_size_pt=12,
        line_spacing=1.25,
        first_line_indent_in=0.3,
    ),
    "print_pdf": FormatProfile(
        key="print_pdf",
        label="Print-ready PDF (6x9)",
        description="Trim-size PDF draft for print workflow and review.",
        output_type="pdf",
        body_font="Times-Roman",
        body_size_pt=11,
        line_spacing=1.25,
        first_line_indent_in=0.2,
        page_width_in=6.0,
        page_height_in=9.0,
        margin_in=0.65,
    ),
}

