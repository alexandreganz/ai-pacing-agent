"""
PacingBrain: LangGraph-based autonomous decision engine.

This module implements the core agentic workflow for media pacing monitoring.
The agent uses a state machine to route decisions based on variance thresholds
and data quality confidence scores.
"""

from typing import TypedDict, Optional, Dict, Any, Literal
from datetime import datetime
from langgraph.graph import StateGraph, END

from src.models.spend import ReconciledSpend, PacingAlert, Platform
from src.analyzers.pacing_analyzer import PacingAnalyzer
from src.agents.confidence_scorer import ConfidenceScorer
from src.utils.slack_notifier import SlackNotifier
from src.utils.audit_logger import AuditLogger


class AgentState(TypedDict):
    """
    State passed between nodes in the LangGraph workflow.

    This state dictionary is maintained throughout the agent's execution
    and modified by each node in the state machine.
    """
    campaign_id: str
    reconciled_spend: Optional[ReconciledSpend]
    variance_result: Optional[Dict[str, Any]]
    confidence_score: float
    action_taken: str
    recommendation: str
    requires_human: bool
    root_cause_analysis: Optional[str]
    mitigation_plan: Optional[str]
    alert: Optional[PacingAlert]


class PacingBrain:
    """
    LangGraph-based autonomous decision engine for media pacing.

    This agent orchestrates the complete pacing workflow:
    1. Fetch & reconcile spend data
    2. Calculate variance
    3. Assess confidence
    4. Route decisions based on severity and confidence
    5. Execute actions (log, alert, or autonomous halt)
    6. Analyze root cause and generate mitigation plans
    """

    # Confidence threshold for autonomous action (70%)
    CONFIDENCE_THRESHOLD = 0.7

    def __init__(
        self,
        platform_api,
        internal_tracker,
        slack_webhook: Optional[str] = None,
        audit_logger: Optional[AuditLogger] = None,
        confidence_threshold: float = CONFIDENCE_THRESHOLD
    ):
        """
        Initialize PacingBrain agent.

        Args:
            platform_api: Platform API client (MockPlatformAPI or real client)
            internal_tracker: Internal tracker client (MockInternalTracker)
            slack_webhook: Optional Slack webhook URL for alerts
            audit_logger: Optional AuditLogger instance
            confidence_threshold: Minimum confidence for autonomous action
        """
        self.platform_api = platform_api
        self.internal_tracker = internal_tracker
        self.confidence_threshold = confidence_threshold

        # Initialize components
        self.analyzer = PacingAnalyzer()
        self.confidence_scorer = ConfidenceScorer()

        # Initialize utilities
        self.slack_notifier = SlackNotifier(slack_webhook) if slack_webhook else None
        self.audit_logger = audit_logger or AuditLogger()

        # Build the state graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Construct the LangGraph state machine.

        Returns:
            Compiled StateGraph ready for execution
        """
        workflow = StateGraph(AgentState)

        # Add all nodes
        workflow.add_node("fetch_and_reconcile", self.fetch_and_reconcile)
        workflow.add_node("calculate_variance", self.calculate_variance)
        workflow.add_node("assess_confidence", self.assess_confidence)
        workflow.add_node("escalate_to_human", self.escalate_to_human)
        workflow.add_node("log_healthy", self.log_healthy)
        workflow.add_node("send_warning_alert", self.send_warning_alert)
        workflow.add_node("autonomous_halt", self.autonomous_halt)
        workflow.add_node("analyze_root_cause", self.analyze_root_cause)
        workflow.add_node("generate_mitigation", self.generate_mitigation)
        workflow.add_node("audit_and_notify", self.audit_and_notify)

        # Set entry point
        workflow.set_entry_point("fetch_and_reconcile")

        # Linear path for data gathering
        workflow.add_edge("fetch_and_reconcile", "calculate_variance")
        workflow.add_edge("calculate_variance", "assess_confidence")

        # Confidence gate: first decision point
        workflow.add_conditional_edges(
            "assess_confidence",
            self.route_by_confidence,
            {
                "low_confidence": "escalate_to_human",
                "high_confidence": "route_by_severity"
            }
        )

        # Severity routing: second decision point (only if high confidence)
        # Note: We need to handle this through a routing node
        workflow.add_node("route_by_severity", self.route_by_severity_node)
        workflow.add_conditional_edges(
            "route_by_severity",
            lambda state: state["__next_node__"],
            {
                "healthy": "log_healthy",
                "warning": "send_warning_alert",
                "critical": "autonomous_halt"
            }
        )

        # Action paths converge to analysis
        workflow.add_edge("send_warning_alert", "analyze_root_cause")
        workflow.add_edge("autonomous_halt", "analyze_root_cause")
        workflow.add_edge("analyze_root_cause", "generate_mitigation")
        workflow.add_edge("generate_mitigation", "audit_and_notify")

        # End states
        workflow.add_edge("log_healthy", END)
        workflow.add_edge("escalate_to_human", END)
        workflow.add_edge("audit_and_notify", END)

        return workflow.compile()

    # ===================
    # Node Implementations
    # ===================

    def fetch_and_reconcile(self, state: AgentState) -> AgentState:
        """
        Fetch spend data from APIs and reconcile with internal tracker.

        This node:
        1. Fetches actual spend from platform API
        2. Fetches target spend from internal tracker
        3. Calculates confidence scores for the reconciliation
        4. Creates a ReconciledSpend object
        """
        campaign_id = state["campaign_id"]

        try:
            # Fetch actual spend from platform API
            actual_spend_record = self.platform_api.get_campaign_spend(campaign_id)

            # Fetch target spend from internal tracker
            target_spend_record = self.internal_tracker.get_target_spend(campaign_id)

            # Calculate confidence scores
            confidence_scores = self.confidence_scorer.calculate_confidence(
                tracker_name=target_spend_record.campaign_name,
                api_name=actual_spend_record.campaign_name,
                tracker_metadata=target_spend_record.metadata,
                api_metadata=actual_spend_record.metadata,
                actual_timestamp=actual_spend_record.timestamp
            )

            # Create reconciled spend object
            reconciled = ReconciledSpend(
                campaign_id=campaign_id,
                campaign_name=actual_spend_record.campaign_name,
                platform=actual_spend_record.platform,
                target_spend=target_spend_record.amount_usd,
                actual_spend=actual_spend_record.amount_usd,
                target_timestamp=target_spend_record.timestamp,
                actual_timestamp=actual_spend_record.timestamp,
                metadata_match_score=confidence_scores["metadata_match_score"],
                name_similarity=confidence_scores["name_similarity"],
                data_freshness_score=confidence_scores["data_freshness_score"]
            )

            state["reconciled_spend"] = reconciled

            # Log reconciliation
            self.audit_logger.log_reconciliation(
                campaign_id=campaign_id,
                target_spend=reconciled.target_spend,
                actual_spend=reconciled.actual_spend,
                confidence_score=reconciled.confidence_score,
                metadata_match_score=reconciled.metadata_match_score,
                name_similarity=reconciled.name_similarity,
                data_freshness_score=reconciled.data_freshness_score
            )

        except Exception as e:
            # Log error and mark for human review
            self.audit_logger.log_error(
                error_type="reconciliation_error",
                error_message=str(e),
                campaign_id=campaign_id
            )
            # Set low confidence to trigger escalation
            state["confidence_score"] = 0.0
            state["requires_human"] = True
            state["recommendation"] = f"Error during reconciliation: {str(e)}"

        return state

    def calculate_variance(self, state: AgentState) -> AgentState:
        """Calculate pacing variance and classify severity."""
        reconciled = state["reconciled_spend"]

        if reconciled:
            variance_result = self.analyzer.calculate_variance(reconciled)
            state["variance_result"] = variance_result
            state["confidence_score"] = reconciled.confidence_score
        else:
            # Handle error case from fetch_and_reconcile
            state["variance_result"] = {
                "variance_pct": 0.0,
                "severity": "critical",
                "confidence": 0.0
            }

        return state

    def assess_confidence(self, state: AgentState) -> AgentState:
        """Assess data quality confidence (no-op, already calculated)."""
        # Confidence already calculated in fetch_and_reconcile
        # This node exists for clarity in the state machine
        return state

    # ================
    # Routing Functions
    # ================

    def route_by_confidence(self, state: AgentState) -> Literal["low_confidence", "high_confidence"]:
        """
        Route based on confidence score.

        If confidence < threshold, escalate to human.
        Otherwise, proceed to severity routing.
        """
        if state["confidence_score"] < self.confidence_threshold:
            return "low_confidence"
        return "high_confidence"

    def route_by_severity_node(self, state: AgentState) -> AgentState:
        """
        Routing node that determines next node based on severity.

        This is a workaround for LangGraph's conditional routing limitations.
        """
        severity = state["variance_result"]["severity"]
        state["__next_node__"] = severity
        return state

    # =============
    # Action Nodes
    # =============

    def escalate_to_human(self, state: AgentState) -> AgentState:
        """Low confidence: escalate to human for review."""
        reconciled = state["reconciled_spend"]
        confidence = state["confidence_score"]

        state["requires_human"] = True
        state["action_taken"] = "escalated_to_human"

        if reconciled:
            # Diagnose low confidence
            confidence_scores = {
                "confidence_score": reconciled.confidence_score,
                "metadata_match_score": reconciled.metadata_match_score,
                "name_similarity": reconciled.name_similarity,
                "data_freshness_score": reconciled.data_freshness_score
            }
            diagnosis = self.confidence_scorer.diagnose_low_confidence(
                confidence_scores,
                self.confidence_threshold
            )

            state["recommendation"] = (
                f"⚠️ Data quality confidence too low for autonomous action "
                f"({confidence:.1%}).\n\n"
                f"{diagnosis}\n\n"
                f"Manual review required for campaign {reconciled.campaign_id}."
            )
        else:
            state["recommendation"] = "Error during reconciliation. Manual review required."

        # Send Slack alert if configured
        if self.slack_notifier and reconciled:
            self.slack_notifier.send_alert(
                campaign_id=reconciled.campaign_id,
                campaign_name=reconciled.campaign_name,
                platform=reconciled.platform.value,
                variance_pct=state["variance_result"]["variance_pct"] if state["variance_result"] else 0,
                variance_amount=reconciled.variance_amount,
                confidence_score=confidence,
                action_taken=state["action_taken"],
                recommendation=state["recommendation"],
                severity="warning"
            )

        # Log decision
        self.audit_logger.log_decision(
            campaign_id=reconciled.campaign_id if reconciled else state["campaign_id"],
            variance_pct=state["variance_result"]["variance_pct"] if state["variance_result"] else 0,
            confidence_score=confidence,
            severity="escalated",
            decision="escalate_to_human",
            reasoning=f"Confidence ({confidence:.1%}) below threshold ({self.confidence_threshold:.1%})"
        )

        return state

    def log_healthy(self, state: AgentState) -> AgentState:
        """Healthy status: log only, no alerts."""
        reconciled = state["reconciled_spend"]
        variance_result = state["variance_result"]

        state["action_taken"] = "logged_healthy"
        state["recommendation"] = self.analyzer.generate_recommendation(
            variance_result, reconciled
        )

        # Log to audit trail
        self.audit_logger.log_event({
            "type": "healthy_pacing",
            "campaign_id": reconciled.campaign_id,
            "variance": variance_result["variance_pct"],
            "confidence": state["confidence_score"],
            "timestamp": datetime.utcnow().isoformat()
        })

        return state

    def send_warning_alert(self, state: AgentState) -> AgentState:
        """Warning level: send Slack alert with recommendations."""
        reconciled = state["reconciled_spend"]
        variance_result = state["variance_result"]

        state["action_taken"] = "warning_alert_sent"
        state["recommendation"] = self.analyzer.generate_recommendation(
            variance_result, reconciled
        )

        # Send Slack alert
        if self.slack_notifier:
            self.slack_notifier.send_alert(
                campaign_id=reconciled.campaign_id,
                campaign_name=reconciled.campaign_name,
                platform=reconciled.platform.value,
                variance_pct=variance_result["variance_pct"],
                variance_amount=reconciled.variance_amount,
                confidence_score=state["confidence_score"],
                action_taken=state["action_taken"],
                recommendation=state["recommendation"],
                severity="warning"
            )

        # Log decision
        self.audit_logger.log_decision(
            campaign_id=reconciled.campaign_id,
            variance_pct=variance_result["variance_pct"],
            confidence_score=state["confidence_score"],
            severity="warning",
            decision="send_alert",
            reasoning=f"Variance {variance_result['variance_pct']:.1f}% exceeds warning threshold"
        )

        return state

    def autonomous_halt(self, state: AgentState) -> AgentState:
        """Critical level: pause campaign + send urgent alert."""
        reconciled = state["reconciled_spend"]
        variance_result = state["variance_result"]

        # Pause campaign via API
        pause_success = self.platform_api.pause_campaign(reconciled.campaign_id)

        state["action_taken"] = "autonomous_halt_executed" if pause_success else "autonomous_halt_failed"
        state["recommendation"] = self.analyzer.generate_recommendation(
            variance_result, reconciled
        )

        # Log action
        self.audit_logger.log_action(
            campaign_id=reconciled.campaign_id,
            action_type="pause_campaign",
            success=pause_success,
            details={
                "variance_pct": variance_result["variance_pct"],
                "variance_amount": reconciled.variance_amount,
                "confidence_score": state["confidence_score"]
            }
        )

        # Send urgent Slack alert
        if self.slack_notifier:
            self.slack_notifier.send_alert(
                campaign_id=reconciled.campaign_id,
                campaign_name=reconciled.campaign_name,
                platform=reconciled.platform.value,
                variance_pct=variance_result["variance_pct"],
                variance_amount=reconciled.variance_amount,
                confidence_score=state["confidence_score"],
                action_taken=state["action_taken"],
                recommendation=state["recommendation"],
                severity="critical",
                paused=pause_success
            )

        # Log decision
        self.audit_logger.log_decision(
            campaign_id=reconciled.campaign_id,
            variance_pct=variance_result["variance_pct"],
            confidence_score=state["confidence_score"],
            severity="critical",
            decision="autonomous_halt",
            reasoning=f"Variance {variance_result['variance_pct']:.1f}% exceeds critical threshold or zero delivery detected"
        )

        return state

    def analyze_root_cause(self, state: AgentState) -> AgentState:
        """Analyze why the anomaly occurred."""
        reconciled = state["reconciled_spend"]
        variance_result = state["variance_result"]

        causes = []

        # Zero delivery analysis
        if variance_result.get("is_zero_delivery"):
            causes.extend([
                "Campaign has zero spend despite positive target",
                "Possible: paused ad sets, audience depletion, or bid too low"
            ])

        # Data quality issues
        if reconciled.data_freshness_score < 0.5:
            causes.append(
                f"Stale data: Last updated {reconciled.actual_timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
            )

        if reconciled.metadata_match_score < 0.8:
            causes.append("Campaign metadata mismatch between tracker and platform")

        # Spend direction
        if reconciled.is_overspending:
            causes.append(
                f"Actual spend (${reconciled.actual_spend:,.2f}) exceeded target "
                f"(${reconciled.target_spend:,.2f}) by ${reconciled.variance_amount:,.2f}"
            )
        elif reconciled.is_underspending:
            causes.append(
                f"Actual spend (${reconciled.actual_spend:,.2f}) below target "
                f"(${reconciled.target_spend:,.2f}) by ${reconciled.variance_amount:,.2f}"
            )

        state["root_cause_analysis"] = "\n".join(f"• {c}" for c in causes)
        return state

    def generate_mitigation(self, state: AgentState) -> AgentState:
        """Generate mitigation plan for future prevention."""
        variance_result = state["variance_result"]
        reconciled = state["reconciled_spend"]

        mitigations = []

        # Zero delivery mitigations
        if variance_result.get("is_zero_delivery"):
            mitigations.extend([
                "Review campaign targeting parameters (audience size, demographics)",
                "Increase bid amount by 20-30% to improve competitiveness",
                "Expand audience targeting criteria or lookalike audiences",
                "Check creative approval status and resubmit if rejected"
            ])

        # Overspend mitigations
        if reconciled.is_overspending:
            mitigations.extend([
                "Reduce daily/lifetime budget to prevent further overspend",
                "Implement automated budget pacing rules in platform",
                "Set up bid caps or cost controls",
                "Review and tighten targeting to reduce spend velocity"
            ])
        # Underspend mitigations
        elif reconciled.is_underspending:
            mitigations.extend([
                "Investigate low delivery causes (auction competitiveness, bid strategy)",
                "Consider reallocating budget to higher-performing campaigns",
                "Test different audience segments or placements",
                "Increase bid amounts or switch to maximize delivery bidding"
            ])

        # Data quality mitigations
        if reconciled.metadata_match_score < 0.8:
            mitigations.append("Implement stricter campaign naming conventions across all platforms")

        if reconciled.data_freshness_score < 0.8:
            mitigations.append("Enable more frequent data refresh (reduce cycle from 4h to 2h)")

        # General recommendations
        mitigations.extend([
            "Set up platform-level automated rules as backup to agent",
            "Schedule daily pacing review with GMA team",
            "Document learnings in campaign retrospective"
        ])

        state["mitigation_plan"] = "\n".join(f"• {m}" for m in mitigations)
        return state

    def audit_and_notify(self, state: AgentState) -> AgentState:
        """Log to audit trail and create final alert."""
        reconciled = state["reconciled_spend"]
        variance_result = state["variance_result"]

        # Create final alert
        alert = PacingAlert(
            alert_id=f"alert_{datetime.utcnow().timestamp()}",
            campaign_id=reconciled.campaign_id,
            severity=variance_result["severity"],
            variance_pct=variance_result["variance_pct"],
            confidence_score=state["confidence_score"],
            action_taken=state["action_taken"],
            recommendation=state["recommendation"],
            requires_human=state.get("requires_human", False),
            timestamp=datetime.utcnow(),
            root_cause_analysis=state.get("root_cause_analysis"),
            mitigation_plan=state.get("mitigation_plan"),
            metadata={
                "campaign_name": reconciled.campaign_name,
                "platform": reconciled.platform.value,
                "target_spend": reconciled.target_spend,
                "actual_spend": reconciled.actual_spend,
                "variance_amount": reconciled.variance_amount
            }
        )

        # Log alert
        self.audit_logger.log_alert(alert)

        state["alert"] = alert
        return state

    # ===================
    # Public Interface
    # ===================

    def run(self, campaign_id: str) -> PacingAlert:
        """
        Execute the full pacing workflow for a campaign.

        Args:
            campaign_id: Campaign identifier

        Returns:
            PacingAlert with final decision and recommendations
        """
        initial_state = AgentState(
            campaign_id=campaign_id,
            reconciled_spend=None,
            variance_result=None,
            confidence_score=0.0,
            action_taken="",
            recommendation="",
            requires_human=False,
            root_cause_analysis=None,
            mitigation_plan=None,
            alert=None
        )

        # Run the graph
        final_state = self.graph.invoke(initial_state)

        return final_state["alert"]

    def run_batch(self, campaign_ids: list) -> list:
        """
        Execute pacing workflow for multiple campaigns.

        Args:
            campaign_ids: List of campaign identifiers

        Returns:
            List of PacingAlert objects
        """
        return [self.run(campaign_id) for campaign_id in campaign_ids]
