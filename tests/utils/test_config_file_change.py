"""Unit tests for the YamlConfig file change detection functionality.

This module contains tests for the YamlConfig class's ability to detect changes
in both the main configuration file and its dependencies.
"""

import os
import time
import tempfile
from pathlib import Path
from quickScheduler.utils.yaml_config import YamlConfig


def test_has_config_file_changed():
    """Test detection of changes in the main configuration file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("key: original_value\n")
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert not config.has_config_file_changed(), "New file should not be detected as changed"
        
        # Ensure file modification time will be different
        time.sleep(0.1)
        
        # Modify the file
        with open(temp_path, 'w') as f:
            f.write("key: updated_value\n")
        
        assert config.has_config_file_changed(), "Modified file should be detected as changed"
    finally:
        os.unlink(temp_path)


def test_check_and_reload_if_needed_for_main_file():
    """Test automatic reload when main configuration file changes."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("key: original_value\n")
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert config["key"] == "original_value"
        
        # Ensure file modification time will be different
        time.sleep(0.1)
        
        # Modify the file
        with open(temp_path, 'w') as f:
            f.write("key: updated_value\n")
        
        # Check and reload if needed
        reloaded = config.check_and_reload_if_needed()
        assert reloaded, "Configuration should have been reloaded"
        assert config["key"] == "updated_value", "Updated value should be loaded"
    finally:
        os.unlink(temp_path)