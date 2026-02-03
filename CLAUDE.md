# CLAUDE.md

This file provides guidance to Claude Code when working on the **AI Pacing Agent for Media Buying** project.

## Project Overview

The AI Pacing Agent is an autonomous LangGraph-based system that monitors media spend across advertising platforms (Google, Meta, DV360) and takes intelligent action based on variance thresholds and data quality confidence scores.

**Status**: MVP Phase 1 complete (mock APIs) | Ready for Phase 2 (real API integration)

**Key Features**:
- Autonomous decision-making with safety guardrails
- Three-tier variance classification (<10% healthy, 10-25% warning, >25% critical)
- Confidence-based routing (70% threshold)
- Root cause analysis and mitigation planning
- Complete audit trail for compliance

## Architecture

### Core Components

```
PacingOrchestrator (src/orchestrator.py)
    ↓
PacingBrain (src/agents/pacing_brain.py) - LangGraph state machine
    ↓
Decision Flow:
    Fetch & Reconcile → Calculate Variance → Assess Confidence
                                                ↓
                              ┌─────────────────┴─────────────────┐
                              ↓                                   ↓
                      [Low Confidence]                    [High Confidence]
                      Escalate to Human                    Route by Severity
                                                                  ↓
                                              ┌───────────────────┼───────────────┐
                                              ↓                   ↓               ↓
                                          Healthy             Warning         Critical
                                         Log Only          Slack Alert    Autonomous Halt
                                                                ↓               ↓
                                                         Root Cause Analysis
                                                         Mitigation Planning
                                                         Audit & Notify
```

### Key Files

**Core Logic**:
- `src/agents/pacing_brain.py` (500+ lines) - Main LangGraph agent
- `src/analyzers/pacing_analyzer.py` (200+ lines) - Variance classification
- `src/agents/confidence_scorer.py` (250+ lines) - Data quality scoring

**Data Models**:
- `src/models/spend.py` (250+ lines) - SpendRecord, ReconciledSpend, PacingAlert

**APIs (MVP - Mock)**:
- `src/api/mock_platform_api.py` (250+ lines) - Simulated platform APIs
- `src/api/internal_tracker.py` (150+ lines) - Simulated internal tracker

**Utilities**:
- `src/utils/slack_notifier.py` (200+ lines) - Slack webhook integration
- `src/utils/audit_logger.py` (150+ lines) - Audit trail logging

**Orchestration**:
- `src/orchestrator.py` (250+ lines) - Multi-platform campaign monitoring

**Tests**:
- `tests/test_pacing_analyzer.py` (180 lines) - 25+ test cases
- `tests/test_confidence_scorer.py` (230 lines) - 30+ test cases
- `tests/test_models.py` (140 lines) - 15+ test cases
- `tests/test_mock_apis.py` (160 lines) - 20+ test cases

**Documentation**:
- `README.md` - Setup, usage, architecture overview
- `docs/architecture.md` - Detailed system design
- `notebooks/demo.ipynb` - Interactive demonstration

## Development Workflow

### Initial Setup

```bash
cd lego-genai
pip install -r requirements.txt
```

**Environment Variables** (optional for MVP):
```bash
cp .env.example .env
# Edit .env with Slack webhook URL
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
CONFIDENCE_THRESHOLD=0.7
```

### Running the Agent

**Quick Demo**:
```bash
python example.py
```

**Full Orchestrator**:
```bash
python -m src.orchestrator
```

**Interactive Notebook**:
```bash
jupyter notebook notebooks/demo.ipynb
```

**Single Campaign Test**:
```python
from src.agents.pacing_brain import PacingBrain
from src.api.mock_platform_api import MockPlatformAPI
from src.api.internal_tracker import MockInternalTracker

# Initialize
api = MockPlatformAPI(Platform.GOOGLE, num_campaigns=5, seed=42)
tracker = MockInternalTracker()
brain = PacingBrain(api, tracker)

# Run for one campaign
alert = brain.run("google_001")
print(alert)
```

### Testing

**Run All Tests**:
```bash
pytest tests/ -v
```

**Run Specific Test File**:
```bash
pytest tests/test_pacing_analyzer.py -v
```

**Run with Coverage**:
```bash
pytest tests/ -v --cov=src --cov-report=html
# View: open htmlcov/index.html
```

**Run Single Test**:
```bash
pytest tests/test_pacing_analyzer.py::TestVarianceCalculation::test_zero_delivery_always_critical -v
```

### Debugging

**Enable Verbose Logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Inspect State at Each Node**:
```python
# In pacing_brain.py, add print statements in nodes:
def calculate_variance(self, state: AgentState) -> AgentState:
    print(f"DEBUG: Reconciled spend = {state['reconciled_spend']}")
    # ... rest of code
```

**Check Audit Log**:
```bash
tail -f audit_log.jsonl
# Or in Python:
from src.utils.audit_logger import AuditLogger
logger = AuditLogger()
events = logger.get_events(event_type="agent_decision")
```

## Common Development Tasks

### 1. Adding a New Platform (e.g., TikTok)

**Step 1**: Add to Platform enum
```python
# src/models/spend.py
class Platform(Enum):
    GOOGLE = "google"
    META = "meta"
    DV360 = "dv360"
    TIKTOK = "tiktok"  # ADD THIS
```

**Step 2**: Create mock API
```python
# In orchestrator.py or test file
tiktok_api = MockPlatformAPI(Platform.TIKTOK, num_campaigns=10, seed=44)
```

**Step 3**: Add to orchestrator
```python
# src/orchestrator.py __init__
self.platforms = platforms or [Platform.GOOGLE, Platform.META, Platform.TIKTOK]
```

### 2. Adjusting Variance Thresholds

**Option A**: Environment variable (preferred)
```bash
# .env
HEALTHY_VARIANCE_THRESHOLD=5.0   # Change from 10.0
WARNING_VARIANCE_THRESHOLD=15.0  # Change from 25.0
```

**Option B**: Code change
```python
# src/analyzers/pacing_analyzer.py
analyzer = PacingAnalyzer(
    healthy_threshold=5.0,
    warning_threshold=15.0
)
```

### 3. Changing Confidence Threshold

```bash
# .env
CONFIDENCE_THRESHOLD=0.8  # Increase from 0.7 (more strict)
```

Or in code:
```python
brain = PacingBrain(
    platform_api=api,
    internal_tracker=tracker,
    confidence_threshold=0.8
)
```

### 4. Customizing Confidence Weights

```python
# src/agents/confidence_scorer.py
scorer = ConfidenceScorer(
    metadata_weight=0.6,      # Increase metadata importance
    name_similarity_weight=0.2,  # Decrease name importance
    freshness_weight=0.2      # Keep freshness same
)
```

### 5. Adding Custom Metadata Fields

```python
# src/agents/confidence_scorer.py
scorer = ConfidenceScorer(
    required_fields=["market", "product", "start_date", "end_date", "campaign_type"]
)
```

### 6. Implementing Real API Client

**Step 1**: Install API SDKs
```bash
pip install google-ads==23.0.0
pip install facebook-business==19.0.0
```

**Step 2**: Create real client (replace mock)
```python
# src/api/google_ads_client.py
from google.ads.googleads.client import GoogleAdsClient

class GoogleAdsAPIClient:
    def __init__(self, credentials_path: str):
        self.client = GoogleAdsClient.load_from_storage(credentials_path)

    def get_campaign_spend(self, campaign_id: str) -> SpendRecord:
        # Use Google Ads API to fetch real spend
        query = f"""
            SELECT campaign.id, campaign.name, metrics.cost_micros
            FROM campaign
            WHERE campaign.id = {campaign_id}
        """
        # ... implement API call
```

**Step 3**: Swap in orchestrator
```python
# src/orchestrator.py
from src.api.google_ads_client import GoogleAdsAPIClient

self.platform_apis = {
    Platform.GOOGLE: GoogleAdsAPIClient("google-ads.yaml"),
    Platform.META: MetaAdsAPIClient("meta-credentials.json")
}
```

### 7. Testing Agent Decisions

**Test Specific Variance Scenario**:
```python
# In test file or notebook
from src.models.spend import ReconciledSpend

reconciled = ReconciledSpend(
    campaign_id="test_critical",
    campaign_name="Test",
    platform=Platform.GOOGLE,
    target_spend=10000,
    actual_spend=14000,  # 40% variance - critical
    target_timestamp=datetime.utcnow(),
    actual_timestamp=datetime.utcnow(),
    metadata_match_score=0.9,
    name_similarity=0.9,
    data_freshness_score=0.9
)

variance_result = analyzer.calculate_variance(reconciled)
assert variance_result["severity"] == "critical"
```

### 8. Adding New Node to LangGraph

**Step 1**: Define node function
```python
# src/agents/pacing_brain.py
def check_historical_patterns(self, state: AgentState) -> AgentState:
    """Check if variance matches historical patterns."""
    # Your logic here
    state["historical_match"] = True
    return state
```

**Step 2**: Add to graph
```python
# In _build_graph()
workflow.add_node("check_historical_patterns", self.check_historical_patterns)
workflow.add_edge("analyze_root_cause", "check_historical_patterns")
workflow.add_edge("check_historical_patterns", "generate_mitigation")
```

## Testing Guidelines

### Test Structure

**Unit Tests**: Test individual components in isolation
- `test_pacing_analyzer.py` - Variance logic only
- `test_confidence_scorer.py` - Confidence scoring only
- `test_models.py` - Data model properties

**Integration Tests**: Test component interactions
- `test_mock_apis.py` - API + tracker interaction
- Future: `test_pacing_brain.py` - Full LangGraph workflow

### Writing New Tests

**Template**:
```python
import pytest
from src.analyzers.pacing_analyzer import PacingAnalyzer

class TestNewFeature:
    """Test description."""

    @pytest.fixture
    def analyzer(self):
        """Setup fixture."""
        return PacingAnalyzer()

    def test_feature_behavior(self, analyzer):
        """Test specific behavior."""
        result = analyzer.some_method()
        assert result == expected_value
```

**Run New Test**:
```bash
pytest tests/test_new_feature.py::TestNewFeature::test_feature_behavior -v
```

### Test Coverage Goals

- Core logic (analyzers, confidence): **95%+**
- Data models: **90%+**
- API clients (mock): **80%+**
- Utilities: **70%+**

## Deployment (Phase 2+)

### Phase 2: Real API Integration

**Prerequisites**:
- Google Ads API credentials (OAuth 2.0)
- Meta Marketing API access token
- API rate limit quotas approved

**Steps**:
1. Implement real API clients (replace `MockPlatformAPI`)
2. Add rate limiting and retry logic
3. Test with 3 pilot campaigns
4. Monitor API costs and latency

### Phase 3: Production Deployment

**Infrastructure**:
```yaml
# docker-compose.yml
services:
  pacing-agent:
    build: .
    environment:
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
      - CONFIDENCE_THRESHOLD=0.7
      - DATABASE_URL=postgresql://...
    volumes:
      - ./audit_logs:/app/logs
```

**Scheduler** (run every 4 hours):
```bash
# cron
0 */4 * * * cd /app && python -m src.orchestrator >> /var/log/pacing-agent.log 2>&1
```

**Or use Airflow**:
```python
# airflow_dag.py
from airflow import DAG
from airflow.operators.python import PythonOperator

def run_pacing_agent():
    from src.orchestrator import PacingOrchestrator
    orch = PacingOrchestrator()
    orch.run_all_campaigns()

dag = DAG('pacing_agent', schedule_interval='0 */4 * * *')
task = PythonOperator(task_id='run_agent', python_callable=run_pacing_agent, dag=dag)
```

## Troubleshooting

### Issue: "Module not found" errors

**Solution**:
```bash
# Ensure you're in project root
cd lego-genai

# Check PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use module syntax
python -m src.orchestrator
```

### Issue: LangGraph state machine not routing correctly

**Debug**:
```python
# Add prints in routing functions
def route_by_confidence(self, state: AgentState) -> Literal["low_confidence", "high_confidence"]:
    confidence = state["confidence_score"]
    print(f"DEBUG: Confidence = {confidence}, Threshold = {self.confidence_threshold}")
    if confidence < self.confidence_threshold:
        print("DEBUG: Routing to low_confidence")
        return "low_confidence"
    print("DEBUG: Routing to high_confidence")
    return "high_confidence"
```

### Issue: Tests failing with "fixture not found"

**Solution**: Check fixture is in same test file or in `conftest.py`:
```python
# tests/conftest.py
import pytest

@pytest.fixture
def sample_reconciled_spend():
    # Shared fixture
    return ReconciledSpend(...)
```

### Issue: Audit log growing too large

**Solution**: Implement log rotation
```bash
# Use logrotate or Python logging
# In audit_logger.py, add size limit:
if os.path.getsize(self.log_path) > 100_000_000:  # 100MB
    os.rename(self.log_path, f"{self.log_path}.{datetime.now().isoformat()}")
```

### Issue: Slack alerts not sending

**Check**:
1. Webhook URL is correct: `echo $SLACK_WEBHOOK_URL`
2. Test connection:
```python
from src.utils.slack_notifier import SlackNotifier
notifier = SlackNotifier(webhook_url)
notifier.test_connection()
```
3. Check firewall/proxy settings

## Performance Optimization

### Current Performance (MVP)
- **Campaign processing**: ~2 seconds per campaign
- **Batch (20 campaigns)**: ~40 seconds
- **Memory usage**: ~50MB

### Optimization Strategies (Phase 4+)

**1. Parallel Processing**:
```python
from concurrent.futures import ThreadPoolExecutor

def run_parallel(campaign_ids):
    with ThreadPoolExecutor(max_workers=5) as executor:
        alerts = list(executor.map(brain.run, campaign_ids))
    return alerts
```

**2. Caching**:
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_target_spend_cached(campaign_id: str):
    return internal_tracker.get_target_spend(campaign_id)
```

**3. Database Instead of JSONL**:
```python
# Use PostgreSQL for audit log
# Faster queries, better concurrency
```

## Code Style Guidelines

**Imports**:
```python
# Standard library
from datetime import datetime
from typing import Dict, List

# Third-party
from langgraph.graph import StateGraph

# Local
from src.models.spend import Platform
```

**Docstrings**:
```python
def calculate_variance(self, reconciled: ReconciledSpend) -> Dict[str, Any]:
    """
    Calculate pacing variance and classify severity.

    Args:
        reconciled: Reconciled spend data with target and actual spend

    Returns:
        Dictionary containing variance_pct, severity, confidence, etc.
    """
```

**Type Hints**: Always use type hints for function parameters and returns

**Error Handling**: Log errors to audit trail
```python
try:
    # risky operation
except Exception as e:
    self.audit_logger.log_error("error_type", str(e), campaign_id)
    raise
```

## Useful Commands

```bash
# Run everything
python example.py

# Run with different seed (different mock data)
python -c "from src.orchestrator import *; orch = PacingOrchestrator(); orch.run_all_campaigns()"

# Check audit log
cat audit_log.jsonl | jq .

# Count alerts by severity
cat audit_log.jsonl | jq -r 'select(.event_type=="pacing_alert") | .severity' | sort | uniq -c

# Find all critical alerts
cat audit_log.jsonl | jq 'select(.severity=="critical")'

# Export audit log to formatted JSON
python -c "from src.utils.audit_logger import AuditLogger; AuditLogger().export_to_json('audit.json')"
```

## Additional Resources

- **LangGraph Docs**: https://python.langchain.com/docs/langgraph
- **Google Ads API**: https://developers.google.com/google-ads/api/docs/start
- **Meta Marketing API**: https://developers.facebook.com/docs/marketing-apis
- **Pydantic**: https://docs.pydantic.dev/latest/

## Questions?

If implementing new features or fixing bugs, always:
1. **Read the plan**: `.claude/plans/twinkling-stirring-pumpkin.md`
2. **Check architecture**: `docs/architecture.md`
3. **Run tests**: Ensure existing tests pass
4. **Add tests**: Write tests for new functionality
5. **Update docs**: Keep README and this file in sync

---

**Current Phase**: MVP (Phase 1) - Mock APIs
**Next Phase**: Real API Integration (Phase 2)
**Target**: Production Deployment (Phase 5)
