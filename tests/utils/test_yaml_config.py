"""Unit tests for the YamlConfig class.

This module contains comprehensive tests for the YamlConfig class,
covering file loading, environment variable substitution, and reload functionality.
"""

import os
import pytest
import tempfile
from pathlib import Path
from quickScheduler.utils.yaml_config import YamlConfig


def test_basic_loading():
    """Test basic YAML file loading."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("key1: value1\nkey2: value2\n")
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert config["key1"] == "value1"
        assert config["key2"] == "value2"
    finally:
        os.unlink(temp_path)


def test_env_var_substitution():
    """Test environment variable substitution in YAML values."""
    # Set test environment variables
    os.environ["TEST_VAR1"] = "test_value1"
    os.environ["TEST_VAR2"] = "test_value2"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("key1: ${TEST_VAR1}\nkey2: prefix_${TEST_VAR2}_suffix\n")
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert config["key1"] == "test_value1"
        assert config["key2"] == "prefix_test_value2_suffix"
    finally:
        os.unlink(temp_path)


def test_nested_env_vars():
    """Test environment variable substitution in nested structures."""
    os.environ["NESTED_VAR"] = "nested_value"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("""
        parent:
          child1: ${NESTED_VAR}
          child2:
            - item1
            - ${NESTED_VAR}
            - item3
        """)
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert config["parent"]["child1"] == "nested_value"
        assert config["parent"]["child2"][1] == "nested_value"
    finally:
        os.unlink(temp_path)


def test_missing_env_var():
    """Test behavior with missing environment variables."""
    # Ensure the environment variable doesn't exist
    if "NONEXISTENT_VAR" in os.environ:
        del os.environ["NONEXISTENT_VAR"]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("key: ${NONEXISTENT_VAR}\n")
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert config["key"] == ""
    finally:
        os.unlink(temp_path)


def test_reload():
    """Test configuration reload functionality."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("key: original_value\n")
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert config["key"] == "original_value"
        
        # Modify the file and reload
        with open(temp_path, 'w') as f:
            f.write("key: updated_value\n")
        
        config.reload()
        assert config["key"] == "updated_value"
    finally:
        os.unlink(temp_path)


def test_get_with_default():
    """Test get method with default values."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("key1: value1\n")
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert config.get("key1") == "value1"
        assert config.get("nonexistent_key") is None
        assert config.get("nonexistent_key", "default_value") == "default_value"
    finally:
        os.unlink(temp_path)


def test_contains():
    """Test __contains__ method."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("key1: value1\n")
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert "key1" in config
        assert "nonexistent_key" not in config
    finally:
        os.unlink(temp_path)


def test_file_not_found():
    """Test behavior when configuration file is not found."""
    nonexistent_path = "/nonexistent/path/config.yaml"
    with pytest.raises(FileNotFoundError):
        YamlConfig(nonexistent_path)


def test_comment_preservation():
    """Test that comments in YAML files are preserved."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        temp.write("""
        # This is a comment
        key1: value1  # Inline comment
        key2: value2
        """)
        temp_path = temp.name

    try:
        config = YamlConfig(temp_path)
        assert config["key1"] == "value1"
        assert config["key2"] == "value2"
        
        # The test passes if no exceptions are raised,
        # as we're mainly testing that comments don't break parsing
    finally:
        os.unlink(temp_path)