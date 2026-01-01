"""
Invoice Processing Agent Nodes
Each node represents a stage in the workflow
"""
from typing import Dict, Any
from datetime import datetime
import uuid
import logging

from ..state import InvoiceProcessingState
from ..tools.bigtool import bigtool
from ..mcp.client import mcp_client
from ..tools.checkpoint_db import checkpoint_db

logger = logging.getLogger(__name__)


class InvoiceProcessingAgents:
    """
    Collection of all agent nodes for invoice processing workflow
    Each method represents a stage/node in the LangGraph
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.match_threshold = config.get("match_threshold", 0.90)
    
    async def intake_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        INTAKE Stage: Accept and validate invoice payload
        """
        logger.info("=" * 60)
        logger.info("STAGE: INTAKE - Accepting invoice payload")
        logger.info("=" * 60)
        
        invoice_payload = state["invoice_payload"]
        workflow_id = str(uuid.uuid4())
        
        # Select storage tool via Bigtool
        storage_tool = bigtool.select("storage", {"priority": "speed"})
        logger.info(f"🔧 Bigtool selected storage: {storage_tool['name']}")
        
        # Validate schema via MCP COMMON
        validation_result = await mcp_client.execute_ability(
            "validate_schema",
            {"payload": invoice_payload}
        )
        
        # Persist raw invoice via MCP COMMON
        persist_result = await mcp_client.execute_ability(
            "persist_raw_invoice",
            {"invoice_id": invoice_payload.get("invoice_id"), "payload": invoice_payload}
        )
        
        raw_id = persist_result.get("raw_id", f"RAW_{workflow_id}")
        ingest_ts = persist_result.get("stored_at", datetime.utcnow().isoformat())
        
        # Add audit log
        checkpoint_db.add_audit_log(
            workflow_id,
            "INTAKE",
            "invoice_ingested",
            {"invoice_id": invoice_payload.get("invoice_id"), "raw_id": raw_id}
        )
        
        logger.info(f"✅ Invoice ingested: {raw_id}")
        
        return {
            "workflow_id": workflow_id,
            "raw_id": raw_id,
            "ingest_ts": ingest_ts,
            "validated": validation_result.get("validated", True),
            "current_stage": "UNDERSTAND",
            "bigtool_selections": {
                "INTAKE_storage": storage_tool["name"]
            },
            "audit_log": [{
                "stage": "INTAKE",
                "action": "invoice_ingested",
                "timestamp": ingest_ts,
                "details": {"raw_id": raw_id}
            }]
        }
    
    async def understand_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        UNDERSTAND Stage: OCR extraction and parsing
        """
        logger.info("=" * 60)
        logger.info("STAGE: UNDERSTAND - OCR and parsing")
        logger.info("=" * 60)
        
        invoice_payload = state["invoice_payload"]
        
        # Select OCR tool via Bigtool
        ocr_tool = bigtool.select("ocr", {"priority": "accuracy"})
        logger.info(f"🔧 Bigtool selected OCR: {ocr_tool['name']}")
        
        # Run OCR via MCP ATLAS
        ocr_result = await mcp_client.execute_ability(
            "ocr_extract",
            {"attachments": invoice_payload.get("attachments", [])}
        )
        
        invoice_text = ocr_result.get("extracted_text", "")
        
        # Parse line items via MCP COMMON
        parse_result = await mcp_client.execute_ability(
            "parse_line_items",
            {"line_items": invoice_payload.get("line_items", []), "text": invoice_text}
        )
        
        parsed_line_items = parse_result.get("parsed_items", [])
        
        # Extract PO references from text
        detected_pos = []
        if "PO-" in invoice_text:
            import re
            pos = re.findall(r'PO-\d+-\d+', invoice_text)
            detected_pos = pos
        
        parsed_invoice = {
            "invoice_text": invoice_text,
            "parsed_line_items": parsed_line_items,
            "detected_pos": detected_pos,
            "currency": invoice_payload.get("currency", "USD"),
            "parsed_dates": {
                "invoice_date": invoice_payload.get("invoice_date"),
                "due_date": invoice_payload.get("due_date")
            }
        }
        
        # Add audit log
        checkpoint_db.add_audit_log(
            state.get("workflow_id"),
            "UNDERSTAND",
            "ocr_and_parsing_completed",
            {"ocr_tool": ocr_tool["name"], "items_parsed": len(parsed_line_items)}
        )
        
        logger.info(f"✅ OCR completed, {len(parsed_line_items)} items parsed")
        
        return {
            "parsed_invoice": parsed_invoice,
            "invoice_text": invoice_text,
            "parsed_line_items": parsed_line_items,
            "detected_pos": detected_pos,
            "parsed_dates": parsed_invoice["parsed_dates"],
            "current_stage": "PREPARE",
            "bigtool_selections": {
                "UNDERSTAND_ocr": ocr_tool["name"]
            },
            "audit_log": [{
                "stage": "UNDERSTAND",
                "action": "ocr_completed",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"items_parsed": len(parsed_line_items)}
            }]
        }
    
    async def prepare_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        PREPARE Stage: Normalize and enrich vendor data
        """
        logger.info("=" * 60)
        logger.info("STAGE: PREPARE - Vendor normalization and enrichment")
        logger.info("=" * 60)
        
        invoice_payload = state["invoice_payload"]
        vendor_name = invoice_payload.get("vendor_name", "")
        
        # Normalize vendor via MCP COMMON
        normalize_result = await mcp_client.execute_ability(
            "normalize_vendor",
            {"vendor_name": vendor_name}
        )
        
        normalized_name = normalize_result.get("normalized_name", vendor_name)
        
        # Select enrichment tool via Bigtool
        enrichment_tool = bigtool.select("enrichment", {"priority": "accuracy"})
        logger.info(f"🔧 Bigtool selected enrichment: {enrichment_tool['name']}")
        
        # Enrich vendor via MCP ATLAS
        enrich_result = await mcp_client.execute_ability(
            "enrich_vendor",
            {"vendor_name": normalized_name, "tax_id": invoice_payload.get("vendor_tax_id")}
        )
        
        enrichment_data = enrich_result.get("enrichment_data", {})
        
        vendor_profile = {
            "normalized_name": normalized_name,
            "tax_id": enrichment_data.get("tax_id", invoice_payload.get("vendor_tax_id")),
            "enrichment_meta": enrichment_data
        }
        
        # Compute flags via MCP COMMON
        flags_result = await mcp_client.execute_ability(
            "compute_flags",
            {"vendor_profile": vendor_profile, "invoice": invoice_payload}
        )
        
        flags = flags_result.get("flags", {})
        
        normalized_invoice = {
            "amount": invoice_payload.get("amount"),
            "currency": invoice_payload.get("currency"),
            "line_items": state.get("parsed_line_items", [])
        }
        
        # Add audit log
        checkpoint_db.add_audit_log(
            state.get("workflow_id"),
            "PREPARE",
            "vendor_enriched",
            {
                "normalized_name": normalized_name,
                "enrichment_tool": enrichment_tool["name"],
                "risk_score": flags.get("risk_score")
            }
        )
        
        logger.info(f"✅ Vendor enriched: {normalized_name} (risk: {flags.get('risk_score', 0):.2f})")
        
        return {
            "vendor_profile": vendor_profile,
            "normalized_invoice": normalized_invoice,
            "flags": flags,
            "current_stage": "RETRIEVE",
            "bigtool_selections": {
                "PREPARE_enrichment": enrichment_tool["name"]
            },
            "audit_log": [{
                "stage": "PREPARE",
                "action": "vendor_enriched",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"normalized_name": normalized_name}
            }]
        }
    
    async def retrieve_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        RETRIEVE Stage: Fetch PO, GRN, and history from ERP
        """
        logger.info("=" * 60)
        logger.info("STAGE: RETRIEVE - Fetching ERP data")
        logger.info("=" * 60)
        
        vendor_profile = state.get("vendor_profile", {})
        vendor_name = vendor_profile.get("normalized_name", "")
        
        # Select ERP connector via Bigtool
        erp_tool = bigtool.select("erp_connector", {"priority": "speed"})
        logger.info(f"🔧 Bigtool selected ERP: {erp_tool['name']}")
        
        # Fetch PO via MCP ATLAS
        po_result = await mcp_client.execute_ability(
            "fetch_po",
            {"vendor_name": vendor_name}
        )
        
        matched_pos = po_result.get("purchase_orders", [])
        
        # Fetch GRN via MCP ATLAS
        grn_result = await mcp_client.execute_ability(
            "fetch_grn",
            {"vendor_name": vendor_name, "pos": matched_pos}
        )
        
        matched_grns = grn_result.get("goods_received_notes", [])
        
        # Fetch history via MCP ATLAS
        history_result = await mcp_client.execute_ability(
            "fetch_history",
            {"vendor_name": vendor_name}
        )
        
        history = history_result.get("historical_invoices", [])
        
        # Add audit log
        checkpoint_db.add_audit_log(
            state.get("workflow_id"),
            "RETRIEVE",
            "erp_data_fetched",
            {
                "erp_tool": erp_tool["name"],
                "pos_found": len(matched_pos),
                "grns_found": len(matched_grns)
            }
        )
        
        logger.info(f"✅ ERP data retrieved: {len(matched_pos)} POs, {len(matched_grns)} GRNs")
        
        return {
            "matched_pos": matched_pos,
            "matched_grns": matched_grns,
            "history": history,
            "current_stage": "MATCH_TWO_WAY",
            "bigtool_selections": {
                "RETRIEVE_erp": erp_tool["name"]
            },
            "audit_log": [{
                "stage": "RETRIEVE",
                "action": "erp_data_fetched",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"pos_found": len(matched_pos)}
            }]
        }
    
    async def match_two_way_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        MATCH_TWO_WAY Stage: Compute matching score
        """
        logger.info("=" * 60)
        logger.info("STAGE: MATCH_TWO_WAY - Computing match score")
        logger.info("=" * 60)
        
        invoice_payload = state["invoice_payload"]
        matched_pos = state.get("matched_pos", [])
        
        invoice_amount = invoice_payload.get("amount", 0)
        po_amount = matched_pos[0].get("amount", 0) if matched_pos else 0
        
        # Compute match score via MCP COMMON
        match_result = await mcp_client.execute_ability(
            "compute_match_score",
            {
                "invoice_amount": invoice_amount,
                "po_amount": po_amount,
                "threshold": self.match_threshold
            }
        )
        
        match_score = match_result.get("match_score", 0.0)
        match_status = match_result.get("match_result", "FAILED")
        tolerance_pct = match_result.get("tolerance_pct", 0)
        match_evidence = match_result.get("match_evidence", {})
        
        # Add audit log
        checkpoint_db.add_audit_log(
            state.get("workflow_id"),
            "MATCH_TWO_WAY",
            "matching_completed",
            {
                "match_score": match_score,
                "match_result": match_status,
                "threshold": self.match_threshold
            }
        )
        
        logger.info(f"✅ Match score: {match_score:.2f} - {match_status}")
        
        return {
            "match_score": match_score,
            "match_result": match_status,
            "tolerance_pct": tolerance_pct,
            "match_evidence": match_evidence,
            "current_stage": "CHECKPOINT_HITL" if match_status == "FAILED" else "RECONCILE",
            "audit_log": [{
                "stage": "MATCH_TWO_WAY",
                "action": "matching_completed",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"match_score": match_score, "match_result": match_status}
            }]
        }
    
    async def checkpoint_hitl_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        CHECKPOINT_HITL Stage: Create checkpoint for human review
        """
        logger.info("=" * 60)
        logger.info("STAGE: CHECKPOINT_HITL - Creating checkpoint for review")
        logger.info("=" * 60)
        
        match_result = state.get("match_result", "UNKNOWN")
        
        # Only create checkpoint if matching failed
        if match_result != "FAILED":
            logger.info("⏭️  Matching succeeded, skipping checkpoint")
            return {
                "current_stage": "RECONCILE"
            }
        
        checkpoint_id = f"CKPT_{uuid.uuid4().hex[:12]}"
        workflow_id = state.get("workflow_id")
        invoice_payload = state["invoice_payload"]
        
        # Select DB tool via Bigtool
        db_tool = bigtool.select("db", {"priority": "speed"})
        logger.info(f"🔧 Bigtool selected DB: {db_tool['name']}")
        
        # Create checkpoint in database
        checkpoint_db.create_checkpoint(
            checkpoint_id=checkpoint_id,
            workflow_id=workflow_id,
            invoice_id=invoice_payload.get("invoice_id"),
            state=dict(state),
            paused_reason="Two-way matching failed - requires human review"
        )
        
        # Add to human review queue
        review_url = checkpoint_db.add_to_review_queue(
            checkpoint_id=checkpoint_id,
            invoice_data=invoice_payload,
            reason=f"Match score {state.get('match_score', 0):.2f} below threshold {self.match_threshold}"
        )
        
        # Add audit log
        checkpoint_db.add_audit_log(
            workflow_id,
            "CHECKPOINT_HITL",
            "checkpoint_created",
            {
                "checkpoint_id": checkpoint_id,
                "reason": "matching_failed"
            }
        )
        
        logger.info(f"⏸️  Checkpoint created: {checkpoint_id}")
        logger.info(f"🔗 Review URL: {review_url}")
        
        return {
            "checkpoint_ref": checkpoint_id,
            "review_url": review_url,
            "paused_reason": "Two-way matching failed - requires human review",
            "current_stage": "HITL_DECISION",
            "bigtool_selections": {
                "CHECKPOINT_db": db_tool["name"]
            },
            "audit_log": [{
                "stage": "CHECKPOINT_HITL",
                "action": "checkpoint_created",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"checkpoint_id": checkpoint_id}
            }]
        }
    
    async def hitl_decision_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        HITL_DECISION Stage: Process human decision
        """
        logger.info("=" * 60)
        logger.info("STAGE: HITL_DECISION - Awaiting human decision")
        logger.info("=" * 60)
        
        checkpoint_id = state.get("checkpoint_ref")

        if not checkpoint_id:
            logger.warning("No checkpoint_ref found, skipping HITL decision")
            return {"current_stage": "RECONCILE"}
        
        # In a real implementation, this would wait for human input
        # For demo purposes, we'll simulate an ACCEPT decision
        logger.info("⏳ Waiting for human decision...")
        logger.info("(In demo mode, automatically accepting after brief pause)")
        
        # Simulate human decision
        import asyncio
        await asyncio.sleep(1)
        
        human_decision = "ACCEPT"  # Could be "ACCEPT" or "REJECT"
        reviewer_id = "demo_reviewer_001"
        
        # Record decision in database
        checkpoint_db.record_decision(
            checkpoint_id=checkpoint_id,
            decision=human_decision,
            reviewer_id=reviewer_id,
            notes="Demo auto-accept for testing"
        )
        
        # Add audit log
        checkpoint_db.add_audit_log(
            state.get("workflow_id"),
            "HITL_DECISION",
            "decision_recorded",
            {
                "checkpoint_id": checkpoint_id,
                "decision": human_decision,
                "reviewer_id": reviewer_id
            }
        )
        
        logger.info(f"✅ Human decision: {human_decision} by {reviewer_id}")
        
        if human_decision == "REJECT":
            return {
                "human_decision": human_decision,
                "reviewer_id": reviewer_id,
                "status": "MANUAL_HANDOFF",
                "current_stage": "COMPLETE"
            }
        
        return {
            "human_decision": human_decision,
            "reviewer_id": reviewer_id,
            "resume_token": f"RESUME_{checkpoint_id}",
            "next_stage": "RECONCILE",
            "current_stage": "RECONCILE",
            "audit_log": [{
                "stage": "HITL_DECISION",
                "action": "decision_recorded",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"decision": human_decision}
            }]
        }
    
    async def reconcile_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        RECONCILE Stage: Build accounting entries
        """
        logger.info("=" * 60)
        logger.info("STAGE: RECONCILE - Building accounting entries")
        logger.info("=" * 60)
        
        invoice_payload = state["invoice_payload"]
        amount = invoice_payload.get("amount", 0)
        
        # Build accounting entries via MCP COMMON
        accounting_result = await mcp_client.execute_ability(
            "build_accounting_entries",
            {
                "amount": amount,
                "vendor": state.get("vendor_profile", {}).get("normalized_name", ""),
                "invoice_id": invoice_payload.get("invoice_id")
            }
        )
        
        accounting_entries = accounting_result.get("accounting_entries", [])
        
        reconciliation_report = {
            "invoice_amount": amount,
            "po_amount": state.get("matched_pos", [{}])[0].get("amount", 0) if state.get("matched_pos") else 0,
            "difference": 0,
            "reconciled": True
        }
        
        # Add audit log
        checkpoint_db.add_audit_log(
            state.get("workflow_id"),
            "RECONCILE",
            "accounting_entries_created",
            {"entries_count": len(accounting_entries)}
        )
        
        logger.info(f"✅ Accounting entries created: {len(accounting_entries)} entries")
        
        return {
            "accounting_entries": accounting_entries,
            "reconciliation_report": reconciliation_report,
            "current_stage": "APPROVE",
            "audit_log": [{
                "stage": "RECONCILE",
                "action": "accounting_entries_created",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"entries_count": len(accounting_entries)}
            }]
        }
    
    async def approve_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        APPROVE Stage: Apply approval policy
        """
        logger.info("=" * 60)
        logger.info("STAGE: APPROVE - Applying approval policy")
        logger.info("=" * 60)
        
        invoice_payload = state["invoice_payload"]
        amount = invoice_payload.get("amount", 0)
        
        # Apply approval policy via MCP ATLAS
        approval_result = await mcp_client.execute_ability(
            "apply_approval_policy",
            {
                "amount": amount,
                "vendor": state.get("vendor_profile", {}).get("normalized_name", "")
            }
        )
        
        approval_status = approval_result.get("approval_status", "AUTO_APPROVED")
        approver_id = approval_result.get("approver_id", "system")
        
        # Add audit log
        checkpoint_db.add_audit_log(
            state.get("workflow_id"),
            "APPROVE",
            "approval_applied",
            {"approval_status": approval_status, "approver_id": approver_id}
        )
        
        logger.info(f"✅ Approval: {approval_status} by {approver_id}")
        
        return {
            "approval_status": approval_status,
            "approver_id": approver_id,
            "current_stage": "POSTING",
            "audit_log": [{
                "stage": "APPROVE",
                "action": "approval_applied",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"approval_status": approval_status}
            }]
        }
    
    async def posting_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        POSTING Stage: Post to ERP and schedule payment
        """
        logger.info("=" * 60)
        logger.info("STAGE: POSTING - Posting to ERP")
        logger.info("=" * 60)
        
        invoice_payload = state["invoice_payload"]
        
        # Select ERP connector via Bigtool
        erp_tool = bigtool.select("erp_connector", {"priority": "speed"})
        logger.info(f"🔧 Bigtool selected ERP: {erp_tool['name']}")
        
        # Post to ERP via MCP ATLAS
        post_result = await mcp_client.execute_ability(
            "post_to_erp",
            {
                "invoice_id": invoice_payload.get("invoice_id"),
                "accounting_entries": state.get("accounting_entries", [])
            }
        )
        
        erp_txn_id = post_result.get("erp_txn_id", "")
        posted = post_result.get("posted", True)
        
        # Schedule payment via MCP ATLAS
        payment_result = await mcp_client.execute_ability(
            "schedule_payment",
            {
                "invoice_id": invoice_payload.get("invoice_id"),
                "amount": invoice_payload.get("amount"),
                "due_date": invoice_payload.get("due_date")
            }
        )
        
        scheduled_payment_id = payment_result.get("scheduled_payment_id", "")
        
        # Add audit log
        checkpoint_db.add_audit_log(
            state.get("workflow_id"),
            "POSTING",
            "posted_to_erp",
            {"erp_txn_id": erp_txn_id, "payment_id": scheduled_payment_id}
        )
        
        logger.info(f"✅ Posted to ERP: {erp_txn_id}, Payment: {scheduled_payment_id}")
        
        return {
            "posted": posted,
            "erp_txn_id": erp_txn_id,
            "scheduled_payment_id": scheduled_payment_id,
            "current_stage": "NOTIFY",
            "bigtool_selections": {
                "POSTING_erp": erp_tool["name"]
            },
            "audit_log": [{
                "stage": "POSTING",
                "action": "posted_to_erp",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"erp_txn_id": erp_txn_id}
            }]
        }
    
    async def notify_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        NOTIFY Stage: Send notifications
        """
        logger.info("=" * 60)
        logger.info("STAGE: NOTIFY - Sending notifications")
        logger.info("=" * 60)
        
        invoice_payload = state["invoice_payload"]
        
        # Select email tool via Bigtool
        email_tool = bigtool.select("email", {"priority": "speed"})
        logger.info(f"🔧 Bigtool selected email: {email_tool['name']}")
        
        # Send notifications via MCP ATLAS
        notify_result = await mcp_client.execute_ability(
            "send_notification",
            {
                "invoice_id": invoice_payload.get("invoice_id"),
                "vendor_email": "vendor@example.com",
                "finance_team": "#finance-team"
            }
        )
        
        notifications_sent = notify_result.get("notifications_sent", [])
        notified_parties = [n["recipient"] for n in notifications_sent]
        
        notify_status = {
            "total_sent": len(notifications_sent),
            "notifications": notifications_sent
        }
        
        # Add audit log
        checkpoint_db.add_audit_log(
            state.get("workflow_id"),
            "NOTIFY",
            "notifications_sent",
            {"parties_notified": len(notified_parties)}
        )
        
        logger.info(f"✅ Notifications sent to {len(notified_parties)} parties")
        
        return {
            "notify_status": notify_status,
            "notified_parties": notified_parties,
            "current_stage": "COMPLETE",
            "bigtool_selections": {
                "NOTIFY_email": email_tool["name"]
            },
            "audit_log": [{
                "stage": "NOTIFY",
                "action": "notifications_sent",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {"parties_notified": len(notified_parties)}
            }]
        }
    
    async def complete_node(self, state: InvoiceProcessingState) -> Dict[str, Any]:
        """
        COMPLETE Stage: Finalize workflow
        """
        logger.info("=" * 60)
        logger.info("STAGE: COMPLETE - Finalizing workflow")
        logger.info("=" * 60)
        
        workflow_id = state.get("workflow_id")
        invoice_payload = state["invoice_payload"]
        
        # Select DB tool via Bigtool
        db_tool = bigtool.select("db", {"priority": "speed"})
        logger.info(f"🔧 Bigtool selected DB: {db_tool['name']}")
        
        # Get full audit log from database
        audit_log = checkpoint_db.get_audit_log(workflow_id)
        
        # Build final payload
        final_payload = {
            "workflow_id": workflow_id,
            "invoice_id": invoice_payload.get("invoice_id"),
            "status": state.get("status", "COMPLETED"),
            "vendor": state.get("vendor_profile", {}).get("normalized_name", ""),
            "amount": invoice_payload.get("amount"),
            "currency": invoice_payload.get("currency"),
            "match_score": state.get("match_score"),
            "approval_status": state.get("approval_status"),
            "erp_txn_id": state.get("erp_txn_id"),
            "payment_id": state.get("scheduled_payment_id"),
            "completed_at": datetime.utcnow().isoformat()
        }
        
        # Add final audit entry
        checkpoint_db.add_audit_log(
            workflow_id,
            "COMPLETE",
            "workflow_completed",
            {"final_status": final_payload["status"]}
        )
        
        logger.info("=" * 60)
        logger.info("✅ WORKFLOW COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info(f"Invoice ID: {invoice_payload.get('invoice_id')}")
        logger.info(f"Final Status: {final_payload['status']}")
        logger.info(f"ERP Transaction: {final_payload.get('erp_txn_id')}")
        logger.info("=" * 60)
        
        return {
            "final_payload": final_payload,
            "audit_log": audit_log,
            "status": "COMPLETED",
            "current_stage": "COMPLETE",
            "bigtool_selections": {
                "COMPLETE_db": db_tool["name"]
            }
        }
