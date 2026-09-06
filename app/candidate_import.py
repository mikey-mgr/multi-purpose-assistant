"""Validated, transactional import of a canonical candidate profile."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.database import (
    Certification,
    Education,
    Project,
    Resume,
    Skill,
    User,
    UserDocument,
    WorkExperience,
    get_session,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserInput(StrictModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    phone_1: str | None = None
    phone_2: str | None = None
    linkedin_url: str | None = None
    location_city: str | None = None
    location_country: str | None = None


class DatedInput(StrictModel):
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def end_not_before_start(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class ExperienceInput(DatedInput):
    company_name: str = Field(min_length=1)
    job_title: str = Field(min_length=1)
    location: str | None = None
    start_date: date
    bullet_points: list[str] = Field(min_length=1)


class ProjectInput(StrictModel):
    project_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tech_stack: list[str] = Field(default_factory=list)
    project_url: str | None = None
    bullet_points: list[str] = Field(default_factory=list)


class EducationInput(DatedInput):
    institution_name: str = Field(min_length=1)
    degree_type: str = Field(min_length=1)
    field_of_study: str = Field(min_length=1)
    grade_or_class: str | None = None
    document_path: str | None = None


class CertificationInput(StrictModel):
    cert_name: str = Field(min_length=1)
    issuing_organization: str = Field(min_length=1)
    issue_date: date | None = None
    credential_url: str | None = None
    document_path: str | None = None


class SkillInput(StrictModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)


class DocumentInput(StrictModel):
    doc_type: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    label: str | None = None


class ResumeInput(StrictModel):
    version_name: str = Field(min_length=1)
    professional_summary: str = Field(min_length=1)
    additional_information: dict[str, str] = Field(default_factory=dict)
    is_active: bool = True
    work_experience: list[ExperienceInput] = Field(default_factory=list)
    projects: list[ProjectInput] = Field(default_factory=list)
    education: list[EducationInput] = Field(default_factory=list)
    certifications: list[CertificationInput] = Field(default_factory=list)
    skills: list[SkillInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_skills(self):
        normalized = [item.name.casefold() for item in self.skills]
        if len(normalized) != len(set(normalized)):
            raise ValueError("skill names must be unique, ignoring case")
        return self


class CandidateProfileInput(StrictModel):
    schema_version: Literal[1]
    profile_status: Literal["draft", "confirmed"] = "draft"
    source_documents: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
    user: UserInput
    resume: ResumeInput
    documents: list[DocumentInput] = Field(default_factory=list)


def load_candidate_profile(path: str | Path) -> CandidateProfileInput:
    with Path(path).open("r", encoding="utf-8") as profile_file:
        raw = yaml.safe_load(profile_file)
    if not isinstance(raw, dict):
        raise ValueError("candidate profile must be a YAML object")
    return CandidateProfileInput.model_validate(raw)


def profile_summary(profile: CandidateProfileInput) -> dict[str, object]:
    return {
        "status": profile.profile_status,
        "email": profile.user.email,
        "resume_version": profile.resume.version_name,
        "experience_count": len(profile.resume.work_experience),
        "project_count": len(profile.resume.projects),
        "education_count": len(profile.resume.education),
        "certification_count": len(profile.resume.certifications),
        "skill_count": len(profile.resume.skills),
        "document_count": len(profile.documents),
        "review_notes": profile.review_notes,
    }


def import_candidate_profile(profile: CandidateProfileInput) -> tuple[str, str]:
    """Import one immutable resume version and return user/resume IDs."""
    if profile.profile_status != "confirmed":
        raise ValueError("refusing to import a draft profile; resolve review_notes and set profile_status: confirmed")

    session = get_session()
    try:
        with session.begin():
            user = session.query(User).filter(User.email == profile.user.email).one_or_none()
            user_values = profile.user.model_dump()
            if user is None:
                user = User(**user_values)
                session.add(user)
                session.flush()
            else:
                for field_name, value in user_values.items():
                    setattr(user, field_name, value)

            duplicate = session.query(Resume).filter(
                Resume.user_id == user.id,
                Resume.version_name == profile.resume.version_name,
            ).one_or_none()
            if duplicate is not None:
                raise ValueError(
                    f"resume version '{profile.resume.version_name}' already exists; use a new version name"
                )

            if profile.resume.is_active:
                session.query(Resume).filter(Resume.user_id == user.id).update(
                    {Resume.is_active: False}, synchronize_session=False
                )

            resume = Resume(
                user_id=user.id,
                version_name=profile.resume.version_name,
                professional_summary=profile.resume.professional_summary,
                additional_information=profile.resume.additional_information,
                is_active=profile.resume.is_active,
            )
            session.add(resume)
            session.flush()

            for index, item in enumerate(profile.resume.work_experience, start=1):
                session.add(WorkExperience(
                    resume_id=resume.id,
                    company_name=item.company_name,
                    job_title=item.job_title,
                    location=item.location,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    bullet_points=item.bullet_points,
                    display_order=index,
                ))

            for index, item in enumerate(profile.resume.projects, start=1):
                session.add(Project(
                    resume_id=resume.id,
                    project_name=item.project_name,
                    description=item.description,
                    tech_stack=item.tech_stack,
                    project_url=item.project_url,
                    bullet_points=item.bullet_points,
                    display_order=index,
                ))

            for index, item in enumerate(profile.resume.education, start=1):
                session.add(Education(
                    resume_id=resume.id,
                    institution_name=item.institution_name,
                    degree_type=item.degree_type,
                    field_of_study=item.field_of_study,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    grade_or_class=item.grade_or_class,
                    document_path=item.document_path,
                    display_order=index,
                ))

            for item in profile.resume.certifications:
                session.add(Certification(
                    resume_id=resume.id,
                    cert_name=item.cert_name,
                    issuing_organization=item.issuing_organization,
                    issue_date=item.issue_date,
                    credential_url=item.credential_url,
                    document_path=item.document_path,
                ))

            for item in profile.resume.skills:
                session.add(Skill(resume_id=resume.id, skill_name=item.name, skill_type=item.type))

            for item in profile.documents:
                existing = session.query(UserDocument).filter(
                    UserDocument.user_id == user.id,
                    UserDocument.doc_type == item.doc_type,
                ).one_or_none()
                if existing is None:
                    session.add(UserDocument(user_id=user.id, **item.model_dump()))
                else:
                    existing.file_path = item.file_path
                    existing.label = item.label

        return str(user.id), str(resume.id)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
