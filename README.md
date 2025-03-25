# Quick Scheduler

A Python-based task scheduler for running automated tasks efficiently. It provides a flexible and user-friendly way to schedule and manage tasks through both YAML configuration and programmatic API.

## Features

- Task scheduling with multiple trigger types (daily, interval)
- YAML-based task configuration
- Programmatic task creation through Python API
- Web-based interface for task management
- Real-time task monitoring and logging
- System resource monitoring
- Timezone support
- Calendar-based scheduling

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Quick Scheduler can be configured using YAML files or programmatically through Python code. Here's a basic example:

```bash
./run.sh python ./examples/main.py
```

This will start the scheduler with example tasks defined in `examples/tasks/` directory. The web interface will be available for task management.

You can define tasks in YAML format:

```yaml
name: Service Health Check
description: Monitors critical services and endpoints
schedule_type: interval
schedule_config:
  start_time: 9:00
  end_time: 17:00
  interval: 60
  timezone: America/New_York
command: curl -f http://localhost:8000/health
```

Or create tasks programmatically:

```python
from quickScheduler.backend.models import TaskModel
from quickScheduler.utils.triggers import TriggerType

task = TaskModel(
    name="Memory Monitor",
    description="Monitor system memory usage",
    schedule_type=TriggerType.DAILY,
    schedule_config={
        "run_time": "12:00",
        "timezone": "America/New_York"
    },
    command="free -h"
)
```

## Screenshots
![Main Page](examples/images/main_page.png)
![Tasks Page](examples/images/tasks.png)
![Task Details Page](examples/images/task.png)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

This project was built with the help of [Trae AI Editor](https://www.trae.ai).