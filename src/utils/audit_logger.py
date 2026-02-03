"""
Audit logging utility.

Logs all agent decisions, actions, and events for compliance and analysis.
Supports JSON file logging and optional SQLite database storage.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class AuditLogger:
    """
    Log agent decisions and actions for audit trail.

    Maintains a complete record of:
    - All pacing checks and variance calculations
    - Confidence scores and data quality metrics
    - Agent decisions (log/alert/halt)
    - Actions taken (pause campaign, send alert)
    - Root cause analysis and recommendations
    """

    def __init__(
        self,
        log_file: str = "audit_log.jsonl",
        log_dir: Optional[str] = None
    ):
        """
        Initialize audit logger.

        Args:
            log_file: Name of log file (JSONL format)
            log_dir: Directory for log files (default: current directory)
        """
        if log_dir:
            self.log_dir = Path(log_dir)
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_path = self.log_dir / log_file
        else:
            self.log_path = Path(log_file)

    def log_event(self, event: Dict[str, Any]):
        """
        Log a generic event.

        Args:
            event: Event dictionary with arbitrary fields
        """
        # Add timestamp if not present
        if "timestamp" not in event:
            event["timestamp"] = datetime.utcnow().isoformat()

        # Append to JSONL file
        with open(self.log_path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def log_alert(self, alert):
        """
        Log a pacing alert.

        Args:
            alert: PacingAlert object
        """
        event = {
            "event_type": "pacing_alert",
            "alert_id": alert.alert_id,
            "campaign_id": alert.campaign_id,
            "severity": alert.severity,
            "variance_pct": alert.variance_pct,
            "confidence_score": alert.confidence_score,
            "action_taken": alert.action_taken,
            "recommendation": alert.recommendation,
            "requires_human": alert.requires_human,
            "root_cause_analysis": alert.root_cause_analysis,
            "mitigation_plan": alert.mitigation_plan,
            "timestamp": alert.timestamp.isoformat(),
            "metadata": alert.metadata
        }
        self.log_event(event)

    def log_decision(
        self,
        campaign_id: str,
        variance_pct: float,
        confidence_score: float,
        severity: str,
        decision: str,
        reasoning: str
    ):
        """
        Log an agent decision.

        Args:
            campaign_id: Campaign identifier
            variance_pct: Percentage variance
            confidence_score: Confidence score
            severity: Severity level
            decision: Decision made (log/alert/halt/escalate)
            reasoning: Explanation of decision
        """
        event = {
            "event_type": "agent_decision",
            "campaign_id": campaign_id,
            "variance_pct": variance_pct,
            "confidence_score": confidence_score,
            "severity": severity,
            "decision": decision,
            "reasoning": reasoning,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.log_event(event)

    def log_action(
        self,
        campaign_id: str,
        action_type: str,
        success: bool,
        details: Optional[Dict] = None
    ):
        """
        Log an action taken by the agent.

        Args:
            campaign_id: Campaign identifier
            action_type: Type of action (pause_campaign, send_alert, etc.)
            success: Whether action succeeded
            details: Optional additional details
        """
        event = {
            "event_type": "agent_action",
            "campaign_id": campaign_id,
            "action_type": action_type,
            "success": success,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self.log_event(event)

    def log_reconciliation(
        self,
        campaign_id: str,
        target_spend: float,
        actual_spend: float,
        confidence_score: float,
        metadata_match_score: float,
        name_similarity: float,
        data_freshness_score: float
    ):
        """
        Log a spend reconciliation.

        Args:
            campaign_id: Campaign identifier
            target_spend: Target spend from tracker
            actual_spend: Actual spend from API
            confidence_score: Overall confidence
            metadata_match_score: Metadata matching score
            name_similarity: Name similarity score
            data_freshness_score: Freshness score
        """
        event = {
            "event_type": "reconciliation",
            "campaign_id": campaign_id,
            "target_spend": target_spend,
            "actual_spend": actual_spend,
            "variance_pct": abs(actual_spend - target_spend) / target_spend * 100 if target_spend > 0 else 0,
            "confidence_score": confidence_score,
            "metadata_match_score": metadata_match_score,
            "name_similarity": name_similarity,
            "data_freshness_score": data_freshness_score,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.log_event(event)

    def log_error(
        self,
        error_type: str,
        error_message: str,
        campaign_id: Optional[str] = None,
        context: Optional[Dict] = None
    ):
        """
        Log an error.

        Args:
            error_type: Type/category of error
            error_message: Error description
            campaign_id: Optional campaign identifier
            context: Optional context information
        """
        event = {
            "event_type": "error",
            "error_type": error_type,
            "error_message": error_message,
            "campaign_id": campaign_id,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self.log_event(event)

    def get_events(
        self,
        event_type: Optional[str] = None,
        campaign_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Retrieve events from log file.

        Args:
            event_type: Filter by event type
            campaign_id: Filter by campaign ID
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        if not self.log_path.exists():
            return []

        events = []
        with open(self.log_path, "r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())

                    # Apply filters
                    if event_type and event.get("event_type") != event_type:
                        continue
                    if campaign_id and event.get("campaign_id") != campaign_id:
                        continue

                    events.append(event)

                    # Apply limit
                    if limit and len(events) >= limit:
                        break

                except json.JSONDecodeError:
                    continue

        return events

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics from audit log.

        Returns:
            Dictionary with aggregated statistics
        """
        if not self.log_path.exists():
            return {
                "total_events": 0,
                "event_types": {},
                "alerts_by_severity": {},
                "decisions_by_type": {},
            }

        events = self.get_events()

        # Count by event type
        event_types = {}
        alerts_by_severity = {}
        decisions_by_type = {}

        for event in events:
            event_type = event.get("event_type", "unknown")
            event_types[event_type] = event_types.get(event_type, 0) + 1

            if event_type == "pacing_alert":
                severity = event.get("severity", "unknown")
                alerts_by_severity[severity] = alerts_by_severity.get(severity, 0) + 1

            if event_type == "agent_decision":
                decision = event.get("decision", "unknown")
                decisions_by_type[decision] = decisions_by_type.get(decision, 0) + 1

        return {
            "total_events": len(events),
            "event_types": event_types,
            "alerts_by_severity": alerts_by_severity,
            "decisions_by_type": decisions_by_type,
            "log_file": str(self.log_path),
            "log_size_bytes": self.log_path.stat().st_size if self.log_path.exists() else 0
        }

    def clear_log(self):
        """
        Clear the audit log file.

        WARNING: This will delete all audit records.
        """
        if self.log_path.exists():
            self.log_path.unlink()
        print(f"✅ Cleared audit log: {self.log_path}")

    def export_to_json(self, output_file: str):
        """
        Export audit log to formatted JSON file.

        Args:
            output_file: Output JSON file path
        """
        events = self.get_events()
        with open(output_file, "w") as f:
            json.dump(events, f, indent=2)
        print(f"✅ Exported {len(events)} events to {output_file}")
