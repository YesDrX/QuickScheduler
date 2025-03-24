"""System statistics module for quickScheduler backend.

This module provides functionality to collect system metrics like CPU usage,
RAM usage, and overall system health status.
"""

import psutil
from typing import Dict

def get_system_stats() -> Dict:
    """Get current system statistics.

    Returns:
        Dict containing CPU usage, RAM usage, and other system metrics
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    
    return {
        "cpu_usage": cpu_percent,
        "ram_total": memory.total / (1024 * 1024 * 1024),  # Convert to GB
        "ram_used": memory.used / (1024 * 1024 * 1024),  # Convert to GB
        "ram_percent": memory.percent
    }