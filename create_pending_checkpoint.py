"""
Create Checkpoint for Manual Review - CORRECTED VERSION
This creates a checkpoint that STAYS PENDING for manual review in UI
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.workflow import InvoiceProcessingWorkflow
from src.tools.checkpoint_db import checkpoint_db


async def create_pending_checkpoint():
    """
    Create a checkpoint that will STAY PENDING for manual review
    """
    print("\n" + "=" * 80)
    print("🎬 CREATING PENDING CHECKPOINT FOR MANUAL REVIEW")
    print("=" * 80 + "\n")
    
    # Load invoice that will fail matching
    with open("config/sample_invoice_fail_match.json", "r") as f:
        invoice_payload = json.load(f)
    
    print(f"Processing invoice: {invoice_payload['invoice_id']}")
    print(f"Vendor: {invoice_payload['vendor_name']}")
    print(f"Amount: ${invoice_payload['amount']}")
    print(f"Expected PO Amount: $1000")
    print(f"Expected Match Score: ~0.85 (below 0.90 threshold)")
    print()
    
    # Initialize workflow
    workflow = InvoiceProcessingWorkflow("config/workflow.json")
    
    # Run workflow - it will pause at checkpoint
    # We'll modify the workflow to NOT auto-continue in HITL_DECISION
    print("Starting workflow...")
    print("This will create a checkpoint and STOP (not auto-accept)")
    print()
    
    try:
        # Run through the graph
        async for state_update in workflow.graph.astream(
            {"invoice_payload": invoice_payload,
             "audit_log": [],
             "bigtool_selections": {},
             "errors": []},
            {"configurable": {"thread_id": "manual_demo"}}
        ):
            for node_name, node_output in state_update.items():
                print(f"✓ Completed: {node_name}")
                
                # If we reach CHECKPOINT_HITL, stop here
                if node_name == "CHECKPOINT_HITL":
                    checkpoint_id = node_output.get("checkpoint_id")
                    review_url = node_output.get("review_url")
                    
                    print("\n" + "=" * 80)
                    print("✅ CHECKPOINT CREATED AND PENDING!")
                    print("=" * 80)
                    print(f"Checkpoint ID: {checkpoint_id}")
                    print(f"Review URL: {review_url}")
                    print(f"Status: PENDING (waiting for human review)")
                    print()
                    print("📱 NOW YOU CAN:")
                    print("   1. Make sure API server is running:")
                    print("      python -m src.api.main")
                    print()
                    print("   2. Open frontend/index.html in browser")
                    print()
                    print("   3. Click 'Refresh' to see this pending invoice")
                    print()
                    print("   4. Review and Accept/Reject the invoice")
                    print("=" * 80 + "\n")
                    
                    # Show pending reviews
                    pending = checkpoint_db.get_pending_reviews()
                    print(f"Total pending reviews in database: {len(pending)}")
                    for review in pending:
                        print(f"  📋 {review['invoice_id']}: {review['reason_for_hold']}")
                    print()
                    
                    return  # STOP HERE - don't continue to HITL_DECISION
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(create_pending_checkpoint())
