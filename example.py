"""
Quick example demonstrating the AI Pacing Agent.

Run this to see the agent in action with mock data.
"""

from src.orchestrator import PacingOrchestrator
from src.models.spend import Platform


def main():
    print("\n" + "=" * 70)
    print(" AI PACING AGENT - DEMO")
    print("=" * 70 + "\n")

    # Initialize orchestrator (with mock APIs)
    orchestrator = PacingOrchestrator(
        platforms=[Platform.GOOGLE, Platform.META],
        slack_webhook=None,  # Set to enable Slack alerts
        confidence_threshold=0.7
    )

    # Run monitoring for all campaigns
    results = orchestrator.run_all_campaigns()

    # Display detailed results for first few campaigns
    print("\n" + "=" * 70)
    print(" DETAILED RESULTS (First 3 Campaigns)")
    print("=" * 70 + "\n")

    for platform, alerts in results.items():
        print(f"\n{platform.value.upper()} Platform:\n")

        for i, alert in enumerate(alerts[:3], 1):
            print(f"Campaign {i}: {alert.campaign_id}")
            print(f"  Severity:      {alert.severity}")
            print(f"  Variance:      {alert.variance_pct:.1f}%")
            print(f"  Confidence:    {alert.confidence_score:.1%}")
            print(f"  Action Taken:  {alert.action_taken}")
            print(f"  Recommendation: {alert.recommendation[:100]}...")
            if alert.root_cause_analysis:
                print(f"  Root Cause:    {alert.root_cause_analysis[:100]}...")
            print()

    print("\n" + "=" * 70)
    print(" END OF DEMO")
    print("=" * 70 + "\n")

    print("✅ Check 'audit_log.jsonl' for full audit trail")
    print("📊 See docs/architecture.md for system design details")


if __name__ == "__main__":
    main()
