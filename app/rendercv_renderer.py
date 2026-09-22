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


def _coerce_strings(items: Any) -> list[str]:
    """Coerce a bullet-points value into a list of strings.

    rendercv requires every highlight to be a string. LLM output (or DB data)
    may embed dicts/lists (e.g. nested bullet groups); those are flattened.
    """
    if items is None:
        return []
    if isinstance(items, str):
        return [items]
    if not isinstance(items, list):
        return [str(items)]
    out: list[str] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, (dict, list)):
            out.extend(_coerce_strings(item))
        else:
            out.append(str(item))
    return out


def _fmt_date(d: str | None) -> str | None:
    if not d:
        return None
    d = str(d)
    if len(d) >= 7:
        return d[:7]  # YYYY-MM
    return d


def _github_profile_url(projects: list[dict]) -> str | None:
    """Return the first GitHub profile URL present in the candidate's projects."""
    for project in projects:
        url = str(project.get("project_url") or "")
        match = re.match(r"https?://(?:www\.)?github\.com/([^/]+)", url, re.IGNORECASE)
        if match:
            return f"https://github.com/{match.group(1)}"
    return None


def _ensure_url_scheme(url: str | None) -> str | None:
    """Prepend https:// when a URL has no scheme.

    Legacy DB data (e.g. linkedin_url "www.linkedin.com/...") fails RenderCV's
    URL validation for custom_connections. Normalizing here keeps old rows working.
    """
    if not url:
        return None
    url = str(url).strip()
    if not url:
        return None
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        return f"https://{url}"
    return url


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
    additional_information = resume.get("additional_information") or {}
    custom_connections = []
    if user.get('linkedin_url'):
        custom_connections.append({
            "fontawesome_icon": "linkedin",
            "placeholder": "LinkedIn",
            "url": _ensure_url_scheme(user["linkedin_url"]),
        })
    if github_profile_url := _github_profile_url(projects):
        custom_connections.append({
            "fontawesome_icon": "github",
            "placeholder": "GitHub",
            "url": github_profile_url,
        })
    if portfolio_url := additional_information.get("portfolio_url"):
        custom_connections.append({
            "fontawesome_icon": "link",
            "placeholder": "Portfolio",
            "url": _ensure_url_scheme(portfolio_url),
        })

    cv: dict[str, Any] = {
        "cv": {
            "name": name,
            "location": location or None,
            "email": user.get("email"),
            "phone": user.get("phone_1") or user.get("phone_2"),
            "headline": resume.get("headline") or os.getenv(
                "CV_HEADLINE", "Software Developer  ·  DevOps Enthusiast"
            ),
            "custom_connections": custom_connections or None,
        }
    }

    summary_text = overrides.get("summary", resume.get("professional_summary"))
    if summary_text:
        sections: dict[str, list] = {}
        sections["PROFESSIONAL PROFILE"] = [summary_text]
    else:
        sections = {}

    # ── Skills ──────────────────────────────────────────────────────
    skills_override = overrides.get("skills")
    if isinstance(skills_override, list) and all(
        isinstance(s, dict) and "label" in s and "details" in s for s in skills_override
    ):
        skills_section = skills_override
    elif skills:
        skills_section = _group_skills(skills)
    else:
        skills_section = []

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
            "highlights": _coerce_strings(highlights),
        })
    if exp_list:
        experience_section = exp_list
    else:
        experience_section = []

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
        education_section = edu_list
    else:
        education_section = []

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
        certifications_section = cert_list
    else:
        certifications_section = []

    # ── Projects ────────────────────────────────────────────────────
    proj_overrides = overrides.get("project_highlights", {})
    proj_list = []
    if proj_overrides:
        # LLM chose which projects to include — only include those it provided overrides for
        proj_names = set(proj_overrides.keys())
        for proj in projects:
            pname = proj.get("project_name", "")
            if pname not in proj_names:
                continue
            highlights = proj_overrides.get(pname, [])
            purl = proj.get("project_url")
            entry = {
                "name": pname,
                "location": None,
                "summary": (
                    f"*Tech:* {' · '.join(proj.get('tech_stack') or [])}"
                    if proj.get("tech_stack") else None
                ),
                "start_date": _fmt_date(proj.get("start_date")),
                "end_date": _fmt_date(proj.get("end_date")),
                "highlights": _coerce_strings(highlights) or None,
            }
            if purl:
                entry["name"] = f"[{pname} (GitHub)]({purl})"
            proj_list.append(entry)
    else:
        # No LLM override — include up to 2 most recent projects by ID
        sorted_projects = sorted(projects, key=lambda p: p.get("id", 0) or 0, reverse=True)
        for proj in sorted_projects[:2]:
            pname = proj.get("project_name", "")
            highlights = proj.get("bullet_points", [])
            purl = proj.get("project_url")
            entry = {
                "name": pname,
                "location": None,
                "summary": (
                    f"*Tech:* {' · '.join(proj.get('tech_stack') or [])}"
                    if proj.get("tech_stack") else None
                ),
                "start_date": _fmt_date(proj.get("start_date")),
                "end_date": _fmt_date(proj.get("end_date")),
                "highlights": _coerce_strings(highlights) or None,
            }
            if purl:
                entry["name"] = f"[{pname} (Click to view)]({purl})"
            proj_list.append(entry)
    if proj_list:
        projects_section = proj_list
    else:
        projects_section = []

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
            references_section = ref_list
        else:
            references_section = []
    else:
        references_section = []

    # Keep the same reading order as the candidate's established CV style.
    if education_section:
        sections["EDUCATION"] = education_section
    if experience_section:
        sections["WORK EXPERIENCE"] = experience_section
    if projects_section:
        sections["PROJECTS"] = projects_section
    if skills_section:
        sections["TECHNICAL SKILLS"] = skills_section
    additional_information_section = []
    portfolio_url = _ensure_url_scheme(additional_information.get("portfolio_url"))
    if portfolio_url:
        portfolio_label = additional_information.get("portfolio_label") or portfolio_url.removeprefix("https://").removeprefix("http://")
        additional_information_section.append(
            f"**Portfolio:** [{portfolio_label}]({portfolio_url})"
        )
    if availability := additional_information.get("availability"):
        additional_information_section.append(f"**Availability:** {availability}")
    if references_note := additional_information.get("references"):
        additional_information_section.append(f"**References:** {references_note}")
    if additional_information_section:
        sections["ADDITIONAL INFORMATION"] = additional_information_section
    if certifications_section:
        sections["CERTIFICATIONS"] = certifications_section
    if references_section:
        sections["REFERENCES"] = references_section

    cv["cv"]["sections"] = sections
    cv["design"] = {
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
    return cv


def _group_skills(skills: list[dict]) -> list[dict]:
    """Group skills into stable, readable CV rows."""
    from collections import defaultdict

    categories = (
        ("Languages", {"Language"}),
        ("Frameworks & Libraries", {"Framework", "ML/AI"}),
        ("DevOps & Tools", {"DevOps", "Tool"}),
        ("Databases", {"Database"}),
        ("Concepts", {"Concept"}),
    )
    groups = defaultdict(list)
    for s in skills:
        groups[s.get("skill_type", "Other")].append(s["skill_name"])
    rows = []
    consumed = set()
    for label, types in categories:
        items = [skill for skill_type in types for skill in groups[skill_type]]
        consumed.update(types)
        if items:
            rows.append({"label": label, "details": ", ".join(items)})
    for label, items in groups.items():
        if label not in consumed and items:
            rows.append({"label": label, "details": ", ".join(items)})
    return rows


def _sanitize_dict(obj: Any) -> Any:
    """Recursively sanitize all string values in a dict/list tree."""
    if isinstance(obj, str):
        return _sanitize_text(obj) or ""
    if isinstance(obj, dict):
        return {k: _sanitize_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_dict(v) for v in obj]
    if obj is None:
        return None
    return str(obj)


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

    The PDF lands in ``RENDERCV_OUTPUT_DIR`` when configured, otherwise in
    ``data/rendercv_output/Name Surname CV - Job Title.pdf``.
    If a file with that name exists, a counter is appended before the extension.
    """
    if output_dir is None:
        output_dir = os.getenv(
            "RENDERCV_OUTPUT_DIR",
            os.path.join(settings.OUTPUT_DIR, "rendercv_output"),
        )
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
