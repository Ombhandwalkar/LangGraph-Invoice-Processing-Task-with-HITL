# LangGraph Invoice Processing Agent with HITL

A production-ready **Invoice Processing Workflow** built with **LangGraph**, featuring:
- 🔄 **12-stage deterministic & non-deterministic workflow**
- ⏸️ **Human-In-The-Loop (HITL)** checkpoint/resume system
- 🤖 **MCP Client** orchestration (COMMON & ATLAS servers)
- 🛠️ **Bigtool** dynamic tool selection
- 💾 **State persistence** with SQLite checkpointing
- 🌐 **REST API** with FastAPI
- 🖥️ **Web UI** for human review

## 📋 Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Workflow Stages](#workflow-stages)
- [API Endpoints](#api-endpoints)
- [Demo & Testing](#demo--testing)
- [Project Structure](#project-structure)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   LangGraph Workflow                     │
│                                                          │
│  INTAKE → UNDERSTAND → PREPARE → RETRIEVE →             │
│  MATCH_TWO_WAY → [CHECKPOINT_HITL?] → HITL_DECISION →   │
│  RECONCILE → APPROVE → POSTING → NOTIFY → COMPLETE      │
│                                                          │
│  Components:                                             │
│  • State Management (TypedDict with operators)           │
│  • Checkpoint System (SQLite persistence)                │
│  • MCP Client (Route to COMMON/ATLAS)                    │
│  • Bigtool (Dynamic tool selection)                      │
└─────────────────────────────────────────────────────────┘
```

## ✨ Features

### 1. **Complete Workflow Implementation**
- ✅ All 12 stages implemented as LangGraph nodes
- ✅ Deterministic sequential execution
- ✅ Non-deterministic HITL decision routing
- ✅ State persistence across all nodes

### 2. **HITL Checkpoint System**
- ✅ Automatic checkpoint creation on matching failure
- ✅ State serialization to SQLite database
- ✅ Human review queue management
- ✅ Resume workflow after human decision
- ✅ Support for ACCEPT/REJECT decisions

### 3. **MCP Client Orchestration**
- ✅ Ability routing to COMMON server (no external dependencies)
- ✅ Ability routing to ATLAS server (external systems)
- ✅ Automatic server selection based on ability type
- ✅ Mock implementations for demo purposes

### 4. **Bigtool Dynamic Tool Selection**
- ✅ OCR tool selection (Google Vision, Tesseract, AWS Textract)
- ✅ Enrichment tool selection (Clearbit, PDL, Vendor DB)
- ✅ ERP connector selection (SAP, NetSuite, Mock)
- ✅ Database selection (Postgres, SQLite, DynamoDB)
- ✅ Email service selection (SendGrid, SES)
- ✅ Context-aware selection (speed, cost, accuracy)

### 5. **State Management**
- ✅ TypedDict-based state schema
- ✅ Operator-based state updates (add, or)
- ✅ Audit log accumulation
- ✅ Bigtool selection tracking

### 6. **REST API**
- ✅ Process invoice endpoint
- ✅ Get pending reviews endpoint
- ✅ Submit human decision endpoint
- ✅ Get audit log endpoint
- ✅ Bigtool history endpoint

### 7. **Web UI**
- ✅ Real-time pending reviews dashboard
- ✅ Invoice details with match score visualization
- ✅ Accept/Reject decision interface
- ✅ Review notes submission
- ✅ Auto-refresh capability

## 📦 Installation

### Prerequisites
- Python 3.9+
- pip

### Setup

1. **Clone/Navigate to project directory**
```bash
cd langgraph-invoice-agent
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables** (optional)
```bash
# Create .env file
touch .env

# Add API keys if using real services
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

## 🚀 Quick Start

### Option 1: Run Test Suite

```bash
python test_runner.py
```

This will:
- ✅ Test successful invoice processing (no HITL)
- ✅ Test invoice with HITL (matching fails)
- ✅ Verify Bigtool selections
- ✅ Display comprehensive logs

### Option 2: Start API Server

```bash
# From project root
cd src/api
python main.py
```

API will be available at `http://localhost:8000`

### Option 3: Use Web UI

1. Start the API server (see Option 2)
2. Open `frontend/index.html` in your browser
3. The dashboard will show pending reviews

## 🔄 Workflow Stages

### Stage Flow

```
START
  ↓
1. INTAKE (Deterministic)
   - Validate invoice schema
   - Persist raw data
   - Tools: Storage (Bigtool), DB
  ↓
2. UNDERSTAND (Deterministic)
   - OCR extraction
   - Parse line items
   - Tools: OCR (Bigtool via ATLAS), NLP Parser
  ↓
3. PREPARE (Deterministic)
   - Normalize vendor name
   - Enrich vendor data
   - Compute flags (risk score)
   - Tools: Enrichment (Bigtool via ATLAS), COMMON utils
  ↓
4. RETRIEVE (Deterministic)
   - Fetch POs from ERP
   - Fetch GRNs
   - Fetch historical invoices
   - Tools: ERP Connector (Bigtool via ATLAS)
  ↓
5. MATCH_TWO_WAY (Deterministic)
   - Compute match score (invoice vs PO)
   - Decision: MATCHED or FAILED
   - Tools: Match Engine (COMMON)
  ↓
  ├─[MATCHED]──────────────────┐
  └─[FAILED]                   │
      ↓                        │
6. CHECKPOINT_HITL             │
   - Create checkpoint          │
   - Persist state to DB        │
   - Add to review queue        │
   - Tools: DB (Bigtool)        │
  ↓                            │
7. HITL_DECISION               │
   (Non-Deterministic)          │
   - Await human decision       │
   - ACCEPT or REJECT           │
  ↓                            │
  ├─[ACCEPT]───────────────────┤
  └─[REJECT]────────┐          │
                     │          │
                     ↓          ↓
8. RECONCILE (Deterministic)
   - Build accounting entries (debit/credit)
   - Create reconciliation report
   - Tools: Accounting Engine (COMMON)
  ↓
9. APPROVE (Deterministic)
   - Apply approval policy
   - Auto-approve or escalate
   - Tools: Workflow Engine (ATLAS)
  ↓
10. POSTING (Deterministic)
    - Post to ERP
    - Schedule payment
    - Tools: ERP Connector (Bigtool via ATLAS)
  ↓
11. NOTIFY (Deterministic)
    - Notify vendor
    - Notify finance team
    - Tools: Email (Bigtool via ATLAS)
  ↓
12. COMPLETE (Deterministic)
    - Generate final payload
    - Create audit log
    - Mark workflow complete
    - Tools: DB (Bigtool)
  ↓
END
```

### Key Decision Points

1. **MATCH_TWO_WAY → CHECKPOINT_HITL**
   - Condition: `match_score < threshold` (default: 0.90)
   - If true: Create checkpoint and pause
   - If false: Continue to RECONCILE

2. **HITL_DECISION → RECONCILE/COMPLETE**
   - ACCEPT: Continue to RECONCILE
   - REJECT: Skip to COMPLETE with status "MANUAL_HANDOFF"

## 🌐 API Endpoints

### Base URL
```
http://localhost:8000
```

### 1. Process Invoice
```http
POST /process-invoice
Content-Type: application/json

{
  "invoice_payload": {
    "invoice_id": "INV-2025-001",
    "vendor_name": "ACME Corporation",
    "vendor_tax_id": "12-3456789",
    "invoice_date": "2025-01-10",
    "due_date": "2025-02-10",
    "amount": 1000.00,
    "currency": "USD",
    "line_items": [...],
    "attachments": [...]
  }
}
```

Response:
```json
{
  "success": true,
  "workflow_id": "uuid",
  "invoice_id": "INV-2025-001",
  "status": "COMPLETED",
  "checkpoint_id": "CKPT_xxx",  // if HITL triggered
  "review_url": "http://...",   // if HITL triggered
  "bigtool_selections": {...}
}
```

### 2. Get Pending Reviews
```http
GET /human-review/pending
```

Response:
```json
{
  "success": true,
  "count": 2,
  "items": [
    {
      "checkpoint_id": "CKPT_xxx",
      "invoice_id": "INV-2025-001",
      "vendor_name": "ACME Corp",
      "amount": 1000.00,
      "created_at": "2025-01-15T10:00:00Z",
      "reason_for_hold": "Match score 0.85 below threshold 0.90",
      "review_url": "http://..."
    }
  ]
}
```

### 3. Submit Human Decision
```http
POST /human-review/decision
Content-Type: application/json

{
  "checkpoint_id": "CKPT_xxx",
  "decision": "ACCEPT",
  "reviewer_id": "reviewer_001",
  "notes": "Reviewed and approved"
}
```

Response:
```json
{
  "success": true,
  "message": "Decision 'ACCEPT' recorded and workflow resumed",
  "final_status": "COMPLETED",
  "workflow_id": "uuid"
}
```

### 4. Get Audit Log
```http
GET /audit/{workflow_id}
```

### 5. Bigtool History
```http
GET /bigtool/history
```

## 🧪 Demo & Testing

### Test Scenarios

#### Scenario 1: Successful Processing (No HITL)
```bash
python test_runner.py
```
- Invoice amount: $1050
- PO amount: $1000
- Match score: 0.95 ✅
- Result: Auto-approved and completed

#### Scenario 2: HITL Required
- Invoice amount: $850
- PO amount: $1000
- Match score: 0.85 ⚠️
- Result: Checkpoint created, awaits human review

### Expected Output

```
================================================================================
TEST CASE 1: Successful Invoice Processing (No HITL)
================================================================================

============================================================
STAGE: INTAKE - Accepting invoice payload
============================================================
🔧 Bigtool selected storage: local_fs
✅ Invoice ingested: RAW_xxx

============================================================
STAGE: UNDERSTAND - OCR and parsing
============================================================
🔧 Bigtool selected OCR: tesseract
✅ OCR completed, 3 items parsed

[... continues through all stages ...]

================================================================================
✅ WORKFLOW COMPLETED SUCCESSFULLY
================================================================================
```

## 📁 Project Structure

```
langgraph-invoice-agent/
├── src/
│   ├── __init__.py
│   ├── state.py                 # State management
│   ├── workflow.py              # LangGraph orchestrator
│   ├── agents/
│   │   ├── __init__.py
│   │   └── invoice_agents.py    # All node implementations
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── client.py            # MCP client system
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── bigtool.py           # Bigtool selector
│   │   └── checkpoint_db.py     # Checkpoint database
│   └── api/
│       ├── __init__.py
│       └── main.py              # FastAPI server
├── config/
│   ├── workflow.json            # Workflow configuration
│   ├── sample_invoice.json      # Test data (successful)
│   └── sample_invoice_fail_match.json  # Test data (HITL)
├── frontend/
│   └── index.html               # Human review UI
├── test_runner.py               # Test suite
├── requirements.txt
└── README.md
```

## 🎯 Key Implementation Highlights

### 1. State Management with Operators
```python
class InvoiceProcessingState(TypedDict):
    # Accumulated with operator.add
    audit_log: Annotated[List[Dict[str, Any]], operator.add]
    # Merged with operator.or_
    bigtool_selections: Annotated[Dict[str, str], operator.or_]
    # Regular fields
    match_score: Optional[float]
    # ... other fields
```

### 2. Conditional Routing
```python
workflow.add_conditional_edges(
    "MATCH_TWO_WAY",
    self._should_checkpoint,
    {
        "checkpoint": "CHECKPOINT_HITL",
        "continue": "RECONCILE"
    }
)
```

### 3. Checkpoint Creation
```python
# Save state to database
checkpoint_db.create_checkpoint(
    checkpoint_id=checkpoint_id,
    workflow_id=workflow_id,
    invoice_id=invoice_id,
    state=dict(state),
    paused_reason="Matching failed"
)

# Add to review queue
checkpoint_db.add_to_review_queue(
    checkpoint_id=checkpoint_id,
    invoice_data=invoice_payload,
    reason="Match score below threshold"
)
```

### 4. Bigtool Selection
```python
# Select tool based on capability and context
ocr_tool = bigtool.select(
    capability="ocr",
    context={"priority": "accuracy"},
    pool_hint=["google_vision", "tesseract", "aws_textract"]
)
# Returns: {"name": "google_vision", "metadata": {...}}
```

### 5. MCP Routing
```python
# Route ability to appropriate server
result = await mcp_client.execute_ability(
    ability_name="enrich_vendor",
    parameters={"vendor_name": "ACME Corp"}
)
# Automatically routes to ATLAS server
```

## 📊 Demo Output Examples

### Bigtool Selections
```
INTAKE_storage: local_fs
UNDERSTAND_ocr: tesseract
PREPARE_enrichment: clearbit
RETRIEVE_erp: mock_erp
CHECKPOINT_db: sqlite
POSTING_erp: mock_erp
NOTIFY_email: sendgrid
COMPLETE_db: sqlite
```

### Audit Log
```
1. INTAKE - invoice_ingested - 2025-01-15T10:00:00Z
2. UNDERSTAND - ocr_completed - 2025-01-15T10:00:01Z
3. PREPARE - vendor_enriched - 2025-01-15T10:00:02Z
4. RETRIEVE - erp_data_fetched - 2025-01-15T10:00:03Z
5. MATCH_TWO_WAY - matching_completed - 2025-01-15T10:00:04Z
6. CHECKPOINT_HITL - checkpoint_created - 2025-01-15T10:00:05Z
7. HITL_DECISION - decision_recorded - 2025-01-15T10:00:10Z
8. RECONCILE - accounting_entries_created - 2025-01-15T10:00:11Z
9. APPROVE - approval_applied - 2025-01-15T10:00:12Z
10. POSTING - posted_to_erp - 2025-01-15T10:00:13Z
11. NOTIFY - notifications_sent - 2025-01-15T10:00:14Z
12. COMPLETE - workflow_completed - 2025-01-15T10:00:15Z
```

## 🔧 Configuration

### Workflow Configuration
Edit `config/workflow.json`:

```json
{
  "config": {
    "match_threshold": 0.90,        // Matching threshold
    "two_way_tolerance_pct": 5,     // Tolerance percentage
    "human_review_queue": "...",    // Queue name
    "checkpoint_table": "...",      // DB table
    "default_db": "..."             // DB connection
  }
}
```

### Environment Variables
Create `.env` file:
```bash
# API Keys (if using real services)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...

# Database
DATABASE_URL=sqlite:///./demo.db

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

## 🚀 Deployment Considerations

### Production Checklist
- [ ] Replace mock MCP implementations with real integrations
- [ ] Add authentication to API endpoints
- [ ] Configure real OCR services (Google Vision, etc.)
- [ ] Set up production database (PostgreSQL)
- [ ] Add monitoring and alerting
- [ ] Implement rate limiting
- [ ] Add comprehensive error handling
- [ ] Set up logging aggregation
- [ ] Configure CORS properly
- [ ] Add API documentation (Swagger)

### Scaling
- Use PostgreSQL for checkpoints (better concurrency)
- Add Redis for caching
- Deploy API with Kubernetes
- Use message queue for async processing
- Implement horizontal scaling

## 📝 License

MIT License - See LICENSE file for details

## 👥 Contributors

Built for Analytos AI coding task

## 📧 Contact

For questions or support, contact: ombhandwalkar38126@gmail.com

---

**Built with ❤️ using LangGraph, FastAPI, and modern AI workflows**
