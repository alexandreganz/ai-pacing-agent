"""
Mock Platform API for Google and Meta.

Simulates realistic platform API responses with various variance scenarios
for testing the pacing agent without requiring real API credentials.
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.models.spend import Platform, DataSource, SpendRecord


class MockPlatformAPI:
    """
    Simulated platform API with realistic behavior.

    Generates mock campaigns with varying spend patterns:
    - Healthy campaigns (variance < 10%)
    - Warning-level campaigns (variance 10-25%)
    - Critical campaigns (variance > 25%)
    - Zero delivery campaigns (actual spend = 0)
    """

    # Variance factor distributions
    VARIANCE_SCENARIOS = {
        "healthy": [0.92, 0.95, 0.97, 1.00, 1.03, 1.05, 1.08],  # -8% to +8%
        "warning_under": [0.75, 0.78, 0.82],  # -25% to -18%
        "warning_over": [1.18, 1.22, 1.25],  # +18% to +25%
        "critical_under": [0.50, 0.60, 0.70],  # -50% to -30%
        "critical_over": [1.35, 1.45, 1.60, 1.80],  # +35% to +80%
        "zero_delivery": [0.0],  # Zero spend
    }

    def __init__(self, platform: Platform, num_campaigns: int = 10, seed: Optional[int] = None):
        """
        Initialize mock API for a specific platform.

        Args:
            platform: Platform enum (GOOGLE, META, etc.)
            num_campaigns: Number of mock campaigns to generate
            seed: Random seed for reproducibility
        """
        self.platform = platform
        self.num_campaigns = num_campaigns

        if seed is not None:
            random.seed(seed)

        self.campaigns = self._generate_mock_campaigns()

    def _generate_mock_campaigns(self) -> List[Dict]:
        """
        Generate realistic campaign data with various spend patterns.

        Returns:
            List of campaign dictionaries with spend, metadata, and status
        """
        campaigns = []

        # Distribution of scenarios (adjust for testing needs)
        scenario_distribution = (
            ["healthy"] * 4 +  # 40% healthy
            ["warning_under", "warning_over"] * 2 +  # 40% warning
            ["critical_under", "critical_over"] +  # 20% critical
            ["zero_delivery"]  # 10% zero delivery
        )

        for i in range(self.num_campaigns):
            # Select variance scenario
            scenario = random.choice(scenario_distribution)
            variance_factor = random.choice(self.VARIANCE_SCENARIOS[scenario])

            # Generate target and actual spend
            target = random.uniform(1000, 15000)
            actual = target * variance_factor

            # Generate realistic metadata
            market = random.choice(["EU", "NA", "APAC"])
            product = random.choice([
                "LEGO_City", "LEGO_Friends", "LEGO_Technic",
                "LEGO_StarWars", "LEGO_Harry_Potter"
            ])

            # Campaign start/end dates
            start_date = datetime.utcnow() - timedelta(days=random.randint(7, 30))
            end_date = start_date + timedelta(days=random.randint(14, 60))

            # Determine status
            status = "active" if actual > 0 else "paused"

            # Last updated (simulate API refresh cycle of 4 hours)
            last_updated = datetime.utcnow() - timedelta(
                hours=random.randint(1, 8)
            )

            campaigns.append({
                "campaign_id": f"{self.platform.value}_{i:03d}",
                "campaign_name": self._generate_campaign_name(market, product, i),
                "spend": actual,
                "target": target,
                "status": status,
                "last_updated": last_updated,
                "metadata": {
                    "market": market,
                    "product": product,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "platform": self.platform.value,
                },
                "scenario": scenario,  # For testing/debugging
            })

        return campaigns

    def _generate_campaign_name(self, market: str, product: str, index: int) -> str:
        """
        Generate realistic campaign name with LEGO naming conventions.

        Args:
            market: Market identifier (EU, NA, APAC)
            product: Product line
            index: Campaign index

        Returns:
            Campaign name string
        """
        quarter = f"Q{random.randint(1, 4)}"
        year = "2026"
        channel = random.choice(["Search", "Display", "Video", "Social"])

        # Sometimes add variation for testing name similarity
        if random.random() < 0.2:
            # Add typo or variation
            product = product.replace("_", " ")  # "LEGO City" vs "LEGO_City"

        return f"LEGO_{market}_{product}_{quarter}_{year}_{channel}_{index:03d}"

    def get_campaign_spend(self, campaign_id: str) -> SpendRecord:
        """
        Fetch spend for a specific campaign.

        Args:
            campaign_id: Unique campaign identifier

        Returns:
            SpendRecord with actual spend data

        Raises:
            ValueError: If campaign not found
        """
        campaign = next(
            (c for c in self.campaigns if c["campaign_id"] == campaign_id),
            None
        )

        if not campaign:
            raise ValueError(
                f"Campaign {campaign_id} not found in {self.platform.value} platform"
            )

        return SpendRecord(
            campaign_id=campaign["campaign_id"],
            campaign_name=campaign["campaign_name"],
            platform=self.platform,
            source=DataSource.PLATFORM_API,
            amount_usd=campaign["spend"],
            timestamp=campaign["last_updated"],
            refresh_cycle_hours=4,  # Platform APIs refresh every 4 hours
            metadata=campaign["metadata"]
        )

    def get_all_campaigns(self) -> List[SpendRecord]:
        """
        Fetch spend for all campaigns.

        Returns:
            List of SpendRecord objects
        """
        return [
            self.get_campaign_spend(c["campaign_id"])
            for c in self.campaigns
        ]

    def pause_campaign(self, campaign_id: str) -> bool:
        """
        Pause a campaign (mock action).

        In a real implementation, this would call the platform API to
        pause the campaign. For testing, we just update the status.

        Args:
            campaign_id: Unique campaign identifier

        Returns:
            True if successfully paused, False if not found
        """
        campaign = next(
            (c for c in self.campaigns if c["campaign_id"] == campaign_id),
            None
        )

        if campaign:
            campaign["status"] = "paused"
            print(
                f"✅ [MOCK] Paused campaign {campaign_id} on {self.platform.value.upper()}"
            )
            return True

        print(f"❌ [MOCK] Campaign {campaign_id} not found on {self.platform.value.upper()}")
        return False

    def resume_campaign(self, campaign_id: str) -> bool:
        """
        Resume a paused campaign (mock action).

        Args:
            campaign_id: Unique campaign identifier

        Returns:
            True if successfully resumed, False if not found
        """
        campaign = next(
            (c for c in self.campaigns if c["campaign_id"] == campaign_id),
            None
        )

        if campaign:
            campaign["status"] = "active"
            print(
                f"✅ [MOCK] Resumed campaign {campaign_id} on {self.platform.value.upper()}"
            )
            return True

        print(f"❌ [MOCK] Campaign {campaign_id} not found on {self.platform.value.upper()}")
        return False

    def get_campaign_status(self, campaign_id: str) -> Optional[str]:
        """
        Get current status of a campaign.

        Args:
            campaign_id: Unique campaign identifier

        Returns:
            Status string ("active" or "paused") or None if not found
        """
        campaign = next(
            (c for c in self.campaigns if c["campaign_id"] == campaign_id),
            None
        )
        return campaign["status"] if campaign else None

    def list_campaign_ids(self) -> List[str]:
        """
        List all campaign IDs.

        Returns:
            List of campaign ID strings
        """
        return [c["campaign_id"] for c in self.campaigns]

    def get_summary_stats(self) -> Dict[str, any]:
        """
        Get summary statistics for all campaigns.

        Returns:
            Dictionary with aggregated stats
        """
        total_target = sum(c["target"] for c in self.campaigns)
        total_actual = sum(c["spend"] for c in self.campaigns)
        active_count = sum(1 for c in self.campaigns if c["status"] == "active")
        paused_count = sum(1 for c in self.campaigns if c["status"] == "paused")

        # Count by scenario
        scenario_counts = {}
        for c in self.campaigns:
            scenario = c["scenario"]
            scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1

        return {
            "platform": self.platform.value,
            "total_campaigns": self.num_campaigns,
            "active_campaigns": active_count,
            "paused_campaigns": paused_count,
            "total_target_spend": total_target,
            "total_actual_spend": total_actual,
            "overall_variance_pct": abs(total_actual - total_target) / total_target * 100,
            "scenario_distribution": scenario_counts,
        }
