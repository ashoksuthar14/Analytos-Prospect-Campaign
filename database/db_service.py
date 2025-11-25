"""
Database Service: Manages SQLite database connections and CRUD operations.
"""

import sqlite3
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager


class DatabaseService:
    """
    Manages database connections and provides CRUD operations.
    
    Handles:
    - Database initialization
    - Connection management
    - CRUD operations for all tables
    - Transaction management
    """
    
    def __init__(self, db_path: str = "./database/prospect_workflow.db"):
        """
        Initialize database service.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database schema if it doesn't exist."""
        schema_path = Path(__file__).parent / "schema.sql"
        
        if not schema_path.exists():
            return
        
        # Check if database already exists and has tables
        if self.db_path.exists():
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
                )
                if cursor.fetchone():
                    # Database already initialized
                    return
            finally:
                conn.close()
        
        # Initialize database
        conn = sqlite3.connect(str(self.db_path))
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
                conn.executescript(schema_sql)
                conn.commit()
        finally:
            conn.close()
    
    @contextmanager
    def get_connection(self):
        """
        Get database connection context manager.
        
        Yields:
            sqlite3.Connection
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ==================== RUNS ====================
    
    def create_run(
        self,
        workflow_name: str,
        config_snapshot: Optional[Dict[str, Any]] = None,
        campaign_name: Optional[str] = None
    ) -> str:
        """
        Create a new campaign run.
        
        Args:
            workflow_name: Name of the campaign workflow
            config_snapshot: Campaign configuration snapshot
            campaign_name: User-friendly name for the campaign
            
        Returns:
            Run ID (UUID string)
        """
        run_id = str(uuid.uuid4())
        config_json = json.dumps(config_snapshot) if config_snapshot else None
        
        # Ensure campaign_name has a value, fallback to workflow_name
        actual_campaign_name = campaign_name if campaign_name else workflow_name
        
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, workflow_name, campaign_name, status, config_snapshot, progress)
                VALUES (?, ?, ?, 'pending', ?, 0)
                """,
                (run_id, workflow_name, actual_campaign_name, config_json)
            )
        
        return run_id
    
    def update_run_status(
        self,
        run_id: str,
        status: str,
        error_message: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        progress: Optional[float] = None
    ) -> None:
        """
        Update run status, metadata, and progress.
        
        Args:
            run_id: Run ID
            status: New status (pending, running, completed, failed, waiting_approval)
            error_message: Error message if status is failed
            metrics: Metrics dictionary
            progress: Progress percentage (0-100)
        """
        updates = []
        params = [status]
        
        if status == "completed":
            updates.append("completed_at = CURRENT_TIMESTAMP")
            updates.append("error_message = NULL")
            # If completed, ensure progress is 100 unless specified
            if progress is None:
                progress = 100.0
        elif status == "failed":
            updates.append("completed_at = CURRENT_TIMESTAMP")
            updates.append("error_message = ?")
            params.append(error_message)
        
        if metrics:
            updates.append("metrics = ?")
            params.append(json.dumps(metrics))
            
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
            
        # Build query
        if updates:
            update_sql = f"""
                UPDATE runs
                SET status = ?, {', '.join(updates)}
                WHERE run_id = ?
            """
        else:
            update_sql = """
                UPDATE runs
                SET status = ?
                WHERE run_id = ?
            """
        params.append(run_id)
        
        with self.get_connection() as conn:
            conn.execute(update_sql, params)
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get run by ID.
        
        Args:
            run_id: Run ID
            
        Returns:
            Run dictionary or None
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,)
            ).fetchone()
            
            if row:
                return self._row_to_dict(row)
            return None
    
    def get_runs(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        return_total: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get runs with filters.
        
        Args:
            workflow_name: Filter by campaign name
            status: Filter by status
            limit: Maximum number of results
            offset: Offset for pagination
            return_total: If True, return tuple of (runs, total_count)
            
        Returns:
            List of run dictionaries, or tuple of (runs, total_count) if return_total=True
        """
        query = "SELECT * FROM runs WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM runs WHERE 1=1"
        params = []
        
        if workflow_name:
            query += " AND workflow_name = ?"
            count_query += " AND workflow_name = ?"
            params.append(workflow_name)
        
        if status:
            query += " AND status = ?"
            count_query += " AND status = ?"
            params.append(status)
        
        with self.get_connection() as conn:
            # Get total count if requested
            total_count = None
            if return_total:
                total_count = conn.execute(count_query, params).fetchone()[0]
            
            # Get paginated results
            query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
            result_params = params + [limit, offset]
            rows = conn.execute(query, result_params).fetchall()
            runs = [self._row_to_dict(row) for row in rows]
            
            if return_total:
                return runs, total_count
            return runs
    
    # ==================== LEADS ====================
    
    def create_lead(self, run_id: str, lead_data: Dict[str, Any]) -> str:
        """
        Create a new lead.
        
        Args:
            run_id: Run ID
            lead_data: Lead data dictionary
            
        Returns:
            Lead ID (UUID string)
        """
        lead_id = str(uuid.uuid4())
        # Map 'enrichment' field to 'enrichment_data' for database storage
        enrichment_data = lead_data.get("enrichment_data") or lead_data.get("enrichment")
        enrichment_json = json.dumps(enrichment_data) if enrichment_data else None
        
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO leads (
                    lead_id, run_id, company_name, domain, contact_email,
                    contact_name, contact_title, revenue, employee_count,
                    industry, location, enrichment_data, score, fit_score,
                    engagement_score, intent_score, apollo_contact_id, 
                    apollo_synced_at, apollo_sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lead_id, run_id,
                    lead_data.get("company_name", ""),
                    lead_data.get("domain"),
                    lead_data.get("contact_email"),
                    lead_data.get("contact_name"),
                    lead_data.get("contact_title"),
                    lead_data.get("revenue"),
                    lead_data.get("employee_count"),
                    lead_data.get("industry"),
                    lead_data.get("location"),
                    enrichment_json,
                    lead_data.get("score"),
                    lead_data.get("fit_score"),
                    lead_data.get("engagement_score"),
                    lead_data.get("intent_score"),
                    lead_data.get("apollo_contact_id"),
                    lead_data.get("apollo_synced_at"),
                    lead_data.get("apollo_sync_status")
                )
            )
        
        return lead_id
    
    def bulk_create_leads(self, run_id: str, leads: List[Dict[str, Any]]) -> List[str]:
        """
        Bulk create leads.
        
        Args:
            run_id: Run ID
            leads: List of lead data dictionaries
            
        Returns:
            List of created lead IDs
        """
        lead_ids = []
        
        with self.get_connection() as conn:
            for lead_data in leads:
                lead_id = str(uuid.uuid4())
                lead_ids.append(lead_id)
                # Map 'enrichment' field to 'enrichment_data' for database storage
                enrichment_data = lead_data.get("enrichment_data") or lead_data.get("enrichment")
                enrichment_json = json.dumps(enrichment_data) if enrichment_data else None
                
                conn.execute(
                    """
                    INSERT INTO leads (
                        lead_id, run_id, company_name, domain, contact_email,
                        contact_name, contact_title, revenue, employee_count,
                        industry, location, enrichment_data, score, fit_score,
                        engagement_score, intent_score, apollo_contact_id,
                        apollo_synced_at, apollo_sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lead_id, run_id,
                        lead_data.get("company_name", ""),
                        lead_data.get("domain"),
                        lead_data.get("contact_email"),
                        lead_data.get("contact_name"),
                        lead_data.get("contact_title"),
                        lead_data.get("revenue"),
                        lead_data.get("employee_count"),
                        lead_data.get("industry"),
                        lead_data.get("location"),
                        enrichment_json,
                        lead_data.get("score"),
                        lead_data.get("fit_score"),
                        lead_data.get("engagement_score"),
                        lead_data.get("intent_score"),
                        lead_data.get("apollo_contact_id"),
                        lead_data.get("apollo_synced_at"),
                        lead_data.get("apollo_sync_status")
                    )
                )
        
        return lead_ids
    
    def get_leads_by_run(
        self,
        run_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get leads for a run with pagination.
        
        Args:
            run_id: Run ID
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of lead dictionaries
        """
        try:
            with self.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM leads
                    WHERE run_id = ?
                    ORDER BY score DESC, created_at ASC
                    LIMIT ? OFFSET ?
                    """,
                    (run_id, limit, offset)
                ).fetchall()
                
                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            # Log error and return empty list instead of crashing
            import traceback
            print(f"Error fetching leads for run {run_id}: {str(e)}")
            print(traceback.format_exc())
            return []
    
    def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get lead by ID."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM leads WHERE lead_id = ?",
                (lead_id,)
            ).fetchone()
            
            if row:
                return self._row_to_dict(row)
            return None
    
    # ==================== MESSAGES ====================
    
    def create_message(self, run_id: str, lead_id: str, message_data: Dict[str, Any]) -> str:
        """
        Create a new message.
        
        Args:
            run_id: Run ID
            lead_id: Lead ID
            message_data: Message data dictionary
            
        Returns:
            Message ID (UUID string)
        """
        message_id = message_data.get("message_id") or str(uuid.uuid4())
        personalization_json = json.dumps(message_data.get("personalization_used")) if message_data.get("personalization_used") else None
        provider = message_data.get("provider")
        provider_message_id = message_data.get("provider_message_id")
        status = message_data.get("status", "pending")
        sent_at = message_data.get("sent_at")
        
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    message_id, lead_id, run_id, subject, body,
                    personalization_used, provider, provider_message_id, status, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    subject = excluded.subject,
                    body = excluded.body,
                    personalization_used = excluded.personalization_used,
                    provider = excluded.provider,
                    provider_message_id = excluded.provider_message_id,
                    status = excluded.status,
                    sent_at = COALESCE(excluded.sent_at, messages.sent_at)
                """,
                (
                    message_id, lead_id, run_id,
                    message_data.get("subject", ""),
                    message_data.get("body", ""),
                    personalization_json,
                    provider,
                    provider_message_id,
                    status,
                    sent_at
                )
            )
        
        return message_id
    
    def update_message_status(
        self,
        message_id: str,
        status: str,
        provider_message_id: Optional[str] = None,
        sent_at: Optional[datetime] = None
    ) -> None:
        """
        Update message status.
        
        Args:
            message_id: Message ID
            status: New status
            provider_message_id: Provider message ID
            sent_at: Sent timestamp
        """
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE messages
                SET status = ?, provider_message_id = ?, sent_at = ?
                WHERE message_id = ?
                """,
                (status, provider_message_id, sent_at, message_id)
            )
    
    def get_messages_by_run(
        self,
        run_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages for a run with pagination."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE run_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (run_id, limit, offset)
            ).fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    # ==================== RESPONSES ====================
    
    def create_response(self, message_id: str) -> str:
        """
        Create a new response record.
        
        Args:
            message_id: Message ID
            
        Returns:
            Response ID (UUID string)
        """
        response_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO responses (response_id, message_id)
                VALUES (?, ?)
                """,
                (response_id, message_id)
            )
        
        return response_id
    
    def update_response(
        self,
        response_id: str,
        opened: Optional[bool] = None,
        clicked: Optional[bool] = None,
        replied: Optional[bool] = None,
        meeting_scheduled: Optional[bool] = None,
        **kwargs
    ) -> None:
        """
        Update response tracking data.
        
        Args:
            response_id: Response ID
            opened: Whether email was opened
            clicked: Whether link was clicked
            replied: Whether email was replied to
            meeting_scheduled: Whether meeting was scheduled
            **kwargs: Additional timestamp fields (opened_at, clicked_at, etc.)
        """
        updates = []
        params = []
        
        if opened is not None:
            updates.append("opened = ?")
            params.append(1 if opened else 0)
            if "opened_at" in kwargs:
                updates.append("opened_at = ?")
                params.append(kwargs["opened_at"])
        
        if clicked is not None:
            updates.append("clicked = ?")
            params.append(1 if clicked else 0)
            if "clicked_at" in kwargs:
                updates.append("clicked_at = ?")
                params.append(kwargs["clicked_at"])
        
        if replied is not None:
            updates.append("replied = ?")
            params.append(1 if replied else 0)
            if "replied_at" in kwargs:
                updates.append("replied_at = ?")
                params.append(kwargs["replied_at"])
        
        if meeting_scheduled is not None:
            updates.append("meeting_scheduled = ?")
            params.append(1 if meeting_scheduled else 0)
            if "meeting_at" in kwargs:
                updates.append("meeting_at = ?")
                params.append(kwargs["meeting_at"])
        
        if updates:
            updates.append("last_updated = CURRENT_TIMESTAMP")
            params.append(response_id)
            
            with self.get_connection() as conn:
                conn.execute(
                    f"UPDATE responses SET {', '.join(updates)} WHERE response_id = ?",
                    params
                )
    
    def get_responses_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all responses for messages in a run."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT r.* FROM responses r
                JOIN messages m ON r.message_id = m.message_id
                WHERE m.run_id = ?
                ORDER BY r.last_updated DESC
                """,
                (run_id,)
            ).fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    # ==================== RECOMMENDATIONS ====================
    
    def create_recommendation(
        self,
        run_id: str,
        field: str,
        old_value: Any,
        new_value: Any,
        reason: str
    ) -> str:
        """
        Create a new recommendation.
        
        Args:
            run_id: Run ID
            field: Field path (e.g., 'scoring.weights.fit_score')
            old_value: Current value
            new_value: Proposed new value
            reason: Reason for recommendation
            
        Returns:
            Recommendation ID (UUID string)
        """
        rec_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO recommendations (
                    rec_id, run_id, field, old_value, new_value, reason
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id, run_id, field,
                    json.dumps(old_value),
                    json.dumps(new_value),
                    reason
                )
            )
        
        return rec_id
    
    def approve_recommendation(self, rec_id: str) -> None:
        """Approve and mark recommendation as applied."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE recommendations
                SET approved = 1, applied_at = CURRENT_TIMESTAMP
                WHERE rec_id = ?
                """,
                (rec_id,)
            )
    
    def get_pending_recommendations(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get pending (unapproved) recommendations.
        
        Args:
            run_id: Optional run ID filter
            
        Returns:
            List of recommendation dictionaries
        """
        query = "SELECT * FROM recommendations WHERE approved = 0"
        params = []
        
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        
        query += " ORDER BY created_at DESC"
        
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]
    
    # ==================== RUN LOGS ====================
    
    def create_run_log(
        self,
        run_id: str,
        agent_name: str,
        step: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        error_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ) -> int:
        """
        Create a run log entry.
        
        Args:
            run_id: Run ID
            agent_name: Name of the agent
            step: Step name (start, tool_call, output, error)
            input_data: Input data dictionary
            output_data: Output data dictionary
            error_data: Error data dictionary
            duration_ms: Duration in milliseconds
            
        Returns:
            Log ID
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO run_logs (
                    run_id, agent_name, step, input_data, output_data,
                    error_data, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, agent_name, step,
                    json.dumps(input_data) if input_data else None,
                    json.dumps(output_data) if output_data else None,
                    json.dumps(error_data) if error_data else None,
                    duration_ms
                )
            )
            return cursor.lastrowid
    
    def get_run_logs(
        self,
        run_id: str,
        agent_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get run logs for a run.
        
        Args:
            run_id: Run ID
            agent_name: Optional agent name filter
            
        Returns:
            List of log dictionaries
        """
        query = "SELECT * FROM run_logs WHERE run_id = ?"
        params = [run_id]
        
        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)
        
        query += " ORDER BY timestamp ASC"
        
        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]
    
    # ==================== ARCHIVE ====================
    
    def archive_old_runs(self, keep_last_n: int = 20) -> int:
        """
        Archive old runs, keeping only the last N active runs.
        
        Args:
            keep_last_n: Number of recent runs to keep active
            
        Returns:
            Number of runs archived
        """
        # Get runs to archive (all except the last N)
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT run_id FROM runs
                ORDER BY started_at DESC
                LIMIT -1 OFFSET ?
                """,
                (keep_last_n,)
            ).fetchall()
            
            run_ids_to_archive = [row["run_id"] for row in rows]
            
            if not run_ids_to_archive:
                return 0
            
            # Mark runs as archived (we'll move data to files later)
            # For now, we'll just mark them in the database
            placeholders = ','.join(['?' for _ in run_ids_to_archive])
            conn.execute(
                f"""
                UPDATE runs
                SET status = 'archived'
                WHERE run_id IN ({placeholders})
                """,
                run_ids_to_archive
            )
        
        return len(run_ids_to_archive)
    
    # ==================== HELPER METHODS ====================
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite row to dictionary."""
        return dict(row)

