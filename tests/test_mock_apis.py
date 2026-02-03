"""
Unit tests for Mock APIs.

Tests MockPlatformAPI and MockInternalTracker.
"""

import pytest
from src.api.mock_platform_api import MockPlatformAPI
from src.api.internal_tracker import MockInternalTracker
from src.models.spend import Platform, DataSource


class TestMockPlatformAPI:
    """Test MockPlatformAPI."""

    @pytest.fixture
    def google_api(self):
        """Create Google platform API with fixed seed."""
        return MockPlatformAPI(Platform.GOOGLE, num_campaigns=5, seed=42)

    @pytest.fixture
    def meta_api(self):
        """Create Meta platform API with fixed seed."""
        return MockPlatformAPI(Platform.META, num_campaigns=5, seed=42)

    def test_initialization(self, google_api):
        """Test API initialization."""
        assert google_api.platform == Platform.GOOGLE
        assert google_api.num_campaigns == 5
        assert len(google_api.campaigns) == 5

    def test_campaign_generation(self, google_api):
        """Test that campaigns are generated correctly."""
        campaigns = google_api.campaigns

        for campaign in campaigns:
            assert "campaign_id" in campaign
            assert "campaign_name" in campaign
            assert "spend" in campaign
            assert "target" in campaign
            assert "status" in campaign
            assert campaign["campaign_id"].startswith("google_")

    def test_get_campaign_spend(self, google_api):
        """Test getting spend for a specific campaign."""
        campaign_id = google_api.list_campaign_ids()[0]
        spend_record = google_api.get_campaign_spend(campaign_id)

        assert spend_record.campaign_id == campaign_id
        assert spend_record.platform == Platform.GOOGLE
        assert spend_record.source == DataSource.PLATFORM_API
        assert spend_record.refresh_cycle_hours == 4

    def test_get_campaign_spend_not_found(self, google_api):
        """Test error when campaign not found."""
        with pytest.raises(ValueError, match="not found"):
            google_api.get_campaign_spend("nonexistent_campaign")

    def test_get_all_campaigns(self, google_api):
        """Test getting all campaigns."""
        all_campaigns = google_api.get_all_campaigns()

        assert len(all_campaigns) == 5
        assert all(record.platform == Platform.GOOGLE for record in all_campaigns)
        assert all(record.source == DataSource.PLATFORM_API for record in all_campaigns)

    def test_pause_campaign(self, google_api):
        """Test pausing a campaign."""
        campaign_id = google_api.list_campaign_ids()[0]

        # Initially should be active (if spend > 0)
        initial_status = google_api.get_campaign_status(campaign_id)

        # Pause it
        success = google_api.pause_campaign(campaign_id)
        assert success is True

        # Check status changed
        assert google_api.get_campaign_status(campaign_id) == "paused"

    def test_pause_nonexistent_campaign(self, google_api):
        """Test pausing nonexistent campaign."""
        success = google_api.pause_campaign("nonexistent")
        assert success is False

    def test_resume_campaign(self, google_api):
        """Test resuming a campaign."""
        campaign_id = google_api.list_campaign_ids()[0]

        # Pause first
        google_api.pause_campaign(campaign_id)
        assert google_api.get_campaign_status(campaign_id) == "paused"

        # Resume
        success = google_api.resume_campaign(campaign_id)
        assert success is True
        assert google_api.get_campaign_status(campaign_id) == "active"

    def test_list_campaign_ids(self, google_api):
        """Test listing campaign IDs."""
        ids = google_api.list_campaign_ids()

        assert len(ids) == 5
        assert all(isinstance(id, str) for id in ids)
        assert all(id.startswith("google_") for id in ids)

    def test_get_summary_stats(self, google_api):
        """Test getting summary statistics."""
        stats = google_api.get_summary_stats()

        assert stats["platform"] == "google"
        assert stats["total_campaigns"] == 5
        assert "active_campaigns" in stats
        assert "paused_campaigns" in stats
        assert "total_target_spend" in stats
        assert "total_actual_spend" in stats
        assert "overall_variance_pct" in stats
        assert "scenario_distribution" in stats

    def test_different_platforms_generate_different_data(self):
        """Test that different platforms generate different campaigns."""
        google_api = MockPlatformAPI(Platform.GOOGLE, num_campaigns=3, seed=42)
        meta_api = MockPlatformAPI(Platform.META, num_campaigns=3, seed=42)

        google_ids = google_api.list_campaign_ids()
        meta_ids = meta_api.list_campaign_ids()

        # IDs should be different (different platforms)
        assert all(id.startswith("google_") for id in google_ids)
        assert all(id.startswith("meta_") for id in meta_ids)

    def test_seed_reproducibility(self):
        """Test that same seed produces same results."""
        api1 = MockPlatformAPI(Platform.GOOGLE, num_campaigns=3, seed=100)
        api2 = MockPlatformAPI(Platform.GOOGLE, num_campaigns=3, seed=100)

        ids1 = api1.list_campaign_ids()
        ids2 = api2.list_campaign_ids()

        assert ids1 == ids2

        # Check that spend values match too
        for id in ids1:
            spend1 = api1.get_campaign_spend(id).amount_usd
            spend2 = api2.get_campaign_spend(id).amount_usd
            assert spend1 == spend2


class TestMockInternalTracker:
    """Test MockInternalTracker."""

    @pytest.fixture
    def tracker(self):
        """Create internal tracker."""
        return MockInternalTracker()

    def test_initialization(self, tracker):
        """Test tracker initialization."""
        assert tracker.target_data == {}

    def test_get_target_spend_generated(self, tracker):
        """Test getting target spend with auto-generation."""
        campaign_id = "google_001"
        spend_record = tracker.get_target_spend(campaign_id)

        assert spend_record.campaign_id == campaign_id
        assert spend_record.platform == Platform.GOOGLE
        assert spend_record.source == DataSource.INTERNAL_TRACKER
        assert spend_record.refresh_cycle_hours == 24
        assert spend_record.amount_usd > 0

    def test_get_target_spend_explicit(self, tracker):
        """Test getting target spend from explicit data."""
        tracker.set_target("google_001", 5000.0)
        spend_record = tracker.get_target_spend("google_001")

        assert spend_record.campaign_id == "google_001"
        assert spend_record.amount_usd == 5000.0

    def test_set_target(self, tracker):
        """Test setting target spend."""
        tracker.set_target("google_001", 8000.0, metadata={"market": "EU"})

        assert tracker.has_campaign("google_001")
        assert tracker.target_data["google_001"]["target_spend"] == 8000.0
        assert tracker.target_data["google_001"]["metadata"]["market"] == "EU"

    def test_bulk_set_targets(self, tracker):
        """Test bulk setting targets."""
        targets = {
            "google_001": 5000.0,
            "google_002": 7000.0,
            "meta_001": 3000.0
        }

        tracker.bulk_set_targets(targets)

        assert len(tracker.get_all_campaign_ids()) == 3
        assert tracker.get_target_spend("google_001").amount_usd == 5000.0
        assert tracker.get_target_spend("google_002").amount_usd == 7000.0

    def test_has_campaign(self, tracker):
        """Test checking campaign existence."""
        assert tracker.has_campaign("google_001") is False

        tracker.set_target("google_001", 5000.0)
        assert tracker.has_campaign("google_001") is True

    def test_get_all_campaign_ids(self, tracker):
        """Test getting all campaign IDs."""
        assert tracker.get_all_campaign_ids() == []

        tracker.set_target("google_001", 5000.0)
        tracker.set_target("meta_001", 3000.0)

        ids = tracker.get_all_campaign_ids()
        assert len(ids) == 2
        assert "google_001" in ids
        assert "meta_001" in ids

    def test_get_summary(self, tracker):
        """Test getting summary statistics."""
        # Empty tracker
        summary = tracker.get_summary()
        assert summary["total_campaigns"] == 0
        assert summary["total_target_spend"] == 0.0

        # With data
        tracker.set_target("google_001", 5000.0)
        tracker.set_target("meta_001", 3000.0)

        summary = tracker.get_summary()
        assert summary["total_campaigns"] == 2
        assert summary["total_target_spend"] == 8000.0
        assert summary["average_target_spend"] == 4000.0
        assert len(summary["campaign_ids"]) == 2

    def test_platform_inference_from_id(self, tracker):
        """Test platform inference from campaign ID."""
        google_record = tracker.get_target_spend("google_999")
        assert google_record.platform == Platform.GOOGLE

        meta_record = tracker.get_target_spend("meta_999")
        assert meta_record.platform == Platform.META


class TestAPIIntegration:
    """Test integration between platform API and tracker."""

    def test_campaign_id_compatibility(self):
        """Test that campaign IDs work across both systems."""
        platform_api = MockPlatformAPI(Platform.GOOGLE, num_campaigns=3, seed=42)
        tracker = MockInternalTracker()

        # Get campaign ID from platform API
        campaign_id = platform_api.list_campaign_ids()[0]

        # Should be able to get target from tracker
        target_record = tracker.get_target_spend(campaign_id)
        assert target_record.campaign_id == campaign_id

        # Should be able to get actual from platform
        actual_record = platform_api.get_campaign_spend(campaign_id)
        assert actual_record.campaign_id == campaign_id

    def test_reconciliation_scenario(self):
        """Test realistic reconciliation scenario."""
        platform_api = MockPlatformAPI(Platform.GOOGLE, num_campaigns=1, seed=42)
        tracker = MockInternalTracker()

        campaign_id = platform_api.list_campaign_ids()[0]

        # Get data from both sources
        actual_record = platform_api.get_campaign_spend(campaign_id)
        target_record = tracker.get_target_spend(campaign_id)

        # Both should have valid data
        assert actual_record.amount_usd >= 0
        assert target_record.amount_usd > 0

        # Calculate variance
        variance = abs(actual_record.amount_usd - target_record.amount_usd)
        variance_pct = (variance / target_record.amount_usd) * 100

        assert variance_pct >= 0
