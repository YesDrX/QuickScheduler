"""Unit tests for the SubProcessRunner class.

This module contains comprehensive tests for the SubProcessRunner class,
covering process management, environment variables, and logging functionality.
"""

import os
import time
import pytest
import tempfile
from pathlib import Path
from quickScheduler.utils.subprocess_runner import SubProcessRunner

def test_simple_command():
    """Test running a simple shell command."""
    runner = SubProcessRunner()
    runner.start("echo 'test'")
    time.sleep(0.1)  # Give process time to complete
    status = runner.get_status()
    assert not status["running"]
    assert status["exit_code"] == 0
    assert "test" in status["output"]

def test_python_callable():
    """Test running a Python callable."""
    def sample_function():
        print("Hello from Python")
        return

    runner = SubProcessRunner()
    runner.start(sample_function)
    time.sleep(0.5)  # Increase sleep time to ensure process completion
    status = runner.get_status()
    assert not status["running"]
    assert status["exit_code"] == 0
    assert "Hello from Python" in status["output"]

def test_environment_variables():
    """Test setting environment variables for shell commands."""
    runner = SubProcessRunner()
    env = {"TEST_VAR": "test_value"}
    runner.start("echo $TEST_VAR", env=env)
    time.sleep(0.1)  # Give process time to complete
    status = runner.get_status()
    assert "test_value" in status["output"]

def test_process_lifecycle():
    """Test process lifecycle management (start/stop/status)."""
    runner = SubProcessRunner()
    runner.start("sleep 10")
    assert runner.is_running()
    
    runner.stop()
    assert not runner.is_running()
    
    status = runner.get_status()
    assert not status["running"]

def test_logging():
    """Test logging functionality."""
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        log_file = temp.name

    runner = SubProcessRunner(log_file)
    runner.start("echo 'test logging'")
    time.sleep(0.1)  # Give process time to complete

    with open(log_file, 'r') as f:
        log_content = f.read()
        assert "Starting shell command" in log_content

    os.unlink(log_file)

def test_error_handling():
    """Test error handling for invalid commands and states."""
    runner = SubProcessRunner()
    
    # Test starting already running process
    runner.start("sleep 5")
    with pytest.raises(ValueError):
        runner.start("echo 'test'")
    runner.stop()

    # Test stopping non-running process
    with pytest.raises(ValueError):
        runner.stop()

    # Test invalid target type
    with pytest.raises(TypeError):
        runner.start(123)

def test_long_running_process():
    """Test handling of long-running processes."""
    runner = SubProcessRunner()
    runner.start("sleep 10")
    
    assert runner.is_running()
    status = runner.get_status()
    assert status["running"]
    assert status["exit_code"] is None
    
    runner.stop()
    assert not runner.is_running()