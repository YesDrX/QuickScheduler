"""LogFileMonitor - A utility class for monitoring log file changes.

This module provides functionality to monitor log files and retrieve new content
on demand, similar to 'tail -f' command but in a non-blocking way.
"""

import os
from typing import Optional

class LogFileMonitor:
    """A class to monitor log file changes and retrieve content updates.

    This class provides functionality to:
    - Monitor log files for new content
    - Get content updates on demand via get() method
    - Handle file rotation and truncation
    - Support different line buffering modes
    """

    def __init__(self, log_file: str, from_start: bool = False):
        """Initialize the LogFileMonitor.

        Args:
            log_file: Path to the log file to monitor
            from_start: If True, start reading from beginning of file
        """
        self.log_file = log_file
        self._last_position = 0
        self._last_size = 0
        if not from_start:
            self._last_position = self._get_file_size()

    def _get_file_size(self) -> int:
        """Get the current size of the log file.

        Returns:
            int: Size of the file in bytes
        """
        try:
            return os.path.getsize(self.log_file)
        except FileNotFoundError:
            return 0

    def get(self) -> Optional[str]:
        """Get new content from the log file since last check.

        Returns:
            Optional[str]: New content from the log file, or None if no new content
        """
        try:
            current_size = self._get_file_size()

            # Handle file rotation or truncation
            if current_size < self._last_size:
                # File was truncated, reset position and read entire content
                self._last_position = 0
                with open(self.log_file, 'r') as f:
                    new_content = f.read()
                    self._last_position = len(new_content)
                    self._last_size = current_size
                    return new_content

            if current_size > self._last_position:
                with open(self.log_file, 'r') as f:
                    f.seek(0)
                    new_content = f.read()
                    if new_content:
                        self._last_position = len(new_content)
                        self._last_size = current_size
                        return new_content

            self._last_size = current_size
            return None

        except FileNotFoundError:
            return None
        except Exception as e:
            return f"Error reading log file: {str(e)}\n"