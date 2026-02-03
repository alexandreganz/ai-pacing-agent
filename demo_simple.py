"""
Simple demo for AI Pacing Agent (Windows-compatible, no emojis).
"""

from src.agents.pacing_brain import PacingBrain
from src.api.mock_platform_api import MockPlatformAPI
from src.api.internal_tracker import MockInternalTracker
from src.models.spend import Platform
from src.utils.audit_logger import AuditLogger


def main():
    print("\n" + "=" * 70)
    print(" AI PACING AGENT - SIMPLE DEMO")
    print("=" * 70 + "\n")

    # Initialize components
    print("Initializing mock APIs...")
    google_api = MockPlatformAPI(Platform.GOOGLE, num_campaigns=10, seed=42)
    internal_tracker = MockInternalTracker()
    # Create fresh audit logger
    import os
    audit_file = "demo_audit.jsonl"
    if os.path.exists(audit_file):
        os.remove(audit_file)
    audit_logger = AuditLogger(log_file=audit_file)

    print("Creating PacingBrain agent...")
    brain = PacingBrain(
        platform_api=google_api,
        internal_tracker=internal_tracker,
        slack_webhook=None,
        audit_logger=audit_logger,
        confidence_threshold=0.7
    )

    print(f"Monitoring {len(google_api.list_campaign_ids())} Google campaigns...\n")

    # Run agent on all campaigns
    alerts = []
    for campaign_id in google_api.list_campaign_ids():
        print(f"Analyzing {campaign_id}...", end=" ")

        try:
            alert = brain.run(campaign_id)
            alerts.append(alert)

            # Print result
            status_map = {
                "healthy": "[OK]",
                "warning": "[WARN]",
                "critical": "[CRIT]"
            }
            status = status_map.get(alert.severity, "[?]")
            print(f"{status} {alert.action_taken} ({alert.variance_pct:.1f}% variance)")

        except Exception as e:
            print(f"[ERROR] {str(e)}")

    # Summary statistics
    print("\n" + "=" * 70)
    print(" SUMMARY")
    print("=" * 70)

    healthy = sum(1 for a in alerts if a.severity == "healthy")
    warning = sum(1 for a in alerts if a.severity == "warning")
    critical = sum(1 for a in alerts if a.severity == "critical")
    autonomous = sum(1 for a in alerts if a.is_autonomous_action)
    escalated = sum(1 for a in alerts if a.requires_human)

    print(f"\nTotal campaigns:      {len(alerts)}")
    print(f"Healthy:              {healthy} ({healthy/len(alerts)*100:.1f}%)")
    print(f"Warnings:             {warning} ({warning/len(alerts)*100:.1f}%)")
    print(f"Critical:             {critical} ({critical/len(alerts)*100:.1f}%)")
    print(f"\nAutonomous actions:   {autonomous}")
    print(f"Human escalations:    {escalated}")

    # Show critical campaigns in detail
    critical_alerts = [a for a in alerts if a.severity == "critical"]
    if critical_alerts:
        print("\n" + "=" * 70)
        print(f" CRITICAL CAMPAIGNS ({len(critical_alerts)} found)")
        print("=" * 70)

        for i, alert in enumerate(critical_alerts, 1):
            print(f"\n{i}. Campaign: {alert.campaign_id}")
            print(f"   Variance:      {alert.variance_pct:.1f}%")
            print(f"   Confidence:    {alert.confidence_score:.1%}")
            print(f"   Action:        {alert.action_taken}")
            print(f"   Recommendation: {alert.recommendation[:150]}...")

    # Audit log summary
    print("\n" + "=" * 70)
    print(" AUDIT LOG")
    print("=" * 70)

    audit_stats = audit_logger.get_summary_stats()
    print(f"\nTotal events logged:  {audit_stats['total_events']}")
    print(f"Log file:            {audit_stats['log_file']}")

    print("\nEvent types:")
    for event_type, count in audit_stats['event_types'].items():
        print(f"  - {event_type:<25} {count:>3}")

    print("\n" + "=" * 70)
    print(" DEMO COMPLETED")
    print("=" * 70)
    print(f"\nAudit log saved to: {audit_logger.log_path}")
    print("Run 'python -m pytest tests/ -v' to run all tests")


if __name__ == "__main__":
    main()
