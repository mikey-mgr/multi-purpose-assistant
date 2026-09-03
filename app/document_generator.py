"""
Document generation layer.
Cover letter DOCX output (PDF resume moved to app/rendercv_renderer.py).
PDF merge utilities.
"""

import logging
import os

from app.config import settings

logger = logging.getLogger(__name__)

_ARIAL_PATH = r"C:\Windows\Fonts\arial.ttf"


def _set_unicode_font(pdf, size: int = 11):
    """Set a Unicode-capable font on the PDF, falling back to Helvetica."""
    if os.path.exists(_ARIAL_PATH):
        pdf.add_font("Unicode", "", _ARIAL_PATH, uni=True)
        pdf.set_font("Unicode", "", size)
    else:
        pdf.set_font("Helvetica", "", size)


def ensure_output_dir(subdir: str = "") -> str:
    base = settings.OUTPUT_DIR
    path = os.path.join(base, subdir) if subdir else base
    os.makedirs(path, exist_ok=True)
    return path


def _add_inline_runs(para, text: str):
    """Add WhatsApp markdown inline runs to an existing paragraph.

    Supports: *bold*, _italic_, ~strikethrough~, ```code```.
    """
    import re
    from docx.shared import Pt

    pattern = re.compile(r"(\*[^*]+\*|_[^_]+_|~[^~]+~|```[^`]+```)")
    parts = pattern.split(text)
    for part in parts:
        if not part:
            continue
        if part.startswith("*") and part.endswith("*") and len(part) > 2:
            run = para.add_run(part[1:-1])
            run.bold = True
        elif part.startswith("_") and part.endswith("_") and len(part) > 2:
            run = para.add_run(part[1:-1])
            run.italic = True
        elif part.startswith("~") and part.endswith("~") and len(part) > 2:
            run = para.add_run(part[1:-1])
            run.font.strike = True
        elif part.startswith("```") and part.endswith("```") and len(part) > 6:
            run = para.add_run(part[3:-3])
            run.font.name = "Courier New"
            run.font.size = Pt(9)
        else:
            para.add_run(part)


def _add_formatted_paragraph(doc, text: str):
    """Legacy helper — splits heading vs normal."""
    import re

    heading_match = re.match(r"^(#{1,3})\s+(.*)", text.strip())
    if heading_match:
        level = len(heading_match.group(1))
        para = doc.add_heading(level=level)
        _add_inline_runs(para, heading_match.group(2).strip())
        return para
    para = doc.add_paragraph()
    _add_inline_runs(para, text)
    return para


def cover_letter_to_docx(text_content: str, output_path: str) -> str:
    """Render markdown/WhatsApp-markdown to DOCX with proper headings and bullets."""
    import re

    try:
        from docx import Document
        doc = Document()
        lines = text_content.strip().split("\n")
        for raw_line in lines:
            line = raw_line.rstrip()
            if not line.strip():
                continue
            stripped = line.strip()
            # Heading: # Title, ## Section, ### Question
            m = re.match(r"^(#{1,3})\s+(.*)", stripped)
            if m:
                level = len(m.group(1))
                para = doc.add_heading(level=level)
                _add_inline_runs(para, m.group(2).strip())
                continue
            # Bullet: * , - , •  (including "* *Bold*:" style)
            bm = re.match(r"^([•\-\*])\s+(.*)", stripped)
            if bm:
                content = bm.group(2)
                para = doc.add_paragraph(style="List Bullet")
                _add_inline_runs(para, content)
                continue
            # Numbered list: 1. , 2. etc (rare, but handle)
            nm = re.match(r"^\d+\.\s+(.*)", stripped)
            if nm:
                para = doc.add_paragraph(style="List Number")
                _add_inline_runs(para, nm.group(1))
                continue
            # Normal paragraph — may contain inline *bold* etc
            para = doc.add_paragraph()
            _add_inline_runs(para, stripped)
        doc.save(output_path)
        logger.info("DOCX written to %s", output_path)
    except ImportError:
        _fallback_text(text_content, output_path.replace(".docx", ".txt"))
        logger.warning("python-docx not installed — saved as .txt instead of .docx")
    return output_path


def cover_letter_to_pdf(text_content: str, output_path: str) -> str:
    """Render cover letter text as a PDF using fpdf2 with a Unicode font."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    _set_unicode_font(pdf, 11)

    for para in text_content.strip().split("\n\n"):
        pdf.multi_cell(0, 6, para.strip())
        pdf.ln(2)

    pdf.output(output_path)
    logger.info("Cover letter PDF written to %s", output_path)
    return output_path


def build_merged_pdf(
    required_docs: list[str],
    docs: dict,
    job_id: int,
) -> str | None:
    """Merge ALL required documents into a single PDF.

    Order: cover letter → resume → education → certification → misc docs.
    Non-PDF files (DOCX, images) are converted on a best-effort basis.
    Returns the path to the merged PDF, or None on failure.
    """
    from pypdf import PdfWriter

    # Collect file paths in desired order
    file_paths: list[str] = []

    if "cover_letter" in required_docs and docs.get("cover_letter_docx"):
        file_paths.append(docs["cover_letter_docx"])

    if "resume" in required_docs and docs.get("resume_pdf"):
        file_paths.append(docs["resume_pdf"])

    if "education_cert" in required_docs:
        file_paths.extend(docs.get("education_docs", []))

    if "certification_cert" in required_docs:
        file_paths.extend(docs.get("certification_docs", []))

    misc = docs.get("misc_docs", {})
    for doc_type in required_docs:
        if doc_type in misc:
            file_paths.append(misc[doc_type])

    if not file_paths:
        logger.warning("No files to merge")
        return None

    out_dir = ensure_output_dir("merged")
    if docs.get("resume_pdf"):
        basename = os.path.basename(docs["resume_pdf"])
    else:
        basename = f"application_{job_id}.pdf"
    merged_path = os.path.join(out_dir, basename)

    merger = PdfWriter()
    temp_files: list[str] = []

    try:
        for fp in file_paths:
            if not os.path.isfile(fp):
                logger.warning("File not found, skipping: %s", fp)
                continue

            ext = os.path.splitext(fp)[1].lower()
            if ext == ".pdf":
                merger.append(fp)
            else:
                pdf_path = _convert_to_pdf(fp, out_dir)
                if pdf_path:
                    merger.append(pdf_path)
                    if pdf_path != fp:
                        temp_files.append(pdf_path)
                else:
                    logger.warning("Could not convert %s to PDF, skipping", fp)

        if merger.pages == 0:
            logger.warning("No pages in merged PDF")
            return None

        merger.write(merged_path)
        merger.close()
        logger.info("Merged PDF written to %s (%d files)", merged_path, len(file_paths))
        return merged_path
    except Exception as e:
        logger.warning("Failed to merge PDFs: %s", e)
        return None
    finally:
        for tmp in temp_files:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _convert_to_pdf(file_path: str, output_dir: str) -> str | None:
    """Convert a non-PDF file to PDF. Returns the PDF path or None."""
    ext = os.path.splitext(file_path)[1].lower()
    basename = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(output_dir, f"{basename}.pdf")

    if ext == ".pdf":
        return file_path

    from fpdf import FPDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    if ext in (".docx", ".doc"):
        try:
            from docx import Document
            doc = Document(file_path)
            pdf.add_page()
            _set_unicode_font(pdf, 11)
            for para in doc.paragraphs:
                pdf.multi_cell(0, 6, para.text)
                pdf.ln(1)
            pdf.output(out_path)
            return out_path
        except Exception as e:
            logger.warning("Failed to convert DOCX to PDF: %s", e)
            return None

    if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
        try:
            pdf.add_page()
            pdf.image(file_path, x=10, y=10, w=190)
            pdf.output(out_path)
            return out_path
        except Exception as e:
            logger.warning("Failed to convert image to PDF: %s", e)
            return None

    if ext == ".txt":
        try:
            pdf.add_page()
            pdf.set_font("Courier", "", 10)
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    pdf.cell(0, 5, line.rstrip())
                    pdf.ln()
            pdf.output(out_path)
            return out_path
        except Exception as e:
            logger.warning("Failed to convert TXT to PDF: %s", e)
            return None

    logger.warning("Unsupported file type %s: %s", ext, file_path)
    return None


def _fallback_text(content: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
