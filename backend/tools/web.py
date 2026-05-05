"""Web tool.

fetch_url: HTTP GET a URL, return text content with content-type filtering.
search_web: Search DuckDuckGo HTML, return top results.

Both flow through the permission gate (category "web") before execution.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Callable
from urllib.parse import parse_qs, quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from ..permissions import PermissionGate
from .spillover import maybe_spillover

logger = logging.getLogger(__name__)

_DDGO_HTML_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = "OpenCowork/1.0"
_ALLOWED_CONTENT_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/xhtml+xml",
)
_MAX_RESULTS = 5


def _is_text_content_type(ct: str) -> bool:
    ct_lower = ct.lower().split(";")[0].strip()
    return any(ct_lower.startswith(prefix) for prefix in _ALLOWED_CONTENT_PREFIXES)


def _extract_real_url(href: str) -> str:
    parsed = urlparse(href)
    if parsed.netloc in ("duckduckgo.com", "html.duckduckgo.com") and "//duckduckgo.com" in href:
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg", [])
        if uddg:
            return uddg[0]
    return href


def _parse_search_results(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for a_tag in soup.find_all("a", class_=re.compile(r"result")):
        href = a_tag.get("href", "")
        title = a_tag.get_text(strip=True)
        if not title or not href:
            continue
        url = _extract_real_url(href)
        snippet = ""
        parent = a_tag.parent
        if parent:
            snippet_tag = parent.find("a", class_=re.compile(r"result__snippet"))
            if snippet_tag:
                snippet = snippet_tag.get_text(strip=True)
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= _MAX_RESULTS:
            break
    return results


async def fetch_url(
    url: str,
    *,
    gate: PermissionGate,
    max_bytes: int = 500_000,
    timeout: float = 30.0,
    on_web_task: Callable[[asyncio.Task], None] | None = None,
) -> dict[str, Any]:
    permission = await gate.check("web", "fetch_url", description=f"Fetch URL: {url}")
    if not permission.allowed:
        if "disabled by toggle" in permission.reason:
            return {"error": permission.reason, "status": "disabled"}
        return {"error": permission.reason, "status": "denied"}

    async def _do_fetch() -> dict[str, Any]:
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
            timeout=httpx.Timeout(timeout),
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        ct = resp.headers.get("content-type", "")
        if not _is_text_content_type(ct):
            return {"error": f"Binary content-type not supported: {ct}", "status": "error"}

        text = resp.text
        if len(text) > max_bytes:
            text = maybe_spillover(text[:max_bytes], prefix="web_fetch")

        return {"content": text, "status": "ok", "url": url, "content_type": ct}

    if on_web_task is not None:
        task = asyncio.create_task(_do_fetch())
        on_web_task(task)
        try:
            return await task
        finally:
            on_web_task(task)
    else:
        return await _do_fetch()


async def search_web(
    query: str,
    *,
    gate: PermissionGate,
    timeout: float = 30.0,
    on_web_task: Callable[[asyncio.Task], None] | None = None,
) -> dict[str, Any]:
    permission = await gate.check("web", "search_web", description=f"Search web: {query}")
    if not permission.allowed:
        if "disabled by toggle" in permission.reason:
            return {"error": permission.reason, "status": "disabled"}
        return {"error": permission.reason, "status": "denied"}

    async def _do_search() -> dict[str, Any]:
        search_url = f"{_DDGO_HTML_URL}?q={quote_plus(query)}"
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
            timeout=httpx.Timeout(timeout),
        ) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()

        html = resp.text
        if "anomaly-modal" in html:
            return {"error": "Search blocked by DuckDuckGo bot detection", "status": "error"}

        results = _parse_search_results(html)
        return {"results": results}

    if on_web_task is not None:
        task = asyncio.create_task(_do_search())
        on_web_task(task)
        try:
            return await task
        finally:
            on_web_task(task)
    else:
        return await _do_search()
