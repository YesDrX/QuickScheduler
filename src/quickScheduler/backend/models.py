"""Models for the quickScheduler backend.

This module defines the Pydantic models used for data validation and serialization
in the quickScheduler backend. It includes models for Tasks (which define what and
when to run) and Jobs (which represent specific instances of task execution).
"""

import hashlib
import json
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey, true
from sqlalchemy.orm import relationship, declarative_base, validates
from sqlalchemy.inspection import inspect
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, Callable

from pydantic import BaseModel, Field, field_validator
from quickScheduler.utils.triggers import TriggerType, TriggerConfig

Base = declarative_base()

def model_to_dict(model):
    """Convert SQLAlchemy model instance to dictionary."""
    return {c.key: getattr(model, c.key) for c in inspect(model).mapper.column_attrs}

class GlobalCallableFunctions:
    _all_functions = {}

    @classmethod
    def register_function(cls, func : Callable) -> str:
        """Register a global callable function."""
        assert callable(func), f"{func} is not a callable function"
        
        _name   = func.__name__
        _module = getattr(func, '__module__', "")
        _file   = getattr(func, '__file__', "")
        key = f"{_file}:{_module}.{_name}"
        if key not in cls._all_functions:
            cls._all_functions[key] = func
        return key
    
    @classmethod
    def get_function(cls, key : str) -> Callable:
        """Get a global callable function by its key."""
        return cls._all_functions.get(key, None)

class TaskModel(Base):
    """SQLAlchemy model for tasks table."""
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, index=True)
    hash_id = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    command = Column(String, nullable=True)
    callable_func = Column(String, nullable=True)
    working_directory = Column(String, nullable=True)
    schedule_type = Column(String)
    schedule_config = Column(JSON, nullable=True)
    environment = Column(JSON, nullable=True)
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Integer, default=60)  # seconds
    timeout = Column(Integer, default=300)  # seconds
    status = Column(String, default='active')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime,
                       default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
    
    def calculate_hash_id(self):
        """Calculate a unique ID for the task."""
        unique_data = {
            'name': self.name,
            'command': self.command,
            'description': self.description,
            'schedule_type': self.schedule_type,
            'schedule_config': self.schedule_config,
            'environment': self.environment,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'timeout': self.timeout
        }
        data_str = json.dumps(unique_data, sort_keys=True)
        hash_obj = hashlib.sha256(data_str.encode())
        self.hash_id = hash_obj.hexdigest()
        return self

    jobs = relationship("JobModel", back_populates="task")

    @validates('schedule_type')
    def validate_schedule_type(self, key, schedule_type):
        """Validate schedule_type against allowed values."""
        try:
            return TriggerType(schedule_type.lower()).value
        except ValueError:
            raise ValueError(
                f"Invalid schedule_type: {schedule_type}. "
                f"Must be one of: {[t.value for t in TriggerType]}"
            )

    @validates('status')
    def validate_status(self, key, status):
        """Validate status against allowed values."""
        try:
            return TaskStatus(status).value
        except ValueError:
            raise ValueError(
                f"Invalid status: {status}. "
                f"Must be one of: {[t.value for t in TaskStatus]}"
            )
    
    @validates('callable_func')
    def validate_callable_func(self, key, value):
        if callable(value):
            # Register the callable and return its key
            return GlobalCallableFunctions.register_function(value)
        elif isinstance(value, str):
            # Optional: Ensure the key is registered
            if not GlobalCallableFunctions.get_function(value):
                raise ValueError(f"Callable '{value}' is not registered.")
            return value
        else:
            raise TypeError("callable_func must be a callable or a registered string key")

class JobModel(Base):
    """SQLAlchemy model for jobs table."""
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True, index=True)
    task_hash_id = Column(String, ForeignKey('tasks.hash_id'))
    trigger_time = Column(DateTime)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default='pending')
    exit_code = Column(Integer, nullable=True)
    log_file = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime,
                       default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))    
    task = relationship("TaskModel", back_populates="jobs")

class TaskStatus(str, Enum):
    """Enumeration of possible task statuses."""
    ACTIVE = "active"  # Task is active and can be scheduled
    PAUSED = "paused"  # Task is temporarily paused
    DISABLED = "disabled"  # Task is disabled and won't be scheduled
    PENDING = "pending"  # Task is created but not yet started

class JobStatus(str, Enum):
    """Enumeration of possible job execution statuses."""
    PENDING = "pending"  # Job is created but not yet started
    RUNNING = "running"  # Job is currently running
    COMPLETED = "completed"  # Job completed successfully
    FAILED = "failed"  # Job execution failed
    CANCELLED = "cancelled"  # Job was cancelled before completion

class TaskBase(BaseModel):
    """Base model for task data."""
    name: str = Field(..., description="Name of the task")
    description: Optional[str] = Field(None, description="Optional description of the task")
    command: Optional[str] = Field(None, description="Command to execute")
    callable_func: Optional[str] = Field(None, description="Python callable to execute")
    working_directory: Optional[str] = Field(None, description="Working directory for command execution")
    schedule_type: TriggerType = Field(..., description="Type of scheduling for this task")
    schedule_config: Optional[Dict[str, Any]] = Field(
        ...,
        description="Configuration for the schedule"
    )
    environment: Optional[Dict[str, str]] = Field(
        default=None,
        description="Environment variables for task execution"
    )
    max_retries: int = Field(0, description="Maximum number of retry attempts on failure")
    retry_delay: int = Field(0, description="Delay in seconds between retry attempts")
    timeout: Optional[int] = Field(None, description="Timeout in seconds for task execution")
    status: TaskStatus = Field(default=TaskStatus.ACTIVE)

class Task(TaskBase):
    """Complete task model with database fields."""
    id: int = Field(..., description="Unique identifier for the task")
    hash_id: str = Field(..., description="Unique hash identifier for the task")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

class TaskCreate(TaskBase):
    """Model for creating a new task."""
    pass

class TaskUpdate(BaseModel):
    """Model for updating an existing task."""
    name: Optional[str] = None
    description: Optional[str] = None
    command: Optional[str] = None
    working_directory: Optional[str] = None
    schedule_type: Optional[TriggerType] = None
    schedule_config: Optional[Dict[str, Any]] = None
    environment: Optional[Dict[str, str]] = None
    max_retries: Optional[int] = None
    retry_delay: Optional[int] = None
    timeout: Optional[int] = None
    status: Optional[TaskStatus] = None

class JobBase(BaseModel):
    """Base model for job data."""
    task_hash_id: str = Field(..., description="ID of the associated task")
    trigger_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="Time when the job was triggered"
    )
    start_time: Optional[datetime] = Field(
        None,
        description="Time when the job started execution"
    )
    end_time: Optional[datetime] = Field(
        None,
        description="Time when the job finished execution"
    )
    status: JobStatus = Field(default=JobStatus.PENDING)
    exit_code: Optional[int] = Field(None, description="Exit code of the command")
    log_file: Optional[str] = Field(None, description="Path to the job's log file")
    error_message: Optional[str] = Field(None, description="Error message if job failed")
    retry_count: int = Field(0, description="Number of retry attempts made")

class Job(JobBase):
    """Complete job model with database fields."""
    id: int = Field(..., description="Unique identifier for the job")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

class JobCreate(JobBase):
    """Model for creating a new job."""
    pass

class JobUpdate(BaseModel):
    """Model for updating an existing job."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[JobStatus] = None
    exit_code: Optional[int] = None
    log_file: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None

class JobTriggerResponse(BaseModel):
    """Response model for job triggering."""
    job_id: int
    message: str

class EmailConfig(BaseModel):
    """Model for email configuration."""
    smtp_server: str
    smtp_port: int
    smtp_usetls: bool
    smtp_username: str
    smtp_password: str
    email_recipients: list[str]

def createTaskModel(callable_func : Callable = None, **kwargs):
    if callable_func is not None:
        return TaskModel(callable_func=callable_func, **kwargs).calculate_hash_id()
    else:
        return TaskModel(**kwargs).calculate_hash_id()