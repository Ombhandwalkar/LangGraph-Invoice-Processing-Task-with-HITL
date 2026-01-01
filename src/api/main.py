"""
FastAPI Backend for Invoice Processing Workflow
Provides REST API for triggering workflows and human review
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
import asyncio
from datetime import datetime

from src.workflow import InvoiceProcessingWorkflow
from src.tools.checkpoint_db import checkpoint_db
from src.tools.bigtool import bigtool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Invoice Processing Workflow API",
    description="LangGraph-based invoice processing with HITL",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize workflow
workflow = None


@app.on_event("startup")
async def startup_event():
    """Initialize workflow on startup"""
    global workflow
    workflow = InvoiceProcessingWorkflow("config/workflow.json")
    logger.info("🚀 Invoice Processing Workflow API started")
    logger.info(workflow.get_graph_visualization())


# Request/Response Models
class LineItemModel(BaseModel):
    desc: str
    qty: float
    unit_price: float
    total: float


class InvoicePayloadModel(BaseModel):
    invoice_id: str
    vendor_name: str
    vendor_tax_id: str
    invoice_date: str
    due_date: str
    amount: float
    currency: str
    line_items: List[LineItemModel]
    attachments: List[str]


class ProcessInvoiceRequest(BaseModel):
    invoice_payload: InvoicePayloadModel
    thread_id: Optional[str] = "default"


class HumanDecisionRequest(BaseModel):
    checkpoint_id: str
    decision: str  # "ACCEPT" or "REJECT"
    reviewer_id: str
    notes: Optional[str] = ""


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Invoice Processing Workflow API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "workflow_loaded": workflow is not None
    }


@app.post("/process-invoice")
async def process_invoice(request: ProcessInvoiceRequest):
    """
    Process an invoice through the complete workflow
    
    This endpoint triggers the full invoice processing workflow:
    1. INTAKE - Validate and store invoice
    2. UNDERSTAND - OCR and parsing
    3. PREPARE - Vendor enrichment
    4. RETRIEVE - Fetch ERP data
    5. MATCH_TWO_WAY - Compute matching score
    6. [Conditional] CHECKPOINT_HITL - Create checkpoint if match fails
    7. [Conditional] HITL_DECISION - Process human decision
    8. RECONCILE - Build accounting entries
    9. APPROVE - Apply approval policy
    10. POSTING - Post to ERP
    11. NOTIFY - Send notifications
    12. COMPLETE - Finalize
    """
    try:
        logger.info(f"Received invoice processing request: {request.invoice_payload.invoice_id}")
        
        # Convert Pydantic model to dict
        invoice_payload = request.invoice_payload.dict()
        
        # Run workflow
        final_state = await workflow.run(
            invoice_payload=invoice_payload,
            thread_id=request.thread_id
        )
        
        return {
            "success": True,
            "message": "Invoice processed successfully",
            "workflow_id": final_state.get("workflow_id"),
            "invoice_id": invoice_payload["invoice_id"],
            "status": final_state.get("status"),
            "final_payload": final_state.get("final_payload"),
            "bigtool_selections": final_state.get("bigtool_selections", {}),
            "checkpoint_id": final_state.get("checkpoint_ref"),
            "review_url": final_state.get("review_url")
        }
    
    except Exception as e:
        logger.error(f"Error processing invoice: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/human-review/pending")
async def get_pending_reviews():
    """
    Get all invoices pending human review
    
    Returns a list of invoices that are paused and waiting for human decision
    """
    try:
        pending = checkpoint_db.get_pending_reviews()
        
        return {
            "success": True,
            "count": len(pending),
            "items": pending
        }
    
    except Exception as e:
        logger.error(f"Error fetching pending reviews: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/human-review/history")
async def get_human_review_history():
    """
    Get history of human decisions (Accepted/Rejected)
    """
    try:
        history = checkpoint_db.get_decision_history()
        
        return {
            "success": True,
            "history": history
        }
    
    except Exception as e:
        logger.error(f"Error fetching review history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/human-review/{checkpoint_id}")
async def get_review_details(checkpoint_id: str):
    """
    Get detailed information about a specific review checkpoint
    """
    try:
        checkpoint_data = checkpoint_db.get_checkpoint(checkpoint_id)
        
        if not checkpoint_data:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        
        state = checkpoint_data["state"]
        
        return {
            "success": True,
            "checkpoint_id": checkpoint_id,
            "invoice_id": checkpoint_data["invoice_id"],
            "paused_reason": checkpoint_data["paused_reason"],
            "status": checkpoint_data["status"],
            "invoice_data": {
                "invoice_id": state["invoice_payload"]["invoice_id"],
                "vendor_name": state["invoice_payload"]["vendor_name"],
                "amount": state["invoice_payload"]["amount"],
                "currency": state["invoice_payload"]["currency"],
                "invoice_date": state["invoice_payload"]["invoice_date"],
                "due_date": state["invoice_payload"]["due_date"]
            },
            "match_data": {
                "match_score": state.get("match_score"),
                "match_result": state.get("match_result"),
                "tolerance_pct": state.get("tolerance_pct"),
                "invoice_amount": state["invoice_payload"]["amount"],
                "po_amount": state.get("matched_pos", [{}])[0].get("amount", 0) if state.get("matched_pos") else 0
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching review details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/human-review/decision")
async def submit_human_decision(request: HumanDecisionRequest):
    """
    Submit a human decision for a checkpoint and resume workflow
    
    The decision can be:
    - ACCEPT: Continue processing the invoice
    - REJECT: Mark for manual handling and complete workflow
    """
    try:
        if request.decision not in ["ACCEPT", "REJECT"]:
            raise HTTPException(
                status_code=400,
                detail="Decision must be either 'ACCEPT' or 'REJECT'"
            )
        
        logger.info(
            f"Received human decision for checkpoint {request.checkpoint_id}: "
            f"{request.decision} by {request.reviewer_id}"
        )
        
        # Resume workflow from checkpoint
        final_state = await workflow.resume_from_checkpoint(
            checkpoint_id=request.checkpoint_id,
            decision=request.decision,
            reviewer_id=request.reviewer_id,
            notes=request.notes
        )
        
        # Determine next stage based on decision
        next_stage = "RECONCILE" if request.decision == "ACCEPT" else "COMPLETE"
        
        return {
            "success": True,
            "message": f"Decision '{request.decision}' recorded and workflow resumed",
            "checkpoint_id": request.checkpoint_id,
            "decision": request.decision,
            "reviewer_id": request.reviewer_id,
            "final_status": final_state.get("status"),
            "workflow_id": final_state.get("workflow_id"),
            # Spec-compliant fields
            "resume_token": f"RESUME_{request.checkpoint_id}_{int(datetime.now().timestamp())}",
            "next_stage": next_stage
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing human decision: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))





@app.get("/workflow/graph")
async def get_workflow_graph():
    """
    Get a visualization of the workflow graph structure
    """
    return {
        "success": True,
        "graph": workflow.get_graph_visualization()
    }


@app.get("/bigtool/history")
async def get_bigtool_history():
    """
    Get the history of Bigtool selections
    """
    history = bigtool.get_selection_history()
    
    return {
        "success": True,
        "count": len(history),
        "selections": history
    }


@app.get("/audit/{workflow_id}")
async def get_audit_log(workflow_id: str):
    """
    Get the audit log for a specific workflow
    """
    try:
        audit_log = checkpoint_db.get_audit_log(workflow_id)
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "count": len(audit_log),
            "audit_log": audit_log
        }
    
    except Exception as e:
        logger.error(f"Error fetching audit log: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
