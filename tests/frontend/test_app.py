"""Test cases for the frontend application module.

This module contains test cases for the frontend web interface, covering:
- Route handlers for task listing and details
- Job history and log views
- Template rendering
- Error handling
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from quickScheduler.frontend.app import FrontEnd

@pytest.fixture
def app():
    return FrontEnd().app

@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_task_data():
    """Sample task data for testing."""
    return {
        "hash_id": "test123",
        "name": "Test Task",
        "command": "echo 'test'",
        "schedule_type": "INTERVAL",
        "schedule_config": {"interval_seconds": 60},
        "status": "ACTIVE",
        "working_directory": "/tmp",
        "environment": {"TEST": "true"},
        "timeout": 300,
        "max_retries": 3,
        "retry_delay": 60
    }


@pytest.fixture
def mock_job_data():
    """Sample job data for testing."""
    from datetime import datetime
    return {
        "job_id": "job123",
        "task_hash_id": "test123",
        "status": "COMPLETED",
        "start_time": datetime(2024, 1, 1, 0, 0, 0),
        "end_time": datetime(2024, 1, 1, 0, 1, 0),
        "exit_code": 0,
        "error": None
    }


def test_index(client):
    """Test index page route."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_list_tasks(client, mock_task_data):
    """Test tasks listing page."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [mock_task_data]
        mock_get.return_value = mock_response
        
        response = client.get("/tasks")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert mock_task_data["name"] in response.text


@pytest.mark.asyncio
async def test_view_task(client, mock_task_data):
    """Test task details page."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_task_data
        mock_get.return_value = mock_response
        
        response = client.get(f"/tasks/{mock_task_data['hash_id']}")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert mock_task_data["name"] in response.text


def test_view_task_not_found(client):
    """Test task details page with non-existent task."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value.status_code = 404
        
        response = client.get("/tasks/nonexistent")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_task_jobs(client, mock_task_data, mock_job_data):
    """Test task job history page."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_task_response = AsyncMock()
        mock_task_response.status_code = 200
        mock_task_response.json.return_value = mock_task_data

        mock_jobs_response = AsyncMock()
        mock_jobs_response.status_code = 200
        mock_jobs_response.json.return_value = [mock_job_data]

        mock_get.side_effect = lambda url, *args, **kwargs: (
            mock_task_response if "/tasks/" in url and "/jobs" not in url
            else mock_jobs_response
        )
        
        response = client.get(f"/tasks/{mock_task_data['hash_id']}/jobs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert mock_job_data["job_id"] in response.text


@pytest.mark.asyncio
async def test_job_details(client, mock_task_data, mock_job_data):
    """Test job details page."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_task_response = AsyncMock()
        mock_task_response.status_code = 200
        mock_task_response.json.return_value = mock_task_data

        mock_job_response = AsyncMock()
        mock_job_response.status_code = 200
        mock_job_response.json.return_value = mock_job_data

        mock_get.side_effect = lambda url, *args, **kwargs: (
            mock_task_response if "/tasks/" in url else mock_job_response
        )
        
        response = client.get(f"/tasks/{mock_task_data['hash_id']}/jobs/{mock_job_data['job_id']}")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert mock_job_data["status"] in response.text


@pytest.mark.asyncio
async def test_job_log(client, mock_task_data, mock_job_data):
    """Test job log page."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_task_response = AsyncMock()
        mock_task_response.status_code = 200
        mock_task_response.json.return_value = mock_task_data

        mock_job_response = AsyncMock()
        mock_job_response.status_code = 200
        mock_job_response.json.return_value = mock_job_data

        mock_log_response = AsyncMock()
        mock_log_response.status_code = 200
        mock_log_response.json.return_value = {"output": "Test log output"}

        def side_effect(url, *args, **kwargs):
            if "/tasks/" in url:
                return mock_task_response
            elif "/log" in url:
                return mock_log_response
            else:
                return mock_job_response

        mock_get.side_effect = side_effect
        
        response = client.get(f"/tasks/{mock_task_data['hash_id']}/jobs/{mock_job_data['job_id']}/log")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Test log output" in response.text