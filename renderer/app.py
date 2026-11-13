"""Stateless RenderCV application renderer.

Accepts structured CV data, cover letter text and supporting documents.
Returns PDFs as base64. No database, no legacy profile and no user state.
"""

import base64
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from docx import Document
from fastapi import FastAPI, Header, HTTPException
from fpdf import FPDF
from PIL import Image
from pydantic import BaseModel, Field
from pypdf import PdfReader, PdfWriter

app = FastAPI(title="Mukana Renderer", version="0.1.0")

THEMES = {
    "harvard",
    "classic",
    "moderncv",
    "sb2nov",
    "engineeringclassic",
    "engineeringresumes",
    "ember",
    "ink",
    "opal",
}

HARVARD_DESIGN: dict[str, Any] = {
    "theme": "harvard",
    "page": {
        "size": "a4",
        "top_margin": "0.55in",
        "bottom_margin": "0.55in",
        "left_margin": "0.65in",
        "right_margin": "0.65in",
        "show_footer": False,
        "show_top_note": False,
    },
    "colors": {
        "body": "rgb(55, 65, 81)",
        "name": "rgb(17, 24, 39)",
        "headline": "rgb(75, 85, 99)",
        "connections": "rgb(55, 65, 81)",
        "section_titles": "rgb(29, 89, 209)",
        "links": "rgb(0, 82, 204)",
    },
    "typography": {
        "line_spacing": "0.35em",
        "alignment": "left",
        "font_family": "Arial",
        "font_size": {
            "body": "10.5pt",
            "name": "25pt",
            "headline": "11pt",
            "connections": "9.5pt",
            "section_titles": "12pt",
        },
        "small_caps": {"section_titles": False},
        "bold": {
            "name": True,
            "headline": False,
            "connections": False,
            "section_titles": True,
        },
    },
    "header": {
        "alignment": "center",
        "space_below_name": "0.08in",
        "space_below_headline": "0.08in",
        "space_below_connections": "0.22in",
        "connections": {
            "show_icons": False,
            "separator": "|",
            "space_between_connections": "0.08in",
        },
    },
    "section_titles": {
        "type": "with_full_line",
        "line_thickness": "0.6pt",
        "space_above": "0.20in",
        "space_below": "0.08in",
    },
    "sections": {
        "space_between_regular_entries": "0.45em",
        "space_between_text_based_entries": "0.15em",
    },
    "entries": {
        "date_and_location_width": "0cm",
        "space_between_columns": "0cm",
        "highlights": {
            "space_left": "0.18in",
            "space_above": "0.05in",
            "space_between_items": "0.02in",
            "space_between_bullet_and_text": "0.45em",
        },
    },
    "templates": {
        "education_entry": {
            "main_column": "**DEGREE_WITH_AREA**  |  INSTITUTION  DATE\nHIGHLIGHTS",
            "degree_column": "",
            "date_and_location_column": "",
        },
        "experience_entry": {
            "main_column": "**POSITION**  |  COMPANY, DATE\nHIGHLIGHTS",
            "date_and_location_column": "",
        },
        "normal_entry": {
            "main_column": "**NAME**\nSUMMARY\nHIGHLIGHTS",
            "date_and_location_column": "",
        },
    },
}

UNICODE_REPLACEMENTS = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2013": "-",
    "\u2014": "--",
    "\u2022": "-",
    "\u2026": "...",
    "\u00a0": " ",
    "\ufffd": "",
    "\u00a9": "(c)",
    "\u00ae": "(r)",
    "\u2122": "(tm)",
}


class Attachment(BaseModel):
    name: str = Field(max_length=250)
    mime: str = Field(max_length=120)
    content_base64: str


class RenderRequest(BaseModel):
    theme: str = "harvard"
    cv: dict[str, Any]
    cover_letter: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    merge: bool = False


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        for old, new in UNICODE_REPLACEMENTS.items():
            value = value.replace(old, new)
        return value
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def normalize_date(value: Any, kind: str = "start") -> Any:
    """RenderCV only accepts YYYY-MM or YYYY-MM-DD. Coerce common inputs."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or re.match(r"^(present|current|now|ongoing)$", text, re.I):
        return None

    match = re.match(r"^(\d{4})-(\d{1,2})(?:-\d{1,2})?$", text)
    if match:
        month = min(12, max(1, int(match.group(2))))
        return f"{match.group(1)}-{month:02d}"

    match = re.match(r"^(\d{4})$", text)
    if match:
        return f"{text}-{'12' if kind == 'end' else '01'}"

    match = re.match(r"^(\d{1,2})/(\d{4})$", text)
    if match:
        return f"{match.group(2)}-{min(12, max(1, int(match.group(1)))):02d}"

    match = re.match(r"^(\d{4})/(\d{1,2})$", text)
    if match:
        return f"{match.group(1)}-{min(12, max(1, int(match.group(2)))):02d}"

    match = re.match(r"^([A-Za-z]{3,9})\s+(\d{4})$", text)
    if match:
        month = MONTHS.get(match.group(1)[:3].lower())
        if month:
            return f"{match.group(2)}-{month}"

    return text


RESERVED_TLDS = {
    "test",
    "invalid",
    "localhost",
    "local",
    "example",
    "internal",
    "lan",
    "home",
    "corp",
    "mail",
    "onion",
}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})$")


def valid_email(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    match = EMAIL_RE.match(value.strip())
    if not match:
        return False
    tld = match.group(1).rsplit(".", 1)[-1].lower()
    return tld not in RESERVED_TLDS


def clean_contact(cv: dict[str, Any]) -> dict[str, Any]:
    """Drop contact values RenderCV cannot validate instead of failing the render."""
    cleaned = dict(cv)
    if "email" in cleaned and not valid_email(cleaned.get("email")):
        cleaned.pop("email", None)
    phone = cleaned.get("phone")
    if isinstance(phone, str) and not re.search(r"\d{6,}", phone):
        cleaned.pop("phone", None)
    networks = cleaned.get("social_networks")
    if isinstance(networks, list):
        kept = [
            network
            for network in networks
            if isinstance(network, dict)
            and isinstance(network.get("username"), str)
            and "." in network["username"]
        ]
        if kept:
            cleaned["social_networks"] = kept
        else:
            cleaned.pop("social_networks", None)
    return cleaned


DATE_FIELDS = {"start_date", "end_date", "date"}


def normalize_dates(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in DATE_FIELDS:
                result[key] = normalize_date(item, "end" if key == "end_date" else "start")
            else:
                result[key] = normalize_dates(item)
        return result
    if isinstance(value, list):
        return [normalize_dates(item) for item in value]
    return value


def design_for(theme: str) -> dict[str, Any]:
    if theme == "harvard":
        return HARVARD_DESIGN
    return {"theme": theme}


def render_cv(cv: dict[str, Any], theme: str) -> bytes:
    cv_document = {
        "cv": clean_contact(normalize_dates(sanitize(cv))),
        "design": design_for(theme),
    }
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        yaml_path = directory / "cv.yaml"
        yaml_path.write_text(
            yaml.dump(cv_document, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        command = [
            sys.executable,
            "-m",
            "rendercv",
            "render",
            str(yaml_path),
            "--output-folder",
            str(directory),
            "--dont-generate-markdown",
            "--dont-generate-html",
            "--dont-generate-png",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            },
            timeout=180,
        )
        pdfs = sorted(directory.glob("*.pdf"))
        if not pdfs:
            detail = (result.stdout or "")[-3000:] + (result.stderr or "")[-3000:]
            raise HTTPException(status_code=500, detail=f"RenderCV did not produce a PDF: {detail}")
        return pdfs[0].read_bytes()


def render_cover_letter(text: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for block in sanitize(text).strip().split("\n\n"):
        pdf.multi_cell(0, 6, block.strip())
        pdf.ln(3)
    return bytes(pdf.output())


def render_cover_letter_docx(text: str) -> bytes:
    document = Document()
    for block in sanitize(text).strip().split("\n\n"):
        document.add_paragraph(block.strip())
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def attachment_pdf(attachment: Attachment) -> bytes:
    data = base64.b64decode(attachment.content_base64)
    mime = attachment.mime.lower()
    if mime == "application/pdf":
        return data
    if mime in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, "PDF", resolution=150)
        return buffer.getvalue()
    raise HTTPException(
        status_code=415,
        detail=f"{attachment.name} is {attachment.mime}; only PDF and image attachments can be merged",
    )


def merge_documents(cover_pdf: bytes, cv_pdf: bytes, attachments: list[Attachment]) -> bytes:
    writer = PdfWriter()
    for content in (cover_pdf, cv_pdf):
        writer.append(io.BytesIO(content))
    for attachment in attachments:
        writer.append(io.BytesIO(attachment_pdf(attachment)))
    buffer = io.BytesIO()
    writer.write(buffer)
    writer.close()
    return buffer.getvalue()


def page_count(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


@app.get("/health")
def health():
    return {"ok": True, "service": "mukana-renderer"}


@app.post("/render")
def render(body: RenderRequest, x_render_secret: str | None = Header(default=None)):
    expected = os.getenv("RENDER_SECRET")
    if expected and x_render_secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if body.theme not in THEMES:
        raise HTTPException(status_code=400, detail=f"Unknown theme: {body.theme}")

    cv_pdf = render_cv(body.cv, body.theme)
    cover_pdf = render_cover_letter(body.cover_letter) if body.cover_letter else None
    cover_docx = render_cover_letter_docx(body.cover_letter) if body.cover_letter else None
    merged = (
        merge_documents(cover_pdf, cv_pdf, body.attachments)
        if body.merge and cover_pdf
        else None
    )

    return {
        "theme": body.theme,
        "cv_pdf": base64.b64encode(cv_pdf).decode("ascii"),
        "cover_letter_pdf": base64.b64encode(cover_pdf).decode("ascii") if cover_pdf else None,
        "cover_letter_docx": base64.b64encode(cover_docx).decode("ascii") if cover_docx else None,
        "merged_pdf": base64.b64encode(merged).decode("ascii") if merged else None,
        "cv_pages": page_count(cv_pdf),
        "merged_pages": page_count(merged) if merged else None,
    }
