"""
Unit tests for data models.

Tests SpendRecord, ReconciledSpend, and PacingAlert data models.
"""

import pytest
from datetime import datetime, timedelta
from src.models.spend import (
    Platform,
    DataSource,
    SpendRecord,
    ReconciledSpend,
    PacingAlert
)


class TestSpendRecord:
    """Test SpendRecord data model."""

    def test_create_spend_record(self):
        """Test creating a SpendRecord."""
        record = SpendRecord(
            campaign_id="test_001",
            campaign_name="Test Campaign",
            platform=Platform.GOOGLE,
            source=DataSource.PLATFORM_API,
            amount_usd=1000.0,
            timestamp=datetime.utcnow(),
            refresh_cycle_hours=4,
            metadata={"market": "EU"}
        )

        assert record.campaign_id == "test_001"
        assert record.platform == Platform.GOOGLE
        assert record.amount_usd == 1000.0

    def test_hours_since_update(self):
        """Test hours_since_update property."""
        old_timestamp = datetime.utcnow() - timedelta(hours=5)
        record = SpendRecord(
            campaign_id="test_001",
            campaign_name="Test",
            platform=Platform.META,
            source=DataSource.PLATFORM_API,
            amount_usd=1000.0,
            timestamp=old_timestamp,
            refresh_cycle_hours=4,
            metadata={}
        )

        assert 4.9 < record.hours_since_update < 5.1  # Allow small time drift

    def test_is_stale(self):
        """Test is_stale property."""
        # Fresh data
        fresh_record = SpendRecord(
            campaign_id="test_001",
            campaign_name="Test",
            platform=Platform.GOOGLE,
            source=DataSource.PLATFORM_API,
            amount_usd=1000.0,
            timestamp=datetime.utcnow() - timedelta(hours=2),
            refresh_cycle_hours=4,
            metadata={}
        )
        assert fresh_record.is_stale is False

        # Stale data
        stale_record = SpendRecord(
            campaign_id="test_002",
            campaign_name="Test",
            platform=Platform.GOOGLE,
            source=DataSource.PLATFORM_API,
            amount_usd=1000.0,
            timestamp=datetime.utcnow() - timedelta(hours=6),
            refresh_cycle_hours=4,
            metadata={}
        )
        assert stale_record.is_stale is True


class TestReconciledSpend:
    """Test ReconciledSpend data model."""

    def create_reconciled(
        self,
        target: float,
        actual: float,
        metadata_match: float = 0.9,
        name_similarity: float = 0.9,
        freshness: float = 0.9
    ) -> ReconciledSpend:
        """Helper to create ReconciledSpend."""
        return ReconciledSpend(
            campaign_id="test_001",
            campaign_name="Test Campaign",
            platform=Platform.GOOGLE,
            target_spend=target,
            actual_spend=actual,
            target_timestamp=datetime.utcnow(),
            actual_timestamp=datetime.utcnow(),
            metadata_match_score=metadata_match,
            name_similarity=name_similarity,
            data_freshness_score=freshness
        )

    def test_confidence_score_calculation(self):
        """Test confidence score weighted average."""
        reconciled = self.create_reconciled(
            target=10000,
            actual=10500,
            metadata_match=1.0,
            name_similarity=0.8,
            freshness=0.6
        )

        # Expected: 1.0 * 0.5 + 0.8 * 0.3 + 0.6 * 0.2 = 0.86
        expected = 0.86
        assert abs(reconciled.confidence_score - expected) < 0.01

    def test_pacing_variance_overspending(self):
        """Test pacing variance for overspending."""
        reconciled = self.create_reconciled(target=10000, actual=12000)
        assert reconciled.pacing_variance == 20.0

    def test_pacing_variance_underspending(self):
        """Test pacing variance for underspending."""
        reconciled = self.create_reconciled(target=10000, actual=8000)
        assert reconciled.pacing_variance == 20.0  # Absolute value

    def test_pacing_variance_zero_target(self):
        """Test pacing variance with zero target."""
        reconciled = self.create_reconciled(target=0, actual=100)
        assert reconciled.pacing_variance == 100.0

    def test_pacing_variance_both_zero(self):
        """Test pacing variance when both are zero."""
        reconciled = self.create_reconciled(target=0, actual=0)
        assert reconciled.pacing_variance == 0.0

    def test_variance_amount(self):
        """Test variance_amount property."""
        reconciled = self.create_reconciled(target=10000, actual=12000)
        assert reconciled.variance_amount == 2000.0

    def test_is_overspending(self):
        """Test is_overspending property."""
        overspending = self.create_reconciled(target=10000, actual=12000)
        assert overspending.is_overspending is True

        on_target = self.create_reconciled(target=10000, actual=10000)
        assert on_target.is_overspending is False

    def test_is_underspending(self):
        """Test is_underspending property."""
        underspending = self.create_reconciled(target=10000, actual=8000)
        assert underspending.is_underspending is True

        on_target = self.create_reconciled(target=10000, actual=10000)
        assert on_target.is_underspending is False

    def test_is_zero_delivery(self):
        """Test is_zero_delivery property."""
        zero_delivery = self.create_reconciled(target=10000, actual=0)
        assert zero_delivery.is_zero_delivery is True

        normal = self.create_reconciled(target=10000, actual=5000)
        assert normal.is_zero_delivery is False

    def test_spend_direction(self):
        """Test spend_direction property."""
        assert self.create_reconciled(10000, 12000).spend_direction == "overspending"
        assert self.create_reconciled(10000, 8000).spend_direction == "underspending"
        assert self.create_reconciled(10000, 0).spend_direction == "zero_delivery"
        assert self.create_reconciled(10000, 10000).spend_direction == "on_target"

    def test_to_dict(self):
        """Test to_dict serialization."""
        reconciled = self.create_reconciled(target=10000, actual=12000)
        data = reconciled.to_dict()

        assert data["campaign_id"] == "test_001"
        assert data["target_spend"] == 10000
        assert data["actual_spend"] == 12000
        assert data["variance_pct"] == 20.0
        assert data["is_overspending"] is True
        assert data["is_zero_delivery"] is False
        assert "timestamp" in data["target_timestamp"]


class TestPacingAlert:
    """Test PacingAlert data model."""

    def create_alert(
        self,
        severity: str = "warning",
        variance: float = 15.0,
        action: str = "slack_alert"
    ) -> PacingAlert:
        """Helper to create PacingAlert."""
        return PacingAlert(
            alert_id="alert_123",
            campaign_id="test_001",
            severity=severity,
            variance_pct=variance,
            confidence_score=0.9,
            action_taken=action,
            recommendation="Test recommendation",
            requires_human=False,
            timestamp=datetime.utcnow(),
            root_cause_analysis="Test root cause",
            mitigation_plan="Test mitigation"
        )

    def test_create_alert(self):
        """Test creating a PacingAlert."""
        alert = self.create_alert()

        assert alert.alert_id == "alert_123"
        assert alert.severity == "warning"
        assert alert.variance_pct == 15.0
        assert alert.action_taken == "slack_alert"

    def test_is_critical(self):
        """Test is_critical property."""
        critical = self.create_alert(severity="critical")
        assert critical.is_critical is True

        warning = self.create_alert(severity="warning")
        assert warning.is_critical is False

    def test_is_autonomous_action(self):
        """Test is_autonomous_action property."""
        halt = self.create_alert(action="autonomous_halt")
        assert halt.is_autonomous_action is True

        alert = self.create_alert(action="slack_alert")
        assert alert.is_autonomous_action is False

        log = self.create_alert(action="logged_healthy")
        assert log.is_autonomous_action is False

    def test_to_dict(self):
        """Test to_dict serialization."""
        alert = self.create_alert()
        data = alert.to_dict()

        assert data["alert_id"] == "alert_123"
        assert data["campaign_id"] == "test_001"
        assert data["severity"] == "warning"
        assert data["variance_pct"] == 15.0
        assert data["is_critical"] is False
        assert data["is_autonomous_action"] is False

    def test_str_representation(self):
        """Test string representation."""
        alert = self.create_alert()
        str_repr = str(alert)

        assert "alert_123" in str_repr
        assert "test_001" in str_repr
        assert "warning" in str_repr
        assert "slack_alert" in str_repr


class TestEnums:
    """Test enum types."""

    def test_platform_enum(self):
        """Test Platform enum values."""
        assert Platform.GOOGLE.value == "google"
        assert Platform.META.value == "meta"
        assert Platform.DV360.value == "dv360"

    def test_data_source_enum(self):
        """Test DataSource enum values."""
        assert DataSource.INTERNAL_TRACKER.value == "internal_tracker"
        assert DataSource.PLATFORM_API.value == "platform_api"
