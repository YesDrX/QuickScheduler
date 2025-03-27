"""Database module for quickScheduler backend.

This module provides SQLAlchemy models and database operations for the quickScheduler
backend. It includes models for Tasks and Jobs, along with database initialization
and session management functionality.
"""
from typing import Optional, List
from sqlalchemy import create_engine, inspect, text, desc, asc
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, TaskModel, JobModel

class Database:
    """Database management class for quickScheduler.

    This class provides methods for database initialization and session management.
    It also includes utility methods for common database operations.
    """

    # Required tables for the application
    REQUIRED_TABLES = {'tasks', 'jobs'}

    def __init__(self, db_url: str = 'sqlite:///quickscheduler.db'):
        """Initialize the database connection.

        Args:
            db_url: SQLAlchemy database URL. Defaults to SQLite database in current directory.
        """
        connect_args = {}
        if 'sqlite' in db_url:
            connect_args['check_same_thread'] = False

        self.engine = create_engine(
            db_url,
            connect_args=connect_args,
            poolclass=NullPool,
            echo=False,  # Enable SQL logging for debugging
            future=True  # Enable SQLAlchemy 2.0 behavior
        )

        # Verify and create required tables
        self._verify_tables()

        # Configure modern SQLAlchemy 2.x session
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            expire_on_commit=False,
            future=True  # Enable SQLAlchemy 2.0 behavior
        )

    def __enter__(self):
        self.session = self.SessionLocal()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def _verify_tables(self) -> None:
        """Verify that all required tables exist and create any missing ones."""
        with self.engine.begin() as conn:
            inspector = inspect(conn)
            existing_tables = set(inspector.get_table_names())
            missing_tables = self.REQUIRED_TABLES - existing_tables
            
            if missing_tables:
                print(f"Creating missing tables: {missing_tables}")
                Base.metadata.create_all(conn)
                
                # Verify tables were created
                inspector = inspect(conn)
                created_tables = set(inspector.get_table_names())
                if not self.REQUIRED_TABLES.issubset(created_tables):
                    raise RuntimeError(
                        f"Failed to create required tables. Missing: {self.REQUIRED_TABLES - created_tables}"
                    )
                print(f"Database tables verified: {self.REQUIRED_TABLES}")

    def create_database(self) -> None:
        """Create all database tables."""
        self._verify_tables()

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            A new SQLAlchemy Session instance.
        """
        session = self.SessionLocal()
        try:
            # Test connection and ensure session is valid
            session.execute(text('SELECT 1'))
            return session
        except Exception as e:
            session.close()
            raise RuntimeError(f"Failed to create database session: {str(e)}") from e

    def get_task_by_id(self, session: Session, task_hash_id: str) -> Optional[TaskModel]:
        """Get a task by its ID.

        Args:
            session: Database session
            task_hash_id: ID of the task to retrieve

        Returns:
            The task if found, None otherwise
        """
        return session.query(TaskModel).filter(TaskModel.hash_id == task_hash_id).first()

    def get_tasks(self, session: Session, skip: int = 0, limit: int = 100) -> List[TaskModel]:
        """Get a list of tasks with pagination.

        Args:
            session: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of tasks
        """
        return session.query(TaskModel).order_by(desc(TaskModel.updated_at), asc(TaskModel.name)).offset(skip).limit(limit).all()

    def get_job_by_id(self, session: Session, job_id: int) -> Optional[JobModel]:
        """Get a job by its ID.

        Args:
            session: Database session
            job_id: ID of the job to retrieve

        Returns:
            The job if found, None otherwise
        """
        return session.query(JobModel).filter(JobModel.id == job_id).first()

    def get_jobs(self, session: Session, skip: int = 0, limit: int = 100) -> List[JobModel]:
        """Get a list of jobs with pagination.

        Args:
            session: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of jobs
        """
        return session.query(JobModel).order_by(desc(JobModel.end_time)).offset(skip).limit(limit).all()

    def get_jobs_by_task_hash_id(self, session: Session, task_hash_id: str, skip: int = 0, limit: int = 100) -> List[JobModel]:
        """Get a list of jobs for a specific task.

        Args:
            session: Database session
            task_hash_id: ID of the task to get jobs for
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of jobs for the specified task
        """
        return session.query(JobModel).filter(JobModel.task_hash_id == task_hash_id).order_by(desc(JobModel.end_time)).offset(skip).limit(limit).all()

    def delete_job(self, session: Session, job_id: int) -> bool:
        """Delete a single job by its ID.

        Args:
            session: Database session
            job_id: ID of the job to delete

        Returns:
            True if job was deleted, False if not found
        """
        job = self.get_job_by_id(session, job_id)
        if job:
            session.delete(job)
            session.commit()
            return True
        return False

    def delete_all_jobs(self, session: Session) -> int:
        """Delete all jobs from the database.

        Args:
            session: Database session

        Returns:
            Number of jobs deleted
        """
        deleted_count = session.query(JobModel).delete()
        session.commit()
        return deleted_count

    def delete_jobs_by_task(self, session: Session, task_hash_id: str) -> int:
        """Delete all jobs for a specific task.

        Args:
            session: Database session
            task_hash_id: ID of the task whose jobs should be deleted

        Returns:
            Number of jobs deleted
        """
        deleted_count = session.query(JobModel).filter(JobModel.task_hash_id == task_hash_id).delete()
        session.commit()
        return deleted_count

    def delete_task(self, session: Session, task_hash_id: str) -> bool:
        """Delete a task and all its associated jobs.

        Args:
            session: Database session
            task_hash_id: ID of the task to delete

        Returns:
            True if task was deleted, False if not found
        """
        task = self.get_task_by_id(session, task_hash_id)
        if task:
            self.delete_jobs_by_task(session, task_hash_id)
            session.delete(task)
            session.commit()
            return True
        return False
        
    def count_tasks(self, session: Session) -> int:
        """Count all tasks in the database.

        Args:
            session: Database session

        Returns:
            Total number of tasks
        """
        return session.query(TaskModel).count()
        
    def count_jobs(self, session: Session) -> int:
        """Count all jobs in the database.

        Args:
            session: Database session

        Returns:
            Total number of jobs
        """
        return session.query(JobModel).count()