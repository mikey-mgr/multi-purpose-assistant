"""
Prefect 3 deployment registration + serve.

Serves four independent deployments.
When ``01-scraper`` runs via schedule, it auto-chains 02→03→04.
Manual runs stop at scrape.

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

_DEFAULTS = {
    "user_id": "ff0465b9-6512-4f47-8b5e-6f14a343a25d",
    "match_model": "openai/gpt-oss-120b:free",
    "generate_model": "models/gemini-3.1-flash-lite",
    "generate_fallback_model": "openai/gpt-oss-120b:free",
    "match_provider": "openrouter",
    "generate_provider": "gemini",
    "generate_fallback_provider": "openrouter",
    "match_limit": 25,  # 02-matcher limit
    "job_limit": 15,    # 03-generator limit
    "scrape_site_names": None,  # None = all sites
    "scrape_max_pages": {"vacancybox": 1, "iharare": 2, "vacancymail": 2},
}


def build():
    serve(
        # 1. Standalone scrape — auto-chains 02→03→04 when scheduled
        scrape_and_store.to_deployment(
            name="01-scraper",
            schedules=[CronSchedule(cron="0 7-21/2 * * *", timezone="Africa/Harare")],
            tags=["production", "scraping"],
            description="Scrape job boards every 2 hours (7am-10pm). Auto-chains 02→03→04 when scheduled.",
            parameters={
                "site_names": _DEFAULTS["scrape_site_names"],
                "max_pages": _DEFAULTS["scrape_max_pages"],
                "user_id": _DEFAULTS["user_id"],
                "match_model": _DEFAULTS["match_model"],
                "match_provider": _DEFAULTS["match_provider"],
                "generate_model": _DEFAULTS["generate_model"],
                "generate_provider": _DEFAULTS["generate_provider"],
                "generate_fallback_model": _DEFAULTS["generate_fallback_model"],
                "generate_fallback_provider": _DEFAULTS["generate_fallback_provider"],
                "match_limit": _DEFAULTS["match_limit"],
                "job_limit": _DEFAULTS["job_limit"],
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
                "limit": _DEFAULTS["match_limit"],
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
            },
        ),
    )


if __name__ == "__main__":
    build()
