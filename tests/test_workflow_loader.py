"""
Unit tests for WorkflowLoader.
"""

import pytest
import json
import os
import tempfile
from configs.workflow_loader import WorkflowLoader


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    import shutil
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_workflow(temp_config_dir):
    """Create a sample workflow.json file."""
    workflow = {
        "workflow_name": "test_workflow",
        "agents": {
            "prospect_search": {
                "depends_on": [],
                "inputs": {"icp": {}}
            },
            "scoring": {
                "depends_on": ["prospect_search"],
                "inputs": {}
            }
        }
    }
    
    workflow_path = os.path.join(temp_config_dir, "workflow.json")
    with open(workflow_path, 'w') as f:
        json.dump(workflow, f)
    
    return workflow, temp_config_dir


def test_load_workflow(sample_workflow):
    """Test loading workflow configuration."""
    workflow, config_dir = sample_workflow
    loader = WorkflowLoader(config_dir=config_dir)
    
    loaded_workflow = loader.get_workflow()
    assert loaded_workflow["workflow_name"] == "test_workflow"


def test_get_agent_config(sample_workflow):
    """Test getting agent configuration."""
    workflow, config_dir = sample_workflow
    loader = WorkflowLoader(config_dir=config_dir)
    
    agent_config = loader.get_agent_config("prospect_search")
    assert agent_config is not None
    assert "depends_on" in agent_config


def test_get_agent_order(sample_workflow):
    """Test getting agent execution order."""
    workflow, config_dir = sample_workflow
    loader = WorkflowLoader(config_dir=config_dir)
    
    order = loader.get_agent_order()
    assert "prospect_search" in order
    assert "scoring" in order
    # prospect_search should come before scoring
    assert order.index("prospect_search") < order.index("scoring")

