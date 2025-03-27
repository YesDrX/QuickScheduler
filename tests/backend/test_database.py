"""Test cases for the database module.

This module contains test cases for the Database class and database models, covering:
- Database initialization and connection
- Task and job model operations
- Session management
- Model validation and constraints
"""

import pytest
import pytz
from datetime import datetime, timedelta
import uuid
from sqlalchemy import text, inspect

from quickScheduler.backend import database, models
from quickScheduler.backend.models import Base
@pytest.fixture(scope="module")
def db(tmp_path_factory):
    """Create a test database instance."""
    # Use a temporary file-based SQLite database
    db_path = tmp_path_factory.mktemp("data") / "test.db"
    db_url = f"sqlite:///{db_path}"
    
    # Initialize database and create tables
    db = database.Database(db_url)
    with db.get_session() as session:
        # Verify tables exist
        inspector = inspect(session.connection())
        assert "tasks" in inspector.get_table_names()
        assert "jobs" in inspector.get_table_names()
    
    yield db
    
    # Clean up database file
    db_path.unlink(missing_ok=True)
    # Clean up after all tests
    Base.metadata.drop_all(db.engine)


@pytest.fixture
def task_model():
    """Create a sample task model."""
    import uuid
    return database.TaskModel(
        name=f"Test Task {uuid.uuid4()}",
        command="echo 'test'",
        schedule_type=models.TriggerType.INTERVAL,
        schedule_config={"interval": 60, "start_time" : "00:00", "end_time":"23:55"},
        status=models.TaskStatus.ACTIVE,
        working_directory="/tmp",
        environment={"TEST": "true"},
        timeout=300,
        max_retries=3,
        retry_delay=60
    )


def test_database_initialization(db):
    """Test database initialization and connection."""
    assert db is not None
    with db.get_session() as session:
        assert session is not None


def test_create_task(db, task_model):
    """Test creating a task in the database."""
    with db.get_session() as session:
        session.add(task_model.calculate_hash_id())
        session.commit()
        session.refresh(task_model.calculate_hash_id())
        
        assert task_model.id is not None
        assert task_model.created_at is not None
        assert task_model.updated_at is not None


def test_get_task_by_id(db, task_model):
    """Test retrieving a task by ID."""
    with db.get_session() as session:
        session.add(task_model.calculate_hash_id())
        session.commit()
        session.refresh(task_model.calculate_hash_id())
        
        retrieved_task = db.get_task_by_id(session, task_model.hash_id)
        assert retrieved_task is not None
        assert retrieved_task.hash_id == task_model.hash_id
        assert retrieved_task.name == task_model.name


def test_update_task(db, task_model):
    """Test updating a task."""
    with db.get_session() as session:
        session.add(task_model.calculate_hash_id())
        session.commit()
        session.refresh(task_model.calculate_hash_id())
        
        task_id = task_model.id
        original_updated_at = task_model.updated_at
        
        # Update task
        task_model.name = "Updated Task"
        task_model.command = "echo 'updated'"
        session.commit()
        session.refresh(task_model.calculate_hash_id())
        
        assert task_model.id == task_id
        assert task_model.name == "Updated Task"
        assert task_model.command == "echo 'updated'"
        assert task_model.updated_at > original_updated_at


def test_delete_task(db, task_model):
    """Test deleting a task and its associated jobs."""
    with db.get_session() as session:
        # Create test task with jobs
        session.add(task_model)
        session.commit()
        
        # Create associated jobs
        job1 = database.JobModel(
            task_hash_id=task_model.hash_id,
            start_time=datetime.now(pytz.UTC),
            end_time=datetime.now(pytz.UTC),
            status=models.JobStatus.COMPLETED
        )
        job2 = database.JobModel(
            task_hash_id=task_model.hash_id,
            start_time=datetime.now(pytz.UTC),
            end_time=datetime.now(pytz.UTC),
            status=models.JobStatus.FAILED
        )
        session.add_all([job1, job2])
        session.commit()

        # Delete the task
        result = db.delete_task(session, task_model.hash_id)
        assert result is True

        # Verify task and jobs are removed
        assert db.get_task_by_id(session, task_model.hash_id) is None
        assert db.count_jobs(session) == 0


def test_delete_nonexistent_task(db):
    """Test deleting a task that doesn't exist."""
    with db.get_session() as session:
        non_existent_id = str(uuid.uuid4())
        result = db.delete_task(session, non_existent_id)
        assert result is False


def test_task_deletion_maintains_integrity(db, task_model):
    """Test deleting one task doesn't affect others."""
    with db.get_session() as session:
        # Create two tasks
        task1 = task_model
        task2 = database.TaskModel(
            name="Other Task",
            command="echo 'other'",
            schedule_type=models.TriggerType.INTERVAL,
            schedule_config={"interval_seconds": 300}
        )
        session.add_all([task1, task2])
        session.commit()

        initial_count = db.count_tasks(session)
        
        # Delete one task
        db.delete_task(session, task1.hash_id)
        
        # Verify counts and remaining task
        assert db.count_tasks(session) == initial_count - 1
        assert db.get_task_by_id(session, task2.hash_id) is not None


def test_create_job(db, task_model):
    """Test creating a job for a task."""
    with db.get_session() as session:
        session.add(task_model.calculate_hash_id())
        session.commit()
        session.refresh(task_model.calculate_hash_id())
        
        job = database.JobModel(
            task_hash_id=task_model.hash_id,
            trigger_time=datetime.now(pytz.UTC),
            status=models.JobStatus.PENDING
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        
        assert job.id is not None
        assert job.task_hash_id == task_model.hash_id
        assert job.status == models.JobStatus.PENDING
        assert job.retry_count == 0


def test_job_lifecycle(db, task_model):
    """Test job status transitions."""
    with db.get_session() as session:
        session.add(task_model.calculate_hash_id())
        session.commit()
        
        job = database.JobModel(
            task_hash_id=task_model.hash_id,
            trigger_time=datetime.now(pytz.UTC),
            status=models.JobStatus.PENDING
        )
        session.add(job)
        session.commit()
        
        # Test status transitions
        job.status = models.JobStatus.RUNNING
        job.start_time = datetime.now(pytz.UTC)
        session.commit()
        
        job.status = models.JobStatus.COMPLETED
        job.end_time = datetime.now(pytz.UTC)
        job.exit_code = 0
        session.commit()
        
        assert job.start_time is not None
        assert job.end_time is not None
        assert job.end_time > job.start_time


def test_task_jobs_relationship(db, task_model):
    """Test relationship between task and its jobs."""
    with db.get_session() as session:
        session.add(task_model.calculate_hash_id())
        session.commit()
        
        # Create multiple jobs for the task
        jobs = [
            database.JobModel(
                task_hash_id=task_model.hash_id,
                trigger_time=datetime.now(pytz.UTC) + timedelta(minutes=i),
                status=models.JobStatus.PENDING
            )
            for i in range(3)
        ]
        session.add_all(jobs)
        session.commit()
        
        # Verify task-jobs relationship
        task = db.get_task_by_id(session, task_model.hash_id)
        assert len(task.jobs) == 3
        assert all(job.task_hash_id == task.hash_id for job in task.jobs)


def test_task_validation(db):
    """Test task model validation."""
    with db.get_session() as session:
        # Test invalid schedule type
        with pytest.raises(ValueError):
            task = database.TaskModel(
                name="Invalid Task",
                command="echo 'test'",
                schedule_type="invalid",
                schedule_config={"interval_seconds": 60},
                status=models.TaskStatus.ACTIVE
            )
            session.add(task)
            session.commit()
        
        # Test invalid status
        with pytest.raises(ValueError):
            task = database.TaskModel(
                name="Invalid Task",
                command="echo 'test'",
                schedule_type=models.TriggerType.INTERVAL,
                schedule_config={"interval_seconds": 60},
                status="invalid"
            )
            session.add(task)
            session.commit()
