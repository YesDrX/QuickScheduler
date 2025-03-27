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
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        log_file = temp.name

    runner = SubProcessRunner(log_file)
    runner.start("echo 'test'")
    time.sleep(0.1)  # Give process time to complete
    status = runner.get_status()
    assert not status["running"]
    assert status["exit_code"] == 0
    assert "test" in status["output"]

    with open(log_file, 'r') as f:
        log_content = f.read()
        assert "command: echo 'test'" in log_content
    os.unlink(log_file)

def test_python_callable():
    """Test running a Python callable."""
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        log_file = temp.name

        def sample_function():
            print("Hello from Python")
            return

        runner = SubProcessRunner(log_file)
        runner.start(sample_function)
        time.sleep(0.5)  # Increase sleep time to ensure process completion
        status = runner.get_status()
        assert not status["running"]
        assert status["exit_code"] == 0

        with open(log_file, 'r') as f:
            log_content = f.read()
            assert "Hello from Python" in log_content

def test_environment_variables():
    """Test setting environment variables for shell commands."""
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        log_file = temp.name

    runner = SubProcessRunner(log_file)
    env = {"TEST_VAR": "test_value"}
    runner.start("echo $TEST_VAR", env=env)
    time.sleep(0.1)  # Give process time to complete
    status = runner.get_status()
    assert "test_value" in status["output"]

    with open(log_file, 'r') as f:
        log_content = f.read()
        assert "command: echo $TEST_VAR" in log_content
    os.unlink(log_file)

def test_process_lifecycle():
    """Test process lifecycle management (start/stop/status)."""
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        log_file = temp.name

    runner = SubProcessRunner(log_file)
    runner.start("sleep 10")
    assert runner.is_running()
    
    runner.stop()
    assert not runner.is_running()
    
    status = runner.get_status()
    assert not status["running"]

    with open(log_file, 'r') as f:
        log_content = f.read()
        assert "command: sleep 10" in log_content
    os.unlink(log_file)

def test_logging():
    """Test logging functionality."""
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        log_file = temp.name

    runner = SubProcessRunner(log_file)
    runner.start("echo 'test logging'")
    time.sleep(0.1)  # Give process time to complete

    with open(log_file, 'r') as f:
        log_content = f.read()
        assert "echo 'test logging'" in log_content

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
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        log_file = temp.name

    runner = SubProcessRunner(log_file)
    runner.start("sleep 10")
    
    assert runner.is_running()
    status = runner.get_status()
    assert status["running"]
    assert status["exit_code"] is None
    
    runner.stop()
    assert not runner.is_running()

    with open(log_file, 'r') as f:
        log_content = f.read()
        assert "command: sleep 10" in log_content
    os.unlink(log_file)