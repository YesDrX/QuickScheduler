import asyncio
import logging
import pprint
from pathlib import Path
from quickScheduler.main import QuickScheduler
from quickScheduler.backend.models import TaskModel, GlobalCallableFunctions, JobModel, model_to_dict
from quickScheduler.utils.triggers import TriggerType

"""
A task could be a python callable
"""
def example_worker():
    print("Hello World!")

"""
This is a callable example, which will raise an exception, and then trigger email/customized alerts
"""
def example_failing_worker():
    print("Hello World!")
    raise Exception("This is an example exception")

"""
This is a sample customized alert sender callback function
"""
def customize_alert_sender(msg : str, task : TaskModel, job : JobModel):
    print("*" * 100)
    print(msg)
    pprint.pprint(model_to_dict(task))
    pprint.pprint(model_to_dict(job))
    print("*" * 100)

"""
Tasks can be defined programmably in code, or loaded from yaml config files. 
"""
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
            callable_func = GlobalCallableFunctions.register_function(example_worker)
        ).calculate_hash_id(),
        TaskModel(
            name="Job to fail",
            description="Print 'Hello World!' to the console",
            schedule_type=TriggerType.IMMEDIATE,
            callable_func = GlobalCallableFunctions.register_function(example_failing_worker)
        ).calculate_hash_id()
    ]

async def main():
    import os

    # Get the path to the YAML tasks directory
    current_dir = Path(__file__).parent
    config_filename = current_dir / "config_private.yaml"
    if not os.path.exists(str(config_filename)):
        config_filename = current_dir / "config.yml"
    
    logging.info(f"starting quick scheduler using config file {config_filename}")
    # Create programmatic tasks
    tasks = create_example_tasks()
    
    # Initialize scheduler with both YAML and programmatic tasks
    scheduler = QuickScheduler(
                    str(config_filename),
                    tasks,
                    send_alert_callable = customize_alert_sender
                )
    
    try:
        # Run the scheduler
        scheduler.run()
    except KeyboardInterrupt:
        print("\nShutting down scheduler...")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s][%(asctime)s] %(message)s')
    asyncio.run(main())