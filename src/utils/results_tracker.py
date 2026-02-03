"""
Results tracker for saving and comparing agent performance over time.

This module allows you to:
- Save agent run results with timestamps
- Compare performance across different configurations
- Track improvement metrics
- Export results for analysis
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class ResultsTracker:
    """
    Track and save agent run results for comparison and analysis.

    Saves results in structured JSON format with:
    - Run metadata (timestamp, configuration)
    - Campaign results (variance, confidence, actions)
    - Summary statistics
    - Performance metrics
    """

    def __init__(self, results_dir: str = "results"):
        """
        Initialize results tracker.

        Args:
            results_dir: Directory to store results files
        """
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)

    def save_run(
        self,
        alerts: List,
        config: Dict[str, Any],
        run_name: Optional[str] = None,
        notes: Optional[str] = None
    ) -> str:
        """
        Save a complete agent run with results.

        Args:
            alerts: List of PacingAlert objects from the run
            config: Configuration used (thresholds, confidence, etc.)
            run_name: Optional name for this run
            notes: Optional notes about this run

        Returns:
            Path to saved results file
        """
        timestamp = datetime.utcnow()
        run_id = timestamp.strftime("%Y%m%d_%H%M%S")

        # Process alerts
        campaign_results = []
        for alert in alerts:
            campaign_results.append({
                "campaign_id": alert.campaign_id,
                "severity": alert.severity,
                "variance_pct": alert.variance_pct,
                "confidence_score": alert.confidence_score,
                "action_taken": alert.action_taken,
                "requires_human": alert.requires_human,
                "is_autonomous_action": alert.is_autonomous_action,
                "metadata": alert.metadata
            })

        # Calculate summary statistics
        total = len(alerts)
        healthy = sum(1 for a in alerts if a.severity == "healthy")
        warning = sum(1 for a in alerts if a.severity == "warning")
        critical = sum(1 for a in alerts if a.severity == "critical")
        autonomous = sum(1 for a in alerts if a.is_autonomous_action)
        escalated = sum(1 for a in alerts if a.requires_human)

        avg_variance = sum(a.variance_pct for a in alerts) / total if total > 0 else 0
        avg_confidence = sum(a.confidence_score for a in alerts) / total if total > 0 else 0

        # Create results structure
        results = {
            "run_metadata": {
                "run_id": run_id,
                "run_name": run_name or f"Run_{run_id}",
                "timestamp": timestamp.isoformat(),
                "notes": notes,
                "total_campaigns": total
            },
            "configuration": config,
            "summary_statistics": {
                "total_campaigns": total,
                "healthy": healthy,
                "warning": warning,
                "critical": critical,
                "healthy_pct": (healthy / total * 100) if total > 0 else 0,
                "warning_pct": (warning / total * 100) if total > 0 else 0,
                "critical_pct": (critical / total * 100) if total > 0 else 0,
                "autonomous_actions": autonomous,
                "human_escalations": escalated,
                "avg_variance_pct": avg_variance,
                "avg_confidence_score": avg_confidence
            },
            "performance_metrics": {
                "autonomous_action_rate": (autonomous / total * 100) if total > 0 else 0,
                "escalation_rate": (escalated / total * 100) if total > 0 else 0,
                "critical_detection_rate": (critical / total * 100) if total > 0 else 0
            },
            "campaign_results": campaign_results
        }

        # Save to file
        filename = f"run_{run_id}.json"
        filepath = self.results_dir / filename

        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"Results saved to: {filepath}")
        return str(filepath)

    def load_run(self, run_id: str) -> Dict[str, Any]:
        """
        Load results from a previous run.

        Args:
            run_id: Run ID or filename

        Returns:
            Results dictionary
        """
        if not run_id.endswith('.json'):
            run_id = f"run_{run_id}.json"

        filepath = self.results_dir / run_id

        with open(filepath, 'r') as f:
            return json.load(f)

    def list_runs(self) -> List[Dict[str, str]]:
        """
        List all saved runs.

        Returns:
            List of dictionaries with run metadata
        """
        runs = []
        for filepath in sorted(self.results_dir.glob("run_*.json")):
            with open(filepath, 'r') as f:
                data = json.load(f)
                runs.append({
                    "run_id": data["run_metadata"]["run_id"],
                    "run_name": data["run_metadata"]["run_name"],
                    "timestamp": data["run_metadata"]["timestamp"],
                    "total_campaigns": data["run_metadata"]["total_campaigns"],
                    "filepath": str(filepath)
                })
        return runs

    def compare_runs(self, run_id_1: str, run_id_2: str) -> Dict[str, Any]:
        """
        Compare two runs to see improvement.

        Args:
            run_id_1: First run ID (baseline)
            run_id_2: Second run ID (comparison)

        Returns:
            Comparison dictionary with deltas
        """
        run1 = self.load_run(run_id_1)
        run2 = self.load_run(run_id_2)

        stats1 = run1["summary_statistics"]
        stats2 = run2["summary_statistics"]

        perf1 = run1["performance_metrics"]
        perf2 = run2["performance_metrics"]

        comparison = {
            "baseline": {
                "run_id": run1["run_metadata"]["run_id"],
                "run_name": run1["run_metadata"]["run_name"],
                "timestamp": run1["run_metadata"]["timestamp"]
            },
            "comparison": {
                "run_id": run2["run_metadata"]["run_id"],
                "run_name": run2["run_metadata"]["run_name"],
                "timestamp": run2["run_metadata"]["timestamp"]
            },
            "configuration_changes": self._compare_configs(
                run1["configuration"],
                run2["configuration"]
            ),
            "statistics_delta": {
                "healthy_pct": stats2["healthy_pct"] - stats1["healthy_pct"],
                "warning_pct": stats2["warning_pct"] - stats1["warning_pct"],
                "critical_pct": stats2["critical_pct"] - stats1["critical_pct"],
                "avg_variance_pct": stats2["avg_variance_pct"] - stats1["avg_variance_pct"],
                "avg_confidence_score": stats2["avg_confidence_score"] - stats1["avg_confidence_score"]
            },
            "performance_delta": {
                "autonomous_action_rate": perf2["autonomous_action_rate"] - perf1["autonomous_action_rate"],
                "escalation_rate": perf2["escalation_rate"] - perf1["escalation_rate"],
                "critical_detection_rate": perf2["critical_detection_rate"] - perf1["critical_detection_rate"]
            },
            "improvement_summary": self._generate_improvement_summary(stats1, stats2, perf1, perf2)
        }

        return comparison

    def _compare_configs(self, config1: Dict, config2: Dict) -> Dict[str, Any]:
        """Compare two configurations and show changes."""
        changes = {}
        all_keys = set(config1.keys()) | set(config2.keys())

        for key in all_keys:
            val1 = config1.get(key)
            val2 = config2.get(key)

            if val1 != val2:
                changes[key] = {
                    "from": val1,
                    "to": val2
                }

        return changes

    def _generate_improvement_summary(
        self,
        stats1: Dict,
        stats2: Dict,
        perf1: Dict,
        perf2: Dict
    ) -> str:
        """Generate human-readable improvement summary."""
        improvements = []

        # Check healthy rate
        healthy_delta = stats2["healthy_pct"] - stats1["healthy_pct"]
        if healthy_delta > 0:
            improvements.append(f"+{healthy_delta:.1f}% more healthy campaigns")
        elif healthy_delta < 0:
            improvements.append(f"{healthy_delta:.1f}% fewer healthy campaigns")

        # Check critical rate
        critical_delta = stats2["critical_pct"] - stats1["critical_pct"]
        if critical_delta < 0:
            improvements.append(f"{abs(critical_delta):.1f}% fewer critical issues")
        elif critical_delta > 0:
            improvements.append(f"+{critical_delta:.1f}% more critical issues")

        # Check autonomous action rate
        auto_delta = perf2["autonomous_action_rate"] - perf1["autonomous_action_rate"]
        if auto_delta > 0:
            improvements.append(f"+{auto_delta:.1f}% more autonomous actions")

        # Check average confidence
        conf_delta = stats2["avg_confidence_score"] - stats1["avg_confidence_score"]
        if conf_delta > 0:
            improvements.append(f"+{conf_delta:.1%} higher average confidence")

        if not improvements:
            return "No significant changes detected"

        return " | ".join(improvements)

    def export_comparison_csv(self, run_ids: List[str], output_file: str):
        """
        Export multiple runs to CSV for analysis.

        Args:
            run_ids: List of run IDs to compare
            output_file: Output CSV file path
        """
        import csv

        rows = []
        for run_id in run_ids:
            run = self.load_run(run_id)
            rows.append({
                "run_id": run["run_metadata"]["run_id"],
                "run_name": run["run_metadata"]["run_name"],
                "timestamp": run["run_metadata"]["timestamp"],
                "total_campaigns": run["run_metadata"]["total_campaigns"],
                "healthy_pct": run["summary_statistics"]["healthy_pct"],
                "warning_pct": run["summary_statistics"]["warning_pct"],
                "critical_pct": run["summary_statistics"]["critical_pct"],
                "autonomous_actions": run["summary_statistics"]["autonomous_actions"],
                "human_escalations": run["summary_statistics"]["human_escalations"],
                "avg_variance": run["summary_statistics"]["avg_variance_pct"],
                "avg_confidence": run["summary_statistics"]["avg_confidence_score"],
                "autonomous_rate": run["performance_metrics"]["autonomous_action_rate"],
                "escalation_rate": run["performance_metrics"]["escalation_rate"]
            })

        with open(output_file, 'w', newline='') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

        print(f"Comparison exported to: {output_file}")

    def get_latest_run(self) -> Optional[Dict[str, Any]]:
        """Get the most recent run."""
        runs = self.list_runs()
        if runs:
            return self.load_run(runs[-1]["run_id"])
        return None

    def delete_run(self, run_id: str):
        """Delete a saved run."""
        if not run_id.endswith('.json'):
            run_id = f"run_{run_id}.json"

        filepath = self.results_dir / run_id
        if filepath.exists():
            filepath.unlink()
            print(f"Deleted run: {run_id}")
        else:
            print(f"Run not found: {run_id}")
