"""
RunLogger: Handles logging to database and JSON files.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from database.db_service import DatabaseService


class RunLogger:
    """
    Logs campaign execution data to both database and JSON files.
    
    Handles:
    - Database logging (summaries)
    - JSON file logging (full traces in debug mode)
    - Archive management
    """
    
    def __init__(
        self,
        db_service: DatabaseService,
        log_dir: str = "./logs",
        enable_full_traces: bool = False
    ):
        """
        Initialize run logger.
        
        Args:
            db_service: Database service instance
            log_dir: Directory for JSON log files
            enable_full_traces: Whether to log full traces to JSON files
        """
        self.db_service = db_service
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir = self.log_dir / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.enable_full_traces = enable_full_traces
        self._run_logs: Dict[str, list] = {}  # In-memory log buffer for JSON export
    
    def log_agent_start(
        self,
        run_id: str,
        agent_name: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log agent start.
        
        Args:
            run_id: Run ID
            agent_name: Name of the agent
            input_data: Input data dictionary
        """
        # Log to database (summary)
        self.db_service.create_run_log(
            run_id=run_id,
            agent_name=agent_name,
            step="start",
            input_data=self._summarize_for_db(input_data) if input_data else None
        )
        
        # Log to JSON file (full trace if enabled)
        if self.enable_full_traces:
            self._log_to_json(
                run_id=run_id,
                agent_name=agent_name,
                step="start",
                input_data=input_data,
                output_data=None,
                error_data=None
            )
    
    def log_tool_call(
        self,
        run_id: str,
        agent_name: str,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
        tool_output: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ) -> None:
        """
        Log tool call.
        
        Args:
            run_id: Run ID
            agent_name: Name of the agent
            tool_name: Name of the tool
            tool_input: Tool input data
            tool_output: Tool output data
            duration_ms: Duration in milliseconds
        """
        # Prepare tool call data
        tool_call_data = {
            "tool_name": tool_name,
            "input": tool_input,
            "output": tool_output
        }
        
        # Log to database (summary)
        self.db_service.create_run_log(
            run_id=run_id,
            agent_name=agent_name,
            step="tool_call",
            input_data={"tool": tool_name},
            output_data=self._summarize_for_db(tool_output) if tool_output else None,
            duration_ms=duration_ms
        )
        
        # Log to JSON file (full trace if enabled)
        if self.enable_full_traces:
            self._log_to_json(
                run_id=run_id,
                agent_name=agent_name,
                step="tool_call",
                input_data=tool_call_data,
                output_data=None,
                error_data=None,
                duration_ms=duration_ms
            )
    
    def log_agent_output(
        self,
        run_id: str,
        agent_name: str,
        output_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ) -> None:
        """
        Log agent output.
        
        Args:
            run_id: Run ID
            agent_name: Name of the agent
            output_data: Output data dictionary
            duration_ms: Duration in milliseconds
        """
        # Log to database (summary)
        self.db_service.create_run_log(
            run_id=run_id,
            agent_name=agent_name,
            step="output",
            output_data=self._summarize_for_db(output_data) if output_data else None,
            duration_ms=duration_ms
        )
        
        # Log to JSON file (full trace if enabled)
        if self.enable_full_traces:
            self._log_to_json(
                run_id=run_id,
                agent_name=agent_name,
                step="output",
                input_data=None,
                output_data=output_data,
                error_data=None,
                duration_ms=duration_ms
            )
    
    def log_agent_error(
        self,
        run_id: Optional[str],
        agent_name: str,
        error_data: Dict[str, Any],
        duration_ms: Optional[int] = None
    ) -> None:
        """
        Log agent error.
        
        Args:
            run_id: Run ID (optional, can be None during initialization)
            agent_name: Name of the agent
            error_data: Error data dictionary
            duration_ms: Duration in milliseconds
        """
        # Skip database logging if no run_id (e.g., during agent initialization)
        if run_id:
            # Log to database (summary)
            self.db_service.create_run_log(
                run_id=run_id,
                agent_name=agent_name,
                step="error",
                error_data=self._summarize_error(error_data),
                duration_ms=duration_ms
            )
        
        # Log to JSON file (always log errors, even if full traces disabled)
        self._log_to_json(
            run_id=run_id,
            agent_name=agent_name,
            step="error",
            input_data=None,
            output_data=None,
            error_data=error_data,
            duration_ms=duration_ms
        )
    
    def _log_to_json(
        self,
        run_id: Optional[str],
        agent_name: str,
        step: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        error_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ) -> None:
        """
        Log to JSON file.
        
        Args:
            run_id: Run ID
            agent_name: Name of the agent
            step: Step name
            input_data: Input data
            output_data: Output data
            error_data: Error data
            duration_ms: Duration in milliseconds
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "run_id": run_id,
            "agent_name": agent_name,
            "step": step,
            "input_data": input_data,
            "output_data": output_data,
            "error_data": error_data,
            "duration_ms": duration_ms
        }
        
        # Use placeholder for None run_id (initialization errors)
        log_run_id = run_id or "init_error"
        
        # Add to in-memory buffer
        if log_run_id not in self._run_logs:
            self._run_logs[log_run_id] = []
        self._run_logs[log_run_id].append(log_entry)
        
        # Write to file immediately (for debugging)
        log_file = self.log_dir / f"{log_run_id}.json"
        self._append_to_json_file(log_file, log_entry)
    
    def _append_to_json_file(self, log_file: Path, entry: Dict[str, Any]) -> None:
        """
        Append log entry to JSON file.
        
        Args:
            log_file: Path to log file
            entry: Log entry dictionary
        """
        # Read existing logs if file exists
        logs = []
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                    if not isinstance(logs, list):
                        logs = []
            except (json.JSONDecodeError, IOError):
                logs = []
        
        # Append new entry
        logs.append(entry)
        
        # Write back to file
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    
    def export_run_logs(self, run_id: str) -> Optional[Path]:
        """
        Export all logs for a run to JSON file.
        
        Args:
            run_id: Run ID
            
        Returns:
            Path to exported log file, or None if no logs
        """
        # Get logs from database
        db_logs = self.db_service.get_run_logs(run_id)
        
        if not db_logs:
            return None
        
        # Convert to export format
        export_data = {
            "run_id": run_id,
            "exported_at": datetime.utcnow().isoformat(),
            "logs": []
        }
        
        for log in db_logs:
            export_entry = {
                "timestamp": log.get("timestamp"),
                "agent_name": log.get("agent_name"),
                "step": log.get("step"),
                "duration_ms": log.get("duration_ms")
            }
            
            # Parse JSON fields
            if log.get("input_data"):
                try:
                    export_entry["input_data"] = json.loads(log["input_data"])
                except (json.JSONDecodeError, TypeError):
                    export_entry["input_data"] = log.get("input_data")
            
            if log.get("output_data"):
                try:
                    export_entry["output_data"] = json.loads(log["output_data"])
                except (json.JSONDecodeError, TypeError):
                    export_entry["output_data"] = log.get("output_data")
            
            if log.get("error_data"):
                try:
                    export_entry["error_data"] = json.loads(log["error_data"])
                except (json.JSONDecodeError, TypeError):
                    export_entry["error_data"] = log.get("error_data")
            
            export_data["logs"].append(export_entry)
        
        # Write to file
        log_file = self.log_dir / f"{run_id}_export.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return log_file
    
    def archive_run_logs(self, run_id: str) -> Optional[Path]:
        """
        Archive run logs to archive directory.
        
        Args:
            run_id: Run ID
            
        Returns:
            Path to archived log file, or None if no logs
        """
        log_file = self.log_dir / f"{run_id}.json"
        if not log_file.exists():
            return None
        
        # Move to archive
        archive_file = self.archive_dir / f"{run_id}.json"
        log_file.rename(archive_file)
        
        # Also archive export if it exists
        export_file = self.log_dir / f"{run_id}_export.json"
        if export_file.exists():
            archive_export = self.archive_dir / f"{run_id}_export.json"
            export_file.rename(archive_export)
        
        return archive_file
    
    def _summarize_for_db(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a summary of data for database storage.
        
        Args:
            data: Full data dictionary
            
        Returns:
            Summarized data dictionary
        """
        if not data:
            return {}
        
        # Import secrets provider for PII redaction
        try:
            from configs.secrets_provider import SecretsProvider
            secrets_provider = SecretsProvider()
        except:
            secrets_provider = None
        
        summary = {}
        
        # Keep top-level keys and limit nested data
        for key, value in data.items():
            if isinstance(value, str):
                # Redact PII from strings
                if secrets_provider:
                    value = secrets_provider.redact_secret(value)
                summary[key] = value[:500] if len(value) > 500 else value  # Limit length
            elif isinstance(value, (list, tuple)):
                summary[key] = {
                    "count": len(value),
                    "type": "array"
                }
                # Keep first few items if small
                if len(value) <= 3:
                    summary[key]["sample"] = value[:3]
            elif isinstance(value, dict):
                # Keep only top-level keys of nested dicts
                summary[key] = {
                    "keys": list(value.keys())[:10],  # Limit to 10 keys
                    "type": "object"
                }
            else:
                summary[key] = value
        
        return summary
    
    def _summarize_error(self, error_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Summarize error data for database.
        
        Args:
            error_data: Error data dictionary
            
        Returns:
            Summarized error dictionary
        """
        summary = {
            "error_type": error_data.get("type", "Unknown"),
            "message": str(error_data.get("message", ""))[:500]  # Limit message length
        }
        
        if "traceback" in error_data:
            # Keep only last few lines of traceback
            traceback_lines = error_data["traceback"].split("\n")
            summary["traceback"] = "\n".join(traceback_lines[-10:])
        
        return summary
    
    def get_run_summary(self, run_id: str) -> Dict[str, Any]:
        """
        Get a summary of run execution.
        
        Args:
            run_id: Run ID
            
        Returns:
            Summary dictionary with metrics
        """
        logs = self.db_service.get_run_logs(run_id)
        
        summary = {
            "run_id": run_id,
            "total_logs": len(logs),
            "agents_executed": set(),
            "total_duration_ms": 0,
            "errors": 0,
            "tool_calls": 0
        }
        
        for log in logs:
            agent_name = log.get("agent_name")
            if agent_name:
                summary["agents_executed"].add(agent_name)
            
            step = log.get("step")
            if step == "error":
                summary["errors"] += 1
            elif step == "tool_call":
                summary["tool_calls"] += 1
            
            duration = log.get("duration_ms")
            if duration:
                summary["total_duration_ms"] += duration
        
        summary["agents_executed"] = list(summary["agents_executed"])
        
        return summary

