"""
LLM interaction layer.
Routes through OpenRouter (OpenAI-compatible) or Gemini.
"""

import logging
from typing import Any

from core.database import build_prompt
from app.config import settings

logger = logging.getLogger(__name__)

_PROVIDER_CONFIG = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_attr": "OPENROUTER_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_attr": "GEMINI_API_KEY",
    },
}


def _get_client(provider: str | None = None):
    """
    Return an OpenAI-compatible client for the given provider.

    Provider values: ``"openrouter"``, ``"gemini"``.
    Falls back to ``settings.LLM_PROVIDER`` if not specified.
    Returns ``None`` if the provider's API key is not set.
    """
    from openai import OpenAI

    provider = provider or settings.LLM_PROVIDER
    cfg = _PROVIDER_CONFIG.get(provider)
    if not cfg:
        logger.warning("Unknown provider '%s', defaulting to openrouter", provider)
        cfg = _PROVIDER_CONFIG["openrouter"]

    api_key = getattr(settings, cfg["key_attr"], None)
    if not api_key:
        logger.warning(
            "Provider '%s' has no API key configured (settings.%s is empty)",
            provider,
            cfg["key_attr"],
        )
        return None

    return OpenAI(api_key=api_key, base_url=cfg["base_url"])


def generate_text(
    prompt_name: str,
    model: str | None = None,
    provider: str | None = None,
    **variables: Any,
) -> dict[str, Any]:
    """
    Load prompt template, substitute variables, call LLM.

    Parameters
    ----------
    prompt_name : str
        Name of the prompt template in the database.
    model : str | None
        Overrides the prompt's default model and ``settings.LLM_MODEL``.
    provider : str | None
        ``"openrouter"`` or ``"gemini"``.  Falls back to ``settings.LLM_PROVIDER``.

    Returns
    -------
    dict with ``content``, ``model``, ``tokens_used``.
    """
    system, user_template, prompt_meta = build_prompt(
        prompt_name,
        **variables,
    )

    resolved_provider = provider or settings.LLM_PROVIDER
    client = _get_client(provider)
    if not client:
        logger.warning("No LLM API key set for provider '%s' — returning mock.", resolved_provider)
        return {
            "content": f"[MOCK] Generated {prompt_name} output",
            "model": "mock",
            "tokens_used": 0,
        }

    resolved_model = model or settings.LLM_MODEL or prompt_meta.model
    logger.info(
        "Calling %s via %s with prompt '%s' (model=%s)",
        prompt_name, resolved_provider, prompt_name, resolved_model,
    )

    # Gemini's OpenAI-compatible endpoint does NOT support the "system" role.
    # Merge system instructions into the user message as a prefix.
    if resolved_provider == "gemini":
        content = system
        if user_template:
            content += "\n\n" + user_template
        messages = [{"role": "user", "content": content}]
    else:
        messages = [{"role": "system", "content": system}]
        if user_template:
            messages.append({"role": "user", "content": user_template})

    response = client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        temperature=float(prompt_meta.temperature or 0.7),
        max_tokens=prompt_meta.max_tokens or 2048,
    )

    result = response.choices[0].message.content
    logger.info(
        "LLM response for '%s': %d chars, %d tokens",
        prompt_name, len(result or ""),
        response.usage.total_tokens if response.usage else 0,
    )
    return {
        "content": result,
        "model": response.model,
        "tokens_used": response.usage.total_tokens if response.usage else 0,
    }


def generate_text_direct(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """
    Call the LLM with raw prompts (no database template lookup).

    Parameters
    ----------
    system_prompt : str
        System-level instructions.
    user_prompt : str
        User message content.
    model : str | None
        Overrides ``settings.LLM_MODEL``.
    provider : str | None
        ``"openrouter"`` or ``"gemini"``.  Falls back to ``settings.LLM_PROVIDER``.

    Returns
    -------
    dict with ``content``, ``model``, ``tokens_used``.
    """
    resolved_provider = provider or settings.LLM_PROVIDER
    client = _get_client(provider)
    if not client:
        logger.warning("No LLM API key set for provider '%s' — returning mock.", resolved_provider)
        return {"content": "[MOCK] generate_text_direct output", "model": "mock", "tokens_used": 0}

    resolved_model = model or settings.LLM_MODEL
    logger.info("Calling direct prompt via %s (model=%s)", resolved_provider, resolved_model)

    if resolved_provider == "gemini":
        content = system_prompt
        if user_prompt:
            content += "\n\n" + user_prompt
        messages = [{"role": "user", "content": content}]
    else:
        messages = [{"role": "system", "content": system_prompt}]
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})

    response = client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
    )

    result = response.choices[0].message.content
    logger.info("Direct LLM response: %d chars, %d tokens", len(result or ""),
                 response.usage.total_tokens if response.usage else 0)
    return {
        "content": result,
        "model": response.model,
        "tokens_used": response.usage.total_tokens if response.usage else 0,
    }


def generate_embedding(text: str, provider: str | None = None) -> list[float]:
    """Generate a vector embedding via the given provider."""
    client = _get_client(provider)
    if not client:
        logger.warning("No LLM API key — returning zero vector.")
        return [0.0] * settings.EMBEDDING_DIM

    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def generate_text_multimodal(
    system_prompt: str,
    user_text: str,
    image_base64: str,
    mimetype: str = "image/jpeg",
    model: str | None = None,
    provider: str | None = None,
    max_tokens: int = 8192,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """
    Call a multimodal-capable LLM (Gemini) with text + image.

    Constructs an OpenAI-compatible multimodal message array and sends
    via the Gemini endpoint. Only works with Gemini (not OpenRouter).

    Parameters
    ----------
    system_prompt : str
        System-level instructions (merged into user message for Gemini).
    user_text : str
        Text prompt accompanying the image.
    image_base64 : str
        Base64-encoded image data (without ``data:`` prefix).
    mimetype : str
        Image MIME type (e.g. ``image/jpeg``, ``image/png``).
    model : str | None
        Overrides ``settings.LLM_MODEL`` (must be a Gemini vision model).
    provider : str | None
        Must be ``"gemini"`` or ``None`` (defaults to settings.LLM_PROVIDER).
    max_tokens : int
        Max output tokens (default 8192).
    temperature : float
        LLM temperature (default 0.7).

    Returns
    -------
    dict with ``content``, ``model``, ``tokens_used``.
    """
    resolved_provider = provider or settings.LLM_PROVIDER
    client = _get_client(resolved_provider)
    if not client:
        logger.warning("No API key for '%s' — returning mock.", resolved_provider)
        return {"content": "[MOCK] multimodal output", "model": "mock", "tokens_used": 0}

    resolved_model = model or settings.LLM_MODEL
    logger.info("Calling multimodal via %s (model=%s, image=%s, text=%d chars)",
                resolved_provider, resolved_model, mimetype, len(user_text))

    content = system_prompt
    if user_text:
        content += "\n\n" + user_text

    # Build multimodal content array: text + image
    image_url = f"data:{mimetype};base64,{image_base64}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": content},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ]

    response = client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    result = response.choices[0].message.content
    logger.info("Multimodal response: %d chars, %d tokens",
                len(result or ""),
                response.usage.total_tokens if response.usage else 0)
    return {
        "content": result,
        "model": response.model,
        "tokens_used": response.usage.total_tokens if response.usage else 0,
    }
