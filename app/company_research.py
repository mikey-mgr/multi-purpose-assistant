"""
Company research via SerpAPI (Google Search).

MVP: company-only research for interview prep.
Gracefully skips if company name or SERPAPI key missing.
"""

import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)

_SERPAPI_URL = "https://serpapi.com/search.json"
_TIMEOUT = 20
_MAX_RESULTS = 5


def _tavily_search(company: str) -> str | None:
    """Fallback search via Tavily — returns formatted string or None on failure."""
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        logger.info("TAVILY_API_KEY not configured — skipping Tavily fallback for '%s'.", company)
        return None
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        # Tavily search is more semantic — keep query concise
        resp = client.search(
            query=f"{company} company overview what does it do",
            max_results=_MAX_RESULTS,
            search_depth="basic",
            include_answer=False,
        )
        results = resp.get("results") or []
        if not results:
            return None
        lines: list[str] = [f"Tavily research for '{company}':"]
        for i, r in enumerate(results[:_MAX_RESULTS], 1):
            title = (r.get("title") or "").strip()
            snippet = (r.get("content") or r.get("snippet") or "").strip()
            link = (r.get("url") or "").strip()
            lines.append(f"{i}. {title}")
            if snippet:
                # Truncate to first 300 chars for LLM
                lines.append(f"   {snippet[:400]}")
            if link:
                lines.append(f"   Source: {link}")
        answer = resp.get("answer")
        if answer:
            lines.append(f"\nSummary: {answer[:500]}")
        logger.info("Tavily fallback for '%s': %d results.", company, len(results))
        return "\n".join(lines)
    except Exception as e:
        logger.warning("Tavily search failed for '%s': %s", company, e)
        return None


def _sanitize_company(company: str) -> str:
    """Take primary company name before slash/dash to avoid noisy queries."""
    # "Ixar Mobile / Ixar Academy Vocational Schools" -> "Ixar Mobile"
    for sep in [" / ", " /", "/ ", " - ", " | ", " — "]:
        if sep in company:
            company = company.split(sep)[0]
            break
    return company.strip()[:60]


def research_company(company_name: str | None) -> str:
    """
    Search SerpAPI for company overview.

    Returns a formatted string for LLM consumption.
    Never raises — returns fallback string on any failure.
    """
    if not company_name or not company_name.strip():
        return "No company name available — skip company research."

    api_key = settings.SERPAPI_API_KEY
    if not api_key:
        logger.warning("SERPAPI_API_KEY not configured — trying Tavily fallback for '%s'.", company_name)
        tavily_result = _tavily_search(_sanitize_company(company_name.strip()))
        if tavily_result:
            return tavily_result
        return f"No company research available for '{company_name}' (no search keys configured)."

    raw_company = company_name.strip()
    company = _sanitize_company(raw_company)
    query = f"{company} company overview what does it do"
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": _MAX_RESULTS,
    }

    data = None
    last_exc = None
    for attempt in range(2):
        try:
            resp = requests.get(_SERPAPI_URL, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            last_exc = e
            logger.warning("SerpAPI attempt %d failed for '%s' (query='%s'): %s", attempt + 1, raw_company, query, e)
            if attempt == 0:
                # Retry with even shorter query
                query = f"{company} overview"
                params["q"] = query
                continue
    if data is None:
        # SerpAPI failed — try Tavily fallback before giving up
        tavily_result = _tavily_search(company)
        if tavily_result:
            return tavily_result
        return f"Company research for '{raw_company}' unavailable (search failed: {last_exc}). Use job description only."

    organic = data.get("organic_results") or []
    if not organic:
        tavily_result = _tavily_search(company)
        if tavily_result:
            return tavily_result
        return f"No search results found for '{company_name}'."

    lines: list[str] = [f"Company research for '{company_name}':"]
    for i, r in enumerate(organic[:_MAX_RESULTS], 1):
        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or r.get("snippet_highlighted_words") or "").strip()
        if isinstance(snippet, list):
            snippet = " ".join(snippet)
        link = (r.get("link") or "").strip()
        lines.append(f"{i}. {title}")
        if snippet:
            lines.append(f"   {snippet}")
        if link:
            lines.append(f"   Source: {link}")

    # Include knowledge graph if present (often has concise company description)
    kg = data.get("knowledge_graph") or {}
    if kg.get("description"):
        lines.append(f"\nKnowledge Graph: {kg['description']}")

    result = "\n".join(lines)
    logger.info("Company research for '%s': %d results.", company_name, min(len(organic), _MAX_RESULTS))
    return result
