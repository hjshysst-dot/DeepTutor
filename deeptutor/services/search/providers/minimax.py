"""
MiniMax Web Search Provider

Uses the MiniMax MCP web_search tool via local HTTP wrapper.
"""

import json
import httpx
from typing import Optional

from ..base import BaseSearchProvider
from ...config import get_env_store


class MiniMaxSearchProvider(BaseSearchProvider):
    """MiniMax web search via MCP wrapper on localhost:3785"""
    
    display_name = "MiniMax Search"
    description = "MiniMax AI web search - uses the same API key as chat"
    supports_answer = True
    requires_api_key = False  # Uses LLM API key
    
    def __init__(self):
        self.base_url = "http://localhost:3785"
    
    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/", timeout=3)
            return response.status_code == 200
        except:
            return False
    
    def search(self, query: str, count: int = 5) -> dict:
        try:
            response = httpx.get(
                f"{self.base_url}/search",
                params={"q": query, "count": count},
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def search_with_answer(self, query: str, count: int = 5) -> dict:
        result = self.search(query, count)
        if "error" in result:
            return {"answer": None, "sources": [], "error": result["error"]}
        
        # Extract answer from MiniMax results
        answer = self._extract_answer(result)
        sources = self._extract_sources(result)
        
        return {
            "answer": answer,
            "sources": sources,
        }
    
    def _extract_answer(self, result: dict) -> Optional[str]:
        """Extract a synthesized answer from search results"""
        if "results" in result and result["results"]:
            first_result = result["results"][0]
            if isinstance(first_result, dict):
                return first_result.get("snippet") or first_result.get("title")
        return None
    
    def _extract_sources(self, result: dict) -> list:
        """Extract source URLs"""
        sources = []
        if "results" in result:
            for r in result["results"]:
                if isinstance(r, dict) and "link" in r:
                    sources.append({
                        "title": r.get("title", ""),
                        "url": r["link"],
                    })
        return sources




# Register this provider
from . import register_provider
register_provider("minimax")(MiniMaxSearchProvider)
