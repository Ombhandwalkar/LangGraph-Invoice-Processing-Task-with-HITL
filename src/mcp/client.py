"""
MCP Client System
Routes abilities to COMMON (no external data) or ATLAS (external system interaction) servers
"""
from typing import Dict, Any, Optional
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class MCPServer(str, Enum):
    COMMON = "COMMON"
    ATLAS = "ATLAS"


class MCPClient:
    """
    MCP Client orchestrates ability execution across COMMON and ATLAS servers
    """
    
    def __init__(self):
        self.common_abilities = {
            # INTAKE
            "validate_schema",
            "persist_raw_invoice",
            
            # UNDERSTAND
            "parse_line_items",
            "normalize_dates",
            
            # PREPARE
            "normalize_vendor",
            "compute_flags",
            
            # MATCH
            "compute_match_score",
            
            # RECONCILE
            "build_accounting_entries",
            
            # COMPLETE
            "generate_audit_log"
        }
        
        self.atlas_abilities = {
            # UNDERSTAND
            "ocr_extract",
            
            # PREPARE
            "enrich_vendor",
            
            # RETRIEVE
            "fetch_po",
            "fetch_grn",
            "fetch_history",
            
            # HITL
            "accept_or_reject_invoice",
            
            # APPROVE
            "apply_approval_policy",
            
            # POSTING
            "post_to_erp",
            "schedule_payment",
            
            # NOTIFY
            "send_notification"
        }
    
    def route_ability(self, ability_name: str) -> MCPServer:
        """
        Determine which MCP server should handle the ability
        """
        if ability_name in self.common_abilities:
            return MCPServer.COMMON
        elif ability_name in self.atlas_abilities:
            return MCPServer.ATLAS
        else:
            # Default to COMMON for unknown abilities
            logger.warning(f"Unknown ability '{ability_name}', routing to COMMON")
            return MCPServer.COMMON
    
    async def execute_ability(
        self,
        ability_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute an ability through the appropriate MCP server
        
        Args:
            ability_name: Name of the ability to execute
            parameters: Parameters for the ability
            context: Additional context
            
        Returns:
            Result from the ability execution
        """
        server = self.route_ability(ability_name)
        
        logger.info(
            f"Executing ability '{ability_name}' via {server.value} server"
        )
        
        try:
            if server == MCPServer.COMMON:
                result = await self._execute_common_ability(ability_name, parameters)
            else:  # ATLAS
                result = await self._execute_atlas_ability(ability_name, parameters)
            
            logger.info(f"Ability '{ability_name}' completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error executing ability '{ability_name}': {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "ability": ability_name,
                "server": server.value
            }
    
    async def _execute_common_ability(
        self,
        ability_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute ability on COMMON server (no external dependencies)
        """
        # Simulate ability execution
        await asyncio.sleep(0.1)
        
        # Mock implementations for demo
        if ability_name == "validate_schema":
            return {
                "success": True,
                "validated": True,
                "schema_version": "1.0"
            }
        
        elif ability_name == "persist_raw_invoice":
            return {
                "success": True,
                "raw_id": f"RAW_{parameters.get('invoice_id', 'unknown')}",
                "stored_at": "2025-01-15T10:00:00Z"
            }
        
        elif ability_name == "parse_line_items":
            return {
                "success": True,
                "parsed_items": parameters.get("line_items", [])
            }
        
        elif ability_name == "normalize_vendor":
            vendor_name = parameters.get("vendor_name", "")
            return {
                "success": True,
                "normalized_name": vendor_name.strip().upper(),
                "confidence": 0.95
            }
        
        elif ability_name == "compute_flags":
            return {
                "success": True,
                "flags": {
                    "missing_info": [],
                    "risk_score": 0.15,
                    "requires_review": False
                }
            }
        
        elif ability_name == "compute_match_score":
            # Simulate matching logic
            invoice_amount = parameters.get("invoice_amount", 0)
            po_amount = parameters.get("po_amount", 0)
            
            if po_amount == 0:
                match_score = 0.0
            else:
                difference = abs(invoice_amount - po_amount) / po_amount
                match_score = max(0.0, 1.0 - difference)
            
            return {
                "success": True,
                "match_score": match_score,
                "match_result": "MATCHED" if match_score >= 0.90 else "FAILED",
                "tolerance_pct": abs(invoice_amount - po_amount) / po_amount * 100 if po_amount else 100,
                "match_evidence": {
                    "invoice_amount": invoice_amount,
                    "po_amount": po_amount,
                    "difference": abs(invoice_amount - po_amount)
                }
            }
        
        elif ability_name == "build_accounting_entries":
            amount = parameters.get("amount", 0)
            return {
                "success": True,
                "accounting_entries": [
                    {
                        "account": "Accounts Payable",
                        "debit": 0,
                        "credit": amount,
                        "description": "Invoice payable"
                    },
                    {
                        "account": "Expense",
                        "debit": amount,
                        "credit": 0,
                        "description": "Goods/Services received"
                    }
                ]
            }
        
        elif ability_name == "generate_audit_log":
            return {
                "success": True,
                "audit_entries": [
                    {
                        "timestamp": "2025-01-15T10:00:00Z",
                        "action": "workflow_completed",
                        "details": parameters
                    }
                ]
            }
        
        # Default response
        return {
            "success": True,
            "message": f"COMMON ability '{ability_name}' executed",
            "data": parameters
        }
    
    async def _execute_atlas_ability(
        self,
        ability_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute ability on ATLAS server (external system interaction)
        """
        # Simulate external API call
        await asyncio.sleep(0.2)
        
        # Mock implementations for demo
        if ability_name == "ocr_extract":
            return {
                "success": True,
                "extracted_text": "INVOICE\\nAmount: $1000\\nVendor: ACME Corp",
                "confidence": 0.92
            }
        
        elif ability_name == "enrich_vendor":
            return {
                "success": True,
                "enrichment_data": {
                    "tax_id": "12-3456789",
                    "credit_score": 750,
                    "risk_rating": "LOW",
                    "address": "123 Business St, City, State 12345"
                }
            }
        
        elif ability_name == "fetch_po":
            return {
                "success": True,
                "purchase_orders": [
                    {
                        "po_number": "PO-2025-001",
                        "amount": 1000.00,
                        "status": "APPROVED",
                        "vendor": parameters.get("vendor_name", "ACME Corp")
                    }
                ]
            }
        
        elif ability_name == "fetch_grn":
            return {
                "success": True,
                "goods_received_notes": [
                    {
                        "grn_number": "GRN-2025-001",
                        "po_reference": "PO-2025-001",
                        "received_date": "2025-01-10",
                        "quantity": 10
                    }
                ]
            }
        
        elif ability_name == "fetch_history":
            return {
                "success": True,
                "historical_invoices": [
                    {
                        "invoice_id": "INV-2024-999",
                        "amount": 950.00,
                        "status": "PAID",
                        "vendor": parameters.get("vendor_name", "ACME Corp")
                    }
                ]
            }
        
        elif ability_name == "accept_or_reject_invoice":
            decision = parameters.get("decision", "ACCEPT")
            return {
                "success": True,
                "decision": decision,
                "reviewer_id": parameters.get("reviewer_id", "reviewer_001"),
                "notes": parameters.get("notes", ""),
                "timestamp": "2025-01-15T10:30:00Z"
            }
        
        elif ability_name == "apply_approval_policy":
            amount = parameters.get("amount", 0)
            auto_approve_threshold = 5000
            
            return {
                "success": True,
                "approval_status": "AUTO_APPROVED" if amount < auto_approve_threshold else "REQUIRES_APPROVAL",
                "approver_id": "system" if amount < auto_approve_threshold else "manager_001",
                "policy_applied": "standard_approval_policy_v1"
            }
        
        elif ability_name == "post_to_erp":
            return {
                "success": True,
                "posted": True,
                "erp_txn_id": f"ERP_TXN_{parameters.get('invoice_id', 'unknown')}",
                "posted_at": "2025-01-15T10:45:00Z"
            }
        
        elif ability_name == "schedule_payment":
            return {
                "success": True,
                "payment_scheduled": True,
                "scheduled_payment_id": f"PAY_{parameters.get('invoice_id', 'unknown')}",
                "scheduled_date": parameters.get("due_date", "2025-02-15")
            }
        
        elif ability_name == "send_notification":
            return {
                "success": True,
                "notifications_sent": [
                    {
                        "recipient": parameters.get("vendor_email", "vendor@example.com"),
                        "type": "email",
                        "status": "sent"
                    },
                    {
                        "recipient": "#finance-team",
                        "type": "slack",
                        "status": "sent"
                    }
                ]
            }
        
        # Default response
        return {
            "success": True,
            "message": f"ATLAS ability '{ability_name}' executed",
            "data": parameters
        }


# Global instance
mcp_client = MCPClient()
