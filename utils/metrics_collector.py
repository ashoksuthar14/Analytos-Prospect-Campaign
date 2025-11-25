"""
Metrics Collector: Collects performance metrics and observability data.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
import time


class MetricsCollector:
    """
    Collects and tracks performance metrics.
    
    Tracks:
    - Per-node execution times
    - Tool call counts
    - Error rates
    - Success rates
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, Any] = {
            "node_timings": {},
            "tool_call_counts": defaultdict(int),
            "error_counts": defaultdict(int),
            "success_counts": defaultdict(int),
            "total_runs": 0,
            "total_errors": 0
        }
        self.current_run_metrics: Dict[str, Any] = {}
    
    def start_run(self, run_id: str) -> None:
        """
        Start tracking metrics for a run.
        
        Args:
            run_id: Run ID
        """
        self.current_run_metrics = {
            "run_id": run_id,
            "started_at": datetime.utcnow().isoformat(),
            "node_timings": {},
            "tool_calls": defaultdict(int),
            "errors": [],
            "completed_nodes": []
        }
    
    def record_node_start(self, agent_name: str) -> float:
        """
        Record node execution start.
        
        Args:
            agent_name: Agent name
            
        Returns:
            Timestamp for calculating duration
        """
        return time.time()
    
    def record_node_end(
        self,
        agent_name: str,
        start_time: float,
        success: bool = True,
        error: Optional[Exception] = None
    ) -> None:
        """
        Record node execution end.
        
        Args:
            agent_name: Agent name
            start_time: Start timestamp
            success: Whether execution succeeded
            error: Exception if failed
        """
        try:
            duration_ms = (time.time() - start_time) * 1000
            
            # Update current run metrics
            if "node_timings" not in self.current_run_metrics:
                self.current_run_metrics["node_timings"] = {}
            if agent_name not in self.current_run_metrics["node_timings"]:
                self.current_run_metrics["node_timings"][agent_name] = []
            self.current_run_metrics["node_timings"][agent_name].append(duration_ms)
            
            if success:
                if "completed_nodes" not in self.current_run_metrics:
                    self.current_run_metrics["completed_nodes"] = []
                self.current_run_metrics["completed_nodes"].append(agent_name)
                self.metrics["success_counts"][agent_name] += 1
            else:
                self.metrics["error_counts"][agent_name] += 1
                if error:
                    if "errors" not in self.current_run_metrics:
                        self.current_run_metrics["errors"] = []
                    self.current_run_metrics["errors"].append({
                        "agent": agent_name,
                        "error": str(error),
                        "type": type(error).__name__
                    })
            
            # Update global metrics
            if agent_name not in self.metrics["node_timings"]:
                self.metrics["node_timings"][agent_name] = []
            self.metrics["node_timings"][agent_name].append(duration_ms)
        except Exception:
            # Silently fail if metrics recording fails
            pass
    
    def record_tool_call(self, agent_name: str, tool_name: str) -> None:
        """
        Record a tool call.
        
        Args:
            agent_name: Agent name
            tool_name: Tool name
        """
        try:
            key = f"{agent_name}.{tool_name}"
            self.metrics["tool_call_counts"][key] += 1
            if "tool_calls" not in self.current_run_metrics:
                self.current_run_metrics["tool_calls"] = defaultdict(int)
            self.current_run_metrics["tool_calls"][key] += 1
        except Exception:
            # Silently fail if metrics recording fails
            pass
    
    def record_error(self, agent_name: str, error: Exception) -> None:
        """
        Record an error.
        
        Args:
            agent_name: Agent name
            error: Exception instance
        """
        try:
            self.metrics["error_counts"][agent_name] += 1
            self.metrics["total_errors"] += 1
        except Exception:
            # Silently fail if metrics recording fails
            pass
    
    def end_run(self, run_id: str, success: bool = True) -> Dict[str, Any]:
        """
        End tracking for a run and return metrics.
        
        Args:
            run_id: Run ID
            success: Whether run succeeded
            
        Returns:
            Run metrics dictionary
        """
        self.current_run_metrics["completed_at"] = datetime.utcnow().isoformat()
        self.current_run_metrics["success"] = success
        
        if success:
            self.metrics["total_runs"] += 1
        
        # Calculate summary statistics
        summary = {
            "run_id": run_id,
            "duration_ms": sum(
                sum(timings) for timings in self.current_run_metrics["node_timings"].values()
            ),
            "nodes_completed": len(self.current_run_metrics["completed_nodes"]),
            "tool_calls": sum(self.current_run_metrics["tool_calls"].values()),
            "errors": len(self.current_run_metrics["errors"]),
            "node_metrics": {}
        }
        
        # Per-node metrics
        for agent_name, timings in self.current_run_metrics["node_timings"].items():
            summary["node_metrics"][agent_name] = {
                "avg_duration_ms": sum(timings) / len(timings) if timings else 0,
                "total_duration_ms": sum(timings),
                "call_count": len(timings)
            }
        
        return summary
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """
        Get global metrics summary.
        
        Returns:
            Global metrics dictionary
        """
        # Calculate averages
        node_averages = {}
        for agent_name, timings in self.metrics["node_timings"].items():
            if timings:
                node_averages[agent_name] = {
                    "avg_duration_ms": sum(timings) / len(timings),
                    "total_calls": len(timings),
                    "success_rate": (
                        self.metrics["success_counts"][agent_name] /
                        (self.metrics["success_counts"][agent_name] + self.metrics["error_counts"][agent_name])
                        if (self.metrics["success_counts"][agent_name] + self.metrics["error_counts"][agent_name]) > 0
                        else 0
                    )
                }
        
        return {
            "total_runs": self.metrics["total_runs"],
            "total_errors": self.metrics["total_errors"],
            "node_metrics": node_averages,
            "tool_call_counts": dict(self.metrics["tool_call_counts"]),
            "error_rates": dict(self.metrics["error_counts"])
        }


# Create singleton instance
metrics_collector = MetricsCollector()

