"""Pydantic schemas for typed data exchange."""

from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Complete user profile assembled from the DB for prompt injection."""
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    linkedin_url: str | None = None
    location: str | None = None
    professional_summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    work_experience: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    certifications: list[dict] = Field(default_factory=list)
    documents: dict[str, str] = Field(default_factory=dict)  # doc_type → label, e.g. {"id_doc": "National ID"}


class JobDescription(BaseModel):
    """Normalised job posting for prompt injection."""
    title: str | None = None
    company: str | None = None
    location: str | None = None
    description: str | None = None
    job_type: str | None = None
    compensation: str | None = None
    site: str | None = None
    url: str | None = None


class GeneratedDocument(BaseModel):
    """Output from an LLM generation step."""
    job_id: int | None = None
    prompt_name: str
    document_type: str  # 'resume', 'cover_letter', 'skills_analysis'
    content: str
    model: str
    tokens_used: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
