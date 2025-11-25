"""
Integration tests for the workflow system.
"""

import pytest
import os
import tempfile
import json
from configs.workflow_loader import WorkflowLoader
from database.db_service import DatabaseService
from utils.rate_limiter import RateLimiter
from utils.input_validator import InputValidator
from utils.metrics_collector import MetricsCollector


@pytest.fixture
def test_environment():
    """Set up test environment."""
    # Create temporary database
    test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    test_db.close()
    
    # Create temporary config directory
    config_dir = tempfile.mkdtemp()
    
    # Create minimal workflow.json
    workflow = {
        "workflow_name": "test_workflow",
        "agents": {
            "prospect_search": {
                "depends_on": [],
                "inputs": {"icp": {}},
                "tools": ["clay_api", "apollo_api"]
            }
        }
    }
    
    workflow_path = os.path.join(config_dir, "workflow.json")
    with open(workflow_path, 'w') as f:
        json.dump(workflow, f)
    
    # Initialize services
    db_service = DatabaseService(db_path=test_db.name)
    workflow_loader = WorkflowLoader(config_dir=config_dir)
    rate_limiter = RateLimiter(db_service=db_service)
    input_validator = InputValidator()
    metrics_collector = MetricsCollector()
    
    yield {
        "db_service": db_service,
        "workflow_loader": workflow_loader,
        "rate_limiter": rate_limiter,
        "input_validator": input_validator,
        "metrics_collector": metrics_collector,
        "db_path": test_db.name,
        "config_dir": config_dir
    }
    
    # Cleanup
    os.unlink(test_db.name)
    import shutil
    shutil.rmtree(config_dir)


def test_workflow_loading(test_environment):
    """Test workflow loading integration."""
    workflow_loader = test_environment["workflow_loader"]
    
    workflow = workflow_loader.get_workflow()
    assert workflow["workflow_name"] == "test_workflow"
    assert "prospect_search" in workflow["agents"]


def test_rate_limiting_integration(test_environment):
    """Test rate limiting integration."""
    rate_limiter = test_environment["rate_limiter"]
    db_service = test_environment["db_service"]
    
    # Create a run with leads
    run_id = db_service.create_run("test_workflow", {})
    db_service.update_run_status(run_id, "completed", metrics={"total_leads": 50})
    
    # Check limits
    allowed, error, info = rate_limiter.check_all_limits(100)
    assert allowed is False or error is not None  # Should fail due to run limit or daily limit


def test_metrics_collection_integration(test_environment):
    """Test metrics collection integration."""
    metrics_collector = test_environment["metrics_collector"]
    
    # Simulate a run
    run_id = "test_run_123"
    metrics_collector.start_run(run_id)
    
    start_time = metrics_collector.record_node_start("test_agent")
    metrics_collector.record_tool_call("test_agent", "test_tool")
    metrics_collector.record_node_end("test_agent", start_time, success=True)
    
    summary = metrics_collector.end_run(run_id, success=True)
    
    assert summary["run_id"] == run_id
    assert summary["nodes_completed"] == 1
    assert summary["tool_calls"] == 1


def test_input_validation_integration(test_environment):
    """Test input validation integration."""
    input_validator = test_environment["input_validator"]
    
    # Test workflow name validation
    valid, error = input_validator.validate_workflow_name("test_workflow_v1")
    assert valid is True
    
    # Test run ID validation
    valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
    valid, error = input_validator.validate_run_id(valid_uuid)
    assert valid is True
    
    # Test pagination validation
    valid, error = input_validator.validate_pagination(limit=50, offset=0)
    assert valid is True

