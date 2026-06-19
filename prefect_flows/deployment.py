"""
Prefect 3 deployment registration + serve.

Serves five independent deployments so you can run any stage
in isolation (e.g. just match, just generate) or the full pipeline.

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
    pull_and_process_jobs,
)

_DEFAULTS = {
    "user_id": "ff0465b9-6512-4f47-8b5e-6f14a343a25d",
    "match_model": "openai/gpt-oss-120b:free",
    "generate_model": "models/gemini-3.1-flash-lite",
    "match_provider": "openrouter",
    "generate_provider": "gemini",
    "match_limit": 25, #02-matcher limit
    "job_limit": 10, #03-generator limit
    "scrape_site_names": None,  # None = all sites
    "scrape_max_pages": {"vacancybox": 1, "iharare": 2, "vacancymail": 2},
}


def build():
    serve(
        # 1. Standalone scrape
        scrape_and_store.to_deployment(
            name="01-scraper",
            tags=["production", "scraping"],
            description="Scrape job boards every 2 hours (7am-10pm).",
            parameters={
                "site_names": _DEFAULTS["scrape_site_names"],
                "max_pages": _DEFAULTS["scrape_max_pages"],
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
        # 3. Standalone generator (generate docs → apply)
        generate_matched_flow.to_deployment(
            name="03-generator",
            tags=["production", "generation"],
            description="Generate docs for matched jobs.",
            parameters={
                "user_id": _DEFAULTS["user_id"],
                "generate_model": _DEFAULTS["generate_model"],
                "generate_provider": _DEFAULTS["generate_provider"],
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
        # 5. Match → generate → apply (all-in-one)
        pull_and_process_jobs.to_deployment(
            name="job-pipeline",
            schedules=[CronSchedule(cron="0 7-21/2 * * *", timezone="Africa/Harare")],
            tags=["production", "job-application"],
            description="Match unscored jobs → generate docs → apply.",
            parameters=_DEFAULTS,
            version="4",
        ),
    )


if __name__ == "__main__":
    build()
