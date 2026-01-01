"""
Invoice Processing State Management
Defines the state structure passed between LangGraph nodes
"""
from typing import TypedDict, Optional, List, Dict, Any, Annotated
from datetime import datetime
import operator


class LineItem(TypedDict):
    desc: str
    qty: float
    unit_price: float
    total: float


class InvoicePayload(TypedDict):
    invoice_id: str
    vendor_name: str
    vendor_tax_id: str
    invoice_date: str
    due_date: str
    amount: float
    currency: str
    line_items: List[LineItem]
    attachments: List[str]


class VendorProfile(TypedDict):
    normalized_name: str
    tax_id: str
    enrichment_meta: Dict[str, Any]


class InvoiceProcessingState(TypedDict):
    """
    Complete state structure for the invoice processing workflow.
    This is passed through all LangGraph nodes.
    """
    # Input invoice data
    invoice_payload: InvoicePayload
    
    # INTAKE stage outputs
    raw_id: Optional[str]
    ingest_ts: Optional[str]
    validated: Optional[bool]
    
    # UNDERSTAND stage outputs
    parsed_invoice: Optional[Dict[str, Any]]
    invoice_text: Optional[str]
    parsed_line_items: Optional[List[Dict[str, Any]]]
    detected_pos: Optional[List[str]]
    parsed_dates: Optional[Dict[str, str]]
    
    # PREPARE stage outputs
    vendor_profile: Optional[VendorProfile]
    normalized_invoice: Optional[Dict[str, Any]]
    flags: Optional[Dict[str, Any]]
    
    # RETRIEVE stage outputs
    matched_pos: Optional[List[Dict[str, Any]]]
    matched_grns: Optional[List[Dict[str, Any]]]
    history: Optional[List[Dict[str, Any]]]
    
    # MATCH_TWO_WAY stage outputs
    match_score: Optional[float]
    match_result: Optional[str]  # "MATCHED" or "FAILED"
    tolerance_pct: Optional[float]
    match_evidence: Optional[Dict[str, Any]]
    
    # CHECKPOINT_HITL stage outputs
    checkpoint_ref: Optional[str]
    review_url: Optional[str]
    paused_reason: Optional[str]
    
    # HITL_DECISION stage outputs
    human_decision: Optional[str]  # "ACCEPT" or "REJECT"
    reviewer_id: Optional[str]
    resume_token: Optional[str]
    next_stage: Optional[str]
    
    # RECONCILE stage outputs
    accounting_entries: Optional[List[Dict[str, Any]]]
    reconciliation_report: Optional[Dict[str, Any]]
    
    # APPROVE stage outputs
    approval_status: Optional[str]
    approver_id: Optional[str]
    
    # POSTING stage outputs
    posted: Optional[bool]
    erp_txn_id: Optional[str]
    scheduled_payment_id: Optional[str]
    
    # NOTIFY stage outputs
    notify_status: Optional[Dict[str, Any]]
    notified_parties: Optional[List[str]]
    
    # COMPLETE stage outputs
    final_payload: Optional[Dict[str, Any]]
    audit_log: Annotated[List[Dict[str, Any]], operator.add]
    status: Optional[str]
    
    # Workflow metadata
    workflow_id: Optional[str]
    current_stage: Optional[str]
    bigtool_selections: Annotated[Dict[str, str], operator.or_]
    errors: Annotated[List[Dict[str, Any]], operator.add]


def create_initial_state(invoice_payload: Dict[str, Any]) -> InvoiceProcessingState:
    """Create initial state from invoice payload"""
    return InvoiceProcessingState(
        invoice_payload=invoice_payload,
        raw_id=None,
        ingest_ts=None,
        validated=None,
        parsed_invoice=None,
        invoice_text=None,
        parsed_line_items=None,
        detected_pos=None,
        parsed_dates=None,
        vendor_profile=None,
        normalized_invoice=None,
        flags=None,
        matched_pos=None,
        matched_grns=None,
        history=None,
        match_score=None,
        match_result=None,
        tolerance_pct=None,
        match_evidence=None,
        checkpoint_ref=None,
        review_url=None,
        paused_reason=None,
        human_decision=None,
        reviewer_id=None,
        resume_token=None,
        next_stage=None,
        accounting_entries=None,
        reconciliation_report=None,
        approval_status=None,
        approver_id=None,
        posted=None,
        erp_txn_id=None,
        scheduled_payment_id=None,
        notify_status=None,
        notified_parties=None,
        final_payload=None,
        audit_log=[],
        status=None,
        workflow_id=None,
        current_stage="INTAKE",
        bigtool_selections={},
        errors=[]
    )
