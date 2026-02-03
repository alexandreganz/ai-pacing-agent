"""
Unit tests for PacingAnalyzer.

Tests variance calculation, severity classification, and recommendation generation.
"""

import pytest
from datetime import datetime
from src.analyzers.pacing_analyzer import PacingAnalyzer
from src.models.spend import ReconciledSpend, Platform


@pytest.fixture
def analyzer():
    """Create PacingAnalyzer with default thresholds."""
    return PacingAnalyzer()


@pytest.fixture
def analyzer_custom():
    """Create PacingAnalyzer with custom thresholds."""
    return PacingAnalyzer(healthy_threshold=5.0, warning_threshold=15.0)


def create_reconciled_spend(
    target: float,
    actual: float,
    confidence: float = 0.9
) -> ReconciledSpend:
    """Helper to create ReconciledSpend for testing."""
    return ReconciledSpend(
        campaign_id="test_001",
        campaign_name="Test Campaign",
        platform=Platform.GOOGLE,
        target_spend=target,
        actual_spend=actual,
        target_timestamp=datetime.utcnow(),
        actual_timestamp=datetime.utcnow(),
        metadata_match_score=confidence,
        name_similarity=confidence,
        data_freshness_score=confidence
    )


class TestVarianceCalculation:
    """Test variance calculation logic."""

    def test_healthy_variance_under_threshold(self, analyzer):
        """Test that small variance is classified as healthy."""
        reconciled = create_reconciled_spend(target=10000, actual=10500)
        result = analyzer.calculate_variance(reconciled)

        assert result["severity"] == "healthy"
        assert result["variance_pct"] == 5.0
        assert result["is_zero_delivery"] is False

    def test_warning_variance(self, analyzer):
        """Test that moderate variance is classified as warning."""
        reconciled = create_reconciled_spend(target=10000, actual=12000)
        result = analyzer.calculate_variance(reconciled)

        assert result["severity"] == "warning"
        assert result["variance_pct"] == 20.0
        assert result["is_zero_delivery"] is False

    def test_critical_variance(self, analyzer):
        """Test that high variance is classified as critical."""
        reconciled = create_reconciled_spend(target=10000, actual=13500)
        result = analyzer.calculate_variance(reconciled)

        assert result["severity"] == "critical"
        assert result["variance_pct"] == 35.0
        assert result["is_zero_delivery"] is False

    def test_zero_delivery_always_critical(self, analyzer):
        """Test that zero delivery is always critical regardless of threshold."""
        reconciled = create_reconciled_spend(target=10000, actual=0)
        result = analyzer.calculate_variance(reconciled)

        assert result["severity"] == "critical"
        assert result["variance_pct"] == 100.0
        assert result["is_zero_delivery"] is True
        assert result["reason"] == "Zero spend detected despite positive target"

    def test_underspending_variance(self, analyzer):
        """Test that underspending is classified correctly."""
        reconciled = create_reconciled_spend(target=10000, actual=7000)
        result = analyzer.calculate_variance(reconciled)

        assert result["severity"] == "critical"
        assert result["variance_pct"] == 30.0
        assert result["is_overspending"] is False

    def test_exact_threshold_boundary_healthy(self, analyzer):
        """Test variance exactly at healthy threshold."""
        reconciled = create_reconciled_spend(target=10000, actual=11000)
        result = analyzer.calculate_variance(reconciled)

        # 10% variance should be at boundary (implementation dependent)
        assert result["variance_pct"] == 10.0

    def test_exact_threshold_boundary_warning(self, analyzer):
        """Test variance exactly at warning threshold."""
        reconciled = create_reconciled_spend(target=10000, actual=12500)
        result = analyzer.calculate_variance(reconciled)

        # 25% variance should be at boundary
        assert result["variance_pct"] == 25.0


class TestCustomThresholds:
    """Test analyzer with custom thresholds."""

    def test_custom_healthy_threshold(self, analyzer_custom):
        """Test that custom healthy threshold is respected."""
        reconciled = create_reconciled_spend(target=10000, actual=10700)
        result = analyzer_custom.calculate_variance(reconciled)

        # 7% variance - healthy with default (10%), warning with custom (5%)
        assert result["severity"] == "warning"
        assert result["variance_pct"] == 7.0

    def test_custom_warning_threshold(self, analyzer_custom):
        """Test that custom warning threshold is respected."""
        reconciled = create_reconciled_spend(target=10000, actual=12000)
        result = analyzer_custom.calculate_variance(reconciled)

        # 20% variance - warning with default (25%), critical with custom (15%)
        assert result["severity"] == "critical"
        assert result["variance_pct"] == 20.0


class TestRecommendationGeneration:
    """Test recommendation generation."""

    def test_healthy_recommendation(self, analyzer):
        """Test recommendation for healthy campaign."""
        reconciled = create_reconciled_spend(target=10000, actual=10500)
        variance_result = analyzer.calculate_variance(reconciled)
        recommendation = analyzer.generate_recommendation(variance_result, reconciled)

        assert "✅" in recommendation
        assert "healthy" in recommendation.lower()
        assert "5.0%" in recommendation

    def test_warning_recommendation_overspending(self, analyzer):
        """Test recommendation for warning-level overspending."""
        reconciled = create_reconciled_spend(target=10000, actual=12000)
        variance_result = analyzer.calculate_variance(reconciled)
        recommendation = analyzer.generate_recommendation(variance_result, reconciled)

        assert "⚠️" in recommendation
        assert "overspending" in recommendation.lower()
        assert "20.0%" in recommendation

    def test_warning_recommendation_underspending(self, analyzer):
        """Test recommendation for warning-level underspending."""
        reconciled = create_reconciled_spend(target=10000, actual=8500)
        variance_result = analyzer.calculate_variance(reconciled)
        recommendation = analyzer.generate_recommendation(variance_result, reconciled)

        assert "⚠️" in recommendation
        assert "underspending" in recommendation.lower()

    def test_critical_recommendation_overspending(self, analyzer):
        """Test recommendation for critical overspending."""
        reconciled = create_reconciled_spend(target=10000, actual=14000)
        variance_result = analyzer.calculate_variance(reconciled)
        recommendation = analyzer.generate_recommendation(variance_result, reconciled)

        assert "🚨" in recommendation
        assert "CRITICAL" in recommendation
        assert "overspending" in recommendation.lower()
        assert "Pause" in recommendation or "pause" in recommendation

    def test_zero_delivery_recommendation(self, analyzer):
        """Test recommendation for zero delivery."""
        reconciled = create_reconciled_spend(target=10000, actual=0)
        variance_result = analyzer.calculate_variance(reconciled)
        recommendation = analyzer.generate_recommendation(variance_result, reconciled)

        assert "🚨" in recommendation
        assert "ZERO DELIVERY" in recommendation
        assert "paused" in recommendation.lower() or "audience" in recommendation.lower()


class TestSeverityClassification:
    """Test severity classification utility method."""

    def test_classify_severity_healthy(self, analyzer):
        """Test classify_severity for healthy variance."""
        assert analyzer.classify_severity(5.0, False) == "healthy"
        assert analyzer.classify_severity(9.9, False) == "healthy"

    def test_classify_severity_warning(self, analyzer):
        """Test classify_severity for warning variance."""
        assert analyzer.classify_severity(15.0, False) == "warning"
        assert analyzer.classify_severity(24.9, False) == "warning"

    def test_classify_severity_critical(self, analyzer):
        """Test classify_severity for critical variance."""
        assert analyzer.classify_severity(30.0, False) == "critical"
        assert analyzer.classify_severity(100.0, False) == "critical"

    def test_classify_severity_zero_delivery(self, analyzer):
        """Test that zero delivery overrides variance."""
        assert analyzer.classify_severity(5.0, True) == "critical"
        assert analyzer.classify_severity(0.0, True) == "critical"


class TestActionableDecisions:
    """Test is_actionable utility method."""

    def test_healthy_not_actionable(self, analyzer):
        """Test that healthy severity is not actionable."""
        assert analyzer.is_actionable("healthy") is False

    def test_warning_actionable(self, analyzer):
        """Test that warning severity is actionable."""
        assert analyzer.is_actionable("warning") is True

    def test_critical_actionable(self, analyzer):
        """Test that critical severity is actionable."""
        assert analyzer.is_actionable("critical") is True


class TestAutonomousAction:
    """Test requires_autonomous_action utility method."""

    def test_critical_high_confidence_requires_action(self, analyzer):
        """Test that critical + high confidence requires autonomous action."""
        assert analyzer.requires_autonomous_action("critical", 0.9, 0.7) is True

    def test_critical_low_confidence_no_action(self, analyzer):
        """Test that critical + low confidence doesn't require autonomous action."""
        assert analyzer.requires_autonomous_action("critical", 0.5, 0.7) is False

    def test_warning_no_autonomous_action(self, analyzer):
        """Test that warning never requires autonomous action."""
        assert analyzer.requires_autonomous_action("warning", 0.9, 0.7) is False

    def test_healthy_no_autonomous_action(self, analyzer):
        """Test that healthy never requires autonomous action."""
        assert analyzer.requires_autonomous_action("healthy", 0.9, 0.7) is False


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_target_spend(self, analyzer):
        """Test handling of zero target spend."""
        reconciled = create_reconciled_spend(target=0, actual=100)
        result = analyzer.calculate_variance(reconciled)

        # Should handle division by zero gracefully
        assert result["variance_pct"] == 100.0

    def test_both_zero(self, analyzer):
        """Test when both target and actual are zero."""
        reconciled = create_reconciled_spend(target=0, actual=0)
        result = analyzer.calculate_variance(reconciled)

        # Should return 0 variance (no issue)
        assert result["variance_pct"] == 0.0

    def test_negative_values_not_possible(self):
        """Test that negative spend values would be caught by data model."""
        # ReconciledSpend should validate non-negative values
        # This is more of a data model test
        pass

    def test_very_large_variance(self, analyzer):
        """Test handling of very large variance."""
        reconciled = create_reconciled_spend(target=100, actual=10000)
        result = analyzer.calculate_variance(reconciled)

        assert result["severity"] == "critical"
        assert result["variance_pct"] == 9900.0  # 9900% variance


class TestAnalyzerConfiguration:
    """Test analyzer configuration export."""

    def test_to_dict(self, analyzer):
        """Test configuration export."""
        config = analyzer.to_dict()

        assert "healthy_threshold" in config
        assert "warning_threshold" in config
        assert config["healthy_threshold"] == 10.0
        assert config["warning_threshold"] == 25.0

    def test_to_dict_custom(self, analyzer_custom):
        """Test configuration export with custom thresholds."""
        config = analyzer_custom.to_dict()

        assert config["healthy_threshold"] == 5.0
        assert config["warning_threshold"] == 15.0
