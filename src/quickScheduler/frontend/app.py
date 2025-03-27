"""Frontend application module for quickScheduler.

This module provides a FastAPI application that serves the web interface
using Jinja2 templates and integrates with the backend API.
"""
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
import numpy as np
import requests
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.routing import request_response
from starlette.middleware.sessions import SessionMiddleware
from quickScheduler.frontend.auth import AuthMiddleware

from quickScheduler.backend.system_stats import get_system_stats
from quickScheduler.utils.datetime_utils import convert_to_local, get_local_timezone, parse_datetime
from quickScheduler.utils.triggers import TriggerType, build_trigger


class FrontEnd:
    def __init__(self, host : str = "0.0.0.0", port : int = 8001, backend_api_url: str = "http://localhost:8000", config=None):
        self.host = host
        self.port = port
        self.config = config

        # Create FastAPI application
        self.app = FastAPI(
            title="QuickScheduler Web Interface",
            description="Web interface for task scheduling and job management",
            version="1.0.0"
        )

        # Add middleware
        self.auth_middleware = AuthMiddleware(app=None, config=self.config)
        self.app.add_middleware(AuthMiddleware, config=self.config, instance=self.auth_middleware)
        self.app.add_middleware(SessionMiddleware, secret_key=os.urandom(24))

        # Setup templates and static files
        self.templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
        self.app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

        # Add custom filters
        self.templates.env.filters["status_color"] = lambda status: {
            "PENDING": "secondary",
            "RUNNING": "primary",
            "COMPLETED": "success",
            "FAILED": "danger",
            "CANCELLED": "warning"
        }.get(status, "secondary")

        self.register_endpoints(app=self.app, backend_api_url=backend_api_url)

    def register_endpoints(self, app : FastAPI, backend_api_url: str):
        @app.get("/login", response_class=HTMLResponse)
        async def login_page(request: Request):
            """Render login page."""
            return self.templates.TemplateResponse("login.html", {"request": request})

        @app.post("/login")
        async def login(request: Request, username: str = Form(...), password: str = Form(...)):
            """Handle login form submission."""
            # Access the auth middleware instance directly from the frontend class
            auth_middleware = self.auth_middleware
            
            if not auth_middleware:
                raise HTTPException(status_code=500, detail="Authentication middleware not configured")
            
            session_token = auth_middleware.validate_credentials(username, password)
            if session_token:
                response = RedirectResponse("/", status_code=303)
                response.set_cookie(
                    key="session", 
                    value=session_token,
                    httponly=True,
                    samesite="lax",
                    secure=False  # Set to True in production with HTTPS
                )
                return response
            
            return self.templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid credentials"}
            )

        @app.get("/", response_class=HTMLResponse)
        async def index(request: Request):
            """Render index page."""
            return self.templates.TemplateResponse("index.html", {"request": request})

        @app.post("/logout")
        async def logout(request: Request):
            """Handle user logout by clearing session."""
            response = RedirectResponse("/login", status_code=303)
            response.delete_cookie("session")
            return response

        @app.get("/system/stats")
        async def get_stats():
            """Get system statistics including CPU and RAM usage."""
            stats = get_system_stats()
            tasks = requests.get(f"{backend_api_url}/tasks/")
            if tasks.ok:
                stats["task_count"] = len(tasks.json())
            jobs  = requests.get(f"{backend_api_url}/jobs/")
            if jobs.ok:
                stats["job_count"] = len(jobs.json())
            health = requests.get(f"{backend_api_url}/health/")
            if health.ok:
                stats["health_status"] = health.json()["status"]
            else:
                stats["health_status"] = "unhealthy"
            return stats
        
        @app.get("/jobs", response_class=HTMLResponse)
        async def list_all_jobs(request: Request):
            """Render all jobs history page."""
            filter_type = request.query_params.get('filter', 'all')
            page = int(request.query_params.get('page', 1))
            limit = 25
            skip = (page - 1) * limit
            async with httpx.AsyncClient() as client:
                # Get all jobs with pagination
                response = await client.get(f"{backend_api_url}/jobs/", params={"skip": skip, "limit": limit})
                assert response.status_code == 200, response.text
                jobs = response.json()
                
                # Get total count for pagination
                count_response = await client.get(f"{backend_api_url}/jobs/count")
                total_jobs = count_response.json()["count"]

                def _calc_job_times(job):
                    rst = {
                        "start_time" : convert_to_local(parse_datetime(job["start_time"]), get_local_timezone()),
                        "end_time"   : convert_to_local(parse_datetime(job["end_time"]), get_local_timezone())
                    }
                    rst["duration"] = np.round((rst["end_time"] - rst["start_time"]).total_seconds(), 2)

                    return rst
                
                jobs = [
                    {
                        **job,
                        **_calc_job_times(job)
                    }
                    for job in jobs
                    if filter_type == 'all' or (filter_type == 'failed' and job.get('exit_code', 0) != 0)
                ]

                # Get task names for each job
                for job in jobs:
                    task_response = await client.get(f"{backend_api_url}/tasks/{job['task_hash_id']}")
                    if task_response.status_code == 200:
                        task = task_response.json()
                        job['task_name'] = task['name']
                    else:
                        job['task_name'] = 'Unknown Task'

            total_pages = (total_jobs + limit - 1) // limit
            return self.templates.TemplateResponse("job_history_all.html", {
                "request": request,
                "jobs": sorted(jobs, key=lambda job: job['end_time'], reverse = True),
                "current_page": page,
                "total_pages": total_pages
            })

        @app.get("/tasks", response_class=HTMLResponse)
        async def list_tasks(request: Request):
            """Render tasks list page."""
            search_query = request.query_params.get('search', '').lower()
            async with httpx.AsyncClient() as client:
                # Get tasks
                response = await client.get(f"{backend_api_url}/tasks/", params={"skip": 0, "limit": 100})
                assert response.status_code == 200, response.text
                tasks = response.json()
                
                # Get jobs for each task to find previous run time
                for task in tasks:
                    jobs_response = await client.get(f"{backend_api_url}/jobs/", params={"task_hash_id": task['hash_id']})
                    jobs = jobs_response.json()
                    
                    # Find latest start time from jobs and convert to local time
                    from quickScheduler.utils.datetime_utils import convert_to_local
                    start_times = [job['start_time'] for job in jobs if job['start_time']]
                    if start_times:
                        latest_time = max(start_times)
                        task['previous_run_time'] = convert_to_local(latest_time, get_local_timezone()).strftime('%Y%m%d %H:%M:%S')
                    else:
                        task['previous_run_time'] = None
                    
                    # Calculate next run time based on schedule type and convert to local time
                    if task['schedule_type'] == TriggerType.IMMEDIATE:
                        task['next_run_time'] = None
                    else:
                        # Create trigger for schedule calculation
                        try:
                            trigger = build_trigger(task["schedule_type"], task["schedule_config"])
                            next_run = trigger.get_next_run()
                            if next_run:
                                task['next_run_time'] = convert_to_local(next_run, get_local_timezone()).strftime('%Y%m%d %H:%M:%S')
                            else:
                                task['next_run_time'] = None
                        except Exception as e:
                            logging.error(f"Error calculating next run time for task {task['hash_id']}: {str(e)}")
                            task['next_run_time'] = None
                
            if search_query:
                from fuzzywuzzy import fuzz
                filtered_tasks = []
                for task in tasks:
                    name_ratio = fuzz.partial_ratio(search_query, task['name'].lower())
                    command_ratio = fuzz.partial_ratio(search_query, task['command'].lower())
                    id_ratio = fuzz.partial_ratio(search_query, task['hash_id'].lower())
                    if max(name_ratio, command_ratio, id_ratio) > 60:  # Threshold for fuzzy matching
                        filtered_tasks.append(task)
                tasks = filtered_tasks
            return self.templates.TemplateResponse("tasks.html", {"request": request, "tasks": tasks})

        @app.get("/tasks/{task_hash_id}", response_class=HTMLResponse)
        async def view_task(request: Request, task_hash_id: str):
            """Render task details page."""
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{backend_api_url}/tasks/{task_hash_id}")
                if response.status_code == 404:
                    raise HTTPException(status_code=404, detail="Task not found")
                task = response.json()
                task["created_at"] = convert_to_local(task["created_at"], get_local_timezone()).strftime('%Y%m%d %H:%M:%S')
                task["updated_at"] = convert_to_local(task["updated_at"], get_local_timezone()).strftime('%Y%m%d %H:%M:%S')

            return self.templates.TemplateResponse("task_details.html", {"request": request, "task": task})

        @app.get("/tasks/{task_hash_id}/jobs", response_class=HTMLResponse)
        async def task_jobs(request: Request, task_hash_id: str):
            """Render task job history page."""
            filter_type = request.query_params.get('filter', 'all')
            page = int(request.query_params.get('page', 1))
            limit = 25
            skip = (page - 1) * limit
            async with httpx.AsyncClient() as client:
                task_response = await client.get(f"{backend_api_url}/tasks/{task_hash_id}")
                if task_response.status_code == 404:
                    logging.info(f"Task with hash_id {task_hash_id} not found")
                    raise HTTPException(status_code=404, detail="Task not found")
                task = task_response.json()
                
                jobs_response = await client.get(f"{backend_api_url}/jobs/", params={"task_hash_id" : task_hash_id, "skip": skip, "limit": limit})
                jobs = jobs_response.json()
                
                # Get total count for pagination
                count_response = await client.get(f"{backend_api_url}/jobs/count", params={"task_hash_id": task_hash_id})
                total_jobs = count_response.json()["count"]
                
                def _calc_job_times(job):
                    rst = {
                        "start_time" : convert_to_local(parse_datetime(job["start_time"]), get_local_timezone()),
                        "end_time"   : convert_to_local(parse_datetime(job["end_time"]), get_local_timezone())
                    }
                    rst["duration"] = np.round((rst["end_time"] - rst["start_time"]).total_seconds(), 2)

                    return rst
                jobs = [
                    {
                        **job,
                        **_calc_job_times(job)
                    }
                    for job in jobs
                    if filter_type == 'all' or (filter_type == 'failed' and job.get('exit_code', 0) != 0)
                ]

            total_pages = (total_jobs + limit - 1) // limit
            return self.templates.TemplateResponse("job_history.html", {
                "request": request,
                "task": task,
                "jobs": sorted(jobs, key=lambda job: job['end_time'], reverse = True),
                "current_page": page,
                "total_pages": total_pages
            })

        @app.get("/tasks/{task_hash_id}/jobs/{job_id}", response_class=HTMLResponse)
        async def job_details(request: Request, task_hash_id: str, job_id: str):
            """Render job details page."""
            async with httpx.AsyncClient() as client:
                task_response = await client.get(f"{backend_api_url}/tasks/{task_hash_id}")
                if task_response.status_code == 404:
                    raise HTTPException(status_code=404, detail="Task not found")
                task = task_response.json()
                
                job_response = await client.get(f"{backend_api_url}/jobs/{job_id}")
                if job_response.status_code == 404:
                    raise HTTPException(status_code=404, detail="Job not found")
                job = job_response.json()
            # Parse timestamp strings into datetime objects
            if isinstance(job.get('start_time'), str):
                job['start_time'] = datetime.fromisoformat(job['start_time'].replace('Z', '+00:00'))
            
            if isinstance(job.get('end_time'), str):
                job['end_time'] = datetime.fromisoformat(job['end_time'].replace('Z', '+00:00'))

            return self.templates.TemplateResponse("job_details.html", {
                "request": request,
                "task": task,
                "job": job
            })

        @app.get("/tasks/{task_hash_id}/jobs/{job_id}/log", response_class=HTMLResponse)
        async def job_log(request: Request, task_hash_id: str, job_id: str):
            """Render job log page."""
            async with httpx.AsyncClient() as client:
                task_response = await client.get(f"{backend_api_url}/tasks/{task_hash_id}")
                if task_response.status_code == 404:
                    logging.info(f"Task with hash_id {task_hash_id} not found")
                    raise HTTPException(status_code=404, detail="Task not found")
                task = task_response.json()
                
                job_response = await client.get(f"{backend_api_url}/jobs/{job_id}")
                if job_response.status_code == 404:
                    logging.info(f"Job with id {job_id} not found")
                    raise HTTPException(status_code=404, detail="Job not found")
                job = job_response.json()
                
                job_log_file = job["log_file"]
                if job_log_file and os.path.exists(job_log_file):
                    with open(job_log_file, "r") as f:
                        log = f.read()
                else:
                    logging.info(f"Log file {job_log_file} not found")
                    log = ""
                template_data = {
                            "request": request,
                            "task": task,
                            "job": job,
                            "log": log
                        }
                return self.templates.TemplateResponse("job_log.html", template_data)

        @app.post("/tasks/{task_hash_id}/status")
        async def update_task_status(request: Request, task_hash_id: str):
            """Update task status endpoint.
            
            Args:
                request: FastAPI request object
                task_hash_id: Task ID
                
            Returns:
                Updated task data
            """
            async with httpx.AsyncClient() as client:
                # Get current task status
                task_response = await client.get(f"{backend_api_url}/tasks/{task_hash_id}")
                if task_response.status_code == 404:
                    raise HTTPException(status_code=404, detail="Task not found")
                task = task_response.json()
                
                # Toggle status
                new_status = "disabled" if task["status"] == "active" else "active"
                
                # Update task status
                logging.info(f"Updating task {task_hash_id} status to {new_status}")
                response = await client.post(
                    f"{backend_api_url}/tasks/{task_hash_id}/status?status={new_status}"
                )
                if response.status_code == 404:
                    raise HTTPException(status_code=404, detail="Task not found")
                return response.json()

        @app.post("/tasks/{task_hash_id}/trigger")
        async def trigger_task(request: Request, task_hash_id: str):
            """Trigger a task execution."""
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{backend_api_url}/tasks/{task_hash_id}/trigger")
                if response.status_code == 404:
                    raise HTTPException(status_code=404, detail="Task not found")
                return response.json()
                
        @app.delete("/jobs/{job_id}")
        async def delete_job(request: Request, job_id: str):
            """Delete a specific job."""
            async with httpx.AsyncClient() as client:
                response = await client.delete(f"{backend_api_url}/jobs/{job_id}")
                if response.status_code != 200:
                    raise HTTPException(status_code=400)
                return response.json()
                
        @app.delete("/jobs")
        async def delete_all_jobs(request: Request):
            """Delete all jobs."""
            async with httpx.AsyncClient() as client:
                response = await client.delete(f"{backend_api_url}/jobs")
                if response.status_code != 200:
                    raise HTTPException(status_code=400)
                return response.json()
                
        @app.delete("/tasks/{task_hash_id}/jobs")
        async def delete_task_jobs(request: Request, task_hash_id: str):
            """Delete all jobs for a specific task."""
            async with httpx.AsyncClient() as client:
                response = await client.delete(f"{backend_api_url}/tasks/{task_hash_id}/jobs")
                if response.status_code != 200:
                    raise HTTPException(status_code=400)
                return response.json()

    def run(self):
        import uvicorn
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")
    
    def run_in_thread(self):
        """Run the FastAPI application in a separate thread."""
        def worker():
            import uvicorn
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")

        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()
        logging.info(f"API server started on http://{self.host}:{self.port}")
        
        return self.thread
    
if __name__ == "__main__":
    FrontEnd().run()