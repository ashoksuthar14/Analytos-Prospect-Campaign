"""
Unit tests for DatabaseService.
"""

import pytest
import os
import tempfile
from database.db_service import DatabaseService


@pytest.fixture
def temp_db():
    """Create a temporary database."""
    test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    test_db.close()
    service = DatabaseService(db_path=test_db.name)
    yield service
    os.unlink(test_db.name)


def test_create_run(temp_db):
    """Test creating a run."""
    run_id = temp_db.create_run(
        workflow_name="test_workflow",
        config_snapshot={"test": "config"}
    )
    
    assert run_id is not None
    assert isinstance(run_id, str)
    
    run = temp_db.get_run(run_id)
    assert run is not None
    assert run["workflow_name"] == "test_workflow"


def test_update_run_status(temp_db):
    """Test updating run status."""
    run_id = temp_db.create_run(
        workflow_name="test_workflow",
        config_snapshot={}
    )
    
    temp_db.update_run_status(run_id, "running")
    run = temp_db.get_run(run_id)
    assert run["status"] == "running"
    
    temp_db.update_run_status(run_id, "completed", metrics={"total_leads": 10})
    run = temp_db.get_run(run_id)
    assert run["status"] == "completed"


def test_create_lead(temp_db):
    """Test creating a lead."""
    run_id = temp_db.create_run(
        workflow_name="test_workflow",
        config_snapshot={}
    )
    
    lead_id = temp_db.create_lead(
        run_id=run_id,
        company_name="Test Company",
        contact_name="Test Contact",
        contact_email="test@example.com",
        score=85.5,
        enriched_data={"industry": "SaaS"}
    )
    
    assert lead_id is not None
    lead = temp_db.get_lead(lead_id)
    assert lead["company_name"] == "Test Company"
    assert lead["score"] == 85.5


def test_get_runs(temp_db):
    """Test getting runs."""
    run_id1 = temp_db.create_run("workflow1", {})
    run_id2 = temp_db.create_run("workflow2", {})
    
    runs = temp_db.get_runs(limit=10)
    assert len(runs) >= 2
    
    # Check that both runs are in the list
    run_ids = [r["run_id"] for r in runs]
    assert run_id1 in run_ids
    assert run_id2 in run_ids


def test_get_run_leads(temp_db):
    """Test getting leads for a run."""
    run_id = temp_db.create_run("test_workflow", {})
    
    lead_id1 = temp_db.create_lead(run_id, "Company1", "Contact1", "email1@test.com", 80)
    lead_id2 = temp_db.create_lead(run_id, "Company2", "Contact2", "email2@test.com", 90)
    
    leads = temp_db.get_run_leads(run_id, limit=10)
    assert len(leads) == 2
    
    company_names = [l["company_name"] for l in leads]
    assert "Company1" in company_names
    assert "Company2" in company_names

