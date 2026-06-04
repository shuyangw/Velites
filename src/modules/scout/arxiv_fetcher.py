"""
The Librarian - ArXiv Technical Paper Fetcher

Detects pre-product innovation signals by fetching papers from ArXiv
in relevant categories (cs.AI, cs.LG, cs.AR, cs.CV).
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from config import settings
from logging_config import get_logger
from modules.scout.exceptions import DataFetchError
from modules.scout.models import PaperObject

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
        cutoff_date = datetime.now(UTC) - timedelta(hours=lookback_hours)

        logger.info(
            "fetching_arxiv_papers",
            categories=categories,
            lookback_hours=lookback_hours,
        )

        try:
            import feedparser
        except ImportError:
            raise DataFetchError("feedparser is required: pip install feedparser")

        # Build query from configured categories
        query = "+OR+".join(f"cat:{cat}" for cat in categories)
        url = (
            f"http://export.arxiv.org/api/query?"
            f"search_query={query}"
            f"&max_results={self.max_results}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )

        logger.debug("arxiv_api_url", url=url)

        try:
            feed = feedparser.parse(url)

            if feed.bozo:
                raise DataFetchError(f"Failed to parse ArXiv feed: {feed.bozo_exception}")

            papers: list[PaperObject] = []

            for entry in feed.entries:
                # Parse dates - use updated_parsed for filtering (catches updates)
                # but keep published_parsed for the actual publication date
                if hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    updated = datetime(*entry.updated_parsed[:6], tzinfo=UTC)
                else:
                    # Skip entries without valid date
                    continue

                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                else:
                    published = updated

                # Filter by cutoff date using updated date (more recent)
                if updated < cutoff_date:
                    continue

                # Extract paper ID from URL (e.g., http://arxiv.org/abs/2601.12345v1)
                paper_id = entry.id.split("/")[-1]
                if paper_id.endswith("v1") or paper_id.endswith("v2") or paper_id.endswith("v3"):
                    paper_id = paper_id[:-2]

                # Extract categories from tags
                categories_list = [tag.term for tag in entry.tags] if hasattr(entry, "tags") else []

                # Extract authors
                authors = (
                    [author.name for author in entry.authors] if hasattr(entry, "authors") else []
                )

                paper = PaperObject(
                    id=f"arxiv_{paper_id}",
                    title=entry.title.replace("\n", " ").strip(),
                    abstract=entry.summary.replace("\n", " ").strip()
                    if hasattr(entry, "summary")
                    else "",
                    authors=authors,
                    url=entry.link,
                    published_date=published,
                    source="arxiv",
                    categories=categories_list,
                )
                papers.append(paper)

            logger.info(
                "arxiv_papers_fetched",
                total_entries=len(feed.entries),
                within_lookback=len(papers),
            )

            return papers

        except Exception as e:
            if isinstance(e, DataFetchError):
                raise
            raise DataFetchError(f"Failed to fetch ArXiv papers: {e}")

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
