"""
Retrieval-Augmented Generation helpers.

Assembles a user profile from the database for prompt injection,
and runs hybrid (keyword + semantic) searches against job postings
and resume data.
"""

import logging
from uuid import UUID

from core.database import (
    get_session, User, Resume, WorkExperience, Project,
    Education, Certification, Skill, ScrapedJob,
    search_jobs_hybrid, search_projects, search_experiences,
)
from app.schemas import UserProfile, JobDescription
from app.llm import generate_embedding

logger = logging.getLogger(__name__)


def assemble_user_profile(user_id: UUID, resume_id: UUID | None = None) -> UserProfile:
    """
    Fetch a user + their active (or specified) resume version
    and return a flat UserProfile for prompt injection.
    """
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        query = session.query(Resume).filter(Resume.user_id == user_id)
        if resume_id:
            query = query.filter(Resume.id == resume_id)
        else:
            query = query.filter(Resume.is_active == True)
        resume = query.first()

        if not resume:
            raise ValueError(f"No resume found for user {user_id}")

        experiences = session.query(WorkExperience).filter(
            WorkExperience.resume_id == resume.id
        ).order_by(WorkExperience.display_order).all()

        projects = session.query(Project).filter(
            Project.resume_id == resume.id
        ).order_by(Project.display_order).all()

        education = session.query(Education).filter(
            Education.resume_id == resume.id
        ).order_by(Education.display_order).all()

        certifications = session.query(Certification).filter(
            Certification.resume_id == resume.id
        ).all()

        skills = session.query(Skill).filter(
            Skill.resume_id == resume.id
        ).all()

        return UserProfile(
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone=user.phone_1 or user.phone_2,
            linkedin_url=user.linkedin_url,
            location=f"{user.location_city or ''}, {user.location_country or ''}".strip(", "),
            professional_summary=resume.professional_summary,
            skills=[s.skill_name for s in skills],
            work_experience=[{
                "company": e.company_name,
                "title": e.job_title,
                "location": e.location,
                "start": str(e.start_date),
                "end": str(e.end_date) if e.end_date else "Present",
                "bullets": e.bullet_points,
            } for e in experiences],
            projects=[{
                "name": p.project_name,
                "description": p.description,
                "tech_stack": p.tech_stack or [],
                "url": p.project_url,
                "bullets": p.bullet_points or [],
            } for p in projects],
            education=[{
                "institution": e.institution_name,
                "degree": e.degree_type,
                "field": e.field_of_study,
                "grade": e.grade_or_class,
                "start": str(e.start_date) if e.start_date else None,
                "end": str(e.end_date) if e.end_date else None,
            } for e in education],
            certifications=[{
                "name": c.cert_name,
                "issuer": c.issuing_organization,
                "date": str(c.issue_date) if c.issue_date else None,
                "url": c.credential_url,
            } for c in certifications],
        )
    finally:
        session.close()


def _fetch_raw_profile_data(user_id, resume_id=None):
    """
    Return raw dicts from all normalised tables for a user+resume.
    Used by the RenderCV renderer to build YAML directly from DB.
    """
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        query = session.query(Resume).filter(Resume.user_id == user_id)
        if resume_id:
            query = query.filter(Resume.id == resume_id)
        else:
            query = query.filter(Resume.is_active == True)
        resume = query.first()
        if not resume:
            raise ValueError(f"No resume found for user {user_id}")

        experiences = session.query(WorkExperience).filter(
            WorkExperience.resume_id == resume.id
        ).order_by(WorkExperience.display_order).all()

        projects = session.query(Project).filter(
            Project.resume_id == resume.id
        ).order_by(Project.display_order).all()

        education = session.query(Education).filter(
            Education.resume_id == resume.id
        ).order_by(Education.display_order).all()

        certifications = session.query(Certification).filter(
            Certification.resume_id == resume.id
        ).all()

        skills = session.query(Skill).filter(
            Skill.resume_id == resume.id
        ).all()

        return {
            "user": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone_1": user.phone_1,
                "phone_2": user.phone_2,
                "linkedin_url": user.linkedin_url,
                "location_city": user.location_city,
                "location_country": user.location_country,
            },
            "resume": {
                "id": resume.id,
                "version_name": resume.version_name,
                "professional_summary": resume.professional_summary,
            },
            "experiences": [
                {
                    "company_name": e.company_name,
                    "job_title": e.job_title,
                    "location": e.location,
                    "start_date": str(e.start_date) if e.start_date else None,
                    "end_date": str(e.end_date) if e.end_date else None,
                    "bullet_points": e.bullet_points or [],
                }
                for e in experiences
            ],
            "projects": [
                {
                    "project_name": p.project_name,
                    "description": p.description,
                    "start_date": None,
                    "end_date": None,
                    "project_url": p.project_url,
                    "bullet_points": p.bullet_points or [],
                }
                for p in projects
            ],
            "education": [
                {
                    "institution_name": e.institution_name,
                    "degree_type": e.degree_type,
                    "field_of_study": e.field_of_study,
                    "grade_or_class": e.grade_or_class,
                    "start_date": str(e.start_date) if e.start_date else None,
                    "end_date": str(e.end_date) if e.end_date else None,
                }
                for e in education
            ],
            "certifications": [
                {
                    "cert_name": c.cert_name,
                    "issuing_organization": c.issuing_organization,
                    "issue_date": str(c.issue_date) if c.issue_date else None,
                    "credential_url": c.credential_url,
                }
                for c in certifications
            ],
            "skills": [
                {"skill_name": s.skill_name, "skill_type": s.skill_type}
                for s in skills
            ],
            "profile": None,  # filled by caller or via assemble_user_profile
        }
    finally:
        session.close()


def _fetch_profile_with_pydantic(user_id, resume_id=None):
    """Convenience: returns both raw dicts and the Pydantic UserProfile."""
    data = _fetch_raw_profile_data(user_id, resume_id)
    data["profile"] = assemble_user_profile(user_id, resume_id)
    return data


def find_relevant_jobs(
    query_text: str,
    site: str | None = None,
    top_k: int = 10,
    use_semantic: bool = True,
) -> list[JobDescription]:
    """
    Hybrid search over scraped_jobs.
    If use_semantic is True, also generates an embedding for the query
    and combines with full-text keyword matching.
    """
    embedding = None
    if use_semantic:
        try:
            embedding = generate_embedding(query_text)
        except Exception as e:
            logger.warning("Semantic search unavailable, falling back to keyword: %s", e)

    results = search_jobs_hybrid(
        query_text=query_text,
        embedding_vector=embedding,
        site=site,
        top_k=top_k,
    )

    return [
        JobDescription(
            title=job.title,
            company=job.company,
            location=job.location,
            description=job.description,
            job_type=job.job_type,
            compensation=job.compensation,
            site=job.site,
            url=job.job_url,
        )
        for job, score in results
    ]
