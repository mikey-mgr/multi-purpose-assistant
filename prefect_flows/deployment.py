"""
Prefect 3 deployment registration + serve.

Serves 7 deployments. Pipeline chaining is opt-in via the ``chain_next``
parameter on each flow.  Deployments do NOT pass ``chain_next=True``
by default, so standalone runs stop at that stage.

To chain the full pipeline:
    prefect deployment run --param chain_next=True 01-scraper

Usage:
    python prefect_flows/deployment.py
"""

from prefect import serve
from prefect.client.schemas.schedules import CronSchedule

from prefect_flows.job_pipeline import (
    scrape_and_store,
    match_jobs_flow,
    generate_matched_flow,
    apply_agent_flow,
)
from prefect_flows.whatsapp_job_flow import process_whatsapp_job, process_whatsapp_text
from prefect_flows.relationship_flows import check_referrals_flow, daily_reminder_flow

_DEFAULTS = {
    "user_id": "ff0465b9-6512-4f47-8b5e-6f14a343a25d",
    "match_model": "models/gemini-3.5-flash-lite",
    "match_fallback_model": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "generate_model": "models/gemini-3.5-flash-lite",
    "generate_fallback_model": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "match_provider": "gemini",
    "match_fallback_provider": "openrouter",
    "generate_provider": "gemini",
    "generate_fallback_provider": "openrouter",
    "match_limit": 15,  # 02-matcher limit
    "job_limit": 5,    # 03-generator limit
    "scrape_site_names": None,  # None = all sites
    "scrape_max_pages": {"vacancybox": 1, "iharare": 2, "vacancymail": 2},
    "chain_next": True,  # auto-chain 01→02→03→04 on scheduled runs
    "max_iterations": 3,  # loop each step to catch up on remaining jobs
}


def build():
    serve(
        # 1. Standalone scrape — auto-chains 02→03→04 when scheduled
        scrape_and_store.to_deployment(
            name="01-scraper",
            schedules=[CronSchedule(cron="0 7-19/3 * * *", timezone="Africa/Harare")],
            tags=["production", "scraping"],
            description="Scrape job boards every hour (7am-10pm). Auto-chains 02→03→04 on schedule. Run with --param chain_next=False to scrape only.",
            parameters={
                "site_names": _DEFAULTS["scrape_site_names"],
                "max_pages": _DEFAULTS["scrape_max_pages"],
                "user_id": _DEFAULTS["user_id"],
                "match_model": _DEFAULTS["match_model"],
                "match_provider": _DEFAULTS["match_provider"],
                "match_fallback_model": _DEFAULTS["match_fallback_model"],
                "match_fallback_provider": _DEFAULTS["match_fallback_provider"],
                "generate_model": _DEFAULTS["generate_model"],
                "generate_provider": _DEFAULTS["generate_provider"],
                "generate_fallback_model": _DEFAULTS["generate_fallback_model"],
                "generate_fallback_provider": _DEFAULTS["generate_fallback_provider"],
                "match_limit": _DEFAULTS["match_limit"],
                "job_limit": _DEFAULTS["job_limit"],
                "chain_next": _DEFAULTS["chain_next"],
                "max_iterations": _DEFAULTS["max_iterations"],
            },
        ),
        # 2. Standalone matcher
        match_jobs_flow.to_deployment(
            name="02-matcher",
            tags=["production", "matching"],
            description="Batch-classify unscored jobs.",
            parameters={
                "user_id": _DEFAULTS["user_id"],
                "match_model": _DEFAULTS["match_model"],
                "match_provider": _DEFAULTS["match_provider"],
                "match_fallback_model": _DEFAULTS["match_fallback_model"],
                "match_fallback_provider": _DEFAULTS["match_fallback_provider"],
                "limit": _DEFAULTS["match_limit"],
                "max_iterations": _DEFAULTS["max_iterations"],
            },
        ),
        # 3. Standalone generator (generate docs only, no apply)
        generate_matched_flow.to_deployment(
            name="03-generator",
            tags=["production", "generation"],
            description="Generate docs for matched jobs.",
            parameters={
                "user_id": _DEFAULTS["user_id"],
                "generate_model": _DEFAULTS["generate_model"],
                "generate_provider": _DEFAULTS["generate_provider"],
                "generate_fallback_model": _DEFAULTS["generate_fallback_model"],
                "generate_fallback_provider": _DEFAULTS["generate_fallback_provider"],
                "limit": _DEFAULTS["job_limit"],
                "max_iterations": _DEFAULTS["max_iterations"],
            },
        ),
        # 4. Standalone apply agent (re-run for failed email sends)
        apply_agent_flow.to_deployment(
            name="04-apply-agent",
            tags=["production", "application"],
            description="Parse apply_instructions for matched jobs and send email / WhatsApp.",
            parameters={
                "user_id": _DEFAULTS["user_id"],
                "generate_model": _DEFAULTS["generate_model"],
                "generate_provider": _DEFAULTS["generate_provider"],
                "limit": _DEFAULTS["job_limit"],
                "max_iterations": _DEFAULTS["max_iterations"],
            },
        ),
        # 5. WhatsApp image job (triggered by webhook, no schedule)
        process_whatsapp_job.to_deployment(
            name="05-whatsapp-image-job",
            tags=["production", "whatsapp"],
            description="Process a job posting image received via WhatsApp webhook.",
            parameters={
                "user_id": _DEFAULTS["user_id"],
                "generate_model": _DEFAULTS["generate_model"],
                "generate_provider": _DEFAULTS["generate_provider"],
                "generate_fallback_model": _DEFAULTS["generate_fallback_model"],
                "generate_fallback_provider": _DEFAULTS["generate_fallback_provider"],
            },
        ),
        # 5b. WhatsApp text job (triggered by webhook, no schedule)
        process_whatsapp_text.to_deployment(
            name="05b-whatsapp-text-job",
            tags=["production", "whatsapp"],
            description="Process WhatsApp text: routes job postings and data queries, then executes.",
            parameters={
                "user_id": _DEFAULTS["user_id"],
                "generate_model": _DEFAULTS["generate_model"],
                "generate_provider": _DEFAULTS["generate_provider"],
                "generate_fallback_model": _DEFAULTS["generate_fallback_model"],
                "generate_fallback_provider": _DEFAULTS["generate_fallback_provider"],
            },
        ),
        # 6. Referral checker — cross-reference matches with contacts
        check_referrals_flow.to_deployment(
            name="06-check-referrals",
            tags=["production", "relationships"],
            description="#7 Cross-reference job matches against your contact network. Sends WhatsApp referral alerts.",
            parameters={
                "user_id": _DEFAULTS["user_id"],
            },
        ),
        # 7. Daily reminder (stub — not enabled)
        daily_reminder_flow.to_deployment(
            name="07-daily-reminder",
            tags=["production", "relationships"],
            description="#10 STUB — Daily relationship nurturing reminders. Set _ENABLED=True in reminder_engine.py and add a schedule.",
            parameters={},
        ),
    )


if __name__ == "__main__":
    build()
