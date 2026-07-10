"""
Daily relationship nurturing reminder engine (#10).

STUB — architecture in place, not enabled.

When enabled, this module will:
  - Morning: generate a WhatsApp digest of today's milestones + stale contacts
  - Evening: prompt you to log today's interactions
  - Generate LLM-powered conversation starters for each outreach suggestion

All functions return None / empty until activated.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from core.database import get_upcoming_milestone_contacts

logger = logging.getLogger(__name__)

# Toggle to enable reminder engine — set to True when ready
_ENABLED = False


def generate_morning_reminder() -> Optional[str]:
    """Generate a personalized morning relationship-nurturing reminder.
    
    STUB: Returns None until _ENABLED is set to True.
    
    When live, this will:
    1. Fetch upcoming milestones (next 3 days)
    2. Fetch stale contacts (no contact in 60+ days)
    3. Generate LLM conversation starters
    4. Return a formatted WhatsApp message
    """
    if not _ENABLED:
        logger.info("Morning reminder: stub — not enabled.")
        return None

    logger.info("Generating morning reminder...")
    return _build_morning_message()


def generate_evening_reminder() -> Optional[str]:
    """Generate an evening prompt to log today's interactions.
    
    STUB: Returns None until _ENABLED is set to True.
    
    When live, this will:
    1. Ask what interactions happened today
    2. Prompt to log value provided / context
    3. Suggest follow-up dates
    """
    if not _ENABLED:
        logger.info("Evening reminder: stub — not enabled.")
        return None

    logger.info("Generating evening reminder...")
    return _build_evening_message()


def check_upcoming_milestones(days: int = 7) -> list[dict]:
    """Check for unacknowledged milestones in the next N days.
    
    STUB: Returns empty list until _ENABLED is set to True.
    """
    if not _ENABLED:
        logger.info("Milestone check: stub — not enabled.")
        return []

    milestones = get_upcoming_milestone_contacts(days=days)
    logger.info("Found %d upcoming milestones in next %d days", len(milestones), days)
    return milestones


def generate_conversation_starter(
    contact_name: str,
    milestone_type: str = "",
    shared_context: str = "",
) -> Optional[str]:
    """Generate an LLM-powered conversation starter for a contact.
    
    STUB: Returns None until _ENABLED is set to True.
    
    Args:
        contact_name: Full name of the contact
        milestone_type: e.g. 'birthday', 'work_anniversary'
        shared_context: e.g. mutual projects, interests
    """
    if not _ENABLED:
        return None

    # Placeholder — will use app.llm.generate_text_direct when live
    return None


def _build_morning_message() -> str:
    """Build the morning reminder message (placeholder)."""
    today = date.today().isoformat()
    return (
        f"🌅 Good morning! Here's your relationship plan for {today}\n\n"
        f"[Reminder engine is in stub mode — enable by setting _ENABLED = True]"
    )


def _build_evening_message() -> str:
    """Build the evening log prompt (placeholder)."""
    return (
        "🌙 Evening check-in\n\n"
        "Did you nurture any relationships today?\n"
        "  • Log calls, messages, or meetings\n"
        "  • Note what value you provided\n"
        "  • Set follow-up dates\n\n"
        "[Reminder engine is in stub mode — enable by setting _ENABLED = True]"
    )
