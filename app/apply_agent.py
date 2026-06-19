"""
Apply Instructions Agent
Parses apply_instructions with an LLM and routes to the appropriate action.
"""

import json
import logging
from app.llm import generate_text

logger = logging.getLogger(__name__)


def parse_apply_instructions(
    apply_instructions: str,
    job_title: str = "",
    company: str = "",
    job_url: str = "",
    model: str | None = None,
    provider: str | None = None,
) -> dict:
    """Parse apply_instructions with the LLM and return structured action."""
    result = generate_text(
        "apply_agent_parser_v1",
        model=model,
        provider=provider,
        apply_instructions=apply_instructions or "",
        job_title=job_title or "Unknown",
        company=company or "Unknown",
        job_url=job_url or "",
    )
    content = result.get("content", "").strip()
    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        parsed = json.loads(content)
        return parsed
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning("Failed to parse LLM output as JSON: %s — raw: %s", e, content[:200])
        return {
            "action": "unknown",
            "recipient": None,
            "subject": None,
            "body": None,
            "required_docs": ["resume"],
            "url": None,
            "notification_text": f"Could not parse apply instructions. Job: {job_title} at {company}. Review manually.",
        }
