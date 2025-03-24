"""Scheduler module for quickScheduler backend.

This module provides the Scheduler class that manages task synchronization
between YAML configuration files and the database, and implements the main
event loop for task scheduling and execution.
"""

import traceback
import logging
import threading
import time
import pytz
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from quickScheduler.backend.database import Database
from quickScheduler.backend.models import TaskModel
from quickScheduler.utils.triggers import build_trigger, BaseTrigger, ImmediateTrigger, DailyTrigger, IntervalTrigger, TriggerType, TriggerConfig
from quickScheduler.utils.yaml_config import YamlConfig
import requests

class Scheduler:
    """A class to manage task scheduling and execution.

    This class is responsible for:
    - Loading tasks from YAML configuration files
    - Synchronizing tasks between configuration files and database
    - Creating and managing task triggers
    - Running the main event loop for task execution
    """

    def __init__(self, config_dir: str, working_directory: str = ".", tasks: Optional[List[TaskModel]] = None, backend_api_url: str = "http://localhost:8000"):
        """Initialize the Scheduler.

        Args:
            config_dir: Directory containing task YAML configuration files
            tasks: Optional list of TaskModel objects to include in scheduling
        """
        self.working_directory = working_directory
        self.config_dir = Path(config_dir)
        self.db = Database(db_url=f"sqlite:///{self.working_directory}/quickscheduler.db")
        self.tasks = tasks or []
        self.task_triggers: Dict[str, Tuple[TaskModel, BaseTrigger]] = {}
        self.all_tasks = {}
        self.backend_api_url = backend_api_url
        self.previous_trigger_time = {}
        # Ensure config directory exists
        if not self.config_dir.exists():
            raise FileNotFoundError(f"Configuration directory not found: {self.config_dir}")

    def _load_yaml_tasks(self) -> List[TaskModel]:
        """Load tasks from YAML configuration files in the config directory.

        Returns:
            List of TaskModel objects loaded from YAML files
        """
        yaml_tasks = []
        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                config = YamlConfig(yaml_file)
                task_data = config.config_data
                if isinstance(task_data, dict):
                    task = TaskModel(**task_data).calculate_hash_id()
                    yaml_tasks.append(task)
            except Exception as e:
                logging.error(f"Error loading task from {yaml_file}: {str(e)}")
        return yaml_tasks

    def _create_trigger(self, task: TaskModel) -> Optional[BaseTrigger]:
        """Create an appropriate trigger for a task based on its schedule type.

        Args:
            task: The task to create a trigger for

        Returns:
            A Trigger object or None if the schedule type is invalid
        """
        try:
            return build_trigger(
                task.schedule_type,
                task.schedule_config
            )
        except Exception as e:
            logging.error(f"Error creating trigger for task {task.hash_id}: {str(e)}")
            return None

    def sync_tasks(self):
        """Synchronize tasks between YAML configurations and database.

        This method:
        - Loads tasks from YAML files
        - Combines with provided task list
        - Syncs with database (adds new tasks, removes deleted ones)
        """
        # Load tasks from YAML files
        yaml_tasks = self._load_yaml_tasks()
        
        # Combine with provided tasks
        all_tasks = {task.hash_id: task for task in self.tasks + yaml_tasks}
        self.all_tasks = all_tasks

        # Sync with database
        session = self.db.get_session()
        try:
            # Get existing tasks from database
            db_tasks = session.query(TaskModel).all()
            db_task_ids = {task.hash_id for task in db_tasks}
            
            # Add new tasks to database
            for task_id, task in all_tasks.items():
                if task_id not in db_task_ids:
                    logging.info(f"[Scheduler] creating task ({task.name}) with id {task_id}")
                    session.add(task)
            
            # Remove tasks that no longer exist in sources
            for db_task in db_tasks:
                if db_task.hash_id not in all_tasks:
                    session.delete(db_task)
            
            session.commit()
        
        except Exception as e:
            traceback.print_exc()
            logging.error(f"[Scheduler] Error syncing tasks with database: {str(e)}")
            session.rollback()
        
        finally:
            session.close()

    def _trigger_task(self, task : TaskModel):
        """
        Triggers a task to run.
        Args:
            task (TaskModel): The task to trigger.
        """
        logging.info(f"Executing task {task.hash_id}: {task.name}")
        # Add your task execution logic here
        response = requests.post(f"{self.backend_api_url}/tasks/{task.hash_id}/trigger")
        if response.status_code == 404:
            logging.error(f"failed to trigger task {task.hash_id} : {task.name}")
        else:
            logging.info(f"successfully triggered task {task.hash_id} : {task.name}")
        self.previous_trigger_time[task.hash_id] = datetime.now(pytz.UTC)

    def run(self):
        """Run the main scheduler event loop.

        This method:
        - Starts the API server
        - Syncs tasks on startup
        - Updates triggers daily
        - Monitors and executes tasks based on their triggers
        """
        self.sync_tasks()
        for task_hash_id, task in self.all_tasks.items():
            trigger = self._create_trigger(task)
            if isinstance(trigger, ImmediateTrigger):
                self._trigger_task(task)
            else:
                self.task_triggers[task.hash_id] = (task, trigger)
        
        system_start_time = datetime.now(pytz.UTC)
        count = 0
        while True:
            try:
                # Update triggers at the start of each day
                now = datetime.now(pytz.UTC)

                # Check and execute due tasks
                for task_hash_id, (task, trigger) in self.task_triggers.items():
                    previous_trigger_time = self.previous_trigger_time.get(task_hash_id, system_start_time)
                    next_run = trigger.get_next_run(previous_trigger_time)
                    if next_run and next_run <= now and abs((next_run - now).total_seconds()) < 5:
                        logging.info(f"task={task.name}, previous_trigger_time={previous_trigger_time}, next_run={next_run}, now={now}")
                        self._trigger_task(task)

                # Sleep briefly to prevent excessive CPU usage
                time.sleep(1)
                if count % 5 == 0:
                    requests.get(f"{self.backend_api_url}/monitor_running_jobs")
            
            except Exception as e:
                logging.error(f"Error in scheduler loop: {str(e)}")
                traceback.print_exc()
                time.sleep(5)  # Sleep longer on error
            count += 1
    
    def run_in_thread(self):
        """Run the scheduler in a separate thread."""
        thread = threading.Thread(target=self.run)
        thread.start()
        return thread