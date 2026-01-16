"""Tests for ArXiv fetcher."""

import pytest

from velites.modules.scout.arxiv_fetcher import ArxivFetcher
from velites.models.paper import PaperObject


class TestArxivFetcher:
    """Tests for ArxivFetcher class."""

    def test_filter_generic_papers_removes_surveys(self, sample_paper: PaperObject) -> None:
        """Test that survey papers are filtered out."""
        fetcher = ArxivFetcher()

        # Create a survey paper
        survey_paper = sample_paper.model_copy()
        survey_paper.title = "A Survey of Machine Learning Techniques"

        papers = [sample_paper, survey_paper]
        filtered = fetcher.filter_generic_papers(papers)

        assert len(filtered) == 1
        assert filtered[0].id == sample_paper.id

    def test_filter_generic_papers_removes_reviews(self, sample_paper: PaperObject) -> None:
        """Test that review papers are filtered out."""
        fetcher = ArxivFetcher()

        review_paper = sample_paper.model_copy()
        review_paper.title = "A Comprehensive Review of Neural Networks"

        papers = [sample_paper, review_paper]
        filtered = fetcher.filter_generic_papers(papers)

        assert len(filtered) == 1

    def test_filter_generic_papers_keeps_regular_papers(self, sample_paper: PaperObject) -> None:
        """Test that regular papers are kept."""
        fetcher = ArxivFetcher()

        papers = [sample_paper]
        filtered = fetcher.filter_generic_papers(papers)

        assert len(filtered) == 1
        assert filtered[0] == sample_paper

    @pytest.mark.asyncio
    async def test_fetch_papers_not_implemented(self) -> None:
        """Test that fetch_papers raises NotImplementedError."""
        fetcher = ArxivFetcher()

        with pytest.raises(NotImplementedError):
            await fetcher.fetch_papers()
