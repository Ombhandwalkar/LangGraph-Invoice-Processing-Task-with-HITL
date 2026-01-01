"""
Test Runner for Invoice Processing Workflow
Demonstrates the complete workflow execution
"""
import asyncio
import json
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.workflow import InvoiceProcessingWorkflow
from src.tools.checkpoint_db import checkpoint_db
from src.tools.bigtool import bigtool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_successful_workflow():
    """
    Test Case 1: Invoice that passes matching - no HITL required
    """
    print("\n" + "=" * 80)
    print("TEST CASE 1: Successful Invoice Processing (No HITL)")
    print("=" * 80 + "\n")
    
    # Load sample invoice
    with open("config/sample_invoice.json", "r") as f:
        invoice_payload = json.load(f)
    
    # Initialize workflow
    workflow = InvoiceProcessingWorkflow("config/workflow.json")
    
    # Run workflow
    final_state = await workflow.run(invoice_payload, thread_id="test_success")
    
    print("\n" + "=" * 80)
    print("TEST CASE 1 RESULTS")
    print("=" * 80)
    print(f"Status: {final_state.get('status')}")
    print(f"Workflow ID: {final_state.get('workflow_id')}")
    match_score = final_state.get('match_score')
    if isinstance(match_score, (int, float)):
        print(f"Match Score: {match_score:.2f}")
    else:
        print(f"Match Score: {match_score}")
    print(f"Match Result: {final_state.get('match_result')}")
    print(f"Approval Status: {final_state.get('approval_status')}")
    print(f"ERP Transaction ID: {final_state.get('erp_txn_id')}")
    print(f"Payment ID: {final_state.get('scheduled_payment_id')}")
    print("\nBigtool Selections:")
    for stage, tool in final_state.get("bigtool_selections", {}).items():
        print(f"  {stage}: {tool}")
    print("=" * 80 + "\n")
    
    return final_state


async def test_hitl_workflow():
    """
    Test Case 2: Invoice that fails matching - requires HITL
    """
    print("\n" + "=" * 80)
    print("TEST CASE 2: Invoice Processing with HITL")
    print("=" * 80 + "\n")
    
    # Load sample invoice that will fail matching
    with open("config/sample_invoice_fail_match.json", "r") as f:
        invoice_payload = json.load(f)
    
    # Initialize workflow
    workflow = InvoiceProcessingWorkflow("config/workflow.json")
    
    # Run workflow (will pause at checkpoint)
    final_state = await workflow.run(invoice_payload, thread_id="test_hitl")
    
    print("\n" + "=" * 80)
    print("CHECKPOINT CREATED - WAITING FOR HUMAN REVIEW")
    print("=" * 80)
    print(f"Checkpoint ID: {final_state.get('checkpoint_ref')}")
    print(f"Review URL: {final_state.get('review_url')}")
    print(f"Paused Reason: {final_state.get('paused_reason')}")
    match_score = final_state.get('match_score')
    if isinstance(match_score, (int, float)):
        print(f"Match Score: {match_score:.2f}")
    else:
        print(f"Match Score: {match_score}")
    print("=" * 80 + "\n")
    
    # Check pending reviews
    pending = checkpoint_db.get_pending_reviews()
    print(f"Pending Reviews: {len(pending)}")
    for review in pending:
        print(f"  - {review['invoice_id']}: {review['reason_for_hold']}")
    
    print("\n⏳ Simulating human review process...")
    await asyncio.sleep(2)
    
    # Simulate human decision (ACCEPT)
    checkpoint_id = final_state.get("checkpoint_ref")
    print(f"\n✅ Human Decision: ACCEPT (Reviewer: test_reviewer)")
    
    # Resume workflow
    resumed_state = await workflow.resume_from_checkpoint(
        checkpoint_id=checkpoint_id,
        decision="ACCEPT",
        reviewer_id="test_reviewer",
        notes="Reviewed and approved - invoice amount acceptable"
    )
    
    print("\n" + "=" * 80)
    print("TEST CASE 2 RESULTS (AFTER HITL)")
    print("=" * 80)
    print(f"Status: {resumed_state.get('status')}")
    print(f"Human Decision: {resumed_state.get('human_decision')}")
    print(f"Reviewer: {resumed_state.get('reviewer_id')}")
    print(f"Approval Status: {resumed_state.get('approval_status')}")
    print(f"ERP Transaction ID: {resumed_state.get('erp_txn_id')}")
    print(f"Payment ID: {resumed_state.get('scheduled_payment_id')}")
    print("\nBigtool Selections:")
    for stage, tool in resumed_state.get("bigtool_selections", {}).items():
        print(f"  {stage}: {tool}")
    print("=" * 80 + "\n")
    
    return resumed_state


async def test_bigtool_selections():
    """
    Test Case 3: Verify Bigtool selections across workflow
    """
    print("\n" + "=" * 80)
    print("TEST CASE 3: Bigtool Selection Verification")
    print("=" * 80 + "\n")
    
    # Reset history
    bigtool.reset_history()
    
    # Run a workflow
    with open("config/sample_invoice.json", "r") as f:
        invoice_payload = json.load(f)
    
    workflow = InvoiceProcessingWorkflow("config/workflow.json")
    await workflow.run(invoice_payload, thread_id="test_bigtool")
    
    # Get Bigtool history
    history = bigtool.get_selection_history()
    
    print("Bigtool Selection History:")
    print("-" * 80)
    for i, selection in enumerate(history, 1):
        print(f"{i}. Capability: {selection['capability']}")
        print(f"   Selected: {selection['selected']}")
        print(f"   Context: {selection.get('context', {})}")
        print(f"   Pool Size: {selection['pool_size']}")
        print()
    
    print("=" * 80 + "\n")


async def main():
    """
    Run all test cases
    """
    print("\n" + "🚀" * 40)
    print("INVOICE PROCESSING WORKFLOW - TEST SUITE")
    print("🚀" * 40 + "\n")
    
    try:
        # Test Case 1: Successful workflow
        await test_successful_workflow()
        
        # Test Case 2: HITL workflow
        await test_hitl_workflow()
        
        # Test Case 3: Bigtool verification
        await test_bigtool_selections()
        
        print("\n" + "✅" * 40)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("✅" * 40 + "\n")
        
    except Exception as e:
        print("\n" + "❌" * 40)
        print(f"TEST FAILED: {str(e)}")
        print("❌" * 40 + "\n")
        raise


if __name__ == "__main__":
    asyncio.run(main())
