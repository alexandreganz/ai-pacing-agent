# AI Pacing Agent for Media Buying

An autonomous AI agent that monitors media spend across Google and Meta platforms, detects anomalies, and takes intelligent action based on variance thresholds and data quality confidence scores.

## Overview

This project implements a **LangGraph-based agentic system** that automates the first layer of media pacing workflow for LEGO Group's Global Media Activation (GMA) team. The agent continuously monitors campaign spend, identifies anomalies, and decides between human escalation or autonomous intervention.

### Key Features

- **Automated Anomaly Detection**: Three-tier variance classification (healthy <10%, warning 10-25%, critical >25%)
- **Zero Delivery Detection**: Immediate identification of campaigns with no spend despite positive targets
- **Confidence-Based Decision Making**: Data quality scoring prevents autonomous action on low-confidence data
- **Autonomous Actions**: Campaign pausing for critical issues (>25% variance with high confidence)
- **Human-in-the-Loop**: Escalation for low-confidence scenarios or borderline cases
- **Root Cause Analysis**: Automatic analysis of why anomalies occurred
- **Mitigation Planning**: Actionable recommendations for preventing future issues
- **Slack Integration**: Real-time alerts with formatted recommendations
- **Audit Trail**: Complete logging of all decisions and actions

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI PACING AGENT                             │
│                                                                  │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Data Ingestion │→│ Reconciliation│→│ PacingBrain      │   │
│  │  Layer         │  │  Engine      │  │  (LangGraph)     │   │
│  └────────────────┘  └──────────────┘  └──────────────────┘   │
│         ↓                    ↓                    ↓            │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Mock Platform │  │ Confidence   │  │ Action Executors │   │
│  │  APIs          │  │ Scorer       │  │ (Alert/Halt)     │   │
│  └────────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Decision Flow

The agent uses a LangGraph state machine to route decisions:

1. **Data Ingestion**: Pull target spend (internal tracker) + actual spend (platform APIs)
2. **Reconciliation**: Fuzzy match campaigns, calculate confidence scores
3. **Variance Analysis**: Compute percentage variance from target
4. **Confidence Gate**: If confidence < 70%, escalate to human
5. **Severity Routing**:
   - **Healthy (<10%)**: Log only
   - **Warning (10-25%)**: Slack alert with recommendations
   - **Critical (>25% or zero delivery)**: Autonomous halt + alert
6. **Root Cause Analysis**: Analyze why the anomaly occurred
7. **Mitigation Planning**: Generate actionable prevention steps

## Installation

### Prerequisites

- Python 3.12 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd lego-genai
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your Slack webhook URL and other settings
```

## Usage

### Quick Start (Mock Data)

Run the agent with mock campaign data:

```python
from src.agents.pacing_brain import PacingBrain
from src.api.mock_platform_api import MockPlatformAPI
from src.utils.audit_logger import AuditLogger

# Initialize components
api_client = MockPlatformAPI(platform="google")
audit_logger = AuditLogger()
slack_webhook = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Create PacingBrain agent
brain = PacingBrain(
    api_client=api_client,
    slack_webhook=slack_webhook,
    audit_logger=audit_logger
)

# Run for a specific campaign
alert = brain.run(campaign_id="google_001")

print(f"Action: {alert.action_taken}")
print(f"Recommendation: {alert.recommendation}")
```

### Interactive Demo

Run the Jupyter notebook demo:

```bash
jupyter notebook notebooks/demo.ipynb
```

This will walk you through:
- 10 test campaigns with varying spend patterns
- Real-time decision visualization
- Alert formatting examples
- Root cause analysis outputs

### Run Tests

```bash
pytest tests/ -v --cov=src
```

## Project Structure

```
lego-genai/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── .env.example                       # Environment variables template
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── spend.py                   # Data models (SpendRecord, ReconciledSpend, PacingAlert)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── pacing_brain.py            # PacingBrain LangGraph agent
│   │   └── confidence_scorer.py       # ConfidenceScorer class
│   ├── analyzers/
│   │   ├── __init__.py
│   │   └── pacing_analyzer.py         # PacingAnalyzer variance logic
│   ├── api/
│   │   ├── __init__.py
│   │   ├── mock_platform_api.py       # Mock Google/Meta APIs
│   │   └── internal_tracker.py        # Mock internal tracker
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── slack_notifier.py          # Slack webhook integration
│   │   └── audit_logger.py            # Audit trail logging
│   └── orchestrator.py                # Main runner (monitors all campaigns)
├── tests/
│   ├── __init__.py
│   ├── test_pacing_analyzer.py
│   ├── test_pacing_brain.py
│   └── test_confidence_scorer.py
├── notebooks/
│   └── demo.ipynb                     # Interactive demo
└── docs/
    ├── architecture.md
    └── api_integration_guide.md
```

## Configuration

### Variance Thresholds

Edit `.env` to customize thresholds:

```bash
HEALTHY_VARIANCE_THRESHOLD=10.0    # < 10% variance
WARNING_VARIANCE_THRESHOLD=25.0    # 10-25% variance
# > 25% is automatically critical
```

### Confidence Scoring

Confidence is calculated from:
- **Metadata Match (50%)**: Market, product, date range consistency
- **Name Similarity (30%)**: Levenshtein distance between campaign names
- **Data Freshness (20%)**: Penalty for stale data (>12 hours old)

Default threshold: 70% confidence required for autonomous action.

## Guardrail Decision Matrix

| Variance | Confidence | Zero Delivery | Action |
|----------|-----------|---------------|---------|
| < 10% | Any | No | Log only |
| 10-25% | ≥ 70% | No | Slack alert |
| 10-25% | < 70% | No | Escalate to human |
| > 25% | ≥ 70% | No | Autonomous halt + alert |
| > 25% | < 70% | No | Escalate to human |
| Any | Any | Yes | Autonomous halt + alert |

## Roadmap

### Phase 1: MVP (Current) ✅
- Mock APIs with realistic variance scenarios
- LangGraph decision engine
- Variance calculation + confidence scoring
- Slack alerting
- Audit logging

### Phase 2: Real API Integration (Weeks 4-6)
- Google Ads API integration
- Meta Marketing API integration
- OAuth 2.0 authentication
- API rate limiting + retry logic

### Phase 3: Human-in-the-Loop (Weeks 7-8)
- Slack interactive buttons (Approve/Reject)
- Human approval queue with timeouts
- Override mechanism

### Phase 4: Enhanced Intelligence (Weeks 9-12)
- LLM-powered root cause analysis (OpenAI/Claude)
- Historical pattern detection
- Predictive pacing forecasts
- Multi-campaign optimization

### Phase 5: Production Deployment (Weeks 13-16)
- Dockerized deployment
- Prometheus + Grafana monitoring
- PagerDuty integration
- Scheduled runs (every 4 hours)

## Contributing

This is an internal LEGO Group project. For questions or contributions, contact the Growth & Enablement team.

## License

Proprietary - LEGO Group Internal Use Only

## Support

- **Documentation**: See `docs/` folder
- **Issues**: Contact Growth & Enablement team
- **Case Study**: See `202601_G&E_Manager_Use_Case.pdf`

---

Built with ❤️ by the Growth & Enablement team for Global Media Activation (GMA)
