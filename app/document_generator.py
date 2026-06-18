"""
Document generation layer.
Cover letter DOCX output (PDF resume moved to app/rendercv_renderer.py).
"""

import logging
import os

from app.config import settings

logger = logging.getLogger(__name__)


def ensure_output_dir(subdir: str = "") -> str:
    base = settings.OUTPUT_DIR
    path = os.path.join(base, subdir) if subdir else base
    os.makedirs(path, exist_ok=True)
    return path


def cover_letter_to_docx(text_content: str, output_path: str) -> str:
    """
    Convert cover letter text to a Word (.docx) file.
    """
    try:
        from docx import Document
        doc = Document()
        for para in text_content.strip().split("\n\n"):
            doc.add_paragraph(para.strip())
        doc.save(output_path)
        logger.info("DOCX written to %s", output_path)
    except ImportError:
        _fallback_text(text_content, output_path.replace(".docx", ".txt"))
        logger.warning("python-docx not installed — saved as .txt instead of .docx")
    return output_path


def _fallback_text(content: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
