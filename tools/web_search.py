"""Brave Search API via httpx. Never raises — returns [] on error."""

import os

import httpx

from logs import log_error


async def search(query: str, num_results: int = 5) -> list[dict]:
    """Search the web via Brave Search API. Returns [{title, url, snippet}]."""
    api_key = os.environ.get("SEARCH_API_KEY", "")
    if not api_key:
        log_error({
            "module": "tools.web_search",
            "error_type": "ConfigError",
            "message": "SEARCH_API_KEY not set in environment",
        })
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key,
                },
                params={"q": query, "count": num_results},
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("web", {}).get("results", [])[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            })
        return results

    except Exception as e:
        log_error({
            "module": "tools.web_search",
            "error_type": type(e).__name__,
            "message": str(e),
        })
        return []
