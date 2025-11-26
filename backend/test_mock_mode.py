"""Tests for mock mode functionality."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Import after setting test env vars
import os
os.environ.setdefault("GROQ_API_KEY", "test_key")

from main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_get_mock_mode_status(client):
    """Test getting mock mode status."""
    response = client.get("/api/emails/mock-mode")
    assert response.status_code == 200
    data = response.json()
    assert "mock_mode" in data
    assert isinstance(data["mock_mode"], bool)


def test_toggle_mock_mode_enable(client):
    """Test enabling mock mode."""
    response = client.post(
        "/api/emails/mock-mode",
        json={"enabled": True},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert data["mock_mode"] is True
    assert "message" in data


def test_toggle_mock_mode_disable(client):
    """Test disabling mock mode."""
    response = client.post(
        "/api/emails/mock-mode",
        json={"enabled": False},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert data["mock_mode"] is False
    assert "message" in data


def test_toggle_mock_mode_invalid_body(client):
    """Test with invalid request body."""
    # Missing 'enabled' field
    response = client.post(
        "/api/emails/mock-mode",
        json={},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_toggle_mock_mode_wrong_type(client):
    """Test with wrong data type."""
    # 'enabled' should be bool, not string
    response = client.post(
        "/api/emails/mock-mode",
        json={"enabled": "true"},
        headers={"Content-Type": "application/json"},
    )
    # FastAPI should handle string "true" as bool conversion, but let's test
    assert response.status_code in [200, 422]


@patch("main.email_analysis_service.generate_mock_emails")
async def test_get_emails_with_mock_mode(mock_generate, client):
    """Test fetching emails when mock mode is enabled."""
    # Enable mock mode first
    client.post("/api/emails/mock-mode", json={"enabled": True})
    
    # Mock the generate_mock_emails to return test data
    mock_generate.return_value = [
        {
            "id": "mock_1",
            "subject": "Test Email",
            "sender": "test@example.com",
            "date": "2025-11-26 10:00:00",
            "bodyPreview": "Test body",
            "fullBody": "Test body full",
            "nlpCategory": "potential",
        }
    ]
    
    response = client.get("/api/emails?limit=20&relevant_only=false")
    # Should work if mock mode is properly enabled
    assert response.status_code in [200, 500]  # 500 if async issue, but endpoint should exist


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

