"""
LangGraph Workflow Orchestrator
Builds and executes the invoice processing graph
"""
import json
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
import logging

from .state import InvoiceProcessingState, create_initial_state
from .agents.invoice_agents import InvoiceProcessingAgents

logger = logging.getLogger(__name__)


class InvoiceProcessingWorkflow:
    """
    Main LangGraph workflow for invoice processing
    """
    
    def __init__(self, config_path: str = "config/workflow.json"):
        # Load workflow configuration
        with open(config_path, 'r') as f:
            self.workflow_config = json.load(f)
        
        self.config = self.workflow_config.get("config", {})
        self.agents = InvoiceProcessingAgents(self.config)
        
        # Create checkpoint saver (disabled — using project's CheckpointDB)
        # LangGraph's SqliteSaver context helper returns a context manager
        # which isn't suitable for direct use here; we rely on our
        # `src.tools.checkpoint_db.checkpoint_db` for persistence instead.
        self.memory = None
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph state graph with all nodes and edges
        """
        # Initialize graph with state schema
        workflow = StateGraph(InvoiceProcessingState)
        
        # Add all nodes
        workflow.add_node("INTAKE", self.agents.intake_node)
        workflow.add_node("UNDERSTAND", self.agents.understand_node)
        workflow.add_node("PREPARE", self.agents.prepare_node)
        workflow.add_node("RETRIEVE", self.agents.retrieve_node)
        workflow.add_node("MATCH_TWO_WAY", self.agents.match_two_way_node)
        workflow.add_node("CHECKPOINT_HITL", self.agents.checkpoint_hitl_node)
        workflow.add_node("HITL_DECISION", self.agents.hitl_decision_node)
        workflow.add_node("RECONCILE", self.agents.reconcile_node)
        workflow.add_node("APPROVE", self.agents.approve_node)
        workflow.add_node("POSTING", self.agents.posting_node)
        workflow.add_node("NOTIFY", self.agents.notify_node)
        workflow.add_node("COMPLETE", self.agents.complete_node)
        
        # Set entry point
        workflow.set_entry_point("INTAKE")
        
        # Add sequential edges (deterministic flow)
        workflow.add_edge("INTAKE", "UNDERSTAND")
        workflow.add_edge("UNDERSTAND", "PREPARE")
        workflow.add_edge("PREPARE", "RETRIEVE")
        workflow.add_edge("RETRIEVE", "MATCH_TWO_WAY")
        
        # Conditional edge: matching might trigger HITL checkpoint
        workflow.add_conditional_edges(
            "MATCH_TWO_WAY",
            self._should_checkpoint,
            {
                "checkpoint": "CHECKPOINT_HITL",
                "continue": "RECONCILE"
            }
        )
        
        # HITL flow
        workflow.add_edge("CHECKPOINT_HITL", "HITL_DECISION")
        
        # Conditional edge: human decision determines next step
        workflow.add_conditional_edges(
            "HITL_DECISION",
            self._handle_human_decision,
            {
                "reconcile": "RECONCILE",
                "reject": "COMPLETE"
            }
        )
        
        # Continue normal flow after reconciliation
        workflow.add_edge("RECONCILE", "APPROVE")
        workflow.add_edge("APPROVE", "POSTING")
        workflow.add_edge("POSTING", "NOTIFY")
        workflow.add_edge("NOTIFY", "COMPLETE")
        
        # Complete is terminal
        workflow.add_edge("COMPLETE", END)
        
        # Compile the graph (no LangGraph checkpointer; app uses local DB)
        return workflow.compile(checkpointer=self.memory)
    
    def _should_checkpoint(
        self,
        state: InvoiceProcessingState
    ) -> Literal["checkpoint", "continue"]:
        """
        Determine if workflow should pause for human review
        """
        match_result = state.get("match_result", "")
        if match_result == "FAILED":
            return "checkpoint"
        return "continue"
    
    def _handle_human_decision(
        self,
        state: InvoiceProcessingState
    ) -> Literal["reconcile", "reject"]:
        """
        Route based on human decision
        """
        decision = state.get("human_decision", "ACCEPT")
        if decision == "REJECT":
            return "reject"
        return "reconcile"
    
    async def run(
        self,
        invoice_payload: Dict[str, Any],
        thread_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Execute the invoice processing workflow
        
        Args:
            invoice_payload: Invoice data to process
            thread_id: Thread ID for checkpointing
            
        Returns:
            Final workflow state
        """
        # Create initial state
        initial_state = create_initial_state(invoice_payload)
        
        logger.info("=" * 80)
        logger.info("🚀 STARTING INVOICE PROCESSING WORKFLOW")
        logger.info("=" * 80)
        logger.info(f"Invoice ID: {invoice_payload.get('invoice_id')}")
        logger.info(f"Vendor: {invoice_payload.get('vendor_name')}")
        logger.info(f"Amount: {invoice_payload.get('currency')} {invoice_payload.get('amount')}")
        logger.info("=" * 80)
        
        # Run the graph
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            # Execute workflow
            final_state = None
            # Keep a cumulative state dict so node outputs are merged
            cumulative_state = dict(initial_state)
            async for state in self.graph.astream(initial_state, config):
                # state is a dict with node name as key
                for node_name, node_state in state.items():
                    logger.info(f"Completed node: {node_name}")
                    # merge node outputs into cumulative state
                    if isinstance(node_state, dict):
                        cumulative_state.update(node_state)
                    final_state = cumulative_state
            
            logger.info("=" * 80)
            logger.info("✅ Workflow execution completed")
            logger.info("=" * 80)
            
            return final_state
        
        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {str(e)}")
            raise
    
    async def resume_from_checkpoint(
        self,
        checkpoint_id: str,
        decision: str,
        reviewer_id: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Resume workflow from a checkpoint after human decision
        
        Args:
            checkpoint_id: The checkpoint to resume from
            decision: Human decision (ACCEPT or REJECT)
            reviewer_id: ID of the reviewer
            notes: Optional notes from reviewer
            
        Returns:
            Final workflow state
        """
        from .tools.checkpoint_db import checkpoint_db
        
        # Get checkpoint from database
        checkpoint_data = checkpoint_db.get_checkpoint(checkpoint_id)
        
        if not checkpoint_data:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        
        # Record the decision
        checkpoint_db.record_decision(
            checkpoint_id=checkpoint_id,
            decision=decision,
            reviewer_id=reviewer_id,
            notes=notes
        )
        
        # Get the stored state
        stored_state = checkpoint_data["state"]
        
        # Update state with decision
        stored_state["human_decision"] = decision
        stored_state["reviewer_id"] = reviewer_id
        
        logger.info("=" * 80)
        logger.info(f"🔄 RESUMING WORKFLOW FROM CHECKPOINT: {checkpoint_id}")
        logger.info(f"Decision: {decision} by {reviewer_id}")
        logger.info("=" * 80)
        
        # If REJECT, skip to COMPLETE
        if decision == "REJECT":
            logger.info("Decision is REJECT - skipping to COMPLETE")
            stored_state["status"] = "MANUAL_HANDOFF"
            final_state = await self.agents.complete_node(stored_state)
            stored_state.update(final_state)
            return stored_state
        
        # If ACCEPT, continue through remaining stages
        logger.info("Decision is ACCEPT - continuing workflow")
        
        # Manually execute remaining stages in order
        stages = [
            ("RECONCILE", self.agents.reconcile_node),
            ("APPROVE", self.agents.approve_node),
            ("POSTING", self.agents.posting_node),
            ("NOTIFY", self.agents.notify_node),
            ("COMPLETE", self.agents.complete_node)
        ]
        
        for stage_name, stage_func in stages:
            logger.info(f"Executing stage: {stage_name}")
            try:
                result = await stage_func(stored_state)
                if isinstance(result, dict):
                    stored_state.update(result)
            except Exception as e:
                logger.error(f"Error in stage {stage_name}: {e}")
                raise
        
        logger.info("=" * 80)
        logger.info("✅ Workflow resumed and completed successfully")
        logger.info("=" * 80)
        
        return stored_state
    
    def get_graph_visualization(self) -> str:
        """
        Get a text representation of the graph structure
        """
        return """
Invoice Processing Workflow Graph:

START
  ↓
INTAKE (Validate & Persist)
  ↓
UNDERSTAND (OCR & Parse)
  ↓
PREPARE (Normalize & Enrich)
  ↓
RETRIEVE (Fetch ERP Data)
  ↓
MATCH_TWO_WAY (Compute Match Score)
  ↓
  ├─[MATCHED]──────────────────┐
  └─[FAILED]                   │
      ↓                        │
CHECKPOINT_HITL               │
      ↓                        │
HITL_DECISION                 │
      ↓                        │
  ├─[ACCEPT]                   │
  │   ↓                        │
  │   └────────────────────────┤
  │                            │
  └─[REJECT]────────┐          │
                     │          │
                     ↓          ↓
                RECONCILE (Build Entries)
                     ↓
                APPROVE (Apply Policy)
                     ↓
                POSTING (Post to ERP)
                     ↓
                NOTIFY (Send Notifications)
                     ↓
                COMPLETE (Finalize)
                     ↓
                    END

Legend:
• Solid lines: Deterministic flow
• Branches: Conditional routing
• CHECKPOINT_HITL: Pause for human review
• HITL_DECISION: Resume based on human input
"""
