"""
The Librarian - ArXiv Technical Paper Fetcher

Detects pre-product innovation signals by fetching papers from ArXiv
in relevant categories (cs.AI, cs.LG, cs.AR, cs.CV).
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from velites.config import settings
from velites.logging import get_logger
from velites.modules.scout.exceptions import DataFetchError
from velites.modules.scout.models import PaperObject

logger = get_logger(__name__)


class BaseArxivFetcher(ABC):
    """Abstract base class for ArXiv fetching."""

    @abstractmethod
    async def fetch_papers(
        self,
        categories: list[str] | None = None,
        lookback_hours: int | None = None,
    ) -> list[PaperObject]:
        """Fetch papers from ArXiv."""
        pass

    @abstractmethod
    def filter_generic_papers(self, papers: list[PaperObject]) -> list[PaperObject]:
        """Filter out survey/review papers."""
        pass


class ArxivFetcher(BaseArxivFetcher):
    """Fetches technical papers from ArXiv API."""

    GENERIC_KEYWORDS = [
        "survey of",
        "review of",
        "a survey",
        "a review",
        "comprehensive survey",
        "systematic review",
    ]

    def __init__(self) -> None:
        self.categories = settings.arxiv_categories
        self.max_results = settings.arxiv_max_results
        self.lookback_hours = settings.arxiv_lookback_hours

    async def fetch_papers(
        self,
        categories: list[str] | None = None,
        lookback_hours: int | None = None,
    ) -> list[PaperObject]:
        """
        Fetch papers from ArXiv API.

        Args:
            categories: ArXiv categories to search (default from settings)
            lookback_hours: Hours to look back (default from settings)

        Returns:
            List of PaperObject instances

        Raises:
            DataFetchError: If fetching fails
        """
        categories = categories or self.categories
        lookback_hours = lookback_hours or self.lookback_hours
        cutoff_date = datetime.utcnow() - timedelta(hours=lookback_hours)

        logger.info(
            "fetching_arxiv_papers",
            categories=categories,
            lookback_hours=lookback_hours,
        )

        # TODO: Implement actual ArXiv API call using feedparser
        # import feedparser
        # query = f"cat:{'+OR+cat:'.join(categories)}"
        # url = f"http://export.arxiv.org/api/query?search_query={query}&max_results={self.max_results}"

        raise NotImplementedError("ArXiv fetcher not yet implemented")

    def filter_generic_papers(self, papers: list[PaperObject]) -> list[PaperObject]:
        """
        Filter out generic survey/review papers.

        Args:
            papers: List of papers to filter

        Returns:
            Filtered list of papers
        """
        filtered = []
        for paper in papers:
            title_lower = paper.title.lower()
            if not any(kw in title_lower for kw in self.GENERIC_KEYWORDS):
                filtered.append(paper)
            else:
                logger.debug("filtered_generic_paper", paper_id=paper.id, title=paper.title)

        logger.info(
            "filtered_papers",
            original_count=len(papers),
            filtered_count=len(filtered),
        )
        return filtered
