"""Integration tests for the full Velites pipeline."""

import pytest


class TestVelitesPipeline:
    """Integration tests for the full pipeline."""

    @pytest.mark.skip(reason="Requires full implementation")
    @pytest.mark.asyncio
    async def test_full_pipeline_run(self) -> None:
        """Test a complete pipeline run."""
        # TODO: Implement after all modules are complete
        pass

    @pytest.mark.skip(reason="Requires full implementation")
    @pytest.mark.asyncio
    async def test_pipeline_with_mock_data(self) -> None:
        """Test pipeline with mocked external data."""
        # TODO: Implement with mocked Scout responses
        pass
