"""
Confidence scorer for data quality assessment.

This module calculates confidence scores for spend reconciliation based on:
- Metadata field matching between tracker and platform API
- Campaign name similarity using Levenshtein distance
- Data freshness (time since last update)
"""

from datetime import datetime
from typing import Dict
from Levenshtein import distance as levenshtein_distance


class ConfidenceScorer:
    """
    Calculate data quality confidence scores for reconciled spend.

    Confidence is a weighted average of:
    - Metadata match (50%): Matching fields like market, product, date range
    - Name similarity (30%): Levenshtein distance between campaign names
    - Data freshness (20%): Penalty for stale data

    Higher confidence (closer to 1.0) indicates higher quality reconciliation.
    """

    # Weights for confidence calculation
    METADATA_WEIGHT = 0.5
    NAME_SIMILARITY_WEIGHT = 0.3
    FRESHNESS_WEIGHT = 0.2

    # Required metadata fields for matching
    REQUIRED_FIELDS = ["market", "product", "start_date", "end_date"]

    def __init__(
        self,
        required_fields: list = None,
        metadata_weight: float = METADATA_WEIGHT,
        name_similarity_weight: float = NAME_SIMILARITY_WEIGHT,
        freshness_weight: float = FRESHNESS_WEIGHT
    ):
        """
        Initialize confidence scorer with configurable weights.

        Args:
            required_fields: List of metadata fields to check for matching
            metadata_weight: Weight for metadata matching (default 0.5)
            name_similarity_weight: Weight for name similarity (default 0.3)
            freshness_weight: Weight for data freshness (default 0.2)
        """
        self.required_fields = required_fields or self.REQUIRED_FIELDS
        self.metadata_weight = metadata_weight
        self.name_similarity_weight = name_similarity_weight
        self.freshness_weight = freshness_weight

        # Validate weights sum to 1.0
        total_weight = metadata_weight + name_similarity_weight + freshness_weight
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0, got {total_weight}. "
                f"Adjust metadata_weight ({metadata_weight}), "
                f"name_similarity_weight ({name_similarity_weight}), "
                f"and freshness_weight ({freshness_weight})."
            )

    def calculate_confidence(
        self,
        tracker_name: str,
        api_name: str,
        tracker_metadata: Dict[str, str],
        api_metadata: Dict[str, str],
        actual_timestamp: datetime
    ) -> Dict[str, float]:
        """
        Calculate overall confidence score and component scores.

        Args:
            tracker_name: Campaign name from internal tracker
            api_name: Campaign name from platform API
            tracker_metadata: Metadata dict from tracker
            api_metadata: Metadata dict from API
            actual_timestamp: Timestamp of actual spend data

        Returns:
            Dictionary with:
            - confidence_score: Overall confidence (0.0 to 1.0)
            - metadata_match_score: Metadata matching score
            - name_similarity: Name similarity score
            - data_freshness_score: Freshness score
        """
        metadata_score = self.calculate_metadata_match(
            tracker_metadata, api_metadata
        )
        name_score = self.calculate_name_similarity(tracker_name, api_name)
        freshness_score = self.calculate_freshness(actual_timestamp)

        confidence = (
            metadata_score * self.metadata_weight +
            name_score * self.name_similarity_weight +
            freshness_score * self.freshness_weight
        )

        return {
            "confidence_score": confidence,
            "metadata_match_score": metadata_score,
            "name_similarity": name_score,
            "data_freshness_score": freshness_score
        }

    def calculate_metadata_match(
        self,
        tracker_metadata: Dict[str, str],
        api_metadata: Dict[str, str]
    ) -> float:
        """
        Compare metadata fields between tracker and API.

        Checks for exact matches on required fields:
        - market: Market name (e.g., "EU", "NA", "APAC")
        - product: Product category (e.g., "LEGO_City", "LEGO_Friends")
        - start_date: Campaign start date
        - end_date: Campaign end date

        Args:
            tracker_metadata: Metadata from internal tracker
            api_metadata: Metadata from platform API

        Returns:
            Score from 0.0 (no matches) to 1.0 (all fields match)
        """
        if not self.required_fields:
            return 1.0  # No fields to check, perfect match

        matched = 0
        total = len(self.required_fields)

        for field in self.required_fields:
            tracker_value = tracker_metadata.get(field)
            api_value = api_metadata.get(field)

            # Both must exist and match
            if (
                tracker_value is not None and
                api_value is not None and
                str(tracker_value).lower() == str(api_value).lower()
            ):
                matched += 1

        return matched / total if total > 0 else 0.0

    def calculate_name_similarity(
        self,
        tracker_name: str,
        api_name: str
    ) -> float:
        """
        Calculate campaign name similarity using Levenshtein distance.

        This handles naming variations, typos, and minor formatting differences
        between internal tracker and platform API campaign names.

        Args:
            tracker_name: Campaign name from tracker
            api_name: Campaign name from API

        Returns:
            Similarity score from 0.0 (completely different) to 1.0 (identical)
        """
        if not tracker_name or not api_name:
            return 0.0

        # Normalize for comparison (lowercase, strip whitespace)
        tracker_normalized = tracker_name.lower().strip()
        api_normalized = api_name.lower().strip()

        # Handle identical match
        if tracker_normalized == api_normalized:
            return 1.0

        # Calculate Levenshtein distance
        max_len = max(len(tracker_normalized), len(api_normalized))
        if max_len == 0:
            return 1.0

        edit_distance = levenshtein_distance(tracker_normalized, api_normalized)

        # Convert distance to similarity score
        # Similarity = 1 - (edit_distance / max_length)
        similarity = 1.0 - (edit_distance / max_len)

        return max(0.0, similarity)  # Ensure non-negative

    def calculate_freshness(self, timestamp: datetime) -> float:
        """
        Calculate freshness score based on data age.

        Penalize stale data based on time since last update:
        - < 4 hours: 1.0 (perfect freshness)
        - 4-12 hours: 0.8 (good)
        - 12-24 hours: 0.5 (acceptable)
        - > 24 hours: 0.2 (stale)

        Args:
            timestamp: Timestamp of the data

        Returns:
            Freshness score from 0.2 (very stale) to 1.0 (fresh)
        """
        hours_old = (datetime.utcnow() - timestamp).total_seconds() / 3600

        if hours_old < 4:
            return 1.0
        elif hours_old < 12:
            return 0.8
        elif hours_old < 24:
            return 0.5
        else:
            return 0.2

    def is_high_confidence(
        self,
        confidence_score: float,
        threshold: float = 0.7
    ) -> bool:
        """
        Check if confidence score exceeds threshold for autonomous action.

        Args:
            confidence_score: Overall confidence score
            threshold: Minimum confidence threshold (default 0.7 = 70%)

        Returns:
            True if confidence exceeds threshold
        """
        return confidence_score >= threshold

    def explain_confidence(
        self,
        tracker_name: str,
        api_name: str,
        tracker_metadata: Dict[str, str],
        api_metadata: Dict[str, str],
        actual_timestamp: datetime,
        scores: Dict[str, float]
    ) -> Dict[str, dict]:
        """
        Generate human-readable explanations for each confidence component.

        Args:
            tracker_name: Campaign name from internal tracker
            api_name: Campaign name from platform API
            tracker_metadata: Metadata dict from tracker
            api_metadata: Metadata dict from API
            actual_timestamp: Timestamp of actual spend data
            scores: Dictionary with component scores from calculate_confidence()

        Returns:
            Dictionary with explanation details for each component:
            - metadata: matched/mismatched fields breakdown
            - name_similarity: edit distance and character counts
            - data_freshness: data age, tier label, and timestamp
        """
        # --- Metadata explanation ---
        matched_fields = []
        mismatched_fields = []
        for field in self.required_fields:
            tracker_val = tracker_metadata.get(field)
            api_val = api_metadata.get(field)
            if (
                tracker_val is not None
                and api_val is not None
                and str(tracker_val).lower() == str(api_val).lower()
            ):
                matched_fields.append(field)
            else:
                mismatched_fields.append({
                    "field": field,
                    "tracker_value": str(tracker_val) if tracker_val is not None else "missing",
                    "api_value": str(api_val) if api_val is not None else "missing",
                })

        metadata_explanation = {
            "score": scores["metadata_match_score"],
            "matched_count": len(matched_fields),
            "total_count": len(self.required_fields),
            "matched_fields": matched_fields,
            "mismatched_fields": mismatched_fields,
            "summary": (
                f"{len(matched_fields)} of {len(self.required_fields)} fields match"
                if self.required_fields
                else "No fields to check"
            ),
        }

        # --- Name similarity explanation ---
        tracker_norm = (tracker_name or "").lower().strip()
        api_norm = (api_name or "").lower().strip()
        if tracker_norm and api_norm:
            edit_dist = levenshtein_distance(tracker_norm, api_norm)
            max_len = max(len(tracker_norm), len(api_norm))
        else:
            edit_dist = 0
            max_len = 0

        name_explanation = {
            "score": scores["name_similarity"],
            "edit_distance": edit_dist,
            "tracker_length": len(tracker_norm),
            "api_length": len(api_norm),
            "summary": (
                "Identical names"
                if edit_dist == 0 and max_len > 0
                else f"Edit distance: {edit_dist} character(s) across {max_len}-char names"
            ),
        }

        # --- Data freshness explanation ---
        hours_old = (datetime.utcnow() - actual_timestamp).total_seconds() / 3600

        if hours_old < 4:
            tier_label = "Fresh"
            tier_range = "< 4 hours"
        elif hours_old < 12:
            tier_label = "Good"
            tier_range = "4–12 hours"
        elif hours_old < 24:
            tier_label = "Acceptable"
            tier_range = "12–24 hours"
        else:
            tier_label = "Stale"
            tier_range = "> 24 hours"

        freshness_explanation = {
            "score": scores["data_freshness_score"],
            "hours_old": round(hours_old, 1),
            "tier_label": tier_label,
            "tier_range": tier_range,
            "last_updated": actual_timestamp.strftime("%Y-%m-%d %H:%M UTC"),
            "summary": (
                f"Data is {hours_old:.1f}h old — {tier_label} ({tier_range})"
            ),
        }

        return {
            "metadata": metadata_explanation,
            "name_similarity": name_explanation,
            "data_freshness": freshness_explanation,
        }

    def diagnose_low_confidence(
        self,
        scores: Dict[str, float],
        threshold: float = 0.7
    ) -> str:
        """
        Diagnose why confidence is low and suggest improvements.

        Args:
            scores: Dictionary with component scores from calculate_confidence()
            threshold: Confidence threshold

        Returns:
            Human-readable diagnosis with improvement suggestions
        """
        confidence = scores["confidence_score"]
        if confidence >= threshold:
            return "Confidence is acceptable. No issues detected."

        issues = []

        # Check metadata matching
        if scores["metadata_match_score"] < 0.8:
            issues.append(
                f"- Low metadata match ({scores['metadata_match_score']:.1%}). "
                f"Verify campaign fields: {', '.join(self.required_fields)}"
            )

        # Check name similarity
        if scores["name_similarity"] < 0.8:
            issues.append(
                f"- Low name similarity ({scores['name_similarity']:.1%}). "
                f"Campaign names differ significantly between tracker and API. "
                f"Standardize naming conventions."
            )

        # Check freshness
        if scores["data_freshness_score"] < 0.8:
            if scores["data_freshness_score"] < 0.5:
                issues.append(
                    f"- Stale data ({scores['data_freshness_score']:.1%}). "
                    f"Data is >12 hours old. Increase refresh frequency."
                )
            else:
                issues.append(
                    f"- Moderately stale data ({scores['data_freshness_score']:.1%}). "
                    f"Data is 4-12 hours old."
                )

        if not issues:
            issues.append("- Confidence below threshold but no specific issues identified.")

        diagnosis = (
            f"Confidence score: {confidence:.1%} (threshold: {threshold:.1%})\n\n"
            f"Issues detected:\n" + "\n".join(issues)
        )

        return diagnosis

    def to_dict(self) -> Dict[str, any]:
        """Export scorer configuration."""
        return {
            "required_fields": self.required_fields,
            "metadata_weight": self.metadata_weight,
            "name_similarity_weight": self.name_similarity_weight,
            "freshness_weight": self.freshness_weight,
        }
