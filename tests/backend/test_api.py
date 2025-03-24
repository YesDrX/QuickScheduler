"""Test cases for the API module.

This module contains test cases for the API endpoints, covering:
- Task CRUD operations
- Job status and history
- Manual task triggering
- Request validation and error handling
"""

import pytest
from typing import Callable, Generator
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from quickScheduler.backend import api, database, models


@pytest.fixture
def db():
    """Create a test database instance."""
    db = database.Database("sqlite:///:memory:")
    db.create_database()
    return db


@pytest.fixture
def session_factory(db) -> Callable[[], Generator[Session, None, None]]:
    """Create a session factory with transaction isolation."""
    def get_session() -> Generator[Session, None, None]:
        session = db.get_session()
        session.begin()
        try:
            yield session
        except:
            session.rollback()
            raise
        finally:
            session.close()
    
    return get_session

@pytest.fixture
def app(session_factory):
    """Create a test FastAPI application."""
    def get_db() -> Generator[Session, None, None]:
        return session_factory()
    api_instance = api.API()
    api_instance.app.dependency_overrides[get_db] = session_factory
    return api_instance.app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def task_data():
    """Sample task data for testing."""
    return {
        "name": "Test Task",
        "command": "echo 'test'",
        "schedule_type": models.TaskScheduleType.INTERVAL,
        "schedule_config": {"interval_seconds": 60},
        "status": models.TaskStatus.ACTIVE,
        "working_directory": "/tmp",
        "environment": {"TEST": "true"},
        "timeout": 300,
        "max_retries": 3,
        "retry_delay": 60
    }


def test_create_task(client, task_data):
    """Test task creation endpoint."""
    response = client.post("/tasks", json=task_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == task_data["name"]
    assert data["command"] == task_data["command"]
    assert "id" in data


def test_get_task(client, task_data):
    """Test getting a single task."""
    # Create task first
    create_response = client.post("/tasks", json=task_data)
    task_hash_id = create_response.json()["hash_id"]

    # Get task
    response = client.get(f"/tasks/{task_hash_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["hash_id"] == task_hash_id
    assert data["name"] == task_data["name"]


def test_get_task_not_found(client):
    """Test getting a non-existent task."""
    response = client.get("/tasks/999")
    assert response.status_code == 404


def test_list_tasks(client, task_data):
    """Test listing all tasks."""
    # Get initial task count
    initial_response = client.get("/tasks")
    initial_tasks = initial_response.json()
    initial_count = len(initial_tasks)
    
    # Create multiple tasks
    for i in range(3):
        task_data["name"] = f"Task {i}"
        client.post("/tasks", json=task_data)
    
    # Get updated task list
    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    
    # Verify task count increased by exactly 3
    assert len(data) == initial_count + 3
    assert all(task["name"].startswith("Task ") for task in data[initial_count:])


def test_update_task(client, task_data):
    """Test updating a task."""
    # Create task
    create_response = client.post("/tasks", json=task_data)
    task_hash_id = create_response.json()["hash_id"]
    
    # Update task
    update_data = task_data.copy()
    update_data["name"] = "Updated Task"
    response = client.put(f"/tasks/{task_hash_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Task"


def test_delete_task(client, task_data):
    """Test deleting a task."""
    # Create task
    create_response = client.post("/tasks", json=task_data)
    task_hash_id = create_response.json()["hash_id"]
    
    # Delete task
    response = client.delete(f"/tasks/{task_hash_id}")
    assert response.status_code == 200
    
    # Verify deletion
    get_response = client.get(f"/tasks/{task_hash_id}")
    assert get_response.status_code == 404


def test_trigger_task(client, task_data):
    """Test manually triggering a task."""
    # Create task
    create_response = client.post("/tasks", json=task_data)
    task_hash_id = create_response.json()["hash_id"]
    
    # Trigger task
    response = client.post(f"/tasks/{task_hash_id}/trigger")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data


def test_get_task_jobs(client, task_data):
    """Test getting job history for a task."""
    # Create task
    create_response = client.post("/tasks", json=task_data, timeout=3)
    task_hash_id = create_response.json()["hash_id"]
    response = client.get(f"/jobs?task_hash_id={task_hash_id}")
    assert response.status_code == 200
    data = response.json()
    existing_jobs = len(data)
    
    # Trigger task multiple times
    for _ in range(3):
        client.post(f"/tasks/{task_hash_id}/trigger", timeout=3)
    
    # Get job history
    response = client.get(f"/jobs?task_hash_id={task_hash_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3 + existing_jobs
    assert all(job["task_hash_id"] == task_hash_id for job in data)


def test_get_job_status(client, task_data):
    """Test getting job status."""
    # Create and trigger task
    create_response = client.post("/tasks", json=task_data)
    task_hash_id = create_response.json()["hash_id"]
    trigger_response = client.post(f"/tasks/{task_hash_id}/trigger")
    job_id = trigger_response.json()["job_id"]
    
    # Get job status
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["task_hash_id"] == task_hash_id
    assert "status" in data


def test_validation_errors(client):
    """Test request validation."""
    # Test invalid schedule type
    invalid_task = {
        "name": "Invalid Task",
        "command": "echo 'test'",
        "schedule_type": "invalid",
        "schedule_config": {"interval_seconds": 60},
        "status": models.TaskStatus.ACTIVE
    }
    response = client.post("/tasks", json=invalid_task)
    assert response.status_code == 422
    
    # Test missing required field
    invalid_task = {
        "name": "Invalid Task",
        "schedule_type": models.TaskScheduleType.INTERVAL,
        "schedule_config": {"interval_seconds": 60}
    }
    response = client.post("/tasks", json=invalid_task)
    assert response.status_code == 422