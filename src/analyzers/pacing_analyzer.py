"""
Pacing variance analyzer for anomaly detection.

This module implements the core anomaly detection logic that classifies
campaign pacing variance into severity levels and generates recommendations.
"""

from typing import Dict, Any
from src.models.spend import ReconciledSpend


class PacingAnalyzer:
    """
    Core anomaly detection logic for media pacing.

    Classifies variance into three severity levels:
    - Healthy: < 10% variance from target
    - Warning: 10-25% variance from target
    - Critical: > 25% variance or zero delivery
    """

    # Variance thresholds (percentage)
    HEALTHY_THRESHOLD = 10.0  # < 10% variance
    WARNING_THRESHOLD = 25.0  # 10-25% variance
    CRITICAL_THRESHOLD = 25.0  # > 25% variance

    def __init__(
        self,
        healthy_threshold: float = HEALTHY_THRESHOLD,
        warning_threshold: float = WARNING_THRESHOLD
    ):
        """
        Initialize analyzer with configurable thresholds.

        Args:
            healthy_threshold: Maximum variance % for healthy classification
            warning_threshold: Maximum variance % for warning classification
                              (above this is critical)
        """
        self.healthy_threshold = healthy_threshold
        self.warning_threshold = warning_threshold

    def calculate_variance(self, reconciled: ReconciledSpend) -> Dict[str, Any]:
        """
        Calculate pacing variance and classify severity.

        Args:
            reconciled: Reconciled spend data with target and actual spend

        Returns:
            Dictionary containing:
            - variance_pct: Percentage variance from target
            - variance_amount: Dollar amount of variance
            - severity: "healthy" | "warning" | "critical"
            - is_zero_delivery: Boolean flag
            - confidence: Confidence score from reconciliation
            - spend_direction: "overspending" | "underspending" | "zero_delivery" | "on_target"
            - reason: Human-readable reason for classification
        """
        variance = reconciled.pacing_variance
        confidence = reconciled.confidence_score

        # Zero delivery is always critical
        if reconciled.is_zero_delivery:
            return {
                "variance_pct": 100.0,
                "variance_amount": reconciled.target_spend,
                "severity": "critical",
                "is_zero_delivery": True,
                "confidence": confidence,
                "spend_direction": "zero_delivery",
                "reason": "Zero spend detected despite positive target"
            }

        # Classify based on variance thresholds
        if variance < self.healthy_threshold:
            severity = "healthy"
            reason = "Variance within acceptable range"
        elif variance < self.warning_threshold:
            severity = "warning"
            reason = "Variance exceeds healthy threshold but below critical"
        else:
            severity = "critical"
            reason = "Variance exceeds critical threshold"

        return {
            "variance_pct": variance,
            "variance_amount": reconciled.variance_amount,
            "severity": severity,
            "is_zero_delivery": False,
            "confidence": confidence,
            "spend_direction": reconciled.spend_direction,
            "is_overspending": reconciled.is_overspending,
            "reason": reason
        }

    def generate_recommendation(
        self,
        variance_result: Dict[str, Any],
        reconciled: ReconciledSpend
    ) -> str:
        """
        Generate human-readable recommendation based on variance analysis.

        Args:
            variance_result: Output from calculate_variance()
            reconciled: Reconciled spend data

        Returns:
            Formatted recommendation string with emoji and actionable advice
        """
        severity = variance_result["severity"]
        variance = variance_result["variance_pct"]
        variance_amount = variance_result["variance_amount"]

        # Healthy status
        if severity == "healthy":
            return (
                f"✅ Campaign pacing is healthy ({variance:.1f}% variance). "
                f"No action required."
            )

        # Determine spending direction
        direction = variance_result["spend_direction"]
        direction_text = {
            "overspending": "overspending",
            "underspending": "underspending",
            "zero_delivery": "has zero delivery",
            "on_target": "on target"
        }.get(direction, direction)

        # Warning level
        if severity == "warning":
            action = self._generate_warning_action(
                reconciled, variance_amount, direction
            )
            return (
                f"⚠️ Campaign is {direction_text} by {variance:.1f}% "
                f"(${variance_amount:,.2f}).\n"
                f"Recommended action: {action}"
            )

        # Critical level
        if variance_result["is_zero_delivery"]:
            return self._generate_zero_delivery_recommendation(reconciled)

        # Critical overspend/underspend
        action = self._generate_critical_action(
            reconciled, variance_amount, direction
        )
        return (
            f"🚨 CRITICAL: Campaign is {direction_text} by {variance:.1f}% "
            f"(${variance_amount:,.2f}).\n"
            f"Immediate action required: {action}"
        )

    def _generate_warning_action(
        self,
        reconciled: ReconciledSpend,
        variance_amount: float,
        direction: str
    ) -> str:
        """Generate action recommendation for warning-level variance."""
        if direction == "overspending":
            return (
                f"Review targeting parameters and reduce daily budget by "
                f"${variance_amount:.2f} to align with target. "
                f"Monitor closely for next 24 hours."
            )
        elif direction == "underspending":
            return (
                f"Investigate delivery issues. Consider increasing bid amounts "
                f"or expanding audience targeting. Target spend increase: "
                f"${variance_amount:.2f}."
            )
        else:
            return "Review campaign settings and pacing parameters."

    def _generate_critical_action(
        self,
        reconciled: ReconciledSpend,
        variance_amount: float,
        direction: str
    ) -> str:
        """Generate action recommendation for critical-level variance."""
        if direction == "overspending":
            return (
                f"Pause campaign immediately to prevent further overspend. "
                f"Redistribute ${variance_amount:.2f} budget to other campaigns. "
                f"Investigate root cause before resuming."
            )
        elif direction == "underspending":
            return (
                f"Campaign severely underdelivering. Pause and conduct "
                f"diagnostic review of: audience size, bid strategy, "
                f"creative approval status, budget allocation. "
                f"Consider reallocating ${variance_amount:.2f} to "
                f"higher-performing campaigns."
            )
        else:
            return "Immediate review and corrective action required."

    def _generate_zero_delivery_recommendation(
        self,
        reconciled: ReconciledSpend
    ) -> str:
        """Generate recommendation for zero delivery scenario."""
        return (
            f"🚨 ZERO DELIVERY DETECTED\n\n"
            f"Campaign: {reconciled.campaign_name}\n"
            f"Target spend: ${reconciled.target_spend:,.2f}\n"
            f"Actual spend: $0.00\n\n"
            f"Possible causes:\n"
            f"• Campaign or ad sets are paused\n"
            f"• Audience size depleted or too narrow\n"
            f"• Bid amount too low to compete\n"
            f"• Budget already exhausted\n"
            f"• Creative pending approval\n"
            f"• Placement restrictions blocking delivery\n\n"
            f"Immediate actions:\n"
            f"1. Check campaign status (active/paused)\n"
            f"2. Review audience size and targeting\n"
            f"3. Increase bid by 20-30%\n"
            f"4. Verify budget allocation\n"
            f"5. Check creative approval status"
        )

    def classify_severity(self, variance_pct: float, is_zero_delivery: bool = False) -> str:
        """
        Classify variance into severity level.

        Args:
            variance_pct: Percentage variance from target
            is_zero_delivery: Whether campaign has zero delivery

        Returns:
            "healthy" | "warning" | "critical"
        """
        if is_zero_delivery:
            return "critical"

        if variance_pct < self.healthy_threshold:
            return "healthy"
        elif variance_pct < self.warning_threshold:
            return "warning"
        else:
            return "critical"

    def is_actionable(self, severity: str) -> bool:
        """
        Check if severity level requires action beyond logging.

        Args:
            severity: Severity level

        Returns:
            True if warning or critical (requires alert/action)
        """
        return severity in ["warning", "critical"]

    def requires_autonomous_action(
        self,
        severity: str,
        confidence_score: float,
        confidence_threshold: float = 0.7
    ) -> bool:
        """
        Determine if agent should take autonomous action.

        Args:
            severity: Severity level
            confidence_score: Data quality confidence score
            confidence_threshold: Minimum confidence for autonomous action

        Returns:
            True if critical severity with sufficient confidence
        """
        return (
            severity == "critical" and
            confidence_score >= confidence_threshold
        )

    def to_dict(self) -> Dict[str, float]:
        """Export analyzer configuration."""
        return {
            "healthy_threshold": self.healthy_threshold,
            "warning_threshold": self.warning_threshold,
        }
