"""
Prefect flows for the Relationship Nurturing System.

Active flows:
  - check-referrals (#7): cross-references new job matches against
    your contact network and notifies you of referral opportunities.

Stub flows (not scheduled, not enabled):
  - daily-reminder (#10): future daily relationship nurturing reminders
"""

import logging

from prefect import flow, task, get_run_logger
from app.config import settings

from app.contact_manager import check_all_matches_for_referrals

logger = logging.getLogger(__name__)


# ── #7: Referral Check (ACTIVE) ───────────────────────────────────────

@task(retries=1, retry_delay_seconds=30)
def check_referrals_task(user_id: str) -> int:
    """Cross-reference all active job matches against contacts.
    
    Returns number of referral opportunities found.
    """
    run_logger = get_run_logger()
    run_logger.info("Checking referral opportunities for user %s ...", user_id)
    results = check_all_matches_for_referrals(user_id)
    run_logger.info("Found %d referral opportunities", len(results))
    return len(results)


@flow(
    name="check-referrals",
    description="Cross-reference job matches with your contact network for referral opportunities (#7).",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
)
def check_referrals_flow(user_id: str | None = None):
    """Check all active job matches for contacts who work at the company.
    
    When a match + contact pair is found:
      1. Records the referral opportunity in job_referral_opportunities
      2. Generates a natural outreach message via LLM
      3. Sends a WhatsApp notification with the suggestion
    """
    run_logger = get_run_logger()
    uid = user_id or "default"
    try:
        count = check_referrals_task(uid)
        run_logger.info("Referral check complete — %d opportunities found.", count)
        if count == 0:
            run_logger.info("No contacts match any current job openings.")
    except Exception as e:
        run_logger.error("Referral check failed: %s", e)
        raise


# ── #10: Daily Reminder (STUB — not scheduled) ────────────────────────

@task
def build_morning_reminder_task() -> str | None:
    """Build the morning relationship reminder. STUB."""
    from app.reminder_engine import generate_morning_reminder
    return generate_morning_reminder()


@task
def build_evening_reminder_task() -> str | None:
    """Build the evening log prompt. STUB."""
    from app.reminder_engine import generate_evening_reminder
    return generate_evening_reminder()


@flow(
    name="daily-reminder",
    description="STUB — Daily relationship nurturing reminder (#10). Not enabled yet.",
    log_prints=True,
)
def daily_reminder_flow():
    """Daily reminder flow for relationship nurturing.
    
    STUB — not enabled. Set _ENABLED = True in app/reminder_engine.py
    and add a Prefect schedule to activate.
    
    When active:
      - Morning: sends WhatsApp with milestones + stale contacts + suggestions
      - Evening: prompts to log interactions
    """
    run_logger = get_run_logger()
    run_logger.info("Daily reminder flow called — this is a STUB, not enabled.")
    run_logger.info("To enable: set _ENABLED = True in app/reminder_engine.py and schedule this flow.")

    morning = build_morning_reminder_task()
    if morning:
        from app.whatsapp_notifier import send_whatsapp
        send_whatsapp(text=morning)

    evening = build_evening_reminder_task()
    if evening:
        from app.whatsapp_notifier import send_whatsapp
        send_whatsapp(text=evening)

    run_logger.info("Reminder flow complete (stub — no messages sent).")
