"""
Unit tests for ConfidenceScorer.

Tests metadata matching, name similarity, freshness scoring, and overall confidence.
"""

import pytest
from datetime import datetime, timedelta
from src.agents.confidence_scorer import ConfidenceScorer


@pytest.fixture
def scorer():
    """Create ConfidenceScorer with default configuration."""
    return ConfidenceScorer()


@pytest.fixture
def scorer_custom():
    """Create ConfidenceScorer with custom weights."""
    return ConfidenceScorer(
        metadata_weight=0.4,
        name_similarity_weight=0.4,
        freshness_weight=0.2
    )


class TestMetadataMatching:
    """Test metadata field matching."""

    def test_perfect_metadata_match(self, scorer):
        """Test that identical metadata scores 1.0."""
        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        api_metadata = tracker_metadata.copy()

        score = scorer.calculate_metadata_match(tracker_metadata, api_metadata)
        assert score == 1.0

    def test_partial_metadata_match(self, scorer):
        """Test that partial match scores proportionally."""
        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        api_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-02-28"  # Different end date
        }

        score = scorer.calculate_metadata_match(tracker_metadata, api_metadata)
        assert score == 0.75  # 3 out of 4 fields match

    def test_no_metadata_match(self, scorer):
        """Test that no matching fields scores 0.0."""
        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        api_metadata = {
            "market": "NA",
            "product": "LEGO_Friends",
            "start_date": "2026-02-01",
            "end_date": "2026-02-28"
        }

        score = scorer.calculate_metadata_match(tracker_metadata, api_metadata)
        assert score == 0.0

    def test_missing_fields(self, scorer):
        """Test handling of missing metadata fields."""
        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City"
            # Missing start_date and end_date
        }
        api_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }

        score = scorer.calculate_metadata_match(tracker_metadata, api_metadata)
        # Only 2 fields can be matched (market and product)
        assert score == 0.5  # 2 matched, 2 missing from tracker

    def test_case_insensitive_matching(self, scorer):
        """Test that metadata matching is case-insensitive."""
        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        api_metadata = {
            "market": "eu",  # Lowercase
            "product": "lego_city",  # Lowercase
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }

        score = scorer.calculate_metadata_match(tracker_metadata, api_metadata)
        assert score == 1.0


class TestNameSimilarity:
    """Test campaign name similarity using Levenshtein distance."""

    def test_identical_names(self, scorer):
        """Test that identical names score 1.0."""
        name = "LEGO_EU_City_Q1_2026_Search_001"
        score = scorer.calculate_name_similarity(name, name)
        assert score == 1.0

    def test_case_insensitive(self, scorer):
        """Test that name comparison is case-insensitive."""
        tracker_name = "LEGO_EU_City_Q1_2026_Search_001"
        api_name = "lego_eu_city_q1_2026_search_001"
        score = scorer.calculate_name_similarity(tracker_name, api_name)
        assert score == 1.0

    def test_whitespace_normalized(self, scorer):
        """Test that extra whitespace is handled."""
        tracker_name = "LEGO EU City Q1 2026 Search 001"
        api_name = "lego eu city q1 2026 search 001"
        score = scorer.calculate_name_similarity(tracker_name, api_name)
        assert score == 1.0

    def test_minor_typo(self, scorer):
        """Test that minor typos still score high."""
        tracker_name = "LEGO_EU_City_Q1_2026_Search_001"
        api_name = "LEGO_EU_Coty_Q1_2026_Search_001"  # "Coty" instead of "City"
        score = scorer.calculate_name_similarity(tracker_name, api_name)
        # 1 character difference out of 31 characters
        assert score > 0.95

    def test_significant_difference(self, scorer):
        """Test that significantly different names score low."""
        tracker_name = "LEGO_EU_City_Q1_2026_Search_001"
        api_name = "LEGO_NA_Friends_Q2_2025_Display_042"
        score = scorer.calculate_name_similarity(tracker_name, api_name)
        assert score < 0.7  # Should be relatively low

    def test_completely_different(self, scorer):
        """Test that completely different names score very low."""
        tracker_name = "LEGO_EU_City_Q1_2026"
        api_name = "Meta_NA_Friends_Display"
        score = scorer.calculate_name_similarity(tracker_name, api_name)
        assert score < 0.5

    def test_empty_strings(self, scorer):
        """Test handling of empty strings."""
        score = scorer.calculate_name_similarity("", "")
        assert score == 1.0  # Both empty = identical

        score = scorer.calculate_name_similarity("LEGO_Campaign", "")
        assert score == 0.0  # One empty

    def test_substring_relationship(self, scorer):
        """Test names where one is substring of other."""
        tracker_name = "LEGO_EU_City"
        api_name = "LEGO_EU_City_Q1_2026"
        score = scorer.calculate_name_similarity(tracker_name, api_name)
        # Should be fairly high since tracker is contained in api
        assert score > 0.6


class TestFreshnessScoring:
    """Test data freshness scoring."""

    def test_very_fresh_data(self, scorer):
        """Test that data < 4 hours old scores 1.0."""
        timestamp = datetime.utcnow() - timedelta(hours=2)
        score = scorer.calculate_freshness(timestamp)
        assert score == 1.0

    def test_fresh_boundary(self, scorer):
        """Test boundary at 4 hours."""
        timestamp = datetime.utcnow() - timedelta(hours=3, minutes=59)
        score = scorer.calculate_freshness(timestamp)
        assert score == 1.0

    def test_moderately_fresh(self, scorer):
        """Test that data 4-12 hours old scores 0.8."""
        timestamp = datetime.utcnow() - timedelta(hours=8)
        score = scorer.calculate_freshness(timestamp)
        assert score == 0.8

    def test_acceptable_freshness(self, scorer):
        """Test that data 12-24 hours old scores 0.5."""
        timestamp = datetime.utcnow() - timedelta(hours=18)
        score = scorer.calculate_freshness(timestamp)
        assert score == 0.5

    def test_stale_data(self, scorer):
        """Test that data > 24 hours old scores 0.2."""
        timestamp = datetime.utcnow() - timedelta(hours=48)
        score = scorer.calculate_freshness(timestamp)
        assert score == 0.2

        timestamp = datetime.utcnow() - timedelta(days=7)
        score = scorer.calculate_freshness(timestamp)
        assert score == 0.2


class TestOverallConfidence:
    """Test overall confidence calculation."""

    def test_perfect_confidence(self, scorer):
        """Test that perfect scores in all categories give 1.0 confidence."""
        tracker_name = "LEGO_EU_City_Q1_2026"
        api_name = "LEGO_EU_City_Q1_2026"
        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        api_metadata = tracker_metadata.copy()
        timestamp = datetime.utcnow() - timedelta(hours=1)

        result = scorer.calculate_confidence(
            tracker_name, api_name,
            tracker_metadata, api_metadata,
            timestamp
        )

        assert result["confidence_score"] == 1.0
        assert result["metadata_match_score"] == 1.0
        assert result["name_similarity"] == 1.0
        assert result["data_freshness_score"] == 1.0

    def test_weighted_confidence(self, scorer):
        """Test that confidence is properly weighted."""
        # Perfect metadata (50% weight)
        # Perfect name (30% weight)
        # Stale data (20% weight) = 0.2
        tracker_name = "LEGO_EU_City"
        api_name = "LEGO_EU_City"
        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        api_metadata = tracker_metadata.copy()
        timestamp = datetime.utcnow() - timedelta(hours=48)  # Stale

        result = scorer.calculate_confidence(
            tracker_name, api_name,
            tracker_metadata, api_metadata,
            timestamp
        )

        # Expected: 1.0 * 0.5 + 1.0 * 0.3 + 0.2 * 0.2 = 0.84
        assert abs(result["confidence_score"] - 0.84) < 0.01
        assert result["data_freshness_score"] == 0.2

    def test_low_confidence_scenario(self, scorer):
        """Test scenario with low confidence across all dimensions."""
        tracker_name = "LEGO_EU_City_Q1_2026"
        api_name = "LEGO_NA_Friends_Q2_2025"  # Very different
        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        api_metadata = {
            "market": "NA",
            "product": "LEGO_Friends",
            "start_date": "2025-02-01",
            "end_date": "2025-02-28"
        }
        timestamp = datetime.utcnow() - timedelta(days=3)  # Very stale

        result = scorer.calculate_confidence(
            tracker_name, api_name,
            tracker_metadata, api_metadata,
            timestamp
        )

        assert result["confidence_score"] < 0.5
        assert result["metadata_match_score"] == 0.0
        assert result["data_freshness_score"] == 0.2


class TestConfidenceThreshold:
    """Test confidence threshold evaluation."""

    def test_high_confidence(self, scorer):
        """Test that high confidence exceeds default threshold."""
        assert scorer.is_high_confidence(0.9, 0.7) is True
        assert scorer.is_high_confidence(0.7, 0.7) is True  # Exact threshold

    def test_low_confidence(self, scorer):
        """Test that low confidence doesn't exceed threshold."""
        assert scorer.is_high_confidence(0.6, 0.7) is False
        assert scorer.is_high_confidence(0.5, 0.7) is False

    def test_custom_threshold(self, scorer):
        """Test custom confidence threshold."""
        assert scorer.is_high_confidence(0.75, 0.8) is False
        assert scorer.is_high_confidence(0.85, 0.8) is True


class TestLowConfidenceDiagnosis:
    """Test low confidence diagnosis."""

    def test_diagnosis_with_low_metadata(self, scorer):
        """Test diagnosis identifies low metadata match."""
        scores = {
            "confidence_score": 0.5,
            "metadata_match_score": 0.3,
            "name_similarity": 0.9,
            "data_freshness_score": 0.8
        }

        diagnosis = scorer.diagnose_low_confidence(scores, 0.7)
        assert "metadata match" in diagnosis.lower()
        assert "0.3" in diagnosis or "30%" in diagnosis

    def test_diagnosis_with_low_name_similarity(self, scorer):
        """Test diagnosis identifies low name similarity."""
        scores = {
            "confidence_score": 0.5,
            "metadata_match_score": 0.9,
            "name_similarity": 0.3,
            "data_freshness_score": 0.8
        }

        diagnosis = scorer.diagnose_low_confidence(scores, 0.7)
        assert "name similarity" in diagnosis.lower()
        assert "naming conventions" in diagnosis.lower()

    def test_diagnosis_with_stale_data(self, scorer):
        """Test diagnosis identifies stale data."""
        scores = {
            "confidence_score": 0.5,
            "metadata_match_score": 0.9,
            "name_similarity": 0.9,
            "data_freshness_score": 0.3
        }

        diagnosis = scorer.diagnose_low_confidence(scores, 0.7)
        assert "stale" in diagnosis.lower() or "fresh" in diagnosis.lower()

    def test_diagnosis_high_confidence(self, scorer):
        """Test diagnosis for acceptable confidence."""
        scores = {
            "confidence_score": 0.9,
            "metadata_match_score": 0.9,
            "name_similarity": 0.9,
            "data_freshness_score": 0.9
        }

        diagnosis = scorer.diagnose_low_confidence(scores, 0.7)
        assert "acceptable" in diagnosis.lower() or "no issues" in diagnosis.lower()


class TestCustomConfiguration:
    """Test scorer with custom configuration."""

    def test_custom_weights(self, scorer_custom):
        """Test that custom weights are applied."""
        tracker_name = "LEGO_EU_City"
        api_name = "LEGO_EU_City"
        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        api_metadata = tracker_metadata.copy()
        timestamp = datetime.utcnow() - timedelta(hours=1)

        result = scorer_custom.calculate_confidence(
            tracker_name, api_name,
            tracker_metadata, api_metadata,
            timestamp
        )

        # Custom weights: metadata 40%, name 40%, freshness 20%
        # All perfect scores = 1.0 * 0.4 + 1.0 * 0.4 + 1.0 * 0.2 = 1.0
        assert result["confidence_score"] == 1.0

    def test_custom_fields(self):
        """Test scorer with custom required fields."""
        custom_scorer = ConfidenceScorer(required_fields=["market", "product"])

        tracker_metadata = {
            "market": "EU",
            "product": "LEGO_City"
            # Missing start_date and end_date
        }
        api_metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": "2026-01-01",  # Extra fields not required
            "end_date": "2026-01-31"
        }

        score = custom_scorer.calculate_metadata_match(tracker_metadata, api_metadata)
        assert score == 1.0  # Only market and product required, both match

    def test_invalid_weights_raise_error(self):
        """Test that invalid weights raise ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            ConfidenceScorer(
                metadata_weight=0.5,
                name_similarity_weight=0.5,
                freshness_weight=0.5  # Sum = 1.5, invalid
            )


class TestConfigurationExport:
    """Test configuration export."""

    def test_to_dict(self, scorer):
        """Test configuration export."""
        config = scorer.to_dict()

        assert "required_fields" in config
        assert "metadata_weight" in config
        assert "name_similarity_weight" in config
        assert "freshness_weight" in config
        assert config["metadata_weight"] == 0.5
        assert config["name_similarity_weight"] == 0.3
        assert config["freshness_weight"] == 0.2

    def test_to_dict_custom(self, scorer_custom):
        """Test configuration export with custom settings."""
        config = scorer_custom.to_dict()

        assert config["metadata_weight"] == 0.4
        assert config["name_similarity_weight"] == 0.4
        assert config["freshness_weight"] == 0.2
