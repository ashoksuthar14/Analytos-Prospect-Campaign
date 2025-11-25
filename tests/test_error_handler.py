"""
Unit tests for ErrorHandler.
"""

import pytest
from utils.error_handler import ErrorHandler, ErrorCategory
from requests.exceptions import HTTPError, ConnectionError, Timeout


def test_categorize_transient_error():
    """Test categorization of transient errors."""
    error = Timeout("Request timeout")
    category = ErrorHandler.categorize_error(error)
    assert category == ErrorCategory.TRANSIENT


def test_categorize_connection_error():
    """Test categorization of connection errors."""
    error = ConnectionError("Connection failed")
    category = ErrorHandler.categorize_error(error)
    assert category == ErrorCategory.TRANSIENT


def test_categorize_api_error():
    """Test categorization of API errors."""
    error = HTTPError("429 Too Many Requests")
    category = ErrorHandler.categorize_error(error)
    assert category == ErrorCategory.API_ERROR or category == ErrorCategory.TRANSIENT


def test_categorize_permanent_error():
    """Test categorization of permanent errors."""
    error = ValueError("Invalid input")
    category = ErrorHandler.categorize_error(error)
    assert category == ErrorCategory.PERMANENT


def test_extract_error_context():
    """Test error context extraction."""
    error = ValueError("Test error")
    context = ErrorHandler.extract_error_context(error)
    
    assert "type" in context
    assert "message" in context
    assert "category" in context
    assert "traceback" in context
    assert context["type"] == "ValueError"
    assert context["message"] == "Test error"


def test_should_retry_transient():
    """Test retry logic for transient errors."""
    error = Timeout("Request timeout")
    should_retry = ErrorHandler.should_retry(error, attempt=1, max_attempts=3)
    assert should_retry is True


def test_should_retry_permanent():
    """Test retry logic for permanent errors."""
    error = ValueError("Invalid input")
    should_retry = ErrorHandler.should_retry(error, attempt=1, max_attempts=3)
    assert should_retry is False


def test_should_retry_max_attempts():
    """Test retry logic when max attempts reached."""
    error = Timeout("Request timeout")
    should_retry = ErrorHandler.should_retry(error, attempt=3, max_attempts=3)
    assert should_retry is False


def test_handle_error():
    """Test error handling with context."""
    error = ValueError("Test error")
    context = {"agent_name": "test_agent", "run_id": "test_run"}
    
    result = ErrorHandler.handle_error(error, context)
    
    assert result["error"] is True
    assert result["category"] == ErrorCategory.PERMANENT.value
    assert "message" in result
    assert "context" in result

