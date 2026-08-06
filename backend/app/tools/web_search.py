"""Frino OS - Web Search Tool (no API key required)"""
from __future__ import annotations
from typing import List
import httpx
import re

from app.tools.registry import BaseTool, ToolCategory, ToolResult


class WebSearchTool(BaseTool):
    def __init__(self):
        super().__init__(
            "web_search",
            "Search the web for current information",
            ToolCategory.BROWSER,
            requires_confirmation=False
        )

    async def execute(self, query: str, **params) -> ToolResult:
        try:
            results = await self._search(query)
            if results:
                return ToolResult(success=True, output=results)
            return ToolResult(success=False, output=None, error="No results found")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    async def _search(self, query: str) -> List[dict]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            # Strategy 1: DuckDuckGo instant answer API (original query)
            results = await self._try_ddg_api(client, query, headers)
            if results:
                return results

            # Strategy 2: DDG API with cleaned query
            clean_q = re.sub(r'\b(20\d{2}|current|latest|now|today|right now)\b', '', query).strip()
            if clean_q != query:
                results = await self._try_ddg_api(client, clean_q, headers)
                if results:
                    return results

            # Strategy 3: Wikipedia API for factual queries
            results = await self._try_wikipedia(client, query)
            if results:
                return results

            # Strategy 4: DuckDuckGo HTML scraping
            results = await self._try_ddg_html(client, query, headers)
            if results:
                return results

            # Strategy 5: DuckDuckGo lite (simpler HTML, less likely to be blocked)
            results = await self._try_ddg_lite(client, query, headers)
            return results

    async def _try_ddg_api(self, client: httpx.AsyncClient, query: str, headers: dict) -> List[dict]:
        try:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                headers=headers
            )
            if resp.status_code == 200:
                return self._parse_api(resp.json())
        except Exception:
            pass
        return []

    async def _try_wikipedia(self, client: httpx.AsyncClient, query: str) -> List[dict]:
        """Use Wikipedia API for factual/knowledge queries."""
        try:
            # Search Wikipedia
            resp = await client.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.replace(" ", "_"),
                headers={"User-Agent": "FrinoOS/1.0"}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("extract"):
                    return [{"title": data.get("title", "Wikipedia"), "snippet": data["extract"]}]

            # Fallback: Wikipedia search API
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": "3",
                    "srprop": "snippet"
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("query", {}).get("search", []):
                    snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                    if snippet:
                        results.append({"title": item["title"], "snippet": snippet})
                if results:
                    return results
        except Exception:
            pass
        return []

    async def _try_ddg_html(self, client: httpx.AsyncClient, query: str, headers: dict) -> List[dict]:
        try:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=headers
            )
            if resp.status_code == 200:
                return self._parse_html(resp.text)
        except Exception:
            pass
        return []

    async def _try_ddg_lite(self, client: httpx.AsyncClient, query: str, headers: dict) -> List[dict]:
        try:
            resp = await client.get(
                "https://lite.duckduckgo.com/lite/",
                params={"q": query},
                headers=headers
            )
            if resp.status_code == 200:
                return self._parse_lite_html(resp.text)
        except Exception:
            pass
        return []

    def _parse_api(self, data: dict) -> List[dict]:
        """Parse DuckDuckGo instant answer API."""
        results = []
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", "Answer"),
                "snippet": data["Abstract"]
            })
        if data.get("Answer"):
            results.append({
                "title": "Direct Answer",
                "snippet": str(data["Answer"])
            })
        if data.get("Definition"):
            results.append({
                "title": "Definition",
                "snippet": data["Definition"]
            })
        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " ") if topic.get("FirstURL") else "Related",
                    "snippet": topic["Text"]
                })
        return results

    def _parse_html(self, html: str) -> List[dict]:
        """Parse DuckDuckGo HTML search results."""
        results = []
        snippet_pattern = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</[at]',
            html, re.DOTALL
        )
        title_pattern = re.findall(
            r'class="result__a"[^>]*>(.*?)</a>',
            html, re.DOTALL
        )
        for i, snippet in enumerate(snippet_pattern[:5]):
            title = title_pattern[i] if i < len(title_pattern) else f"Result {i+1}"
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            if clean_snippet:
                results.append({"title": clean_title, "snippet": clean_snippet})
        return results

    def _parse_lite_html(self, html: str) -> List[dict]:
        """Parse DuckDuckGo lite HTML results."""
        results = []
        # DDG lite uses table-based layout
        snippets = re.findall(r'class="result-snippet">(.*?)</td>', html, re.DOTALL)
        titles = re.findall(r'class="result-link">(.*?)</a>', html, re.DOTALL)
        for i, snippet in enumerate(snippets[:5]):
            title = titles[i] if i < len(titles) else f"Result {i+1}"
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            if clean_snippet:
                results.append({"title": clean_title, "snippet": clean_snippet})
        return results
