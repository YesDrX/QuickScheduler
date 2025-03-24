#!/usr/bin/env python3

import asyncio
import logging
import os
from pathlib import Path
from quickScheduler.main import QuickScheduler
from quickScheduler.backend.models import TaskModel, GlobalCallableFunctions
from quickScheduler.utils.triggers import TriggerType

def example_worker():
    print("Hello World!")
example_worker_key = GlobalCallableFunctions.register_function(example_worker)

# Example programmatic tasks
def create_example_tasks():
    return [
        TaskModel(
            name="Memory Monitor",
            description="Monitor system memory usage and alert if above threshold",
            schedule_type=TriggerType.DAILY,
            schedule_config={
                "run_time" : "12:00",
                "timezone" : "America/New_York"
            },
            command="free -h"
        ).calculate_hash_id(),
        TaskModel(
            name="Hello World",
            description="Print 'Hello World!' to the console",
            schedule_type=TriggerType.DAILY,
            schedule_config={
                "run_time" : "12:00",
                "timezone" : "America/New_York"
            },
            callable_func = example_worker_key
        ).calculate_hash_id()
    ]

async def main():
    # Get the path to the YAML tasks directory
    current_dir = Path(__file__).parent
    tasks_dir = current_dir / "tasks"
    config_filename = current_dir / "config.yml"
    
    # Create programmatic tasks
    tasks = create_example_tasks()
    
    # Initialize scheduler with both YAML and programmatic tasks
    scheduler = QuickScheduler(str(config_filename), tasks)
    
    try:
        # Run the scheduler
        scheduler.run()
    except KeyboardInterrupt:
        print("\nShutting down scheduler...")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s][%(asctime)s] %(message)s')
    asyncio.run(main())