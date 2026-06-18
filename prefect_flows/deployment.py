"""
Prefect 3 deployment registration + serve.

Usage:
    python prefect_flows/deployment.py

This registers a cron-scheduled deployment AND acts as the worker.
Keep it running in a terminal alongside `prefect server start`.
"""

from prefect.client.schemas.schedules import CronSchedule

from prefect_flows.job_pipeline import pull_and_process_jobs


def build():
    pull_and_process_jobs.serve(
        name="job-pipeline",
        schedules=[CronSchedule(cron="0 */6 * * *", timezone="Africa/Harare")],
        tags=["production", "job-application"],
        description="Every 6 hours: fetch unprocessed jobs, generate ATS resume & cover letter.",
        parameters={"user_id": "ff0465b9-6512-4f47-8b5e-6f14a343a25d"},
        version="1",
    )


if __name__ == "__main__":
    build()
