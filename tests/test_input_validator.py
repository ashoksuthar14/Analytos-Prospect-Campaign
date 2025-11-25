"""
Unit tests for InputValidator.
"""

import pytest
from utils.input_validator import InputValidator


@pytest.fixture
def validator():
    """Create an input validator instance."""
    return InputValidator()


def test_validate_workflow_name_valid(validator):
    """Test validation of valid workflow names."""
    valid, error = validator.validate_workflow_name("prospect_to_lead_v1")
    assert valid is True
    assert error is None


def test_validate_workflow_name_empty(validator):
    """Test validation of empty workflow name."""
    valid, error = validator.validate_workflow_name("")
    assert valid is False
    assert "non-empty" in error


def test_validate_workflow_name_too_long(validator):
    """Test validation of workflow name that's too long."""
    long_name = "a" * 101
    valid, error = validator.validate_workflow_name(long_name)
    assert valid is False
    assert "100 characters" in error


def test_validate_workflow_name_invalid_chars(validator):
    """Test validation of workflow name with invalid characters."""
    valid, error = validator.validate_workflow_name("test'; DROP TABLE")
    assert valid is False
    assert "invalid characters" in error


def test_validate_run_id_valid(validator):
    """Test validation of valid run ID."""
    valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
    valid, error = validator.validate_run_id(valid_uuid)
    assert valid is True
    assert error is None


def test_validate_run_id_invalid(validator):
    """Test validation of invalid run ID."""
    valid, error = validator.validate_run_id("not-a-uuid")
    assert valid is False
    assert "Invalid run ID" in error


def test_validate_icp_valid(validator):
    """Test validation of valid ICP."""
    icp = {
        "revenue_range": {"min": 1000000, "max": 5000000},
        "employee_count": {"min": 10, "max": 100}
    }
    valid, error = validator.validate_icp(icp)
    assert valid is True
    assert error is None


def test_validate_icp_invalid_revenue(validator):
    """Test validation of ICP with invalid revenue range."""
    icp = {
        "revenue_range": {"min": 5000000, "max": 1000000}  # min > max
    }
    valid, error = validator.validate_icp(icp)
    assert valid is False
    assert "Revenue min" in error


def test_sanitize_string(validator):
    """Test string sanitization."""
    dirty = "<script>alert('xss')</script>"
    clean = validator.sanitize_string(dirty)
    assert "<" not in clean
    assert ">" not in clean


def test_sanitize_string_max_length(validator):
    """Test string sanitization with max length."""
    long_string = "a" * 2000
    sanitized = validator.sanitize_string(long_string, max_length=1000)
    assert len(sanitized) == 1000


def test_validate_pagination_valid(validator):
    """Test validation of valid pagination parameters."""
    valid, error = validator.validate_pagination(limit=50, offset=0)
    assert valid is True
    assert error is None


def test_validate_pagination_invalid_limit(validator):
    """Test validation of invalid limit."""
    valid, error = validator.validate_pagination(limit=0, offset=0)
    assert valid is False
    assert "Limit" in error


def test_validate_pagination_invalid_offset(validator):
    """Test validation of invalid offset."""
    valid, error = validator.validate_pagination(limit=50, offset=-1)
    assert valid is False
    assert "Offset" in error


def test_prevent_sql_injection(validator):
    """Test SQL injection prevention."""
    safe = "SELECT * FROM users WHERE id = 1"
    assert validator.prevent_sql_injection(safe) is True
    
    dangerous = "'; DROP TABLE users; --"
    assert validator.prevent_sql_injection(dangerous) is False


def test_validate_json_structure(validator):
    """Test JSON structure validation."""
    data = {"field1": "value1", "field2": "value2"}
    required = ["field1", "field2"]
    valid, error = validator.validate_json_structure(data, required)
    assert valid is True
    assert error is None
    
    missing = {"field1": "value1"}
    valid, error = validator.validate_json_structure(missing, required)
    assert valid is False
    assert "Missing required fields" in error

