"""
Checkpoint Database System
Stores workflow state for HITL (Human-In-The-Loop) review
"""
import json
import sqlite3
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CheckpointDB:
    """
    Manages checkpoint storage for HITL workflow pausing and resuming
    """
    
    def __init__(self, db_path: str = "./demo.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Checkpoints table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                invoice_id TEXT NOT NULL,
                state_blob TEXT NOT NULL,
                paused_reason TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                reviewer_id TEXT,
                decision TEXT,
                decision_notes TEXT,
                decided_at TEXT
            )
        """)
        
        # Human review queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS human_review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkpoint_id TEXT NOT NULL,
                invoice_id TEXT NOT NULL,
                vendor_name TEXT,
                amount REAL,
                currency TEXT,
                reason_for_hold TEXT,
                review_url TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(checkpoint_id)
            )
        """)
        
        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def create_checkpoint(
        self,
        checkpoint_id: str,
        workflow_id: str,
        invoice_id: str,
        state: Dict[str, Any],
        paused_reason: str
    ) -> Dict[str, Any]:
        """
        Create a checkpoint for HITL review
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        created_at = datetime.utcnow().isoformat()
        state_blob = json.dumps(state)
        
        try:
            cursor.execute("""
                INSERT INTO checkpoints 
                (checkpoint_id, workflow_id, invoice_id, state_blob, paused_reason, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (checkpoint_id, workflow_id, invoice_id, state_blob, paused_reason, created_at, "PENDING"))
            
            conn.commit()
            
            logger.info(f"Checkpoint created: {checkpoint_id}")
            
            return {
                "checkpoint_id": checkpoint_id,
                "created_at": created_at,
                "status": "PENDING"
            }
        
        except Exception as e:
            logger.error(f"Error creating checkpoint: {str(e)}")
            conn.rollback()
            raise
        
        finally:
            conn.close()
    
    def add_to_review_queue(
        self,
        checkpoint_id: str,
        invoice_data: Dict[str, Any],
        reason: str
    ) -> str:
        """
        Add checkpoint to human review queue
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        created_at = datetime.utcnow().isoformat()
        review_url = f"http://localhost:8000/review/{checkpoint_id}"
        
        try:
            cursor.execute("""
                INSERT INTO human_review_queue
                (checkpoint_id, invoice_id, vendor_name, amount, currency, reason_for_hold, review_url, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                checkpoint_id,
                invoice_data.get("invoice_id", "unknown"),
                invoice_data.get("vendor_name", "unknown"),
                invoice_data.get("amount", 0),
                invoice_data.get("currency", "USD"),
                reason,
                review_url,
                created_at,
                "PENDING"
            ))
            
            conn.commit()
            
            logger.info(f"Added to review queue: {checkpoint_id}")
            
            return review_url
        
        except Exception as e:
            logger.error(f"Error adding to review queue: {str(e)}")
            conn.rollback()
            raise
        
        finally:
            conn.close()
    
    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """
        Get all pending reviews from the queue
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT checkpoint_id, invoice_id, vendor_name, amount, currency, 
                   reason_for_hold, review_url, created_at
            FROM human_review_queue
            WHERE status = 'PENDING'
            ORDER BY created_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "checkpoint_id": row[0],
                "invoice_id": row[1],
                "vendor_name": row[2],
                "amount": row[3],
                "currency": row[4],
                "reason_for_hold": row[5],
                "review_url": row[6],
                "created_at": row[7]
            }
            for row in rows
        ]
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve checkpoint state
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT workflow_id, invoice_id, state_blob, paused_reason, status, 
                   decision, decision_notes, reviewer_id
            FROM checkpoints
            WHERE checkpoint_id = ?
        """, (checkpoint_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "checkpoint_id": checkpoint_id,
            "workflow_id": row[0],
            "invoice_id": row[1],
            "state": json.loads(row[2]),
            "paused_reason": row[3],
            "status": row[4],
            "decision": row[5],
            "decision_notes": row[6],
            "reviewer_id": row[7]
        }
    
    def record_decision(
        self,
        checkpoint_id: str,
        decision: str,
        reviewer_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Record human decision on a checkpoint
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        decided_at = datetime.utcnow().isoformat()
        
        try:
            # Update checkpoint
            cursor.execute("""
                UPDATE checkpoints
                SET status = ?, decision = ?, reviewer_id = ?, decision_notes = ?, decided_at = ?
                WHERE checkpoint_id = ?
            """, ("RESOLVED", decision, reviewer_id, notes, decided_at, checkpoint_id))
            
            # Update review queue
            cursor.execute("""
                UPDATE human_review_queue
                SET status = ?
                WHERE checkpoint_id = ?
            """, ("RESOLVED", checkpoint_id))
            
            conn.commit()
            
            logger.info(f"Decision recorded for checkpoint {checkpoint_id}: {decision}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error recording decision: {str(e)}")
            conn.rollback()
            return False
        
        finally:
            conn.close()
    
    def add_audit_log(
        self,
        workflow_id: str,
        stage: str,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Add entry to audit log
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.utcnow().isoformat()
        details_json = json.dumps(details) if details else None
        
        try:
            cursor.execute("""
                INSERT INTO audit_log (workflow_id, stage, action, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (workflow_id, stage, action, details_json, timestamp))
            
            conn.commit()
        
        except Exception as e:
            logger.error(f"Error adding audit log: {str(e)}")
            conn.rollback()
        
        finally:
            conn.close()
    
    def get_audit_log(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Get audit log for a workflow
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stage, action, details, timestamp
            FROM audit_log
            WHERE workflow_id = ?
            ORDER BY timestamp ASC
        """, (workflow_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "stage": row[0],
                "action": row[1],
                "details": json.loads(row[2]) if row[2] else None,
                "timestamp": row[3]
            }
            for row in rows
        ]
    
    def get_decision_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get history of resolved reviews, classified by decision
        """
        
        # correcting the SQL to join with human_review_queue for metadata
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.checkpoint_id, c.invoice_id, h.vendor_name, h.amount, h.currency, 
                   c.decision, c.decision_notes, c.reviewer_id, c.decided_at
            FROM checkpoints c
            LEFT JOIN human_review_queue h ON c.checkpoint_id = h.checkpoint_id
            WHERE c.status = 'RESOLVED' AND c.decision IS NOT NULL
            ORDER BY c.decided_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        history = {
            "ACCEPT": [],
            "REJECT": []
        }
        
        for row in rows:
            decision = row[5] 
            item = {
                "checkpoint_id": row[0],
                "invoice_id": row[1],
                "vendor_name": row[2],
                "amount": row[3],
                "currency": row[4],
                "decision": decision,
                "notes": row[6],
                "reviewer": row[7],
                "decided_at": row[8]
            }
            
            if decision in history:
                history[decision].append(item)
                
        return history


# Global instance
checkpoint_db = CheckpointDB()
