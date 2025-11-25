"""
Unit tests for RateLimiter.
"""

import pytest
from datetime import datetime, timedelta
from utils.rate_limiter import RateLimiter
from database.db_service import DatabaseService


@pytest.fixture
def db_service():
    """Create a test database service."""
    import os
    import tempfile
    test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    test_db.close()
    service = DatabaseService(db_path=test_db.name)
    yield service
    os.unlink(test_db.name)


@pytest.fixture
def rate_limiter(db_service):
    """Create a rate limiter instance."""
    return RateLimiter(
        db_service=db_service,
        max_leads_per_run=50,
        max_leads_per_day=200
    )


def test_check_run_limit_within_limit(rate_limiter):
    """Test run limit check when within limit."""
    allowed, error = rate_limiter.check_run_limit(30)
    assert allowed is True
    assert error is None


def test_check_run_limit_exceeds_limit(rate_limiter):
    """Test run limit check when exceeding limit."""
    allowed, error = rate_limiter.check_run_limit(100)
    assert allowed is False
    assert "exceeds limit" in error


def test_check_daily_limit_within_limit(rate_limiter, db_service):
    """Test daily limit check when within limit."""
    # Create a test run with some leads
    run_id = db_service.create_run(
        workflow_name="test",
        config_snapshot={}
    )
    db_service.update_run_status(
        run_id,
        "completed",
        metrics={"total_leads": 50}
    )
    
    allowed, error, usage = rate_limiter.check_daily_limit(100)
    assert allowed is True
    assert error is None
    assert usage == 50


def test_check_daily_limit_exceeds_limit(rate_limiter, db_service):
    """Test daily limit check when exceeding limit."""
    # Create test runs that exceed daily limit
    for i in range(5):
        run_id = db_service.create_run(
            workflow_name="test",
            config_snapshot={}
        )
        db_service.update_run_status(
            run_id,
            "completed",
            metrics={"total_leads": 50}
        )
    
    allowed, error, usage = rate_limiter.check_daily_limit(50)
    assert allowed is False
    assert "exceeds limit" in error or "Daily limit" in error


def test_check_all_limits(rate_limiter):
    """Test combined limit checks."""
    allowed, error, info = rate_limiter.check_all_limits(30)
    assert allowed is True
    assert error is None
    assert "leads_used_today" in info or info == {}

