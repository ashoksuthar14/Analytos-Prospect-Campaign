"""
Detailed logging system for agents.
Tracks every step of each agent's execution.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
import traceback


class DetailedLogger:
    """
    Enhanced logger that captures detailed agent execution steps.
    """
    
    def __init__(self, log_dir: str = "./logs", enable_console: bool = True):
        """
        Initialize detailed logger.
        
        Args:
            log_dir: Directory to store logs
            enable_console: Whether to print to console
        """
        self.log_dir = log_dir
        self.enable_console = enable_console
        os.makedirs(log_dir, exist_ok=True)
    
    def log_agent_start(self, run_id: str, agent_name: str, input_data: Any = None):
        """Log when agent starts processing."""
        self._log(run_id, agent_name, "START", {
            "timestamp": datetime.utcnow().isoformat(),
            "input_preview": self._preview_data(input_data)
        })
    
    def log_agent_step(self, run_id: str, agent_name: str, step_name: str, data: Dict[str, Any]):
        """Log intermediate step in agent."""
        self._log(run_id, agent_name, f"STEP: {step_name}", data)
    
    def log_api_call(
        self,
        run_id: str,
        agent_name: str,
        endpoint: str,
        method: str,
        request_data: Any,
        response_data: Any,
        status_code: Optional[int] = None,
        error: Optional[str] = None
    ):
        """Log API call details."""
        self._log(run_id, agent_name, "API_CALL", {
            "endpoint": endpoint,
            "method": method,
            "request": self._preview_data(request_data, max_len=200),
            "response": self._preview_data(response_data, max_len=200),
            "status_code": status_code,
            "error": error,
            "success": error is None
        })
    
    def log_data_transformation(
        self,
        run_id: str,
        agent_name: str,
        transformation: str,
        input_data: Any,
        output_data: Any
    ):
        """Log data transformation."""
        self._log(run_id, agent_name, f"TRANSFORM: {transformation}", {
            "input_preview": self._preview_data(input_data),
            "output_preview": self._preview_data(output_data),
            "input_type": type(input_data).__name__,
            "output_type": type(output_data).__name__
        })
    
    def log_decision(
        self,
        run_id: str,
        agent_name: str,
        decision: str,
        reason: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Log agent decision."""
        self._log(run_id, agent_name, f"DECISION: {decision}", {
            "reason": reason,
            "data": data
        })
    
    def log_agent_complete(
        self,
        run_id: str,
        agent_name: str,
        output_data: Any,
        duration_ms: Optional[float] = None
    ):
        """Log when agent completes successfully."""
        self._log(run_id, agent_name, "COMPLETE", {
            "timestamp": datetime.utcnow().isoformat(),
            "output_preview": self._preview_data(output_data),
            "duration_ms": duration_ms,
            "success": True
        })
    
    def log_agent_error(
        self,
        run_id: str,
        agent_name: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log agent error."""
        self._log(run_id, agent_name, "ERROR", {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context
        })
    
    def _log(self, run_id: str, agent_name: str, event: str, data: Dict[str, Any]):
        """Internal logging method."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "run_id": run_id,
            "agent": agent_name,
            "event": event,
            **data
        }
        
        # Console output
        if self.enable_console:
            self._print_console(agent_name, event, data)
        
        # File output
        self._write_to_file(run_id, log_entry)
    
    def _print_console(self, agent_name: str, event: str, data: Dict[str, Any]):
        """Print to console with formatting."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color codes for different event types
        colors = {
            "START": "\033[94m",  # Blue
            "COMPLETE": "\033[92m",  # Green
            "ERROR": "\033[91m",  # Red
            "API_CALL": "\033[96m",  # Cyan
            "DECISION": "\033[93m",  # Yellow
            "STEP": "\033[95m",  # Magenta
            "TRANSFORM": "\033[90m"  # Gray
        }
        
        event_type = event.split(":")[0] if ":" in event else event
        color = colors.get(event_type, "\033[0m")
        reset = "\033[0m"
        
        print(f"{color}[{timestamp}] [{agent_name}] {event}{reset}")
        
        # Print key data points
        if "error" in data or "error_message" in data:
            print(f"  ❌ Error: {data.get('error_message', data.get('error', 'Unknown'))}")
        
        if "success" in data:
            status = "✅" if data["success"] else "❌"
            print(f"  {status} Success: {data['success']}")
        
        if "endpoint" in data:
            print(f"  🔗 {data.get('method', 'POST')} {data['endpoint']}")
        
        if "status_code" in data:
            status = data["status_code"]
            status_icon = "✅" if 200 <= status < 300 else "❌"
            print(f"  {status_icon} Status: {status}")
        
        # Print preview of important data
        for key in ["input_preview", "output_preview", "response", "reason"]:
            if key in data and data[key]:
                preview = str(data[key])[:100]
                print(f"  📄 {key}: {preview}{'...' if len(str(data[key])) > 100 else ''}")
    
    def _write_to_file(self, run_id: str, log_entry: Dict[str, Any]):
        """Write log entry to file."""
        log_file = os.path.join(self.log_dir, f"{run_id}_detailed.log")
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"Warning: Could not write to log file: {e}")
    
    def _preview_data(self, data: Any, max_len: int = 100) -> str:
        """Create a preview of data for logging."""
        if data is None:
            return "None"
        
        try:
            if isinstance(data, (dict, list)):
                if isinstance(data, list):
                    preview = f"List({len(data)} items)"
                    if data and len(data) > 0:
                        first_item = str(data[0])[:50]
                        preview += f" - First: {first_item}..."
                else:
                    preview = f"Dict({len(data)} keys)"
                    keys = list(data.keys())[:3]
                    preview += f" - Keys: {keys}"
                return preview
            else:
                str_data = str(data)
                if len(str_data) > max_len:
                    return str_data[:max_len] + "..."
                return str_data
        except:
            return f"<{type(data).__name__}>"
    
    def get_agent_summary(self, run_id: str, agent_name: str) -> Dict[str, Any]:
        """Get summary of agent execution from logs."""
        log_file = os.path.join(self.log_dir, f"{run_id}_detailed.log")
        
        if not os.path.exists(log_file):
            return {}
        
        events = []
        errors = []
        api_calls = []
        
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    if entry.get("agent") == agent_name:
                        events.append(entry)
                        
                        if "ERROR" in entry.get("event", ""):
                            errors.append(entry)
                        
                        if "API_CALL" in entry.get("event", ""):
                            api_calls.append(entry)
            
            return {
                "agent": agent_name,
                "total_events": len(events),
                "errors": len(errors),
                "api_calls": len(api_calls),
                "events": events[-10:]  # Last 10 events
            }
        except Exception:
            return {}

