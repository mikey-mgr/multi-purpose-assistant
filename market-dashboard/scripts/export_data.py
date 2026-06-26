"""
Export job market data from PostgreSQL to CSV files for the Observable dashboard.

Usage:
    cd market-dashboard && npm run export-data
    # or directly (from repo root):
    conda run -n prefect_env python market-dashboard/scripts/export_data.py
"""

import csv
import logging
import os
import re
import sys
from collections import Counter, defaultdict

# Ensure repo root is on sys.path (script is at market-dashboard/scripts/export_data.py → up 3 levels)
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from core.database import get_session, ScrapedJob, JobEnrichment, JobMatch

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")


def _write_csv(filename: str, headers: list[str], rows: list[list]):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    logger.info("Wrote %d rows → %s", len(rows), filename)


def _norm_job_type(text: str) -> str:
    t = text.strip().lower()
    return {
        "full time": "Full-time", "full-time": "Full-time",
        "part time": "Part-time", "part-time": "Part-time",
        "contract": "Contract", "internship": "Internship",
        "temporary": "Temporary", "freelance": "Freelance",
    }.get(t, text.strip())


def _ascii(text: str) -> str:
    """Replace common non-ASCII chars with ASCII equivalents."""
    t = text
    for ch, repl in {"\u2011": "-", "\u2012": "-", "\u2013": "-",
                      "\u2014": "-", "\u2015": "-", "\u2212": "-",
                      "\u2018": "'", "\u2019": "'",
                      "\u201c": '"', "\u201d": '"',
                      "\u2026": "...", "\u00a0": " "}.items():
        t = t.replace(ch, repl)
    return t


SKILL_ALIASES = {
    "microsoft excel": "excel", "ms excel": "excel",
    "microsoft word": "word", "ms word": "word",
    "microsoft outlook": "outlook", "ms outlook": "outlook",
    "microsoft powerpoint": "powerpoint", "ms powerpoint": "powerpoint",
    "microsoft office": "microsoft office", "ms office": "microsoft office",
    "microsoft office suite": "microsoft office",
    "microsoft office word": "word", "ms office word": "word",
    "microsoft office excel": "excel", "ms office excel": "excel",
    "microsoft office outlook": "outlook", "ms office outlook": "outlook",
    "microsoft office powerpoint": "powerpoint", "ms office powerpoint": "powerpoint",
    "microsoft office access": "access", "ms office access": "access",
    "crm": "crm systems", "crm system": "crm systems", "crm software": "crm systems",
    "social media platforms": "social media management",
    "social media": "social media management",
    "presentation skills": "presentation",
    "report writing": "reporting",
    "computer literacy": "computer skills",
    "microsoft 365": "microsoft office", "office 365": "microsoft office",
    "microsoft teams": "teams", "ms teams": "teams",
}


def _norm_skill(text: str) -> str:
    t = _ascii(text.lower().strip())
    t = t.replace("-", " ")
    t = re.sub(r"\s+", " ", t)
    # Apply UK→US and skill aliases
    uk_us = {"organisation": "organization", "organisations": "organizations",
             "organisational": "organizational",
             "organise": "organize", "organises": "organizes", "organised": "organized",
             "organising": "organizing",
             "specialisation": "specialization", "specialised": "specialized",
             "specialises": "specializes", "specialising": "specializing",
             "utilise": "utilize", "utilised": "utilized", "utilising": "utilizing"}
    words = t.split()
    words = [uk_us.get(w, w) for w in words]
    t = " ".join(words).strip()
    return SKILL_ALIASES.get(t, t)
    t = re.sub(r"\s+", " ", t)
    uk_us = {"organisation": "organization", "organisations": "organizations",
             "organisational": "organizational",
             "organise": "organize", "organises": "organizes", "organised": "organized",
             "organising": "organizing",
             "specialisation": "specialization", "specialised": "specialized",
             "specialises": "specializes", "specialising": "specializing",
             "utilise": "utilize", "utilised": "utilized", "utilising": "utilizing"}
    words = t.split()
    words = [uk_us.get(w, w) for w in words]
    return " ".join(words).strip()


def _norm_company(val) -> str:
    if val is None or (isinstance(val, float) and str(val) == "nan"):
        return ""
    c = str(val).strip()
    return "" if c.lower() in ("", "nan", "none", "null") else c


def _norm_title(text: str) -> str:
    title = (text or "").lower().strip()
    title = re.sub(r"[^\w\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    session = get_session()

    try:
        raw_rows = session.query(ScrapedJob, JobEnrichment).outerjoin(
            JobEnrichment, ScrapedJob.id == JobEnrichment.job_id
        ).order_by(ScrapedJob.scraped_at.desc()).all()

        # ── Dedup: keep best record per (title, company) ───
        groups = defaultdict(list)
        for sj, je in raw_rows:
            key = (_norm_title(sj.title or ""), _norm_company(sj.company).lower())
            groups[key].append((sj, je))

        rows = []
        for key, items in groups.items():
            items.sort(key=lambda x: (
                1 if x[1] else 0,
                sum(1 for f in ["technical_skills", "soft_skills", "required_qualifications",
                                 "normalized_category", "job_type", "required_experience",
                                 "currency", "min_salary", "max_salary"]
                    if x[1] and getattr(x[1], f, None)),
                x[0].scraped_at.isoformat() if x[0].scraped_at else ""
            ), reverse=True)
            rows.append(items[0])

        logger.info("Dedup: %d raw → %d unique", len(raw_rows), len(rows))

        # ── Jobs overview ────────────────────
        overview = []
        for sj, je in rows:
            overview.append([
                sj.id, _ascii(sj.title or ""), _norm_company(sj.company), _ascii(sj.location or ""),
                str(sj.date_posted or ""), sj.scraped_at.isoformat() if sj.scraped_at else "",
                je.normalized_category or "" if je else "",
                _norm_job_type(je.job_type) if je and je.job_type else "",
                "Yes" if je and je.remote_eligible else ("No" if je else ""),
                je.required_experience or "" if je else "",
                je.currency or "" if je else "",
                je.min_salary or "" if je else "",
                je.max_salary or "" if je else "",
            ])
        _write_csv("jobs.csv", [
            "id", "title", "company", "location", "date_posted", "scraped_at",
            "category", "job_type", "remote_eligible", "required_experience",
            "currency", "min_salary", "max_salary",
        ], overview)

        # ── Skills (technical) ───────────────
        tech_skills: Counter = Counter()
        for _, je in rows:
            if je and je.technical_skills:
                for s in je.technical_skills:
                    tech_skills[_norm_skill(s)] += 1
        _write_csv("technical_skills.csv", ["skill", "job_count"],
                    [[s, c] for s, c in tech_skills.most_common()])

        # ── Skills (soft) ────────────────────
        soft_skills: Counter = Counter()
        for _, je in rows:
            if je and je.soft_skills:
                for s in je.soft_skills:
                    soft_skills[_norm_skill(s)] += 1
        _write_csv("soft_skills.csv", ["skill", "job_count"],
                    [[s, c] for s, c in soft_skills.most_common()])

        # ── Qualifications ───────────────────
        quals: Counter = Counter()
        for _, je in rows:
            if je and je.required_qualifications:
                for q in je.required_qualifications:
                    quals[_norm_skill(q)] += 1
        _write_csv("qualifications.csv", ["qualification", "job_count"],
                    [[q, c] for q, c in quals.most_common()])

        # ── Companies hiring ─────────────────
        companies: Counter = Counter()
        for sj, _ in rows:
            c = _norm_company(sj.company).lower()
            if c:
                companies[c] += 1
        _write_csv("companies.csv", ["company", "job_count"],
                    [[c, n] for c, n in companies.most_common()])

        # ── Categories ───────────────────────
        cats: Counter = Counter()
        for _, je in rows:
            if je and je.normalized_category:
                cats[je.normalized_category] += 1
        _write_csv("categories.csv", ["category", "job_count"],
                    [[c, n] for c, n in cats.most_common()])

        # ── Job types ────────────────────────
        types: Counter = Counter()
        for _, je in rows:
            if je and je.job_type:
                types[_norm_job_type(je.job_type)] += 1
        _write_csv("job_types.csv", ["type", "job_count"],
                    [[t, n] for t, n in types.most_common()])

        # ── Experience levels ────────────────
        def _norm_exp(text: str) -> str:
            t = text.lower().strip()
            m = re.search(r"(\d+)\s*[–\-to]+\s*(\d+)", t)
            if m:
                lo, hi = int(m.group(1)), int(m.group(2))
                return f"{lo}-{hi} years"
            # "X+ years", "X+ year"
            m = re.search(r"(\d+)\s*\+", t)
            if m:
                yr = int(m.group(1))
                return f"{yr}+ years"
            # "at least X years", "minimum X years", "min X years"
            m = re.search(r"(?:at least|minimum|min)[.\s]*(\d+)", t)
            if m:
                yr = int(m.group(1))
                return f"{yr}+ years"
            # "X-years" or "X year" or "X years" (just a number)
            m = re.search(r"(\d+)\s*(?:year|yr)", t)
            if m:
                yr = int(m.group(1))
                return f"{yr} year{'s' if yr > 1 else ''}"
            # bare number
            m = re.search(r"\b(\d+)\b", t)
            if m:
                yr = int(m.group(1))
                return f"{yr}+ years"
            return t

        exp: Counter = Counter()
        for _, je in rows:
            if je and je.required_experience:
                exp[_norm_exp(je.required_experience)] += 1
        _write_csv("experience.csv", ["level", "job_count"],
                    [[l, n] for l, n in exp.most_common()])

        # ── Match outcomes ───────────────────
        matches = session.query(JobMatch).all()
        outcomes: Counter = Counter()
        for m in matches:
            outcomes[m.status] += 1
        _write_csv("match_outcomes.csv", ["status", "count"],
                    [[s, c] for s, c in outcomes.most_common()])

        logger.info("Export complete — %d files written to %s", 10, OUT_DIR)

    finally:
        session.close()


if __name__ == "__main__":
    main()
