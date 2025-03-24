"""Test cases for the scheduler module.

This module contains test cases for the TaskScheduler class, covering:
- Task scheduling and trigger creation
- Job execution and status management
- Error handling and retry mechanisms
- Manual task triggering
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from quickScheduler.backend import database, models, scheduler
from quickScheduler.utils.triggers import Trigger, OnStartTrigger
from quickScheduler.utils.subprocess_runner import SubProcessRunner


@pytest.fixture
def db():
    """Create a test database instance."""
    return database.Database(":memory:")


@pytest.fixture
def task_scheduler(db):
    """Create a TaskScheduler instance with test database."""
    return scheduler.TaskScheduler(db)


@pytest.fixture
def active_task(db):
    """Create a test task in the database."""
    with db.get_session() as session:
        task = database.TaskModel(
            name="Test Task",
            command="echo 'test'",
            schedule_type=models.TaskScheduleType.CRON,
            schedule_config={"cron_expression": "*/1 * * * *"},
            status=models.TaskStatus.ACTIVE
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


@pytest.mark.asyncio
async def test_schedule_task(task_scheduler, active_task):
    """Test scheduling a task creates appropriate trigger."""
    await task_scheduler.schedule_task(active_task)
    
    assert active_task.id in task_scheduler.triggers
    trigger = task_scheduler.triggers[active_task.id]
    assert isinstance(trigger, Trigger)
    assert trigger.cron == "*/1 * * * *"


@pytest.mark.asyncio
async def test_execute_task_success(task_scheduler, active_task):
    """Test successful task execution."""
    with patch.object(SubProcessRunner, 'run') as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ''
        
        await task_scheduler.execute_task(active_task.id)
        
        with task_scheduler.db.get_session() as session:
            jobs = session.query(database.JobModel).all()
            assert len(jobs) == 1
            job = jobs[0]
            assert job.status == models.JobStatus.COMPLETED
            assert job.exit_code == 0
            assert job.error_message is None


@pytest.mark.asyncio
async def test_execute_task_failure(task_scheduler, active_task):
    """Test task execution failure."""
    with patch.object(SubProcessRunner, 'run') as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = 'Command failed'
        
        await task_scheduler.execute_task(active_task.id)
        
        with task_scheduler.db.get_session() as session:
            jobs = session.query(database.JobModel).all()
            assert len(jobs) == 1
            job = jobs[0]
            assert job.status == models.JobStatus.FAILED
            assert job.exit_code == 1
            assert job.error_message == 'Command failed'


@pytest.mark.asyncio
async def test_execute_task_with_retry(task_scheduler, active_task):
    """Test task execution with retry on failure."""
    active_task.max_retries = 1
    active_task.retry_delay = 1
    
    with patch.object(SubProcessRunner, 'run') as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = 'Command failed'
        
        await task_scheduler.execute_task(active_task.id)
        
        with task_scheduler.db.get_session() as session:
            jobs = session.query(database.JobModel).all()
            assert len(jobs) == 2  # Original attempt + 1 retry
            assert all(job.status == models.JobStatus.FAILED for job in jobs)
            assert jobs[0].retry_count == 1


@pytest.mark.asyncio
async def test_trigger_task_manually(task_scheduler, active_task):
    """Test manual task triggering."""
    job_id = await task_scheduler.trigger_task_manually(active_task.id)
    assert job_id is not None
    
    with task_scheduler.db.get_session() as session:
        job = session.query(database.JobModel).get(job_id)
        assert job is not None
        assert job.task_id == active_task.id
        assert job.status == models.JobStatus.PENDING


@pytest.mark.asyncio
async def test_start_stop(task_scheduler, active_task):
    """Test scheduler start and stop functionality."""
    # Start scheduler
    start_task = asyncio.create_task(task_scheduler.start())
    await asyncio.sleep(0.1)  # Allow time for startup
    assert task_scheduler.running
    assert active_task.id in task_scheduler.triggers
    
    # Stop scheduler
    await task_scheduler.stop()
    assert not task_scheduler.running
    assert not task_scheduler.triggers
    
    # Cancel start task
    start_task.cancel()
    try:
        await start_task
    except asyncio.CancelledError:
        pass