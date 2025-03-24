import os
import logging
from typing import List
import time

from quickScheduler.backend.api import API
from quickScheduler.backend.models import TaskModel
from quickScheduler.backend.scheduler import Scheduler
from quickScheduler.frontend.app import FrontEnd
from quickScheduler.utils.yaml_config import YamlConfig
from quickScheduler.utils.triggers import TriggerType


class QuickScheduler:
    def __init__(self, config_file : str, tasks : List[TaskModel] = []):
        self.config_file = config_file
        self.config = YamlConfig(config_file)
        self.tasks = tasks
        self.backend_api_host = self.config.get("backend_api_host", "127.0.0.1")
        self.backend_api_port = self.config.get("backend_api_port", 8000)
        self.backend_api_url = f"http://{self.backend_api_host}:{self.backend_api_port}"
    
    def start_api(self):
        self.api = API(
            host = self.backend_api_host,
            port = self.backend_api_port,
            working_directory = self.config.get("data_dir", "~/.schedulerData/")
        )
        self.api_thread = self.api.run_api_in_thread()
    
    def start_scheduler(self):
        self.scheduler = Scheduler(
            config_dir = os.path.join(self.config.get("data_dir", "~/.schedulerData"), "tasks"),
            working_directory = self.config.get("data_dir", "~/.schedulerData/"),
            tasks = self.tasks,
            backend_api_url = self.backend_api_url
        )
        self.scheduler_thread = self.scheduler.run_in_thread()
    
    def start_frontend(self):
        self.frontend = FrontEnd(
            host = self.config.get("frontend_host", "0.0.0.0"),
            port = self.config.get("frontend_port", 8001),
            backend_api_url = self.backend_api_url
        )
        self.frontend_thread = self.frontend.run_in_thread()
    
    def run(self):
        self.start_api()
        self.start_scheduler()
        self.start_frontend()

        assert self.api_thread.is_alive(), f"failed to start API server"
        assert self.scheduler_thread.is_alive(), f"failed to start scheduler"
        assert self.frontend_thread.is_alive(), f"failed to start frontend"

        while True:
            if not self.api_thread.is_alive():
                logging.info("API server stopped, restarting...")
                self.start_api()
            if not self.scheduler_thread.is_alive():
                logging.info("Scheduler stopped, restarting...")
                self.start_scheduler()
            if not self.frontend_thread.is_alive():
                logging.info("Frontend stopped, restarting...")
                self.start_frontend()
            time.sleep(1)