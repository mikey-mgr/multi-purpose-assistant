"""
LLM interaction layer.
Builds prompts from templates, calls the model, returns structured output.
"""

import logging
from typing import Any

from core.database import build_prompt
from app.config import settings

logger = logging.getLogger(__name__)


def generate_text(
    prompt_name: str,
    **variables: Any,
) -> dict[str, Any]:
    """
    Load prompt template, substitute variables, call LLM.
    Returns dict with 'content', 'model', 'tokens_used'.
    """
    system, user_template, prompt_meta = build_prompt(
        prompt_name,
        **variables,
    )

    if settings.OPENAI_API_KEY:
        return _call_openai(system, user_template, prompt_meta)
    else:
        logger.warning("No OPENAI_API_KEY set — returning mock output.")
        return {
            "content": f"[MOCK] Generated {prompt_name} output",
            "model": "mock",
            "tokens_used": 0,
        }


def _call_openai(
    system: str,
    user_message: str,
    prompt_meta: Any,
) -> dict[str, Any]:
    """Call OpenAI Chat Completions API."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    messages = [{"role": "system", "content": system}]
    if user_message:
        messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=prompt_meta.model or settings.OPENAI_MODEL,
        messages=messages,
        temperature=float(prompt_meta.temperature or 0.7),
        max_tokens=prompt_meta.max_tokens or 2048,
    )

    return {
        "content": response.choices[0].message.content,
        "model": response.model,
        "tokens_used": response.usage.total_tokens if response.usage else 0,
    }


def generate_embedding(text: str) -> list[float]:
    """Generate a vector embedding for the given text."""
    if not settings.OPENAI_API_KEY:
        logger.warning("No OPENAI_API_KEY — returning zero vector.")
        return [0.0] * settings.EMBEDDING_DIM

    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding
