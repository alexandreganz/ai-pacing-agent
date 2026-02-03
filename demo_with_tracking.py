"""
Demo showing how to track and compare agent results over time.
"""

from src.api.mock_platform_api import MockPlatformAPI
from src.api.internal_tracker import MockInternalTracker
from src.models.spend import Platform, ReconciledSpend, PacingAlert
from src.analyzers.pacing_analyzer import PacingAnalyzer
from src.agents.confidence_scorer import ConfidenceScorer
from src.utils.results_tracker import ResultsTracker
from datetime import datetime


def run_agent_with_config(config):
    """Run agent with specific configuration and return alerts."""
    print(f"\nRunning with config: {config['name']}")
    print("-" * 60)

    # Initialize components
    api = MockPlatformAPI(
        Platform.GOOGLE,
        num_campaigns=config['num_campaigns'],
        seed=config['seed']
    )
    tracker = MockInternalTracker()
    analyzer = PacingAnalyzer(
        healthy_threshold=config['healthy_threshold'],
        warning_threshold=config['warning_threshold']
    )
    scorer = ConfidenceScorer()

    # Process campaigns
    alerts = []
    for campaign_id in api.list_campaign_ids():
        # Fetch data
        actual = api.get_campaign_spend(campaign_id)
        target = tracker.get_target_spend(campaign_id)

        # Calculate confidence
        confidence_scores = scorer.calculate_confidence(
            tracker_name=target.campaign_name,
            api_name=actual.campaign_name,
            tracker_metadata=target.metadata,
            api_metadata=actual.metadata,
            actual_timestamp=actual.timestamp
        )

        # Create reconciled spend
        reconciled = ReconciledSpend(
            campaign_id=campaign_id,
            campaign_name=actual.campaign_name,
            platform=actual.platform,
            target_spend=target.amount_usd,
            actual_spend=actual.amount_usd,
            target_timestamp=target.timestamp,
            actual_timestamp=actual.timestamp,
            metadata_match_score=confidence_scores["metadata_match_score"],
            name_similarity=confidence_scores["name_similarity"],
            data_freshness_score=confidence_scores["data_freshness_score"]
        )

        # Calculate variance
        variance_result = analyzer.calculate_variance(reconciled)

        # Determine action
        if reconciled.confidence_score < config['confidence_threshold']:
            action_taken = "escalated_to_human"
            requires_human = True
        elif variance_result["severity"] == "healthy":
            action_taken = "logged_healthy"
            requires_human = False
        elif variance_result["severity"] == "warning":
            action_taken = "warning_alert_sent"
            requires_human = False
        else:
            action_taken = "autonomous_halt_executed"
            requires_human = False

        # Create alert
        alert = PacingAlert(
            alert_id=f"alert_{len(alerts)}",
            campaign_id=campaign_id,
            severity=variance_result["severity"],
            variance_pct=variance_result["variance_pct"],
            confidence_score=reconciled.confidence_score,
            action_taken=action_taken,
            recommendation="Test recommendation",
            requires_human=requires_human,
            timestamp=datetime.utcnow(),
            metadata={
                "target_spend": target.amount_usd,
                "actual_spend": actual.amount_usd
            }
        )
        alerts.append(alert)

    # Print summary
    healthy = sum(1 for a in alerts if a.severity == "healthy")
    warning = sum(1 for a in alerts if a.severity == "warning")
    critical = sum(1 for a in alerts if a.severity == "critical")

    print(f"Total:    {len(alerts)} campaigns")
    print(f"Healthy:  {healthy} ({healthy/len(alerts)*100:.1f}%)")
    print(f"Warning:  {warning} ({warning/len(alerts)*100:.1f}%)")
    print(f"Critical: {critical} ({critical/len(alerts)*100:.1f}%)")

    return alerts


def main():
    print("\n" + "=" * 70)
    print(" AI PACING AGENT - RESULTS TRACKING DEMO")
    print("=" * 70)

    # Initialize results tracker
    tracker = ResultsTracker(results_dir="results")

    # Configuration 1: Baseline (strict thresholds)
    config1 = {
        "name": "Baseline (Strict Thresholds)",
        "num_campaigns": 20,
        "seed": 42,
        "confidence_threshold": 0.7,
        "healthy_threshold": 10.0,
        "warning_threshold": 25.0
    }

    alerts1 = run_agent_with_config(config1)
    run1_path = tracker.save_run(
        alerts1,
        config1,
        run_name="Baseline_Strict",
        notes="Initial run with strict thresholds for comparison"
    )
    print(f"✓ Saved to: {run1_path}")

    # Configuration 2: Relaxed thresholds
    config2 = {
        "name": "Relaxed Thresholds",
        "num_campaigns": 20,
        "seed": 42,  # Same seed for fair comparison
        "confidence_threshold": 0.6,  # Lower confidence threshold
        "healthy_threshold": 15.0,    # Higher healthy threshold
        "warning_threshold": 30.0     # Higher warning threshold
    }

    alerts2 = run_agent_with_config(config2)
    run2_path = tracker.save_run(
        alerts2,
        config2,
        run_name="Relaxed_Thresholds",
        notes="Relaxed thresholds to allow more autonomous action"
    )
    print(f"✓ Saved to: {run2_path}")

    # Configuration 3: Very strict
    config3 = {
        "name": "Very Strict",
        "num_campaigns": 20,
        "seed": 42,
        "confidence_threshold": 0.8,  # Higher confidence required
        "healthy_threshold": 5.0,     # Lower healthy threshold
        "warning_threshold": 15.0     # Lower warning threshold
    }

    alerts3 = run_agent_with_config(config3)
    run3_path = tracker.save_run(
        alerts3,
        config3,
        run_name="Very_Strict",
        notes="Very strict thresholds for maximum safety"
    )
    print(f"✓ Saved to: {run3_path}")

    # List all runs
    print("\n" + "=" * 70)
    print(" SAVED RUNS")
    print("=" * 70)
    runs = tracker.list_runs()
    for run in runs:
        print(f"\n{run['run_name']}")
        print(f"  Run ID: {run['run_id']}")
        print(f"  Time: {run['timestamp']}")
        print(f"  Campaigns: {run['total_campaigns']}")

    # Compare runs
    print("\n" + "=" * 70)
    print(" COMPARISON: Baseline vs Relaxed")
    print("=" * 70)

    comparison = tracker.compare_runs(
        runs[-3]['run_id'],  # Baseline
        runs[-2]['run_id']   # Relaxed
    )

    print(f"\nBaseline: {comparison['baseline']['run_name']}")
    print(f"Comparison: {comparison['comparison']['run_name']}")

    print("\nConfiguration Changes:")
    for key, change in comparison['configuration_changes'].items():
        print(f"  {key}: {change['from']} → {change['to']}")

    print("\nStatistics Delta:")
    for key, delta in comparison['statistics_delta'].items():
        sign = "+" if delta > 0 else ""
        print(f"  {key}: {sign}{delta:.2f}")

    print("\nPerformance Delta:")
    for key, delta in comparison['performance_delta'].items():
        sign = "+" if delta > 0 else ""
        print(f"  {key}: {sign}{delta:.2f}%")

    print(f"\nImprovement Summary:")
    print(f"  {comparison['improvement_summary']}")

    # Export to CSV
    print("\n" + "=" * 70)
    print(" EXPORTING TO CSV")
    print("=" * 70)

    run_ids = [run['run_id'] for run in runs[-3:]]
    tracker.export_comparison_csv(run_ids, "results_comparison.csv")

    print("\n" + "=" * 70)
    print(" DEMO COMPLETE")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("  ✓ Results are saved with full configuration")
    print("  ✓ Runs can be compared to measure improvement")
    print("  ✓ Configuration changes are tracked")
    print("  ✓ Performance metrics show impact of changes")
    print("\nNext Steps:")
    print("  - View results in: results/")
    print("  - Open CSV: results_comparison.csv")
    print("  - Compare more runs using ResultsTracker")


if __name__ == "__main__":
    main()
