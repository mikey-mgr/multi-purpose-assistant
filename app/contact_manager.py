"""
Contact management and job referral bridge (#7).

Core features:
  - Cross-reference job matches against contacts at the same company
  - Generate LLM-powered referral outreach suggestions
  - Send WhatsApp notifications for referral opportunities
  - Contact CRUD operations (for future import workflows)

The key insight: when a job match appears and you know someone there,
the system alerts you and suggests a natural outreach message.
"""

import json
import logging
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func

from core.database import (
    get_session,
    Contact,
    ContactProfile,
    ContactGroup,
    ContactGroupMembership,
    ContactInteraction,
    ContactMilestone,
    JobMatch,
    JobReferralOpportunity,
    ScrapedJob,
    find_referral_opportunities_for_job,
    find_all_referral_opportunities,
    save_referral_opportunity,
)
from app.llm import generate_text_direct
from app.whatsapp_notifier import send_whatsapp

logger = logging.getLogger(__name__)

_REFERRAL_PROMPT = """You are a career networking coach. Given a job match and a contact who works at that company, suggest a natural, low-pressure message the user can send to ask about the role.

Rules:
1. Keep it casual and authentic — this is a real relationship, not a cold email
2. Mention something specific about the contact's work or shared history
3. Don't explicitly ask for a referral — ask for "thoughts" or "advice" about the role/team
4. Max 3 short sentences
5. Output ONLY the message text, no preamble"""


def check_new_match_for_referrals(job_id: int, user_id: str) -> list[dict]:
    """Check a single job match for referral opportunities.
    
    Core #7 function. Called after a match is created.
    Returns referral opportunities found and sends WhatsApp notification.
    """
    opportunities = find_referral_opportunities_for_job(job_id)
    if not opportunities:
        logger.info("No referral contacts found for job #%d", job_id)
        return []

    session = get_session()
    try:
        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        match = session.query(JobMatch).filter(
            JobMatch.job_id == job_id,
            JobMatch.user_id == uid,
        ).first()
        if not match:
            logger.warning("No job match found for job #%s / user %s", job_id, user_id)
            return []

        results = []
        for opp in opportunities:
            contact = opp["contact"]
            job = opp["job"]

            referral = save_referral_opportunity(str(match.id), contact["id"])
            message = _build_referral_message(contact, job)

            send_whatsapp(
                text=(
                    f"🔔 Referral Opportunity!\n\n"
                    f"Job: {job['title']} at {job['company']}\n"
                    f"Contact: {contact['first_name']} {contact['last_name']}"
                    f"{' (' + contact['job_title'] + ')' if contact.get('job_title') else ''}\n\n"
                    f"Suggested outreach:\n{message}"
                ),
            )

            results.append({
                "contact_id": contact["id"],
                "contact_name": f"{contact['first_name']} {contact['last_name']}",
                "message": message,
                "referral_id": str(referral.id),
            })

        logger.info(
            "Found %d referral opportunities for job #%d '%s'",
            len(results), job_id, job.get("title", ""),
        )
        return results
    finally:
        session.close()


def check_all_matches_for_referrals(user_id: str) -> list[dict]:
    """Check all active matches for referral opportunities.
    
    Used by the check-referrals Prefect flow.
    Returns all referral opportunities found (new and existing).
    """
    opportunities = find_all_referral_opportunities(user_id)
    if not opportunities:
        logger.info("No referral opportunities found for user %s", user_id)
        return []

    results = []
    for opp in opportunities:
        # Save if not already recorded
        try:
            save_referral_opportunity(opp["job_match_id"], opp["contact"]["id"])
        except Exception:
            pass  # already exists

        message = _build_referral_message(
            opp["contact"],
            {"title": opp["job_title"], "company": opp["company"]},
        )

        send_whatsapp(
            text=(
                f"🔔 Referral Opportunity!\n\n"
                f"Job: {opp['job_title']} at {opp['company']}"
                f"{' (Match score: ' + str(opp.get('score', '')) + ')' if opp.get('score') else ''}\n"
                f"Contact: {opp['contact']['first_name']} {opp['contact']['last_name']}"
                f"{' (' + opp['contact'].get('job_title', '') + ')' if opp['contact'].get('job_title') else ''}\n\n"
                f"Suggested outreach:\n{message}"
            ),
        )

        results.append(opp)

    logger.info("Processed %d referral opportunities", len(results))
    return results


def generate_referral_message(contact: dict, job: dict) -> str:
    """Use LLM to generate a natural referral outreach message."""
    system = _REFERRAL_PROMPT
    user = (
        f"Contact: {contact.get('first_name', '')} {contact.get('last_name', '')}\n"
        f"Contact's role: {contact.get('job_title', 'Unknown')}\n"
        f"Job title: {job.get('title', 'Unknown')}\n"
        f"Company: {job.get('company', 'Unknown')}\n"
    )
    try:
        result = generate_text_direct(system, user)
        return result.get("content", "").strip()
    except Exception as e:
        logger.warning("LLM referral message generation failed: %s", e)
        return _fallback_message(contact, job)


def _build_referral_message(contact: dict, job: dict) -> str:
    """Build a referral message with LLM, fallback to template."""
    msg = generate_referral_message(contact, job)
    if msg:
        return msg
    return _fallback_message(contact, job)


def _fallback_message(contact: dict, job: dict) -> str:
    """Template fallback if LLM is unavailable."""
    first = contact.get("first_name", "")
    contact_role = contact.get("job_title", "")
    job_title = job.get("title", "this role")
    company = job.get("company", "")

    lines = [f"Hey {first},"]
    if contact_role:
        lines.append(f"Hope you're doing well over at {company}! I see you're working as a {contact_role} there.")
    else:
        lines.append(f"Hope you're doing well at {company}!")
    lines.append(f"I noticed they're hiring for a {job_title} position and wanted to ask if you have any thoughts on the team or the role.")
    lines.append("Would love to catch up either way! 🙌")
    return "\n".join(lines)


# ── Contact CRUD (for #9 data population) ─────────────────────────────

def create_contact(
    first_name: str,
    last_name: str,
    email: str | None = None,
    phone: str | None = None,
    current_company: str | None = None,
    job_title: str | None = None,
    linkedin_url: str | None = None,
    location_city: str | None = None,
    location_country: str | None = None,
    source: str = "manual",
    notes: str | None = None,
) -> Contact:
    """Create a new contact record."""
    session = get_session()
    try:
        contact = Contact(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            current_company=current_company,
            job_title=job_title,
            linkedin_url=linkedin_url,
            location_city=location_city,
            location_country=location_country,
            source=source,
            notes=notes,
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)
        logger.info("Created contact: %s %s (id=%s)", first_name, last_name, contact.id)
        return contact
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_contact_company(contact_id: str, company: str, job_title: str | None = None) -> bool:
    """Update a contact's current company (key field for #7 matching)."""
    session = get_session()
    try:
        cid = UUID(contact_id) if isinstance(contact_id, str) else contact_id
        contact = session.query(Contact).filter(Contact.id == cid).first()
        if not contact:
            logger.warning("Contact %s not found", contact_id)
            return False
        contact.current_company = company
        if job_title:
            contact.job_title = job_title
        contact.updated_at = datetime.now(timezone.utc)
        session.commit()
        logger.info(
            "Updated contact %s %s: company='%s', title='%s'",
            contact.first_name, contact.last_name, company, job_title,
        )
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_contact_by_email(email: str) -> Contact | None:
    """Find a contact by email."""
    session = get_session()
    try:
        return session.query(Contact).filter(Contact.email == email).first()
    finally:
        session.close()


def log_interaction(
    contact_id: str,
    interaction_type: str,
    direction: str,
    notes: str | None = None,
    context: str | None = None,
    value_provided: str | None = None,
    follow_up_date: date | None = None,
) -> ContactInteraction:
    """Log an interaction with a contact."""
    session = get_session()
    try:
        cid = UUID(contact_id) if isinstance(contact_id, str) else contact_id
        interaction = ContactInteraction(
            contact_id=cid,
            interaction_type=interaction_type,
            direction=direction,
            notes=notes,
            context=context,
            value_provided=value_provided,
            follow_up_date=follow_up_date,
        )
        session.add(interaction)
        session.commit()
        session.refresh(interaction)
        return interaction
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def add_contact_to_group(contact_id: str, group_name: str) -> bool:
    """Add a contact to a group, creating the group if needed."""
    session = get_session()
    try:
        cid = UUID(contact_id) if isinstance(contact_id, str) else contact_id

        group = session.query(ContactGroup).filter(
            ContactGroup.group_name == group_name
        ).first()
        if not group:
            group = ContactGroup(group_name=group_name)
            session.add(group)
            session.flush()

        existing = session.query(ContactGroupMembership).filter(
            ContactGroupMembership.contact_id == cid,
            ContactGroupMembership.group_id == group.id,
        ).first()
        if existing:
            return True

        membership = ContactGroupMembership(
            contact_id=cid,
            group_id=group.id,
        )
        session.add(membership)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def import_contacts_bulk(contacts_list: list[dict]) -> tuple[int, int]:
    """Import multiple contacts at once.
    
    Returns (created_count, updated_count).
    Deduplicates by email if available.
    """
    created = 0
    updated = 0
    session = get_session()
    try:
        for data in contacts_list:
            email = data.get("email")
            if email:
                existing = session.query(Contact).filter(
                    Contact.email == email
                ).first()
                if existing:
                    for key, val in data.items():
                        if val is not None and key not in ("email",):
                            setattr(existing, key, val)
                    existing.last_imported_at = datetime.now(timezone.utc)
                    updated += 1
                    continue

            contact = Contact(
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                email=email,
                phone=data.get("phone"),
                current_company=data.get("current_company"),
                job_title=data.get("job_title"),
                linkedin_url=data.get("linkedin_url"),
                location_city=data.get("location_city"),
                location_country=data.get("location_country"),
                source=data.get("source", "manual"),
                source_id=data.get("source_id"),
                notes=data.get("notes"),
                last_imported_at=datetime.now(timezone.utc),
            )
            session.add(contact)
            created += 1

        session.commit()
        logger.info("Bulk import: %d created, %d updated", created, updated)
        return created, updated
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
