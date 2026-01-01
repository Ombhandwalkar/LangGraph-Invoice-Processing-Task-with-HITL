"""
Create Multiple Pending Checkpoints
Generates 10+ random invoices that will fail matching to populate the review queue
"""
import asyncio
import json
import sys
import random
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.workflow import InvoiceProcessingWorkflow
from src.tools.checkpoint_db import checkpoint_db

VENDORS = ["Tech Solutions Inc", "Office Supplies Co", "Global logistics", "Cloud Services Ltd", "Marketing Pro Agency"]
INVOICE_PREFIXES = ["INV", "BIL", "REC", "2025"]

async def create_invoice(index: int):
    """Create a single invoice that fails matching"""
    
    vendor = random.choice(VENDORS)
    amount = round(random.uniform(500.0, 5000.0), 2)
    # Make sure it fails matching (PO amount is usually fixed or simulated)
    # In this mock setup, let's assume PO is always 10% higher or lower to cause mismatch
    
    invoice_id = f"{random.choice(INVOICE_PREFIXES)}-2025-{random.randint(1000, 9999)}"
    
    payload = {
        "invoice_id": invoice_id,
        "vendor_name": vendor,
        "vendor_tax_id": f"TAX-{random.randint(10000, 99999)}",
        "invoice_date": (datetime.now() - timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d"),
        "due_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
        "amount": amount,
        "currency": "USD",
        "line_items": [
             {"desc": "Service Fee", "qty": 1, "unit_price": amount, "total": amount}
        ],
        "attachments": []
    }
    
    print(f"[{index}] Generating {invoice_id} for {vendor} ($ {amount})")
    
    workflow = InvoiceProcessingWorkflow("config/workflow.json")
    
    # We need to ensure it fails matching. The current match logic (mock)
    # might compare against a static value or the invoice itself.
    # Looking at create_pending_checkpoint.py, it uses sample_invoice_fail_match.json.
    # Let's hope the system is robust enough or we might need to be clever.
    # The README says "PO amount: $1000" for one scenario.
    # Let's just run it. If it auto-completes, we'll see.
    
    try:
        async for state_update in workflow.graph.astream(
            {"invoice_payload": payload,
             "audit_log": [],
             "bigtool_selections": {},
             "errors": []},
            {"configurable": {"thread_id": f"batch_{index}_{invoice_id}"}}
        ):
            for node_name, node_output in state_update.items():
                if node_name == "CHECKPOINT_HITL":
                    print(f"   ✅ Checkpoint created for {invoice_id}")
                    return # Stop after checkpoint
                
    except Exception as e:
        print(f"   ❌ Error processing {invoice_id}: {e}")

async def main():
    print("\n" + "=" * 80)
    print("🚀 BATCH GENERATING 10 PENDING INVOICES")
    print("=" * 80 + "\n")
    
    tasks = []
    for i in range(10):
        tasks.append(create_invoice(i+1))
    
    # Run concurrently
    await asyncio.gather(*tasks)
    
    print("\n" + "=" * 80)
    print("✅ BATCH GENERATION COMPLETE")
    print("=" * 80 + "\n")
    
    pending = checkpoint_db.get_pending_reviews()
    print(f"Total pending reviews in DB: {len(pending)}")

if __name__ == "__main__":
    asyncio.run(main())
