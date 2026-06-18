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
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

logger = logging.getLogger(__name__)


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
) -> dict:
    """
    Build a RenderCV-ready dictionary from database data and optional
    LLM-rewritten section content.

    `llm_section_overrides` keys (all optional):
      - summary: str — rewritten professional summary
      - experience_highlights: dict[company_name, list[str]] — rewritten bullets
      - skills: list[{"label": str, "details": str}] — curated skills list
      - project_highlights: dict[project_name, list[str]] — rewritten bullets
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
            "headline": overrides.get("summary", resume.get("professional_summary", "")),
            "location": location or None,
            "email": user.get("email"),
            "phone": user.get("phone_1") or user.get("phone_2"),
            "social_networks": social or None,
        }
    }

    # ── Professional Summary (custom section for the full text) ─────
    sections: dict[str, list] = {}
    summary_text = overrides.get("summary", resume.get("professional_summary"))
    if summary_text:
        sections["Professional Summary"] = [summary_text]

    # ── Skills ──────────────────────────────────────────────────────
    skills_override = overrides.get("skills")
    if skills_override:
        sections["skills"] = skills_override
    elif skills:
        sections["skills"] = _group_skills(skills)

    # ── Experience ──────────────────────────────────────────────────
    exp_overrides = overrides.get("experience_highlights", {})
    exp_list = []
    for exp in experiences:
        company = exp.get("company_name", "")
        highlights = exp_overrides.get(company, exp.get("bullet_points", []))
        exp_list.append({
            "company": company,
            "position": exp.get("job_title"),
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
        edu_list.append({
            "institution": edu.get("institution_name"),
            "area": edu.get("field_of_study"),
            "degree": edu.get("degree_type"),
            "start_date": _fmt_date(edu.get("start_date")),
            "end_date": _fmt_date(edu.get("end_date")),
            "highlights": highlights or None,
        })
    if edu_list:
        sections["education"] = edu_list

    # ── Certifications ──────────────────────────────────────────────
    cert_list = []
    for cert in certifications:
        cert_list.append({
            "name": cert.get("cert_name"),
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
        proj_list.append({
            "name": pname,
            "location": None,
            "start_date": _fmt_date(proj.get("start_date")),
            "end_date": _fmt_date(proj.get("end_date")),
            "summary": proj.get("description"),
            "highlights": highlights or None,
        })
    if proj_list:
        sections["projects"] = proj_list

    cv["cv"]["sections"] = sections
    cv["design"] = {"theme": "harvard"}
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


def write_yaml(cv_dict: dict, output_path: str) -> str:
    """Write the RenderCV YAML file."""
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(cv_dict, f, allow_unicode=True, sort_keys=False)
    return output_path


def render(
    cv_dict: dict,
    output_dir: str | None = None,
) -> str:
    """
    Write YAML, call `rendercv render`, return path to generated PDF.

    The PDF lands in data/rendercv_output/<name>_cv.pdf.
    """
    if output_dir is None:
        output_dir = os.path.join(settings.OUTPUT_DIR, "rendercv_output")
    os.makedirs(output_dir, exist_ok=True)

    name = cv_dict["cv"]["name"]
    name_slug = slugify(name)

    # Write YAML to temp location, then copy to output dir
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as tmp:
        yaml_path = tmp.name
        yaml.dump(cv_dict, tmp, allow_unicode=True, sort_keys=False)

    try:
        # rendercv always writes to a subfolder named after the YAML's stem
        stem = Path(yaml_path).stem
        rendercv_out = Path(yaml_path).parent / stem

        result = subprocess.run(
            ["rendercv", "render", yaml_path, "--output-folder", str(rendercv_out)],
            capture_output=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=120,
        )
        if result.returncode != 0:
            # rendercv sometimes exits 1 due to Unicode console issues on
            # Windows even when the PDF was generated successfully — treat
            # the PDF's existence as the real signal.
            logger.warning("rendercv exited %d (may be a false positive)", result.returncode)

        # Copy PDF to our output dir
        pdf_name = f"{name_slug}_cv.pdf"
        src_pdf = rendercv_out / pdf_name
        if src_pdf.exists():
            dst_pdf = os.path.join(output_dir, pdf_name)
            import shutil
            shutil.copy2(str(src_pdf), dst_pdf)
            logger.info("PDF written to %s", dst_pdf)
        else:
            # Try the stem name rendercv generates
            src_pdf = rendercv_out / f"{stem}_cv.pdf"
            if src_pdf.exists():
                dst_pdf = os.path.join(output_dir, pdf_name)
                import shutil
                shutil.copy2(str(src_pdf), dst_pdf)
                logger.info("PDF written to %s", dst_pdf)
            else:
                logger.warning("PDF not found in rendercv output; check stderr:\n%s", result.stderr)
                return ""

        # Also save a copy of the source YAML
        yaml_dst = os.path.join(output_dir, f"{name_slug}_cv.yaml")
        shutil.copy2(yaml_path, yaml_dst)

        return dst_pdf
    finally:
        os.unlink(yaml_path)
