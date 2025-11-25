"""
Observability: Tracks metrics, timing, and performance.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import time
import threading


class MetricsCollector:
    """
    Collects and tracks metrics for observability.
    
    Tracks:
    - Per-node timing
    - Tool call counts
    - Error rates
    - Performance metrics
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, Any] = {
            "node_timings": [],
            "tool_calls": defaultdict(int),
            "errors": defaultdict(int),
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0
        }
        self.lock = threading.Lock()
    
    def record_node_timing(
        self,
        run_id: str,
        agent_name: str,
        duration_ms: float
    ) -> None:
        """
        Record node execution timing.
        
        Args:
            run_id: Run ID
            agent_name: Agent name
            duration_ms: Duration in milliseconds
        """
        try:
            with self.lock:
                # Ensure node_timings is a list
                if not isinstance(self.metrics.get("node_timings"), list):
                    self.metrics["node_timings"] = []
                
                self.metrics["node_timings"].append({
                    "run_id": run_id,
                    "agent_name": agent_name,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.utcnow().isoformat()
                })
        except Exception:
            # Silently fail if metrics recording fails
            pass
    
    def record_tool_call(
        self,
        run_id: str,
        agent_name: str,
        tool_name: str
    ) -> None:
        """
        Record a tool call.
        
        Args:
            run_id: Run ID
            agent_name: Agent name
            tool_name: Tool name
        """
        try:
            with self.lock:
                # Ensure tool_calls is a defaultdict
                if not isinstance(self.metrics.get("tool_calls"), defaultdict):
                    from collections import defaultdict
                    self.metrics["tool_calls"] = defaultdict(int)
                
                key = f"{agent_name}_{tool_name}"
                self.metrics["tool_calls"][key] += 1
        except Exception:
            # Silently fail if metrics recording fails
            pass
    
    def record_error(
        self,
        run_id: str,
        agent_name: str,
        error_type: str
    ) -> None:
        """
        Record an error.
        
        Args:
            run_id: Run ID
            agent_name: Agent name
            error_type: Error type/category
        """
        try:
            with self.lock:
                # Ensure errors is a defaultdict
                if not isinstance(self.metrics.get("errors"), defaultdict):
                    from collections import defaultdict
                    self.metrics["errors"] = defaultdict(int)
                
                key = f"{agent_name}_{error_type}"
                self.metrics["errors"][key] += 1
        except Exception:
            # Silently fail if metrics recording fails
            pass
    
    def record_run_completion(
        self,
        run_id: str,
        success: bool
    ) -> None:
        """
        Record run completion.
        
        Args:
            run_id: Run ID
            success: Whether run succeeded
        """
        with self.lock:
            self.metrics["total_runs"] += 1
            if success:
                self.metrics["successful_runs"] += 1
            else:
                self.metrics["failed_runs"] += 1
    
    def get_node_stats(self, agent_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for nodes.
        
        Args:
            agent_name: Optional agent name filter
            
        Returns:
            Statistics dictionary
        """
        with self.lock:
            timings = self.metrics["node_timings"]
            
            if agent_name:
                timings = [t for t in timings if t["agent_name"] == agent_name]
            
            if not timings:
                return {
                    "count": 0,
                    "avg_duration_ms": 0,
                    "min_duration_ms": 0,
                    "max_duration_ms": 0
                }
            
            durations = [t["duration_ms"] for t in timings]
            
            return {
                "count": len(timings),
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "agent_name": agent_name
            }
    
    def get_tool_stats(self) -> Dict[str, int]:
        """
        Get tool call statistics.
        
        Returns:
            Dictionary mapping tool names to call counts
        """
        with self.lock:
            return dict(self.metrics["tool_calls"])
    
    def get_error_stats(self) -> Dict[str, int]:
        """
        Get error statistics.
        
        Returns:
            Dictionary mapping error types to counts
        """
        with self.lock:
            return dict(self.metrics["errors"])
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """
        Get overall statistics.
        
        Returns:
            Overall statistics dictionary
        """
        with self.lock:
            total_runs = self.metrics["total_runs"]
            success_rate = (
                self.metrics["successful_runs"] / total_runs
                if total_runs > 0 else 0
            )
            
            return {
                "total_runs": total_runs,
                "successful_runs": self.metrics["successful_runs"],
                "failed_runs": self.metrics["failed_runs"],
                "success_rate": success_rate,
                "error_rate": (
                    self.metrics["failed_runs"] / total_runs
                    if total_runs > 0 else 0
                )
            }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary.
        
        Returns:
            Metrics summary dictionary
        """
        return {
            "overall": self.get_overall_stats(),
            "node_stats": self.get_node_stats(),
            "tool_stats": self.get_tool_stats(),
            "error_stats": self.get_error_stats(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def clear_old_metrics(self, days: int = 7) -> None:
        """
        Clear metrics older than specified days.
        
        Args:
            days: Number of days to keep
        """
        with self.lock:
            cutoff = datetime.utcnow() - timedelta(days=days)
            cutoff_iso = cutoff.isoformat()
            
            self.metrics["node_timings"] = [
                t for t in self.metrics["node_timings"]
                if t["timestamp"] > cutoff_iso
            ]


# Global metrics collector instance
metrics_collector = MetricsCollector()

