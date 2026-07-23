"""
RenderCV resume generator.

Assembles a RenderCV-compatible YAML dictionary from the user's profile data,
optionally merges in LLM-rewritten section content, shells out to
`rendercv render`, and copies the output PDF to data/rendercv_output/.
"""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from app.config import settings
from app.utils import unique_path

logger = logging.getLogger(__name__)

_LATEX_UNSAFE_RE = re.compile(r'[\u201c\u201d\u2018\u2019\u2013\u2014\u2022\u2026\u00a0\ufffd\u00a9\u00ae\u2122]')


def _sanitize_text(text: str | None) -> str | None:
    """Replace LaTeX-unsafe Unicode chars with ASCII equivalents before YAML export."""
    if not text:
        return text
    replacements = {
        '\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
        '\u2013': '-', '\u2014': '--', '\u2022': '-', '\u2026': '...',
        '\u00a0': ' ', '\ufffd': '', '\u00a9': '(c)', '\u00ae': '(r)',
        '\u2122': '(tm)',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def slugify(name: str) -> str:
    return re.sub(r'[^a-z0-9_]', '', name.lower().replace(' ', '_'))


def _fmt_date(d: str | None) -> str | None:
    if not d:
        return None
    d = str(d)
    if len(d) >= 7:
        return d[:7]  # YYYY-MM
    return d


def build_yaml_dict(
    user: dict[str, Any],
    resume: dict[str, Any],
    experiences: list[dict],
    education: list[dict],
    certifications: list[dict],
    projects: list[dict],
    skills: list[dict],
    llm_section_overrides: dict[str, Any] | None = None,
    references_full: list[dict] | None = None,
) -> dict:
    """
    Build a RenderCV-ready dictionary from database data and optional
    LLM-rewritten section content.

    `llm_section_overrides` keys (all optional):
      - summary: str — rewritten professional summary
      - experience_highlights: dict["Company Name - Job Title", list[str]] — rewritten bullets (composite key)
      - skills: list[{"label": str, "details": str}] — curated skills list
      - project_highlights: dict[project_name, list[str]] — rewritten bullets
      - references: list[{"ref_id": str, "name": str, "description": str}] — AI-decided ref entries

    `references_full`: full reference records from the DB (with phone/email) for populating
      the references section without exposing contact details to the LLM.
    """
    overrides = llm_section_overrides or {}

    # ── Header ──────────────────────────────────────────────────────
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    location = ", ".join(
        filter(None, [user.get('location_city'), user.get('location_country')])
    )
    social = []
    if user.get('linkedin_url'):
        social.append({"network": "LinkedIn", "username": user['linkedin_url']})

    cv: dict[str, Any] = {
        "cv": {
            "name": name,
            "location": location or None,
            "email": user.get("email"),
            "phone": user.get("phone_1") or user.get("phone_2"),
            "social_networks": social or None,
        }
    }

    summary_text = overrides.get("summary", resume.get("professional_summary"))
    if summary_text:
        sections: dict[str, list] = {}
        sections["Professional Summary"] = [summary_text]
    else:
        sections = {}

    # ── Skills ──────────────────────────────────────────────────────
    skills_override = overrides.get("skills")
    if isinstance(skills_override, list) and all(
        isinstance(s, dict) and "label" in s and "details" in s for s in skills_override
    ):
        sections["skills"] = skills_override
    elif skills:
        sections["skills"] = _group_skills(skills)

    # ── Experience ──────────────────────────────────────────────────
    exp_overrides = overrides.get("experience_highlights", {})
    exp_list = []
    for exp in experiences:
        company = exp.get("company_name", "")
        position = exp.get("job_title", "")
        highlights = exp_overrides.get(f"{company} - {position}", exp.get("bullet_points", []))
        exp_list.append({
            "company": company,
            "position": position,
            "location": exp.get("location"),
            "start_date": _fmt_date(exp.get("start_date")),
            "end_date": _fmt_date(exp.get("end_date")),
            "highlights": highlights,
        })
    if exp_list:
        sections["experience"] = exp_list

    # ── Education ───────────────────────────────────────────────────
    edu_list = []
    for edu in education:
        highlights = []
        if edu.get("grade_or_class"):
            highlights.append(f"Grade: {edu['grade_or_class']}")
        degree = edu.get("degree_type", "")
        field = edu.get("field_of_study", "")
        # area should be just the field, degree is separate — RenderCV's
        # DEGREE_WITH_AREA locale template combines them properly
        edu_list.append({
            "institution": edu.get("institution_name"),
            "area": field or None,
            "degree": degree or None,
            "start_date": _fmt_date(edu.get("start_date")),
            "end_date": _fmt_date(edu.get("end_date")),
            "highlights": highlights or None,
        })
    if edu_list:
        sections["education"] = edu_list

    # ── Certifications ──────────────────────────────────────────────
    cert_list = []
    for cert in certifications:
        cname = cert.get("cert_name") or ""
        curl = cert.get("credential_url")
        cert_list.append({
            "name": f"[{cname} (Click to view)]({curl})" if curl else cname,
            "issuer": cert.get("issuing_organization"),
            "date": _fmt_date(cert.get("issue_date")),
        })
    if cert_list:
        sections["certifications"] = cert_list

    # ── Projects ────────────────────────────────────────────────────
    proj_overrides = overrides.get("project_highlights", {})
    proj_list = []
    for proj in projects:
        pname = proj.get("project_name", "")
        highlights = proj_overrides.get(pname, proj.get("bullet_points", []))
        purl = proj.get("project_url")
        entry = {
            "name": pname,
            "location": None,
            "start_date": _fmt_date(proj.get("start_date")),
            "end_date": _fmt_date(proj.get("end_date")),
            "highlights": highlights or None,
        }
        if purl:
            entry["name"] = f"[{pname} (Click to view)]({purl})"
        proj_list.append(entry)
    if proj_list:
        sections["projects"] = proj_list

    # ── References ────────────────────────────────────────────────────
    ref_overrides = overrides.get("references")
    if isinstance(ref_overrides, list) and ref_overrides and references_full:
        ref_index = {r["ref_id"]: r for r in references_full}
        ref_list = []
        for ref in ref_overrides:
            rid = ref.get("ref_id")
            full = ref_index.get(rid)
            if not full:
                continue
            contact_lines = []
            if full.get("email"):
                contact_lines.append(f"Email: {full['email']}")
            if full.get("phone"):
                contact_lines.append(f"Phone: {full['phone']}")
            ref_list.append({
                "name": full["name"],
                "summary": ref.get("description", ""),
                "highlights": contact_lines or None,
            })
        if ref_list:
            sections["references"] = ref_list

    cv["cv"]["sections"] = sections
    cv["design"] = {
        "theme": "harvard",
        "templates": {
            "education_entry": {
                "degree_column": "",
            },
        },
    }
    return cv


def _group_skills(skills: list[dict]) -> list[dict]:
    """Group skills by skill_type into label/details pairs."""
    from collections import defaultdict
    groups = defaultdict(list)
    for s in skills:
        groups[s.get("skill_type", "Other")].append(s["skill_name"])
    return [
        {"label": label, "details": ", ".join(items)}
        for label, items in groups.items()
    ]


def _sanitize_dict(obj: Any) -> Any:
    """Recursively sanitize all string values in a dict/list tree."""
    if isinstance(obj, str):
        return _sanitize_text(obj) or ""
    if isinstance(obj, dict):
        return {k: _sanitize_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_dict(v) for v in obj]
    return obj


def write_yaml(cv_dict: dict, output_path: str) -> str:
    """Write the RenderCV YAML file."""
    cv_dict = _sanitize_dict(cv_dict)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(cv_dict, f, allow_unicode=True, sort_keys=False)
    return output_path


def render(
    cv_dict: dict,
    job_title: str = "",
    output_dir: str | None = None,
) -> str:
    """
    Write YAML, call ``rendercv render``, return path to generated PDF.

    The PDF lands in ``data/rendercv_output/Name Surname CV - Job Title.pdf``.
    If a file with that name exists, a counter is appended before the extension.
    """
    if output_dir is None:
        output_dir = os.path.join(settings.OUTPUT_DIR, "rendercv_output")
    os.makedirs(output_dir, exist_ok=True)

    cv_dict = _sanitize_dict(cv_dict)
    name = cv_dict["cv"]["name"]

    # Use a unique temp directory per render call — prevents race when
    # multiple tasks run concurrently (each gets its own output folder).
    with tempfile.TemporaryDirectory() as tmp_dir:
        yaml_path = os.path.join(tmp_dir, "cv.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(cv_dict, f, allow_unicode=True, sort_keys=False)

        cmd = ["rendercv", "render", yaml_path, "--output-folder", tmp_dir]
        if os.name == "nt":
            cmd = [sys.executable, "-m", "rendercv", "render", yaml_path, "--output-folder", tmp_dir]
        result = subprocess.run(cmd,
            capture_output=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning("rendercv exited %d (may be a false positive)", result.returncode)

        pdf_files = list(Path(tmp_dir).glob("*CV*.pdf"))
        if not pdf_files:
            logger.warning("No PDF found in rendercv output; stderr:\n%s", result.stderr)
            logger.warning("rendercv stdout:\n%s", result.stdout)
            return ""

        src_pdf = str(pdf_files[0])
        logger.info("Found rendercv PDF: %s", src_pdf)

        cv_basename = f"{name} CV - {job_title}" if job_title else f"{name} CV"
        dst_pdf = unique_path(output_dir, cv_basename, ".pdf")
        dst_yaml = unique_path(output_dir, cv_basename, ".yaml")
        import shutil
        shutil.copy2(src_pdf, dst_pdf)
        shutil.copy2(yaml_path, dst_yaml)
        logger.info("PDF written to %s", dst_pdf)
        logger.info("YAML written to %s", dst_yaml)

        return dst_pdf
