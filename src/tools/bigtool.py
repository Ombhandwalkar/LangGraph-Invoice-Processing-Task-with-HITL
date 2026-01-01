"""
Bigtool - Dynamic Tool Selection System
Intelligently selects the best tool from a pool based on capability and context
"""
import random
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolCapability(str, Enum):
    OCR = "ocr"
    ENRICHMENT = "enrichment"
    ERP_CONNECTOR = "erp_connector"
    STORAGE = "storage"
    DB = "db"
    EMAIL = "email"


class BigtoolPicker:
    """
    Bigtool intelligently selects tools from pools based on:
    - Capability required
    - Context (cost, speed, accuracy trade-offs)
    - Availability
    - Historical performance
    """
    
    def __init__(self):
        self.tool_pools = {
            ToolCapability.OCR: [
                {
                    "name": "google_vision",
                    "cost": "high",
                    "accuracy": "high",
                    "speed": "medium",
                    "available": True
                },
                {
                    "name": "tesseract",
                    "cost": "free",
                    "accuracy": "medium",
                    "speed": "fast",
                    "available": True
                },
                {
                    "name": "aws_textract",
                    "cost": "medium",
                    "accuracy": "high",
                    "speed": "medium",
                    "available": True
                }
            ],
            ToolCapability.ENRICHMENT: [
                {
                    "name": "clearbit",
                    "cost": "high",
                    "accuracy": "high",
                    "speed": "fast",
                    "available": True
                },
                {
                    "name": "people_data_labs",
                    "cost": "medium",
                    "accuracy": "medium",
                    "speed": "fast",
                    "available": True
                },
                {
                    "name": "vendor_db",
                    "cost": "free",
                    "accuracy": "medium",
                    "speed": "very_fast",
                    "available": True
                }
            ],
            ToolCapability.ERP_CONNECTOR: [
                {
                    "name": "sap_sandbox",
                    "cost": "free",
                    "accuracy": "high",
                    "speed": "medium",
                    "available": True
                },
                {
                    "name": "netsuite",
                    "cost": "medium",
                    "accuracy": "high",
                    "speed": "medium",
                    "available": True
                },
                {
                    "name": "mock_erp",
                    "cost": "free",
                    "accuracy": "high",
                    "speed": "very_fast",
                    "available": True
                }
            ],
            ToolCapability.STORAGE: [
                {
                    "name": "s3",
                    "cost": "low",
                    "accuracy": "high",
                    "speed": "fast",
                    "available": True
                },
                {
                    "name": "gcs",
                    "cost": "low",
                    "accuracy": "high",
                    "speed": "fast",
                    "available": True
                },
                {
                    "name": "local_fs",
                    "cost": "free",
                    "accuracy": "high",
                    "speed": "very_fast",
                    "available": True
                }
            ],
            ToolCapability.DB: [
                {
                    "name": "postgres",
                    "cost": "medium",
                    "accuracy": "high",
                    "speed": "fast",
                    "available": True
                },
                {
                    "name": "sqlite",
                    "cost": "free",
                    "accuracy": "high",
                    "speed": "very_fast",
                    "available": True
                },
                {
                    "name": "dynamodb",
                    "cost": "low",
                    "accuracy": "high",
                    "speed": "fast",
                    "available": False
                }
            ],
            ToolCapability.EMAIL: [
                {
                    "name": "sendgrid",
                    "cost": "medium",
                    "accuracy": "high",
                    "speed": "fast",
                    "available": True
                },
                {
                    "name": "smartlead",
                    "cost": "medium",
                    "accuracy": "high",
                    "speed": "medium",
                    "available": False
                },
                {
                    "name": "ses",
                    "cost": "low",
                    "accuracy": "high",
                    "speed": "fast",
                    "available": True
                }
            ]
        }
        
        # Tool selection history for optimization
        self.selection_history: List[Dict[str, Any]] = []
    
    def select(
        self, 
        capability: str, 
        context: Optional[Dict[str, Any]] = None,
        pool_hint: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Select the best tool for the given capability and context
        
        Args:
            capability: The tool capability needed (e.g., "ocr", "enrichment")
            context: Additional context for selection (e.g., {"priority": "speed"})
            pool_hint: Optional list of preferred tools
            
        Returns:
            Selected tool information including name and metadata
        """
        try:
            cap_enum = ToolCapability(capability)
        except ValueError:
            logger.error(f"Unknown capability: {capability}")
            return {"name": "mock_tool", "error": "Unknown capability"}
        
        available_tools = [
            tool for tool in self.tool_pools.get(cap_enum, [])
            if tool["available"]
        ]
        
        if not available_tools:
            logger.warning(f"No available tools for capability: {capability}")
            return {"name": "mock_tool", "error": "No available tools"}
        
        # Filter by pool_hint if provided
        if pool_hint:
            preferred_tools = [
                tool for tool in available_tools
                if tool["name"] in pool_hint
            ]
            if preferred_tools:
                available_tools = preferred_tools
        
        # Selection strategy based on context
        if context:
            priority = context.get("priority", "balanced")
            
            if priority == "speed":
                # Prioritize speed
                available_tools.sort(
                    key=lambda t: {"very_fast": 0, "fast": 1, "medium": 2, "slow": 3}.get(t["speed"], 4)
                )
            elif priority == "cost":
                # Prioritize low cost
                available_tools.sort(
                    key=lambda t: {"free": 0, "low": 1, "medium": 2, "high": 3}.get(t["cost"], 4)
                )
            elif priority == "accuracy":
                # Prioritize accuracy
                available_tools.sort(
                    key=lambda t: {"high": 0, "medium": 1, "low": 2}.get(t["accuracy"], 3)
                )
        
        # Select the top tool
        selected_tool = available_tools[0]
        
        # Log selection
        selection_record = {
            "capability": capability,
            "selected": selected_tool["name"],
            "context": context,
            "pool_size": len(available_tools)
        }
        self.selection_history.append(selection_record)
        
        logger.info(
            f"Bigtool selected '{selected_tool['name']}' for capability '{capability}' "
            f"(context: {context})"
        )
        
        return {
            "name": selected_tool["name"],
            "capability": capability,
            "metadata": {
                "cost": selected_tool["cost"],
                "accuracy": selected_tool["accuracy"],
                "speed": selected_tool["speed"]
            }
        }
    
    def get_selection_history(self) -> List[Dict[str, Any]]:
        """Get the history of tool selections"""
        return self.selection_history.copy()
    
    def reset_history(self):
        """Clear selection history"""
        self.selection_history = []


# Global instance
bigtool = BigtoolPicker()
