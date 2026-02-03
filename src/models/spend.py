"""
Data models for media spend tracking and reconciliation.

This module defines the core data structures used throughout the AI Pacing Agent:
- Platform and DataSource enums for type safety
- SpendRecord for individual spend data points
- ReconciledSpend for matched target vs actual spend with confidence scoring
- PacingAlert for agent actions and recommendations
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict


class Platform(Enum):
    """Supported media platforms."""
    GOOGLE = "google"
    META = "meta"
    DV360 = "dv360"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"


class DataSource(Enum):
    """Source of spend data."""
    INTERNAL_TRACKER = "internal_tracker"
    PLATFORM_API = "platform_api"


@dataclass
class SpendRecord:
    """
    Single spend data point from any source.

    Represents either target spend (from internal tracker) or actual spend
    (from platform API) for a specific campaign.
    """
    campaign_id: str
    campaign_name: str
    platform: Platform
    source: DataSource
    amount_usd: float
    timestamp: datetime
    refresh_cycle_hours: int  # 4 for API, 24 for tracker
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def hours_since_update(self) -> float:
        """Calculate hours since last data update."""
        return (datetime.utcnow() - self.timestamp).total_seconds() / 3600

    @property
    def is_stale(self) -> bool:
        """Check if data is stale (older than refresh cycle)."""
        return self.hours_since_update > self.refresh_cycle_hours


@dataclass
class ReconciledSpend:
    """
    Matched target vs actual spend with confidence score.

    Represents a successfully reconciled pair of target (from internal tracker)
    and actual (from platform API) spend data, including data quality metrics.
    """
    campaign_id: str
    campaign_name: str
    platform: Platform
    target_spend: float  # From internal tracker
    actual_spend: float  # From platform API
    target_timestamp: datetime
    actual_timestamp: datetime

    # Data quality metrics (0.0 to 1.0)
    metadata_match_score: float
    name_similarity: float
    data_freshness_score: float

    @property
    def confidence_score(self) -> float:
        """
        Overall confidence in this reconciliation.

        Weighted average:
        - Metadata match: 50%
        - Name similarity: 30%
        - Data freshness: 20%
        """
        return (
            self.metadata_match_score * 0.5 +
            self.name_similarity * 0.3 +
            self.data_freshness_score * 0.2
        )

    @property
    def pacing_variance(self) -> float:
        """
        Percentage variance from target spend.

        Returns:
            Absolute percentage variance (always positive).
            100.0 if target is zero but actual > 0.
            0.0 if both target and actual are zero.
        """
        if self.target_spend == 0:
            return 100.0 if self.actual_spend > 0 else 0.0
        return abs(self.actual_spend - self.target_spend) / self.target_spend * 100

    @property
    def variance_amount(self) -> float:
        """Absolute dollar amount of variance."""
        return abs(self.actual_spend - self.target_spend)

    @property
    def is_overspending(self) -> bool:
        """Check if campaign is spending more than target."""
        return self.actual_spend > self.target_spend

    @property
    def is_underspending(self) -> bool:
        """Check if campaign is spending less than target."""
        return self.actual_spend < self.target_spend and self.actual_spend > 0

    @property
    def is_zero_delivery(self) -> bool:
        """
        Check if campaign has zero spend despite positive target.

        This is a critical condition indicating campaign delivery failure.
        """
        return self.actual_spend == 0 and self.target_spend > 0

    @property
    def spend_direction(self) -> str:
        """Get spending direction as human-readable string."""
        if self.is_zero_delivery:
            return "zero_delivery"
        elif self.is_overspending:
            return "overspending"
        elif self.is_underspending:
            return "underspending"
        else:
            return "on_target"

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "platform": self.platform.value,
            "target_spend": self.target_spend,
            "actual_spend": self.actual_spend,
            "variance_pct": self.pacing_variance,
            "variance_amount": self.variance_amount,
            "confidence_score": self.confidence_score,
            "is_overspending": self.is_overspending,
            "is_zero_delivery": self.is_zero_delivery,
            "spend_direction": self.spend_direction,
            "target_timestamp": self.target_timestamp.isoformat(),
            "actual_timestamp": self.actual_timestamp.isoformat(),
        }


@dataclass
class PacingAlert:
    """
    Alert/action generated by the agent.

    Represents the final output of the PacingBrain agent's decision-making process,
    including the action taken, recommendations, and analysis.
    """
    alert_id: str
    campaign_id: str
    severity: str  # "healthy", "warning", "critical"
    variance_pct: float
    confidence_score: float
    action_taken: str  # "log_only", "slack_alert", "autonomous_halt", "escalated_to_human"
    recommendation: str
    requires_human: bool
    timestamp: datetime
    root_cause_analysis: Optional[str] = None
    mitigation_plan: Optional[str] = None
    metadata: Dict[str, any] = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical alert."""
        return self.severity == "critical"

    @property
    def is_autonomous_action(self) -> bool:
        """Check if agent took autonomous action (not just alerting)."""
        return self.action_taken == "autonomous_halt"

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "campaign_id": self.campaign_id,
            "severity": self.severity,
            "variance_pct": self.variance_pct,
            "confidence_score": self.confidence_score,
            "action_taken": self.action_taken,
            "recommendation": self.recommendation,
            "requires_human": self.requires_human,
            "timestamp": self.timestamp.isoformat(),
            "root_cause_analysis": self.root_cause_analysis,
            "mitigation_plan": self.mitigation_plan,
            "metadata": self.metadata,
            "is_critical": self.is_critical,
            "is_autonomous_action": self.is_autonomous_action,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"PacingAlert(id={self.alert_id}, "
            f"campaign={self.campaign_id}, "
            f"severity={self.severity}, "
            f"variance={self.variance_pct:.1f}%, "
            f"action={self.action_taken})"
        )
