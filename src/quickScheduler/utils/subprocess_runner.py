"""SubProcessRunner - A utility class for managing subprocess execution.

This module provides a class for running and managing subprocesses, supporting both
Python callables and shell commands. It includes features for process control,
environment variable configuration, and output logging.
"""

import os
import sys
import time
import logging
import tempfile
import subprocess
import dill
import socket
import getpass
from typing import Optional, Union, Callable, Dict, Any
from pathlib import Path

SCHEDULER_LOG_DIVIDER = f"================================[SCHEDULER]================================\n"

def _run_python_callable(serialized_func, conn, log_file):
    """Run a Python callable in a separate process.

    Args:
        serialized_func: The serialized function using dill
        conn: The pipe connection for communication
    """
    import sys
    import io

    with open(log_file, "w") as stdout:
        sys.stdout = stdout

        stdout.write(SCHEDULER_LOG_DIVIDER)
        stdout.write(f"hostname: {socket.gethostname()}\n")
        stdout.write(f"username: {getpass.getuser()}\n")
        stdout.write(f"pid: {os.getpid()}\n")
        stdout.write(f"cwd: {os.getcwd()}\n")
        stdout.flush()

        try:
            # Deserialize and run the function
            func = dill.loads(serialized_func)
            stdout.write(f"callable: {func}\n")
            stdout.write(SCHEDULER_LOG_DIVIDER)
            result = func()
            stdout.write(SCHEDULER_LOG_DIVIDER)
            stdout.write(f"result: {result}\n")
            stdout.flush()
            conn.send((True, ""))
        
        except Exception as e:
            conn.send((False, str(e)))
            raise
        
        finally:
            sys.stdout = sys.__stdout__

class SubProcessRunner:
    """A class to manage subprocess execution with logging and environment control.

    This class provides functionality to:
    - Run Python callables or shell commands as subprocesses
    - Configure environment variables for shell commands
    - Log process output to specified files
    - Control process lifecycle (start, stop, check status)
    """

    def __init__(self, log_file: str = None):
        """Initialize the SubProcessRunner.

        Args:
            log_file: Optional path to the log file. If not provided,
                     a temporary file will be created.
        """
        self.process: Optional[subprocess.Popen] = None
        self.log_file = log_file or tempfile.mktemp(prefix='subprocess_runner_')
        self.logger = logging.getLogger(__name__)

    def start(self, 
              target: Union[Callable, str], 
              env: Optional[Dict[str, str]] = None,
              shell: bool = False,
              **kwargs: Any) -> None:
        """Start a subprocess with the given target.

        Args:
            target: Either a Python callable or a shell command string
            env: Optional dictionary of environment variables
            shell: Whether to run the command in a shell (default: False)
            **kwargs: Additional arguments to pass to subprocess.Popen

        Raises:
            ValueError: If process is already running
            TypeError: If target type is invalid
        """
        if self.is_running():
            raise ValueError("Process is already running")

        if isinstance(target, str):
            # For shell commands
            with open(self.log_file, 'w') as log_file:
                log_file.write(SCHEDULER_LOG_DIVIDER)
                log_file.write(f"hostname: {socket.gethostname()}\n")
                log_file.write(f"username: {getpass.getuser()}\n")
                log_file.write(f"pid: {os.getpid()}\n")
                log_file.write(f"cwd: {os.getcwd()}\n")
                log_file.write(f"command: {target}\n")
                log_file.write(SCHEDULER_LOG_DIVIDER)
                log_file.flush()

                final_env = os.environ.copy()
                if env:
                    final_env.update(env)
                self.process = subprocess.Popen(
                    target,
                    shell=True,
                    env=final_env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    **kwargs
                )
        
        elif callable(target):
            # For Python callables
            logging.info(f"Starting Python callable: {target.__name__}")
            
            # Use multiprocessing for Python callables
            from multiprocessing import Process, Pipe
            parent_conn, child_conn = Pipe()
            
            # Serialize the function using dill
            serialized_func = dill.dumps(target)
            
            p = Process(target=_run_python_callable, args=(serialized_func, child_conn, self.log_file))
            p.start()
            self.process = p
            self.conn = parent_conn
        else:
            raise TypeError("Target must be either a callable or a string command")

    def stop(self) -> None:
        """Stop the currently running process.

        Raises:
            ValueError: If no process is running
        """
        if not self.is_running():
            raise ValueError("No process is running")

        self.process.terminate()
        try:
            self.process.wait(timeout=5)  # Wait up to 5 seconds for graceful termination
        except subprocess.TimeoutExpired:
            self.logger.warning("Process did not terminate gracefully, forcing...")
            self.process.kill()
            self.process.wait()

        self.process = None

    def is_running(self) -> bool:
        """Check if the process is currently running.

        Returns:
            bool: True if process is running, False otherwise
        """
        if self.process is None:
            return False
        if isinstance(self.process, subprocess.Popen):
            return self.process.poll() is None
        return self.process.is_alive()

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the process.

        Returns:
            Dict containing process status information including:
            - running: bool indicating if process is running
            - exit_code: int or None if still running
            - output: str containing process output
            - error: str containing process errors
        """
        status = {
            "running": self.is_running(),
            "exit_code": None,
            "output": "",
            "error": ""
        }

        if self.process:
            if isinstance(self.process, subprocess.Popen):
                if not self.is_running():
                    status["exit_code"] = self.process.returncode

                # Get output and error if available
                try:
                    output, error = self.process.communicate(timeout=0.1)
                    # Read log file contents
                    with open(self.log_file, 'r') as f:
                        status["output"] = f.read()
                    status["error"] = error
                except subprocess.TimeoutExpired:
                    # Process still running, don't consume output yet
                    pass
            else:  # multiprocessing.Process
                if not self.is_running():
                    status["exit_code"] = 0 if self.process.exitcode == 0 else 1
                if hasattr(self, 'conn'):
                    if self.conn.poll():
                        success, result = self.conn.recv()
                        if success:
                            status["output"] = str(result)
                        else:
                            status["error"] = str(result)

        return status