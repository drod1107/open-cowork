"""Web tools: URL fetching and DuckDuckGo search.

Both actions gate through permissions. `search_web` defaults to allow; only
`fetch_url` routinely prompts.
"""
from __future__ import annotations

import html
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from ..permissions import PermissionGate

_USER_AGENT = "OpenCowork/0.1 (+https://github.com/drod1107/Unit_Testing_Repo)"


@dataclass
class FetchResult:
    url: str
    status: int
    content: str
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "content": self.content,
            "allowed": self.allowed,
            "reason": self.reason,
        }


@dataclass
class SearchResult:
    query: str
    results: list[dict[str, str]]
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": self.results,
            "allowed": self.allowed,
            "reason": self.reason,
        }


async def fetch_url(
    url: str,
    *,
    gate: PermissionGate,
    max_bytes: int = 500_000,
    client: httpx.AsyncClient | None = None,
) -> FetchResult:
    permission = await gate.check("web", "fetch", description=f"Fetch {url}")
    if not permission.allowed:
        return FetchResult(url, 0, permission.reason, False, permission.reason)

    own_client = client is None
    c = client or httpx.AsyncClient(
        timeout=15.0, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
    )
    try:
        resp = await c.get(url)
        body = resp.text[:max_bytes]
        return FetchResult(url, resp.status_code, body, True, permission.reason)
    finally:
        if own_client:
            await c.aclose()


_DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.S,
)


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


async def search_web(
    query: str,
    *,
    gate: PermissionGate,
    max_results: int = 8,
    client: httpx.AsyncClient | None = None,
) -> SearchResult:
    permission = await gate.check("web", "search", description=f"Search: {query}")
    if not permission.allowed:
        return SearchResult(query, [], False, permission.reason)

    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    own_client = client is None
    c = client or httpx.AsyncClient(
        timeout=15.0, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
    )
    try:
        resp = await c.get(url)
        matches = _DDG_RESULT_RE.findall(resp.text or "")
        results = [
            {
                "url": _strip_tags(m[0]),
                "title": _strip_tags(m[1]),
                "snippet": _strip_tags(m[2]),
            }
            for m in matches[:max_results]
        ]
        return SearchResult(query, results, True, permission.reason)
    finally:
        if own_client:
            await c.aclose()
