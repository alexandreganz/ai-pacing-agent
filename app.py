"""
Streamlit UI for AI Pacing Agent - Interview Demo

A visual interface to demonstrate the AI Pacing Agent's capabilities.
Perfect for presentations and interviews.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json

from src.agents.pacing_brain import PacingBrain
from src.api.mock_platform_api import MockPlatformAPI
from src.api.internal_tracker import MockInternalTracker
from src.models.spend import Platform
from src.utils.audit_logger import AuditLogger
from src.utils.results_tracker import ResultsTracker
from src.analyzers.pacing_analyzer import PacingAnalyzer
from src.agents.confidence_scorer import ConfidenceScorer


# Page configuration
st.set_page_config(
    page_title="AI Pacing Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .healthy { color: #28a745; }
    .warning { color: #ffc107; }
    .critical { color: #dc3545; }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state."""
    if 'alerts' not in st.session_state:
        st.session_state.alerts = []
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'results_saved' not in st.session_state:
        st.session_state.results_saved = False


def create_severity_chart(alerts):
    """Create pie chart showing severity distribution."""
    severity_counts = {
        "Healthy": sum(1 for a in alerts if a.severity == "healthy"),
        "Warning": sum(1 for a in alerts if a.severity == "warning"),
        "Critical": sum(1 for a in alerts if a.severity == "critical")
    }

    fig = go.Figure(data=[go.Pie(
        labels=list(severity_counts.keys()),
        values=list(severity_counts.values()),
        marker_colors=['#28a745', '#ffc107', '#dc3545'],
        hole=0.4
    )])

    fig.update_layout(
        title="Campaign Severity Distribution",
        height=300,
        showlegend=True
    )

    return fig


def create_variance_chart(alerts):
    """Create bar chart showing variance distribution."""
    df = pd.DataFrame([
        {
            "Campaign": a.campaign_id,
            "Variance %": a.variance_pct,
            "Severity": a.severity
        }
        for a in alerts
    ])

    color_map = {
        "healthy": "#28a745",
        "warning": "#ffc107",
        "critical": "#dc3545"
    }

    fig = px.bar(
        df,
        x="Campaign",
        y="Variance %",
        color="Severity",
        color_discrete_map=color_map,
        title="Campaign Variance Distribution"
    )

    fig.update_layout(height=400)
    return fig


def create_confidence_chart(alerts):
    """Create scatter plot showing confidence vs variance."""
    df = pd.DataFrame([
        {
            "Campaign": a.campaign_id,
            "Variance %": a.variance_pct,
            "Confidence": a.confidence_score * 100,
            "Severity": a.severity,
            "Action": a.action_taken
        }
        for a in alerts
    ])

    color_map = {
        "healthy": "#28a745",
        "warning": "#ffc107",
        "critical": "#dc3545"
    }

    fig = px.scatter(
        df,
        x="Confidence",
        y="Variance %",
        color="Severity",
        color_discrete_map=color_map,
        size=[10]*len(df),
        hover_data=["Campaign", "Action"],
        title="Confidence vs Variance Analysis"
    )

    # Add threshold lines
    fig.add_hline(y=10, line_dash="dash", line_color="green", annotation_text="Healthy threshold")
    fig.add_hline(y=25, line_dash="dash", line_color="orange", annotation_text="Warning threshold")
    fig.add_vline(x=70, line_dash="dash", line_color="blue", annotation_text="Confidence threshold")

    fig.update_layout(height=400)
    return fig


def run_agent(platform, num_campaigns, seed, confidence_threshold, healthy_threshold, warning_threshold):
    """Run the pacing agent with given configuration."""
    with st.spinner("Initializing agent..."):
        # Create components
        platform_api = MockPlatformAPI(platform, num_campaigns=num_campaigns, seed=seed)
        internal_tracker = MockInternalTracker()
        audit_logger = AuditLogger(log_file="streamlit_audit.jsonl")

        # Create analyzer with custom thresholds
        analyzer = PacingAnalyzer(
            healthy_threshold=healthy_threshold,
            warning_threshold=warning_threshold
        )

        # Create brain (we'll process manually to show progress)
        scorer = ConfidenceScorer()

    # Process campaigns with progress bar
    campaign_ids = platform_api.list_campaign_ids()
    progress_bar = st.progress(0)
    status_text = st.empty()

    alerts = []

    for i, campaign_id in enumerate(campaign_ids):
        status_text.text(f"Processing {campaign_id}... ({i+1}/{len(campaign_ids)})")

        # Fetch data
        actual = platform_api.get_campaign_spend(campaign_id)
        target = internal_tracker.get_target_spend(campaign_id)

        # Calculate confidence
        confidence_scores = scorer.calculate_confidence(
            tracker_name=target.campaign_name,
            api_name=actual.campaign_name,
            tracker_metadata=target.metadata,
            api_metadata=actual.metadata,
            actual_timestamp=actual.timestamp
        )

        # Create reconciled spend
        from src.models.spend import ReconciledSpend
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

        # Generate recommendation
        recommendation = analyzer.generate_recommendation(variance_result, reconciled)

        # Determine action
        if variance_result["confidence"] < confidence_threshold:
            action_taken = "escalated_to_human"
        elif variance_result["severity"] == "healthy":
            action_taken = "logged_healthy"
        elif variance_result["severity"] == "warning":
            action_taken = "warning_alert_sent"
        else:
            action_taken = "autonomous_halt_executed"

        # Create alert
        from src.models.spend import PacingAlert
        alert = PacingAlert(
            alert_id=f"alert_{i}",
            campaign_id=campaign_id,
            severity=variance_result["severity"],
            variance_pct=variance_result["variance_pct"],
            confidence_score=reconciled.confidence_score,
            action_taken=action_taken,
            recommendation=recommendation,
            requires_human=(variance_result["confidence"] < confidence_threshold),
            timestamp=datetime.utcnow(),
            metadata={
                "target_spend": target.amount_usd,
                "actual_spend": actual.amount_usd
            }
        )

        alerts.append(alert)
        progress_bar.progress((i + 1) / len(campaign_ids))

    status_text.text("✅ Processing complete!")
    return alerts


def main():
    """Main Streamlit app."""
    initialize_session_state()

    # Header
    st.title("🤖 AI Pacing Agent - Interview Demo")
    st.markdown("**Autonomous Media Spend Monitoring with LangGraph**")

    # Sidebar - Configuration
    st.sidebar.header("⚙️ Configuration")

    platform = st.sidebar.selectbox(
        "Platform",
        [Platform.GOOGLE, Platform.META, Platform.DV360],
        format_func=lambda x: x.value.upper()
    )

    num_campaigns = st.sidebar.slider(
        "Number of Campaigns",
        min_value=5,
        max_value=50,
        value=20,
        step=5
    )

    seed = st.sidebar.number_input(
        "Random Seed (for reproducibility)",
        min_value=1,
        max_value=1000,
        value=42
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🎚️ Agent Thresholds")

    confidence_threshold = st.sidebar.slider(
        "Confidence Threshold (%)",
        min_value=50,
        max_value=95,
        value=70,
        step=5,
        help="Minimum confidence required for autonomous action"
    ) / 100

    healthy_threshold = st.sidebar.slider(
        "Healthy Variance Threshold (%)",
        min_value=5,
        max_value=20,
        value=10,
        step=1,
        help="Maximum variance for healthy classification"
    )

    warning_threshold = st.sidebar.slider(
        "Warning Variance Threshold (%)",
        min_value=15,
        max_value=40,
        value=25,
        step=5,
        help="Maximum variance for warning classification"
    )

    # Run button
    if st.sidebar.button("🚀 Run Agent", type="primary"):
        st.session_state.alerts = run_agent(
            platform,
            num_campaigns,
            seed,
            confidence_threshold,
            healthy_threshold,
            warning_threshold
        )
        st.session_state.results_saved = False

    # Save results button
    if st.session_state.alerts and not st.session_state.results_saved:
        st.sidebar.markdown("---")
        run_name = st.sidebar.text_input("Run Name", value=f"Run_{datetime.now().strftime('%Y%m%d_%H%M')}")
        notes = st.sidebar.text_area("Notes", placeholder="Optional notes about this run...")

        if st.sidebar.button("💾 Save Results"):
            tracker = ResultsTracker()
            config = {
                "platform": platform.value,
                "num_campaigns": num_campaigns,
                "seed": seed,
                "confidence_threshold": confidence_threshold,
                "healthy_threshold": healthy_threshold,
                "warning_threshold": warning_threshold
            }
            filepath = tracker.save_run(st.session_state.alerts, config, run_name, notes)
            st.sidebar.success(f"Saved to {filepath}")
            st.session_state.results_saved = True

    # Main content
    if not st.session_state.alerts:
        # Welcome screen
        st.info("👈 Configure settings in the sidebar and click 'Run Agent' to start")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🎯 What This Demonstrates")
            st.markdown("""
            - **Autonomous Decision-Making**: Agent classifies campaigns and takes action
            - **Safety Guardrails**: Low confidence → human escalation
            - **Three-Tier Classification**: Healthy / Warning / Critical
            - **Confidence Scoring**: Metadata + Name similarity + Freshness
            - **Configurable Thresholds**: Adjust and see impact in real-time
            """)

        with col2:
            st.markdown("### 🏗️ Architecture")
            st.markdown("""
            ```
            Data Ingestion → Reconciliation
                    ↓
            Variance Analysis → Confidence Scoring
                    ↓
            Decision Logic (LangGraph)
                    ↓
            Actions: Log / Alert / Halt / Escalate
            ```
            """)

        st.markdown("---")
        st.markdown("### 📊 Previous Runs")

        tracker = ResultsTracker()
        runs = tracker.list_runs()

        if runs:
            runs_df = pd.DataFrame(runs)
            st.dataframe(runs_df, use_container_width=True)
        else:
            st.info("No previous runs found. Run the agent to create your first results!")

    else:
        # Results view
        alerts = st.session_state.alerts

        # Summary metrics
        st.markdown("### 📊 Summary Metrics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Campaigns",
                len(alerts),
                help="Total campaigns processed"
            )

        with col2:
            healthy = sum(1 for a in alerts if a.severity == "healthy")
            st.metric(
                "Healthy",
                f"{healthy} ({healthy/len(alerts)*100:.1f}%)",
                help="Campaigns within acceptable variance"
            )

        with col3:
            warning = sum(1 for a in alerts if a.severity == "warning")
            st.metric(
                "Warning",
                f"{warning} ({warning/len(alerts)*100:.1f}%)",
                help="Campaigns requiring attention"
            )

        with col4:
            critical = sum(1 for a in alerts if a.severity == "critical")
            st.metric(
                "Critical",
                f"{critical} ({critical/len(alerts)*100:.1f}%)",
                help="Campaigns requiring immediate action"
            )

        # Charts
        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.plotly_chart(create_severity_chart(alerts), use_container_width=True)

        with col2:
            autonomous = sum(1 for a in alerts if a.is_autonomous_action)
            escalated = sum(1 for a in alerts if a.requires_human)

            fig = go.Figure(data=[go.Bar(
                x=["Autonomous Actions", "Human Escalations", "Alerts Sent"],
                y=[autonomous, escalated, warning + critical],
                marker_color=['#17a2b8', '#ffc107', '#6c757d']
            )])
            fig.update_layout(title="Action Distribution", height=300)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.plotly_chart(create_variance_chart(alerts), use_container_width=True)

        st.markdown("---")
        st.plotly_chart(create_confidence_chart(alerts), use_container_width=True)

        # Campaign details table
        st.markdown("---")
        st.markdown("### 📋 Campaign Details")

        df = pd.DataFrame([
            {
                "Campaign ID": a.campaign_id,
                "Severity": a.severity.upper(),
                "Variance %": f"{a.variance_pct:.1f}%",
                "Confidence": f"{a.confidence_score:.1%}",
                "Action": a.action_taken.replace('_', ' ').title(),
                "Target": f"${a.metadata.get('target_spend', 0):,.2f}",
                "Actual": f"${a.metadata.get('actual_spend', 0):,.2f}"
            }
            for a in alerts
        ])

        # Color code by severity
        def highlight_severity(row):
            if "CRITICAL" in row["Severity"]:
                return ['background-color: #f8d7da'] * len(row)
            elif "WARNING" in row["Severity"]:
                return ['background-color: #fff3cd'] * len(row)
            else:
                return ['background-color: #d4edda'] * len(row)

        st.dataframe(
            df.style.apply(highlight_severity, axis=1),
            use_container_width=True,
            height=400
        )

        # Detailed view
        st.markdown("---")
        st.markdown("### 🔍 Detailed Campaign Analysis")

        selected_campaign = st.selectbox(
            "Select Campaign",
            [a.campaign_id for a in alerts]
        )

        selected_alert = next(a for a in alerts if a.campaign_id == selected_campaign)

        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown(f"**Campaign:** {selected_alert.campaign_id}")
            st.markdown(f"**Severity:** :{selected_alert.severity}: {selected_alert.severity.upper()}")
            st.markdown(f"**Variance:** {selected_alert.variance_pct:.1f}%")
            st.markdown(f"**Confidence:** {selected_alert.confidence_score:.1%}")
            st.markdown(f"**Action:** {selected_alert.action_taken.replace('_', ' ').title()}")
            st.markdown(f"**Requires Human:** {'Yes' if selected_alert.requires_human else 'No'}")

        with col2:
            st.markdown("**Financial Details:**")
            st.markdown(f"- Target Spend: ${selected_alert.metadata.get('target_spend', 0):,.2f}")
            st.markdown(f"- Actual Spend: ${selected_alert.metadata.get('actual_spend', 0):,.2f}")
            variance_amount = abs(selected_alert.metadata.get('actual_spend', 0) - selected_alert.metadata.get('target_spend', 0))
            st.markdown(f"- Variance Amount: ${variance_amount:,.2f}")

        st.markdown("**Recommendation:**")
        st.info(selected_alert.recommendation)


if __name__ == "__main__":
    main()
