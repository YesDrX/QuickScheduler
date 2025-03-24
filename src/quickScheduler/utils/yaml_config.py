"""YamlConfig - A utility class for YAML configuration management.

This module provides a class for reading and managing YAML configuration files,
supporting environment variable substitution and comment preservation.
"""

import os
import re
from typing import Any, Dict, Optional, Union
from pathlib import Path

from ruamel.yaml import YAML


class YamlConfig:
    """A class to manage YAML configuration files with environment variable support.

    This class provides functionality to:
    - Load YAML configuration files with comment preservation
    - Substitute environment variables in the format ${EnvVarName}
    - Reload configurations from file
    - Access configuration values through dictionary-like interface
    - Track and monitor imported/included configuration files for changes
    """

    def __init__(self, config_file: Union[str, Path]):
        """Initialize the YamlConfig.

        Args:
            config_file: Path to the YAML configuration file
        """
        self.config_file = Path(config_file)
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.config_data = {}
        self.dependencies = {}
        
        if self.config_file.exists():
            self.reload()
        else:
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a file path that could be relative or absolute.

        Args:
            file_path: The file path to resolve

        Returns:
            The resolved Path object
        """
        path = Path(file_path)
        if path.is_absolute():
            return path
        else:
            # Resolve relative to the directory containing the current config file
            return self.config_file.parent / path

    def _import_config(self, file_path: str) -> Any:
        """Import another YAML config file as a value.

        Args:
            file_path: Path to the YAML file to import

        Returns:
            The loaded configuration data
        """
        resolved_path = self._resolve_path(file_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Imported configuration file not found: {resolved_path}")
        
        # Track this dependency
        self._track_dependency(resolved_path)
        
        # Create a new YamlConfig instance for the imported file
        imported_config = YamlConfig(resolved_path)
        return imported_config.config_data

    def _include_config(self, file_path: str) -> Dict[str, Any]:
        """Include another YAML config file and merge its contents.

        Args:
            file_path: Path to the YAML file to include

        Returns:
            The loaded configuration data as a dictionary
        """
        resolved_path = self._resolve_path(file_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Included configuration file not found: {resolved_path}")
        
        # Track this dependency
        self._track_dependency(resolved_path)
        
        # Load the included file directly
        yaml = YAML()
        with open(resolved_path, 'r') as f:
            included_data = yaml.load(f) or {}
        
        # Process the included data for environment variables and nested imports/includes
        return self._substitute_env_vars(included_data)

    def _substitute_env_vars(self, value: Any) -> Any:
        """Recursively substitute environment variables and handle imports/includes in configuration values.

        Args:
            value: The configuration value to process

        Returns:
            The processed value with environment variables substituted and imports/includes processed
        """
        if isinstance(value, str):
            # Handle environment variables: ${EnvVarName}
            env_pattern = r'\${([^}]+)}'
            env_matches = re.findall(env_pattern, value)
            
            result = value
            for env_var in env_matches:
                env_value = os.environ.get(env_var, '')
                result = result.replace(f"${{{env_var}}}", env_value)
            
            # Handle __import__(file_path) pattern
            import_pattern = r'__import__\(\s*([^)]+)\s*\)'
            import_match = re.search(import_pattern, result)
            if import_match and result.strip() == import_match.group(0):
                # If the entire string is an import directive
                file_path = import_match.group(1).strip().strip('\'"')
                return self._import_config(file_path)
            
            # Handle __include__(file_path) pattern
            include_pattern = r'__include__\(\s*([^)]+)\s*\)'
            include_match = re.search(include_pattern, result)
            if include_match and result.strip() == include_match.group(0):
                # If the entire string is an include directive
                file_path = include_match.group(1).strip().strip('\'"')
                return self._include_config(file_path)
            
            return result
        elif isinstance(value, dict):
            return {k: self._substitute_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._substitute_env_vars(item) for item in value]
        else:
            return value

    def _track_dependency(self, file_path: Path) -> None:
        """Track a dependency file and its last modification time.

        Args:
            file_path: Path to the dependency file
        """
        self.dependencies[str(file_path)] = file_path.stat().st_mtime

    def has_dependencies_changed(self) -> bool:
        """Check if any of the dependencies have changed since they were last loaded.

        Returns:
            True if any dependency has changed, False otherwise
        """
        for file_path_str, last_mtime in self.dependencies.items():
            file_path = Path(file_path_str)
            if file_path.exists() and file_path.stat().st_mtime > last_mtime:
                return True
        return False
        
    def has_config_file_changed(self) -> bool:
        """Check if the main configuration file has changed since it was last loaded.

        Returns:
            True if the main config file has changed, False otherwise
        """
        # The main config file should be in the dependencies dictionary
        config_file_str = str(self.config_file)
        if config_file_str in self.dependencies:
            last_mtime = self.dependencies[config_file_str]
            if self.config_file.exists() and self.config_file.stat().st_mtime > last_mtime:
                return True
        return False

    def reload(self) -> None:
        """Reload the configuration from the file.

        This method reloads the configuration data from the file and
        processes any environment variables.
        """
        # Clear dependencies before reloading
        self.dependencies = {}
        
        with open(self.config_file, 'r') as f:
            self.config_data = self.yaml.load(f) or {}
        
        # Track the main config file itself
        self._track_dependency(self.config_file)
        
        # Process environment variables in the loaded configuration
        self.config_data = self._substitute_env_vars(self.config_data)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.

        Args:
            key: The configuration key
            default: Default value to return if key is not found

        Returns:
            The configuration value or default if not found
        """
        return self.config_data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Get a configuration value using dictionary-like access.

        Args:
            key: The configuration key

        Returns:
            The configuration value

        Raises:
            KeyError: If the key is not found in the configuration
        """
        return self.config_data[key]

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the configuration.

        Args:
            key: The configuration key

        Returns:
            True if the key exists, False otherwise
        """
        return key in self.config_data
        
    def check_and_reload_if_needed(self) -> bool:
        """Check if any dependencies have changed and reload if necessary.
        
        This method checks if the main configuration file or any of the imported or included 
        configuration files have changed since they were last loaded, and reloads the 
        configuration if needed.
        
        Returns:
            True if the configuration was reloaded, False otherwise
        """
        if self.has_dependencies_changed() or self.has_config_file_changed():
            self.reload()
            return True
        return False