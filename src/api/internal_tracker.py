"""
Mock Internal Spend Tracker.

Simulates the internal tracking system that stores target spend data
for campaigns. In production, this would query a database or data warehouse.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Optional
from src.models.spend import Platform, DataSource, SpendRecord


class MockInternalTracker:
    """
    Simulated internal spend tracker.

    Stores target spend data with metadata for campaign reconciliation.
    Simulates daily refresh cycle (24 hours) typical of internal systems.
    """

    def __init__(self, target_data: Optional[Dict[str, Dict]] = None):
        """
        Initialize internal tracker with optional target data.

        Args:
            target_data: Optional dictionary mapping campaign_id to target info.
                        If None, generates targets dynamically based on campaign_id.
        """
        self.target_data = target_data or {}

    def get_target_spend(self, campaign_id: str) -> SpendRecord:
        """
        Fetch target spend from internal tracker.

        Args:
            campaign_id: Campaign identifier (should match platform API ID)

        Returns:
            SpendRecord with target spend data

        Raises:
            ValueError: If campaign not found and can't be inferred
        """
        # If we have explicit target data, use it
        if campaign_id in self.target_data:
            data = self.target_data[campaign_id]
            return self._create_spend_record(campaign_id, data)

        # Otherwise, generate target dynamically based on campaign_id
        return self._generate_target_from_id(campaign_id)

    def _create_spend_record(
        self,
        campaign_id: str,
        data: Dict
    ) -> SpendRecord:
        """
        Create SpendRecord from target data dictionary.

        Args:
            campaign_id: Campaign identifier
            data: Dictionary with target_spend and metadata

        Returns:
            SpendRecord object
        """
        # Tracker updates daily (24-hour refresh cycle)
        # Simulate data that's 6-18 hours old
        timestamp = datetime.utcnow() - timedelta(hours=data.get("hours_old", 12))

        return SpendRecord(
            campaign_id=campaign_id,
            campaign_name=data.get("campaign_name", campaign_id.replace("_", " ").title()),
            platform=Platform(data.get("platform", self._infer_platform(campaign_id))),
            source=DataSource.INTERNAL_TRACKER,
            amount_usd=data["target_spend"],
            timestamp=timestamp,
            refresh_cycle_hours=24,  # Daily refresh
            metadata=data.get("metadata", {})
        )

    def _generate_target_from_id(self, campaign_id: str) -> SpendRecord:
        """
        Generate target spend dynamically based on campaign ID.

        Used when explicit target data isn't provided. Extracts metadata
        from campaign ID structure (platform_index format).

        Args:
            campaign_id: Campaign identifier (e.g., "google_001")

        Returns:
            SpendRecord with generated target
        """
        # Parse campaign ID to extract platform
        platform_str = campaign_id.split("_")[0]

        try:
            platform = Platform(platform_str)
        except ValueError:
            raise ValueError(
                f"Cannot infer platform from campaign_id: {campaign_id}. "
                f"Expected format: platform_index (e.g., 'google_001')"
            )

        # Generate deterministic target based on campaign index
        # This ensures consistency across multiple calls
        index = int(campaign_id.split("_")[1]) if "_" in campaign_id else 0
        base_target = 5000  # Base spend
        target = base_target + (index * 500)  # Vary by index

        # Generate metadata (simplified version)
        metadata = {
            "market": "EU",
            "product": "LEGO_City",
            "start_date": (datetime.utcnow() - timedelta(days=14)).strftime("%Y-%m-%d"),
            "end_date": (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d"),
        }

        # Tracker data is typically 12 hours old (daily refresh, queried mid-day)
        timestamp = datetime.utcnow() - timedelta(hours=12)

        return SpendRecord(
            campaign_id=campaign_id,
            campaign_name=campaign_id.replace("_", " ").title(),
            platform=platform,
            source=DataSource.INTERNAL_TRACKER,
            amount_usd=target,
            timestamp=timestamp,
            refresh_cycle_hours=24,
            metadata=metadata
        )

    def _infer_platform(self, campaign_id: str) -> str:
        """
        Infer platform from campaign ID.

        Args:
            campaign_id: Campaign identifier

        Returns:
            Platform string
        """
        if "google" in campaign_id.lower():
            return "google"
        elif "meta" in campaign_id.lower():
            return "meta"
        elif "dv360" in campaign_id.lower():
            return "dv360"
        else:
            return "google"  # Default

    def set_target(
        self,
        campaign_id: str,
        target_spend: float,
        metadata: Optional[Dict] = None,
        platform: Optional[Platform] = None
    ):
        """
        Set target spend for a campaign.

        Useful for test scenarios where you want to control exact targets.

        Args:
            campaign_id: Campaign identifier
            target_spend: Target spend amount in USD
            metadata: Optional metadata dictionary
            platform: Optional platform enum
        """
        self.target_data[campaign_id] = {
            "target_spend": target_spend,
            "metadata": metadata or {},
            "platform": platform.value if platform else self._infer_platform(campaign_id),
            "hours_old": 12,  # Default to 12 hours old
        }

    def bulk_set_targets(self, targets: Dict[str, float]):
        """
        Set multiple targets at once.

        Args:
            targets: Dictionary mapping campaign_id to target_spend
        """
        for campaign_id, target_spend in targets.items():
            self.set_target(campaign_id, target_spend)

    def sync_from_platform(self, platform_api, dirty_ratio: float = 0.15, seed: Optional[int] = None):
        """
        Populate tracker targets from platform API campaign data.

        Simulates a real-world scenario where the internal tracker and platform
        API share the same campaign catalog. A configurable dirty_ratio introduces
        mismatches (wrong name or metadata) for a subset of campaigns, causing
        low confidence scores and human escalation — demonstrating safety guardrails.

        Args:
            platform_api: MockPlatformAPI instance to sync from
            dirty_ratio: Fraction of campaigns with intentional mismatches (default 0.15)
            seed: Optional random seed for reproducibility of dirty selection
        """
        if seed is not None:
            rng = random.Random(seed)
        else:
            rng = random.Random()

        for campaign in platform_api.campaigns:
            campaign_id = campaign["campaign_id"]
            is_dirty = rng.random() < dirty_ratio

            if is_dirty:
                # Introduce mismatches to simulate data quality issues
                dirty_name = rng.choice([
                    f"Unknown_Campaign_{campaign_id.split('_')[-1]}",
                    f"Legacy_Import_{rng.randint(1000, 9999)}",
                    f"Unmatched_{campaign['metadata']['platform']}_{rng.randint(100, 999)}",
                ])
                dirty_metadata = {
                    "market": rng.choice(["LATAM", "MEA", "CIS"]),
                    "product": rng.choice(["LEGO_Duplo", "LEGO_Ninjago", "LEGO_Creator"]),
                    "start_date": "2025-01-01",
                    "end_date": "2025-03-31",
                }
                self.target_data[campaign_id] = {
                    "target_spend": campaign["target"],
                    "campaign_name": dirty_name,
                    "metadata": dirty_metadata,
                    "platform": campaign["metadata"]["platform"],
                    "hours_old": 12,
                }
            else:
                # Clean sync: same name (with optional minor variation) and metadata
                name = campaign["campaign_name"]
                if rng.random() < 0.3:
                    # Minor variation: swap underscores/spaces or change case
                    name = name.replace("_", " ") if "_" in name else name.replace(" ", "_")

                self.target_data[campaign_id] = {
                    "target_spend": campaign["target"],
                    "campaign_name": name,
                    "metadata": dict(campaign["metadata"]),
                    "platform": campaign["metadata"]["platform"],
                    "hours_old": rng.uniform(6, 18),
                }

    def get_all_campaign_ids(self) -> list:
        """
        Get all campaign IDs in the tracker.

        Returns:
            List of campaign ID strings
        """
        return list(self.target_data.keys())

    def has_campaign(self, campaign_id: str) -> bool:
        """
        Check if campaign exists in tracker.

        Args:
            campaign_id: Campaign identifier

        Returns:
            True if campaign exists
        """
        return campaign_id in self.target_data

    def get_summary(self) -> Dict[str, any]:
        """
        Get summary statistics for all tracked campaigns.

        Returns:
            Dictionary with aggregated stats
        """
        if not self.target_data:
            return {
                "total_campaigns": 0,
                "total_target_spend": 0.0,
            }

        total_target = sum(d["target_spend"] for d in self.target_data.values())

        return {
            "total_campaigns": len(self.target_data),
            "total_target_spend": total_target,
            "average_target_spend": total_target / len(self.target_data),
            "campaign_ids": list(self.target_data.keys()),
        }
