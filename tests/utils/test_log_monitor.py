"""Unit tests for the LogFileMonitor class.

This module contains tests for the LogFileMonitor class,
covering file monitoring, content streaming, and error handling.
"""

import os
import time
import tempfile
from pathlib import Path
from quickScheduler.utils.log_monitor import LogFileMonitor

def test_monitor_new_content():
    """Test monitoring new content written to log file."""
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        log_file = temp.name

    try:
        # Initialize monitor
        monitor = LogFileMonitor(log_file)

        # Write content to file
        with open(log_file, 'w') as f:
            f.write("test line 1\n")
            f.flush()

        # Get new content
        time.sleep(0.2)  # Give monitor time to detect changes
        content = monitor.get()
        assert content is not None
        assert "test line 1" in content

        # Write more content
        with open(log_file, 'a') as f:
            f.write("test line 2\n")
            f.flush()

        time.sleep(0.2)
        content = monitor.get()
        assert content is not None
        assert "test line 2" in content

    finally:
        os.unlink(log_file)

def test_monitor_from_start():
    """Test monitoring from start of file."""
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(b"existing content\n")
        log_file = temp.name

    try:
        monitor = LogFileMonitor(log_file, from_start=True)
        content = monitor.get()
        assert content is not None
        assert "existing content" in content

    finally:
        os.unlink(log_file)

def test_handle_file_rotation():
    """Test handling of file rotation/truncation."""
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        log_file = temp.name

    try:
        # Initialize monitor
        monitor = LogFileMonitor(log_file)

        # Write initial content
        with open(log_file, 'w') as f:
            f.write("initial content\n")
            f.flush()

        time.sleep(0.2)
        content = monitor.get()
        assert content is not None
        assert "initial content" in content

        # Simulate file rotation by truncating
        with open(log_file, 'w') as f:
            f.write("new content after rotation\n")
            f.flush()

        time.sleep(0.2)
        content = monitor.get()
        assert content is not None
        assert "new content after rotation" in content

    finally:
        os.unlink(log_file)

def test_nonexistent_file():
    """Test monitoring a non-existent file."""
    monitor = LogFileMonitor("/nonexistent/file.log")

    # Monitor should handle non-existent file
    time.sleep(0.2)
    content = monitor.get()
    assert content is None
    assert monitor._get_file_size() == 0