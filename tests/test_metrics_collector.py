"""
Unit tests for MetricsCollector.
"""

import pytest
from utils.metrics_collector import MetricsCollector
import time


@pytest.fixture
def metrics_collector():
    """Create a metrics collector instance."""
    return MetricsCollector()


def test_start_run(metrics_collector):
    """Test starting a run."""
    run_id = "test_run_123"
    metrics_collector.start_run(run_id)
    
    assert metrics_collector.current_run_metrics["run_id"] == run_id
    assert "started_at" in metrics_collector.current_run_metrics


def test_record_node_start_end(metrics_collector):
    """Test recording node start and end."""
    metrics_collector.start_run("test_run")
    
    start_time = metrics_collector.record_node_start("test_agent")
    time.sleep(0.01)  # Small delay to ensure duration > 0
    metrics_collector.record_node_end("test_agent", start_time, success=True)
    
    assert "test_agent" in metrics_collector.current_run_metrics["node_timings"]
    assert len(metrics_collector.current_run_metrics["node_timings"]["test_agent"]) > 0


def test_record_node_end_with_error(metrics_collector):
    """Test recording node end with error."""
    metrics_collector.start_run("test_run")
    
    start_time = metrics_collector.record_node_start("test_agent")
    error = ValueError("Test error")
    metrics_collector.record_node_end("test_agent", start_time, success=False, error=error)
    
    assert len(metrics_collector.current_run_metrics["errors"]) > 0
    assert metrics_collector.metrics["error_counts"]["test_agent"] == 1


def test_record_tool_call(metrics_collector):
    """Test recording tool calls."""
    metrics_collector.start_run("test_run")
    metrics_collector.record_tool_call("test_agent", "test_tool")
    
    key = "test_agent.test_tool"
    assert metrics_collector.metrics["tool_call_counts"][key] == 1
    assert metrics_collector.current_run_metrics["tool_calls"][key] == 1


def test_end_run_success(metrics_collector):
    """Test ending a successful run."""
    metrics_collector.start_run("test_run")
    
    start_time = metrics_collector.record_node_start("test_agent")
    metrics_collector.record_node_end("test_agent", start_time, success=True)
    
    summary = metrics_collector.end_run("test_run", success=True)
    
    assert summary["run_id"] == "test_run"
    assert summary["success"] is True
    assert summary["nodes_completed"] == 1
    assert "node_metrics" in summary


def test_end_run_failure(metrics_collector):
    """Test ending a failed run."""
    metrics_collector.start_run("test_run")
    
    start_time = metrics_collector.record_node_start("test_agent")
    metrics_collector.record_node_end("test_agent", start_time, success=False)
    
    summary = metrics_collector.end_run("test_run", success=False)
    
    assert summary["success"] is False
    assert metrics_collector.metrics["total_errors"] == 1


def test_get_global_metrics(metrics_collector):
    """Test getting global metrics."""
    metrics_collector.start_run("test_run_1")
    start_time = metrics_collector.record_node_start("test_agent")
    metrics_collector.record_node_end("test_agent", start_time, success=True)
    metrics_collector.end_run("test_run_1", success=True)
    
    global_metrics = metrics_collector.get_global_metrics()
    
    assert global_metrics["total_runs"] == 1
    assert "test_agent" in global_metrics["node_metrics"]
    assert "tool_call_counts" in global_metrics

