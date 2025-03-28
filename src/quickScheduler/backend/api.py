"""API module for quickScheduler backend.

This module provides the FastAPI application that exposes REST endpoints for
task and job management. It includes endpoints for CRUD operations on tasks
and jobs, as well as endpoints for task scheduling and job control.
"""

import asyncio
import logging
import os
import pprint
import threading
import traceback
from copy import deepcopy
from datetime import datetime
from typing import Callable, List, Optional

import pytz
import yaml
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pathvalidate import sanitize_filename
from sqlalchemy import text

from quickScheduler.backend import database, models
from quickScheduler.utils.email_utils import send_email
from quickScheduler.utils.subprocess_runner import SubProcessRunner

def represent_unserializable(dumper, data):
    return dumper.represent_scalar('!unserializable', str(data))
yaml.add_multi_representer(object, represent_unserializable)

class API:
    def __init__(
            self,
            host: str = "0.0.0.0",
            port: int = 8000,
            working_directory: str = ".",
            email_config : Optional[models.EmailConfig] = None,
            send_alert_callable : Optional[Callable] = None,
            url_prefix : Optional[str] = None
        ):
        """
        Initialize the API server.
        Args:
            host (str): Host address for the server.
            port (int): Port number for the server.
            working_directory (str): Working directory for the server.
            email_config (Optional[models.EmailConfig]): Email configuration for sending alerts.
            send_alert_callable (Optional[Callable]): Callable function for sending alerts.
                Args for send_alert_callable should be:
                    msg  : str
                    task : models.TaskModel
                    job  : models.TaskModel
        """
        logging.info(f"initializing API server in {working_directory}")
        self.working_directory = os.path.abspath(os.path.expanduser(working_directory))
        self.host = host
        self.port = port
        self.email_config = email_config
        self.send_alert_callable = send_alert_callable
        self.thread = None
        self.log_dir = os.path.join(self.working_directory, "logs")
        self.url_prefix = url_prefix
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)

        # Create FastAPI application
        self.app = FastAPI(
            title="QuickScheduler API",
            description="REST API for task scheduling and job management",
            version="1.0.0"
        )

        # Initialize database
        self.db = database.Database(db_url=f"sqlite:///{self.working_directory}/quickscheduler.db")
        self.db.create_database()
        self.register_endpoints(app=self.app, db=self.db)

        # Monitor running jobs
        self.running_jobs = set()

    def register_endpoints(self, app: FastAPI, db: database.Database):
        @app.post("/tasks/", response_model=models.Task)
        async def create_task(task: models.TaskCreate):
            """Create a new task.

            Args:
                task: Task data
                db: Database instance

            Returns:
                Created task

            Raises:
                HTTPException: If task creation fails
            """
            session = db.get_session()
            db_task = database.TaskModel(**task.model_dump()).calculate_hash_id()
            task_hash_id = db_task.hash_id
            existing_task = db.get_task_by_id(session=db.get_session(), task_hash_id=str(task_hash_id))
            
            if existing_task is None:
                logging.info(f"creating task ({task.name}) with id {task_hash_id}")
                session.add(db_task)
                try:
                    session.commit()
                    session.refresh(db_task)
                    return db_task
                except Exception as e:
                    traceback.print_exc()
                    session.rollback()
                    raise HTTPException(status_code=400, detail=str(e))
                finally:
                    session.close()
            else:
                logging.info(f"task with id {task_hash_id} already exists.")
                return existing_task

        @app.get("/tasks/", response_model=List[models.Task])
        async def list_tasks(
            skip: int = Query(0, ge=0),
            limit: int = Query(100, ge=1)
        ):
            """List tasks with pagination.

            Args:
                skip: Number of records to skip
                limit: Maximum number of records to return

            Returns:
                List of tasks
            """
            session = db.get_session()
            try:
                rst = db.get_tasks(session, skip=skip, limit=limit)
                return rst
            finally:
                session.close()

        @app.get("/tasks/{task_hash_id}", response_model=models.Task)
        async def get_task(task_hash_id: str):
            """Get a task by ID.

            Args:
                task_hash_id: Task ID
                db: Database session

            Returns:
                Task data

            Raises:
                HTTPException: If task not found
            """
            task = db.get_task_by_id(session=db.get_session(), task_hash_id=task_hash_id)
            if task is None:
                raise HTTPException(status_code=404, detail="Task not found")
            return task

        @app.put("/tasks/{task_hash_id}", response_model=models.Task)
        async def update_task(
            task_hash_id: str,
            task_update: models.TaskUpdate
        ):
            """Update a task.

            Args:
                task_hash_id: Task ID
                task_update: Updated task data
                db: Database session

            Returns:
                Updated task

            Raises:
                HTTPException: If task not found or update fails
            """
            db_session = db.get_session()
            task = db.get_task_by_id(session=db_session, task_hash_id=task_hash_id)
            if task is None:
                raise HTTPException(status_code=404, detail="Task not found")

            update_data = task_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(task, field, value)

            try:
                db_session.commit()
                db_session.refresh(task)
                return task
            except Exception as e:
                db_session.rollback()
                raise HTTPException(status_code=400, detail=str(e))

        @app.delete("/tasks/{task_hash_id}")
        async def delete_task(task_hash_id: str):
            """Delete a task.

            Args:
                task_hash_id: Task ID
                db: Database session

            Returns:
                Success message

            Raises:
                HTTPException: If task not found or deletion fails
            """
            session = db.get_session()
            if db.delete_task(session, task_hash_id):
                return {"message": "Task deleted successfully"}
            else:
                raise HTTPException(status_code=404)

        @app.delete("/jobs/{job_id}")
        async def delete_job(job_id: int):
            """Delete a single job.

            Args:
                job_id: Job ID

            Returns:
                deletion message
            """
            session = db.get_session()
            if db.delete_job(session, job_id):
                return {"message": "Job deleted successfully"}
            else:
                raise HTTPException(status_code=404)

        @app.delete("/jobs/")
        async def delete_all_jobs():
            """Delete all jobs.

            Returns:
                Message

            Raises:
                HTTPException: If deletion fails
            """
            session = db.get_session()
            if db.delete_all_jobs(session):
                return {"message": "All jobs deleted successfully"}
            else:
                raise HTTPException(status_code=404)

        @app.delete("/tasks/{task_hash_id}/jobs")
        async def delete_task_jobs(task_hash_id: str):
            """Delete all jobs for a specific task.

            Args:
                task_hash_id: Task ID

            Returns:
                Message
            """
            session = db.get_session()
            if db.delete_jobs_by_task(session, task_hash_id):
                return {"message": "All jobs for task deleted successfully"}
            else:
                raise HTTPException(status_code=404)

        @app.post("/tasks/{task_hash_id}/trigger", response_model=models.JobTriggerResponse)
        async def trigger_task(
            task_hash_id: str,
            background_tasks: BackgroundTasks
        ):
            """Manually trigger a task.

            Args:
                task_hash_id: Task ID
                background_tasks: FastAPI background tasks
                db: Database session

            Returns:
                Created job response with job_id

            Raises:
                HTTPException: If task not found or triggering fails
            """
            logging.info(f"triggering task with Hash_ID {task_hash_id}")
            db_session = db.get_session()
            task = db.get_task_by_id(session=db_session, task_hash_id=task_hash_id)
            if task is None:
                logging.error(f"Task with Hash_ID {task_hash_id} not found")
                raise HTTPException(status_code=404, detail="Task not found")
            
            if str(task.status) != 'active':
                logging.error(f"Task with Hash_ID {task_hash_id} is not active")
                raise HTTPException(status_code=400, detail="Task is not active")

            # Create a new job
            job = database.JobModel(
                task_hash_id=task_hash_id,
                trigger_time=datetime.now(pytz.UTC),
                status=models.JobStatus.PENDING
            )
            db_session.add(job)

            try:
                db_session.commit()
                db_session.refresh(job)
                # Execute the job in the background
                job_id = int(job.id)
                background_tasks.add_task(execute_job, job_id)
                logging.info(f"Job triggered with ID: {job_id}")
                self.running_jobs.add(job_id)
                return {"job_id": job_id, "message": "Job triggered successfully"}
            
            except Exception as e:
                logging.error(f"Failed to trigger job: {e}")
                db_session.rollback()
                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/jobs/", response_model=List[models.Job])
        async def list_jobs(
            task_hash_id: Optional[str] = None,
            skip: int = Query(0, ge=0),
            limit: int = Query(100, ge=1)
        ):
            """List jobs with optional task filter and pagination.

            Args:
                task_hash_id: Optional task ID to filter jobs
                skip: Number of records to skip
                limit: Maximum number of records to return
                db: Database session

            Returns:
                List of jobs
            """
            db_session = db.get_session()
            if task_hash_id is not None:
                return db.get_jobs_by_task_hash_id(db_session, task_hash_id, skip=skip, limit=limit)
            else:
                return db.get_jobs(db_session, skip=skip, limit=limit)
        
        @app.get("/jobs/count", response_class=JSONResponse)
        async def get_job_count(task_hash_id : Optional[str] = None):
            """Get the count of jobs.
            Returns:
                JSON response with job count
            """
            db_session = db.get_session()
            if task_hash_id is not None:
                jobs = db.get_jobs_by_task_hash_id(db_session, task_hash_id)
            else:
                jobs = db.get_jobs(db_session)
            return {"count": len(jobs)}

        @app.get("/jobs/{job_id}", response_model=models.Job)
        async def get_job(job_id: int):
            """Get a job by ID.

            Args:
                job_id: Job ID
                db: Database session

            Returns:
                Job data

            Raises:
            
                HTTPException: If job not found
            """
            db_session = db.get_session()
            job = db.get_job_by_id(db_session, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job not found")
            return job

        async def execute_job(job_id: int):
            """Execute a job in the background.

            This function is called by the background task system to execute a job.
            It updates the job status and handles retries if configured.

            Args:
                job_id: Job ID
                db: Database session
            """
            db_session = db.get_session()
            job = db.get_job_by_id(db_session, job_id)
            if job is None:
                logging.error(f"Job with ID {job_id} not found")
                return

            task_hash_id = str(job.task_hash_id)
            task = db.get_task_by_id(db_session, task_hash_id)
            if task is None:
                logging.error(f"Task with Hash_ID {task_hash_id} not found")
                return

            # Extract and convert task values
            task_command = task.command
            task_environment = dict(task.environment) if task.environment else {}
            task_working_directory = str(task.working_directory or ".")
            task_callable = task.callable_func
            if task_callable is not None:
                task_callable = models.GlobalCallableFunctions.get_function(str(task_callable))

            # Update job status to running using proper SQLAlchemy update
            job_id = int(job.id)
            task_dir = sanitize_filename(task.name.replace(" ", "_")).lower()
            logfile = f"{self.log_dir}/{task_dir}/{datetime.now():%Y%m%d_%H%M%S}_{job.id}.log"
            if not os.path.exists(os.path.dirname(logfile)):
                os.makedirs(os.path.dirname(logfile), exist_ok=True)
            
            db_session.query(models.JobModel).filter_by(id=job_id).update({
                "status": str(models.JobStatus.RUNNING.value),
                "start_time": datetime.utcnow(),
                "log_file" : logfile
            })
            db_session.commit()

            try:
                # Create subprocess runner
                runner = SubProcessRunner(log_file=logfile)
                
                # Execute the command
                if task_command is not None:
                    runner.start(
                        target=str(task_command),
                        env=dict(task_environment),
                        cwd=str(task_working_directory),
                        shell=True
                    )
                elif task_callable is not None:
                    runner.start(
                        target=task_callable,
                        cwd=str(task_working_directory),
                        shell=True
                    )
                else:
                    raise ValueError("No command or callable function specified")
                
                # Wait for completion and get status
                while runner.is_running():
                    await asyncio.sleep(0.1)
                result = runner.get_status()

                # Update job status based on result
                job_id = int(job.id)
                status = str(
                    models.JobStatus.COMPLETED.value if result.get('exit_code') == 0
                    else models.JobStatus.FAILED.value
                )
                error_message = str(result.get('error', '')) if result.get('exit_code') != 0 else None
                
                db_session.query(models.JobModel).filter_by(id=job_id).update({
                    "end_time": datetime.utcnow(),
                    "exit_code": int(result.get('exit_code', 1)),
                    "status": status,
                    "error_message": error_message
                })

            except Exception as e:
                # Handle execution error
                job_id = int(job.id)
                db_session.query(models.JobModel).filter_by(id=job_id).update({
                    "end_time": datetime.utcnow(),
                    "status": str(models.JobStatus.FAILED.value),
                    "error_message": str(e)
                })

                # Handle retries if configured
                max_retries = int(task.max_retries)
                retry_count = int(job.retry_count)
                retry_delay = float(task.retry_delay)
                
                if max_retries > 0 and retry_count < max_retries:
                    db_session.query(models.JobModel).filter_by(id=job_id).update({
                        "retry_count": retry_count + 1
                    })
                    db_session.commit()
                    # Schedule retry after delay
                    await asyncio.sleep(retry_delay)
                    await execute_job(job_id)
                    return

            db_session.commit()

        @app.post("/tasks/{task_hash_id}/status")
        async def update_task_status(
            task_hash_id: str,
            status: models.TaskStatus
        ):
            """Update task status to enable or disable it.

            Args:
                task_hash_id: Task ID
                status: New status (active or disabled)

            Returns:
                Updated task

            Raises:
                HTTPException: If task not found or status update fails
            """
            db_session = db.get_session()
            try:
                task = db.get_task_by_id(session=db_session, task_hash_id=task_hash_id)
                if task is None:
                    raise HTTPException(status_code=404, detail="Task not found")
                db_session.query(database.TaskModel).filter_by(hash_id=task_hash_id).update({
                    "status": status.value
                })
                db_session.commit()
                db_session.refresh(task)
                return task
            except Exception as e:
                db_session.rollback()
                raise HTTPException(status_code=400, detail=str(e))
            finally:
                db_session.close()

        @app.get("/health")
        async def health_check():
            """Health check endpoint that verifies service status.

            Returns:
                dict: Health status information
            """
            try:
                # Check database connectivity
                session = db.get_session()
                rst = session.scalar(text("SELECT 1"))
                if rst == 1:
                    return {"status": "healthy", "database": "connected"}
                else:
                    return {"status": "unhealthy", "database": "disconnected"}
            except Exception as e:
                traceback.print_exc()
                raise HTTPException(status_code=503, detail="Service unhealthy: Database connection failed")

        @app.get("/monitor_running_jobs")
        async def monitor_running_jobs():
            """Monitor running jobs and execute them if they are ready.
            Returns:
                dict: Response message
            """
            db_session   = db.get_session()
            running_jobs = deepcopy(self.running_jobs)
            failed_jobs  = set()
            for job_id in running_jobs:
                job = db.get_job_by_id(db_session, job_id)
                if job is None:
                    logging.error(f"Job with ID {job_id} not found")
                    self.running_jobs.remove(job_id)
                status = str(job.status)
                if status in ['failed', 'cancelled', 'completed']:
                    logging.info(f"Job with ID {job_id} is finished")
                    self.running_jobs.remove(job_id)
                    if status == "failed":
                        failed_jobs.add(job)
            if failed_jobs:
                ## send alerts here
                for job in failed_jobs:
                    task = db.get_task_by_id(db_session, job.task_hash_id)
                    if task:
                        logging.error(f"Task {task.name}'s job {job.id} failed")
                        subject = f"Task {task.name}'s job {job.id} has failed"
                    else:
                        logging.error(f"Job {job.id} failed")
                        subject = f"Job {job.id} has failed"
                    
                    ## send email here
                    if self.email_config:
                        if task:
                            email_contents = [
                                f"### Task {task.name}'s job {job.id} has failed",
                                f"### Task Config",
                                "<pre>\n" + yaml.dump(models.model_to_dict(task), default_flow_style=False, sort_keys=False) + "</pre>",
                                # pprint.pformat(, indent=4),
                                f"### Error",
                                job.error_message
                            ]
                        else:
                            email_contents = [
                                f"### Job {job.id} has failed",
                                f"### Job Config",
                                "<pre>\n" + yaml.dump(models.model_to_dict(job), default_flow_style=False, sort_keys=False) + "</pre>",
                                f"### Error",
                                job.error_message
                            ]
                        if self.url_prefix:
                            email_contents = [
                                f"[Failed Job]({self.url_prefix}/tasks/{job.task_hash_id}/jobs/{job.id})"
                            ] + email_contents

                        send_email(
                            from_address   = self.email_config.smtp_username,
                            to_address     = self.email_config.email_recipients,
                            subject        = subject,
                            email_contents = email_contents,
                            attachments    = {
                                os.path.basename(job.log_file) : job.log_file
                            },
                            smtp_host     = self.email_config.smtp_server,
                            smtp_port     = self.email_config.smtp_port,
                            use_tls       = self.email_config.smtp_usetls,
                            smtp_password = self.email_config.smtp_password
                        )
                    
                    ## use customized method to send alert
                    if self.send_alert_callable:
                        self.send_alert_callable(subject, task, job)

    def run_api_in_thread(self):
        """Run the FastAPI application in a separate thread."""
        def worker():
            import uvicorn
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")

        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()
        logging.info(f"API server started on http://{self.host}:{self.port}")
        
        return self.thread
    
    def run(self):
        import uvicorn
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")

if __name__ == "__main__":
    API().run()