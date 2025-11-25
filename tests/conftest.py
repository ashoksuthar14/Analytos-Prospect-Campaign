"""
Pytest configuration and shared fixtures.
"""

import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def test_env_vars(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")
    monkeypatch.setenv("CLAY_API_KEY", "test_clay_key")
    monkeypatch.setenv("APOLLO_API_KEY", "test_apollo_key")
    monkeypatch.setenv("DATABASE_PATH", ":memory:")  # Use in-memory DB for tests
    return monkeypatch

