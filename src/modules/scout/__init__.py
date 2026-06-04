"""
Scout Module - Data Ingestion

The "Senses" of Velites. Responsible for fetching raw, unstructured data
from external sources. Performs no analysis, only normalization.

Components:
- Librarian (arxiv_fetcher): Technical paper discovery from ArXiv
- News Aggregator (news_fetcher): Business news and market context
- Market Feeder (market_fetcher): Real-time market data
"""

from modules.scout.arxiv_fetcher import ArxivFetcher
from modules.scout.market_fetcher import MarketFetcher
from modules.scout.news_fetcher import NewsFetcher

__all__ = ["ArxivFetcher", "NewsFetcher", "MarketFetcher"]
