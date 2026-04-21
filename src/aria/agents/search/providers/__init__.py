"""
Search provider adapters per blueprint §11.1.

Each provider implements the SearchProvider protocol and normalizes
responses to SearchHit. Hardening (httpx, tenacity retry, CredentialManager)
is applied per blueprint §11.3.
"""

from .brave import BraveProvider
from .exa import ExaProvider
from .firecrawl import FirecrawlProvider
from .searxng import SearXNGProvider
from .serpapi import SerpAPIProvider
from .tavily import TavilyProvider

__all__ = [
    "BraveProvider",
    "TavilyProvider",
    "FirecrawlProvider",
    "ExaProvider",
    "SearXNGProvider",
    "SerpAPIProvider",
]
