"""
Slack notification utility.

Sends formatted alerts to Slack via webhook integration.
"""

import requests
from typing import Dict, Optional, List
from datetime import datetime


class SlackNotifier:
    """
    Send formatted Slack notifications for pacing alerts.

    Supports rich formatting with blocks, sections, and contextual information
    including variance details, recommendations, root cause analysis, and
    mitigation plans.
    """

    def __init__(self, webhook_url: str):
        """
        Initialize Slack notifier with webhook URL.

        Args:
            webhook_url: Slack incoming webhook URL
        """
        self.webhook_url = webhook_url

    def send_alert(
        self,
        campaign_id: str,
        campaign_name: str,
        platform: str,
        variance_pct: float,
        variance_amount: float,
        confidence_score: float,
        action_taken: str,
        recommendation: str,
        severity: str = "warning",
        root_cause_analysis: Optional[str] = None,
        mitigation_plan: Optional[str] = None,
        paused: bool = False
    ) -> bool:
        """
        Send a pacing alert to Slack.

        Args:
            campaign_id: Campaign identifier
            campaign_name: Human-readable campaign name
            platform: Platform name (google, meta, etc.)
            variance_pct: Percentage variance from target
            variance_amount: Dollar amount of variance
            confidence_score: Data quality confidence score
            action_taken: Action taken by agent
            recommendation: Recommendation text
            severity: Alert severity (healthy, warning, critical)
            root_cause_analysis: Optional root cause analysis
            mitigation_plan: Optional mitigation plan
            paused: Whether campaign was paused

        Returns:
            True if message sent successfully, False otherwise
        """
        # Determine emoji and status text based on severity and action
        emoji = self._get_emoji(severity, paused)
        status = "PAUSED" if paused else severity.upper()

        # Build message blocks
        blocks = self._build_alert_blocks(
            emoji=emoji,
            status=status,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            platform=platform,
            variance_pct=variance_pct,
            variance_amount=variance_amount,
            confidence_score=confidence_score,
            action_taken=action_taken,
            recommendation=recommendation,
            root_cause_analysis=root_cause_analysis,
            mitigation_plan=mitigation_plan
        )

        # Send message
        message = {
            "text": f"{emoji} Media Pacing {status}: {campaign_name}",
            "blocks": blocks
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Failed to send Slack alert: {e}")
            return False

    def _get_emoji(self, severity: str, paused: bool) -> str:
        """Get appropriate emoji for alert."""
        if paused:
            return "🚨"
        elif severity == "critical":
            return "🚨"
        elif severity == "warning":
            return "⚠️"
        else:
            return "✅"

    def _build_alert_blocks(
        self,
        emoji: str,
        status: str,
        campaign_id: str,
        campaign_name: str,
        platform: str,
        variance_pct: float,
        variance_amount: float,
        confidence_score: float,
        action_taken: str,
        recommendation: str,
        root_cause_analysis: Optional[str],
        mitigation_plan: Optional[str]
    ) -> List[Dict]:
        """Build Slack message blocks."""
        blocks = [
            # Header
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Campaign Pacing {status}",
                    "emoji": True
                }
            },
            # Divider
            {"type": "divider"},
            # Campaign info
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Campaign:*\n{campaign_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Platform:*\n{platform.upper()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Variance:*\n{variance_pct:.1f}% (${variance_amount:,.2f})"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence:*\n{confidence_score:.1%}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Action:*\n{action_taken.replace('_', ' ').title()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Campaign ID:*\n`{campaign_id}`"
                    }
                ]
            },
            # Divider
            {"type": "divider"},
            # Recommendation
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recommendation:*\n{recommendation}"
                }
            }
        ]

        # Add root cause analysis if present
        if root_cause_analysis:
            blocks.extend([
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Root Cause Analysis:*\n{root_cause_analysis}"
                    }
                }
            ])

        # Add mitigation plan if present
        if mitigation_plan:
            blocks.extend([
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Mitigation Plan:*\n{mitigation_plan}"
                    }
                }
            ])

        # Add timestamp footer
        blocks.extend([
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ])

        return blocks

    def send_summary(
        self,
        total_campaigns: int,
        healthy_count: int,
        warning_count: int,
        critical_count: int,
        actions_taken: int
    ) -> bool:
        """
        Send a summary report of pacing monitoring.

        Args:
            total_campaigns: Total campaigns monitored
            healthy_count: Number of healthy campaigns
            warning_count: Number of warnings
            critical_count: Number of critical issues
            actions_taken: Number of autonomous actions

        Returns:
            True if message sent successfully
        """
        message = {
            "text": "Pacing Monitor Summary",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Pacing Monitor Summary",
                        "emoji": True
                    }
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Total Campaigns:*\n{total_campaigns}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Healthy:*\n✅ {healthy_count}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Warnings:*\n⚠️ {warning_count}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Critical:*\n🚨 {critical_count}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Actions Taken:*\n{actions_taken}"
                        }
                    ]
                },
                {"type": "divider"},
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        }
                    ]
                }
            ]
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Failed to send Slack summary: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test Slack webhook connection.

        Returns:
            True if connection successful
        """
        message = {
            "text": "🤖 AI Pacing Agent - Test Message",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "AI Pacing Agent webhook test successful! :white_check_mark:"
                    }
                }
            ]
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            response.raise_for_status()
            print("✅ Slack webhook connection successful")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Slack webhook connection failed: {e}")
            return False
