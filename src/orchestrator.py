"""
Main orchestrator for running the AI Pacing Agent.

This module provides the entry point for monitoring multiple campaigns
across platforms and executing the pacing workflow.
"""

import os
from typing import List, Dict, Optional
from datetime import datetime

from src.agents.pacing_brain import PacingBrain
from src.api.mock_platform_api import MockPlatformAPI
from src.api.internal_tracker import MockInternalTracker
from src.utils.audit_logger import AuditLogger
from src.models.spend import Platform, PacingAlert


class PacingOrchestrator:
    """
    Orchestrates pacing monitoring across multiple campaigns and platforms.

    Responsibilities:
    - Initialize platform APIs and internal trackers
    - Run PacingBrain for all campaigns
    - Aggregate results and generate summary reports
    - Handle errors and retries
    """

    def __init__(
        self,
        platforms: List[Platform] = None,
        slack_webhook: Optional[str] = None,
        audit_log_file: str = "audit_log.jsonl",
        confidence_threshold: float = 0.7
    ):
        """
        Initialize orchestrator.

        Args:
            platforms: List of platforms to monitor (default: GOOGLE, META)
            slack_webhook: Slack webhook URL for alerts
            audit_log_file: Path to audit log file
            confidence_threshold: Confidence threshold for autonomous action
        """
        self.platforms = platforms or [Platform.GOOGLE, Platform.META]
        self.slack_webhook = slack_webhook or os.getenv("SLACK_WEBHOOK_URL")
        self.confidence_threshold = confidence_threshold

        # Initialize audit logger
        self.audit_logger = AuditLogger(log_file=audit_log_file)

        # Initialize API clients (using mocks for MVP)
        self.platform_apis = {
            platform: MockPlatformAPI(platform, num_campaigns=10, seed=42)
            for platform in self.platforms
        }

        # Initialize internal tracker
        self.internal_tracker = MockInternalTracker()

        # Initialize PacingBrain agents for each platform
        self.agents = {
            platform: PacingBrain(
                platform_api=api,
                internal_tracker=self.internal_tracker,
                slack_webhook=self.slack_webhook,
                audit_logger=self.audit_logger,
                confidence_threshold=self.confidence_threshold
            )
            for platform, api in self.platform_apis.items()
        }

    def run_all_campaigns(self) -> Dict[Platform, List[PacingAlert]]:
        """
        Run pacing workflow for all campaigns across all platforms.

        Returns:
            Dictionary mapping Platform to list of PacingAlerts
        """
        print(f"\n{'=' * 70}")
        print(f"AI Pacing Agent - Monitoring Started")
        print(f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"{'=' * 70}\n")

        results = {}

        for platform, agent in self.agents.items():
            print(f"\n🔍 Monitoring {platform.value.upper()} campaigns...")

            # Get all campaign IDs for this platform
            campaign_ids = self.platform_apis[platform].list_campaign_ids()
            print(f"   Found {len(campaign_ids)} campaigns\n")

            # Run pacing workflow for each campaign
            alerts = []
            for campaign_id in campaign_ids:
                try:
                    print(f"   📊 Analyzing {campaign_id}...", end=" ")
                    alert = agent.run(campaign_id)
                    alerts.append(alert)

                    # Print result
                    emoji = self._get_result_emoji(alert.severity)
                    print(f"{emoji} {alert.action_taken} ({alert.variance_pct:.1f}% variance)")

                except Exception as e:
                    print(f"❌ Error: {str(e)}")
                    self.audit_logger.log_error(
                        error_type="orchestration_error",
                        error_message=str(e),
                        campaign_id=campaign_id,
                        context={"platform": platform.value}
                    )

            results[platform] = alerts

        # Print summary
        self._print_summary(results)

        return results

    def run_platform(self, platform: Platform) -> List[PacingAlert]:
        """
        Run pacing workflow for a single platform.

        Args:
            platform: Platform to monitor

        Returns:
            List of PacingAlerts
        """
        if platform not in self.agents:
            raise ValueError(f"Platform {platform.value} not configured")

        agent = self.agents[platform]
        campaign_ids = self.platform_apis[platform].list_campaign_ids()

        alerts = []
        for campaign_id in campaign_ids:
            try:
                alert = agent.run(campaign_id)
                alerts.append(alert)
            except Exception as e:
                self.audit_logger.log_error(
                    error_type="platform_monitoring_error",
                    error_message=str(e),
                    campaign_id=campaign_id,
                    context={"platform": platform.value}
                )

        return alerts

    def run_campaign(self, campaign_id: str, platform: Platform) -> PacingAlert:
        """
        Run pacing workflow for a single campaign.

        Args:
            campaign_id: Campaign identifier
            platform: Platform of the campaign

        Returns:
            PacingAlert
        """
        if platform not in self.agents:
            raise ValueError(f"Platform {platform.value} not configured")

        return self.agents[platform].run(campaign_id)

    def _get_result_emoji(self, severity: str) -> str:
        """Get emoji for result display."""
        return {
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "🚨"
        }.get(severity, "❓")

    def _print_summary(self, results: Dict[Platform, List[PacingAlert]]):
        """Print summary report of monitoring run."""
        print(f"\n{'=' * 70}")
        print("📊 Monitoring Summary")
        print(f"{'=' * 70}\n")

        # Aggregate stats
        total_campaigns = 0
        healthy_count = 0
        warning_count = 0
        critical_count = 0
        actions_taken = 0
        escalations = 0

        for platform, alerts in results.items():
            total_campaigns += len(alerts)

            for alert in alerts:
                if alert.severity == "healthy":
                    healthy_count += 1
                elif alert.severity == "warning":
                    warning_count += 1
                elif alert.severity == "critical":
                    critical_count += 1

                if alert.is_autonomous_action:
                    actions_taken += 1

                if alert.requires_human:
                    escalations += 1

        # Print stats
        print(f"Total campaigns monitored:  {total_campaigns}")
        print(f"✅ Healthy:                 {healthy_count} ({healthy_count/total_campaigns*100:.1f}%)")
        print(f"⚠️  Warnings:                {warning_count} ({warning_count/total_campaigns*100:.1f}%)")
        print(f"🚨 Critical:                {critical_count} ({critical_count/total_campaigns*100:.1f}%)")
        print(f"\n🤖 Autonomous actions:      {actions_taken}")
        print(f"👤 Human escalations:       {escalations}")

        # Audit log stats
        audit_stats = self.audit_logger.get_summary_stats()
        print(f"\n📝 Audit log entries:       {audit_stats['total_events']}")

        print(f"\n{'=' * 70}\n")

    def get_platform_api(self, platform: Platform) -> MockPlatformAPI:
        """Get platform API client for a specific platform."""
        return self.platform_apis.get(platform)

    def get_agent(self, platform: Platform) -> PacingBrain:
        """Get PacingBrain agent for a specific platform."""
        return self.agents.get(platform)


def main():
    """
    Main entry point for running the AI Pacing Agent.

    Usage:
        python -m src.orchestrator
    """
    # Load configuration from environment
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))

    # Initialize orchestrator
    orchestrator = PacingOrchestrator(
        platforms=[Platform.GOOGLE, Platform.META],
        slack_webhook=slack_webhook,
        confidence_threshold=confidence_threshold
    )

    # Run monitoring for all campaigns
    results = orchestrator.run_all_campaigns()

    # Optional: Send summary to Slack
    if slack_webhook:
        # Aggregate summary stats
        total_campaigns = sum(len(alerts) for alerts in results.values())
        healthy = sum(1 for alerts in results.values() for a in alerts if a.severity == "healthy")
        warning = sum(1 for alerts in results.values() for a in alerts if a.severity == "warning")
        critical = sum(1 for alerts in results.values() for a in alerts if a.severity == "critical")
        actions = sum(1 for alerts in results.values() for a in alerts if a.is_autonomous_action)

        from src.utils.slack_notifier import SlackNotifier
        notifier = SlackNotifier(slack_webhook)
        notifier.send_summary(
            total_campaigns=total_campaigns,
            healthy_count=healthy,
            warning_count=warning,
            critical_count=critical,
            actions_taken=actions
        )


if __name__ == "__main__":
    main()
