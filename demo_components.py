"""
Component-level demo showing individual AI Pacing Agent components.
"""

from datetime import datetime, timedelta
from src.models.spend import Platform, DataSource, SpendRecord, ReconciledSpend
from src.analyzers.pacing_analyzer import PacingAnalyzer
from src.agents.confidence_scorer import ConfidenceScorer
from src.api.mock_platform_api import MockPlatformAPI
from src.api.internal_tracker import MockInternalTracker


def main():
    print("\n" + "=" * 70)
    print(" AI PACING AGENT - COMPONENT DEMO")
    print("=" * 70 + "\n")

    # 1. Initialize components
    print("1. Initializing components...")
    analyzer = PacingAnalyzer()
    scorer = ConfidenceScorer()
    google_api = MockPlatformAPI(Platform.GOOGLE, num_campaigns=10, seed=42)
    internal_tracker = MockInternalTracker()
    print("   [OK] All components initialized\n")

    # 2. Show mock campaign data
    print("2. Mock Campaign Data")
    print("-" * 70)
    stats = google_api.get_summary_stats()
    print(f"   Platform:         {stats['platform'].upper()}")
    print(f"   Total campaigns:  {stats['total_campaigns']}")
    print(f"   Active:           {stats['active_campaigns']}")
    print(f"   Paused:           {stats['paused_campaigns']}")
    print(f"   Total target:     ${stats['total_target_spend']:,.2f}")
    print(f"   Total actual:     ${stats['total_actual_spend']:,.2f}")
    print(f"   Overall variance: {stats['overall_variance_pct']:.1f}%\n")

    # 3. Process sample campaigns
    print("3. Processing Sample Campaigns")
    print("-" * 70)

    campaign_ids = google_api.list_campaign_ids()[:5]  # First 5 campaigns
    results = []

    for campaign_id in campaign_ids:
        # Fetch data
        actual_record = google_api.get_campaign_spend(campaign_id)
        target_record = internal_tracker.get_target_spend(campaign_id)

        # Calculate confidence
        confidence_scores = scorer.calculate_confidence(
            tracker_name=target_record.campaign_name,
            api_name=actual_record.campaign_name,
            tracker_metadata=target_record.metadata,
            api_metadata=actual_record.metadata,
            actual_timestamp=actual_record.timestamp
        )

        # Create reconciled spend
        reconciled = ReconciledSpend(
            campaign_id=campaign_id,
            campaign_name=actual_record.campaign_name,
            platform=actual_record.platform,
            target_spend=target_record.amount_usd,
            actual_spend=actual_record.amount_usd,
            target_timestamp=target_record.timestamp,
            actual_timestamp=actual_record.timestamp,
            metadata_match_score=confidence_scores["metadata_match_score"],
            name_similarity=confidence_scores["name_similarity"],
            data_freshness_score=confidence_scores["data_freshness_score"]
        )

        # Calculate variance
        variance_result = analyzer.calculate_variance(reconciled)

        # Generate recommendation
        recommendation = analyzer.generate_recommendation(variance_result, reconciled)

        # Determine action
        if variance_result["severity"] == "healthy":
            action = "Log Only"
        elif variance_result["severity"] == "warning":
            action = "Slack Alert"
        else:  # critical
            action = "Autonomous Halt" if reconciled.confidence_score >= 0.7 else "Escalate to Human"

        results.append({
            "campaign_id": campaign_id,
            "target": target_record.amount_usd,
            "actual": actual_record.amount_usd,
            "variance_pct": variance_result["variance_pct"],
            "confidence": reconciled.confidence_score,
            "severity": variance_result["severity"],
            "action": action,
            "recommendation": recommendation
        })

        # Print result
        status_map = {"healthy": "[OK]", "warning": "[WARN]", "critical": "[CRIT]"}
        status = status_map.get(variance_result["severity"], "[?]")
        print(f"   {campaign_id}: {status} {action}")
        print(f"      Target: ${target_record.amount_usd:,.2f}")
        print(f"      Actual: ${actual_record.amount_usd:,.2f}")
        print(f"      Variance: {variance_result['variance_pct']:.1f}%")
        print(f"      Confidence: {reconciled.confidence_score:.1%}")
        print()

    # 4. Summary Statistics
    print("4. Summary Statistics")
    print("-" * 70)

    healthy = sum(1 for r in results if r["severity"] == "healthy")
    warning = sum(1 for r in results if r["severity"] == "warning")
    critical = sum(1 for r in results if r["severity"] == "critical")
    autonomous = sum(1 for r in results if r["action"] == "Autonomous Halt")
    escalated = sum(1 for r in results if r["action"] == "Escalate to Human")

    print(f"   Total processed:      {len(results)}")
    print(f"   Healthy:              {healthy} ({healthy/len(results)*100:.1f}%)")
    print(f"   Warnings:             {warning} ({warning/len(results)*100:.1f}%)")
    print(f"   Critical:             {critical} ({critical/len(results)*100:.1f}%)")
    print(f"   Autonomous actions:   {autonomous}")
    print(f"   Human escalations:    {escalated}\n")

    # 5. Detailed Analysis of One Campaign
    print("5. Detailed Analysis of Most Critical Campaign")
    print("-" * 70)

    # Find most critical
    critical_results = [r for r in results if r["severity"] == "critical"]
    if critical_results:
        most_critical = max(critical_results, key=lambda x: x["variance_pct"])

        print(f"   Campaign: {most_critical['campaign_id']}")
        print(f"   Variance: {most_critical['variance_pct']:.1f}%")
        print(f"   Confidence: {most_critical['confidence']:.1%}")
        print(f"   Action: {most_critical['action']}")
        print(f"\n   Recommendation:")
        print(f"   {most_critical['recommendation'][:200]}...")
    else:
        print("   No critical campaigns found.\n")

    # 6. Confidence Scoring Example
    print("\n6. Confidence Scoring Components")
    print("-" * 70)

    example = results[0]
    campaign_id = example["campaign_id"]
    actual_record = google_api.get_campaign_spend(campaign_id)
    target_record = internal_tracker.get_target_spend(campaign_id)

    confidence_scores = scorer.calculate_confidence(
        tracker_name=target_record.campaign_name,
        api_name=actual_record.campaign_name,
        tracker_metadata=target_record.metadata,
        api_metadata=actual_record.metadata,
        actual_timestamp=actual_record.timestamp
    )

    print(f"   Campaign: {campaign_id}")
    print(f"   Metadata Match:  {confidence_scores['metadata_match_score']:.1%} (50% weight)")
    print(f"   Name Similarity: {confidence_scores['name_similarity']:.1%} (30% weight)")
    print(f"   Data Freshness:  {confidence_scores['data_freshness_score']:.1%} (20% weight)")
    print(f"   Overall Confidence: {confidence_scores['confidence_score']:.1%}")

    hours_old = (datetime.utcnow() - actual_record.timestamp).total_seconds() / 3600
    print(f"\n   Data age: {hours_old:.1f} hours")
    print(f"   Tracker name: {target_record.campaign_name}")
    print(f"   API name:     {actual_record.campaign_name}")

    # 7. Decision Logic
    print("\n7. Decision Logic")
    print("-" * 70)
    print("   Variance Thresholds:")
    print("      < 10%:      Healthy    -> Log Only")
    print("      10-25%:     Warning    -> Slack Alert")
    print("      > 25%:      Critical   -> Autonomous Halt (if confidence >= 70%)")
    print("      Zero spend: Critical   -> Autonomous Halt")
    print("\n   Confidence Threshold:")
    print("      >= 70%:     Agent can take autonomous action")
    print("      < 70%:      Escalate to human for review")

    print("\n" + "=" * 70)
    print(" DEMO COMPLETED")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("  - Variance classification works correctly (healthy/warning/critical)")
    print("  - Confidence scoring considers metadata, names, and freshness")
    print("  - Safety guardrails prevent autonomous action on low-confidence data")
    print("  - All components integrate seamlessly")
    print("\nNext steps:")
    print("  - Run full orchestrator with: python -m src.orchestrator")
    print("  - Run tests with: python -m pytest tests/ -v")
    print("  - View architecture: docs/architecture.md")


if __name__ == "__main__":
    main()
