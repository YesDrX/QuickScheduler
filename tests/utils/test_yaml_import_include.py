"""Unit tests for the YamlConfig import and include functionality.

This module contains tests for the YamlConfig class's ability to import
and include other YAML configuration files.
"""

import os
import pytest
import tempfile
from pathlib import Path
from quickScheduler.utils.yaml_config import YamlConfig


def test_import_absolute_path():
    """Test importing a YAML file using an absolute path."""
    # Create the file to be imported
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as import_temp:
        import_temp.write("imported_key: imported_value\n")
        import_path = import_temp.name
    
    # Create the main config file that imports the other file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as main_temp:
        main_temp.write(f"import_result: __import__({import_path})\n")
        main_path = main_temp.name
    
    try:
        config = YamlConfig(main_path)
        assert "import_result" in config
        assert config["import_result"]["imported_key"] == "imported_value"
    finally:
        os.unlink(import_path)
        os.unlink(main_path)


def test_import_relative_path():
    """Test importing a YAML file using a relative path."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create the file to be imported
        import_path = Path(temp_dir) / "imported.yaml"
        with open(import_path, 'w') as f:
            f.write("imported_key: imported_value\n")
        
        # Create the main config file that imports the other file
        main_path = Path(temp_dir) / "main.yaml"
        with open(main_path, 'w') as f:
            f.write("import_result: __import__(imported.yaml)\n")
        
        config = YamlConfig(main_path)
        assert "import_result" in config
        assert config["import_result"]["imported_key"] == "imported_value"


def test_include_absolute_path():
    """Test including a YAML file using an absolute path."""
    # Create the file to be included
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as include_temp:
        include_temp.write("included_key: included_value\n")
        include_path = include_temp.name
    
    # Create the main config file that includes the other file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as main_temp:
        main_temp.write(f"include_result: __include__({include_path})\n")
        main_path = main_temp.name
    
    try:
        config = YamlConfig(main_path)
        assert "include_result" in config
        assert config["include_result"]["included_key"] == "included_value"
    finally:
        os.unlink(include_path)
        os.unlink(main_path)


def test_include_relative_path():
    """Test including a YAML file using a relative path."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create the file to be included
        include_path = Path(temp_dir) / "included.yaml"
        with open(include_path, 'w') as f:
            f.write("included_key: included_value\n")
        
        # Create the main config file that includes the other file
        main_path = Path(temp_dir) / "main.yaml"
        with open(main_path, 'w') as f:
            f.write("include_result: __include__(included.yaml)\n")
        
        config = YamlConfig(main_path)
        assert "include_result" in config
        assert config["include_result"]["included_key"] == "included_value"


def test_nested_import():
    """Test nested imports in YAML files."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create the deepest file to be imported
        deep_path = Path(temp_dir) / "deep.yaml"
        with open(deep_path, 'w') as f:
            f.write("deep_key: deep_value\n")
        
        # Create the middle file that imports the deep file
        middle_path = Path(temp_dir) / "middle.yaml"
        with open(middle_path, 'w') as f:
            f.write("middle_key: middle_value\nmiddle_import: __import__(deep.yaml)\n")
        
        # Create the main config file that imports the middle file
        main_path = Path(temp_dir) / "main.yaml"
        with open(main_path, 'w') as f:
            f.write("main_key: main_value\nmain_import: __import__(middle.yaml)\n")
        
        config = YamlConfig(main_path)
        assert config["main_key"] == "main_value"
        assert config["main_import"]["middle_key"] == "middle_value"
        assert config["main_import"]["middle_import"]["deep_key"] == "deep_value"


def test_env_vars_in_imported_file():
    """Test environment variable substitution in imported files."""
    os.environ["IMPORT_TEST_VAR"] = "import_test_value"
    
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create the file to be imported with env vars
        import_path = Path(temp_dir) / "imported.yaml"
        with open(import_path, 'w') as f:
            f.write("env_key: ${IMPORT_TEST_VAR}\n")
        
        # Create the main config file that imports the other file
        main_path = Path(temp_dir) / "main.yaml"
        with open(main_path, 'w') as f:
            f.write("import_result: __import__(imported.yaml)\n")
        
        config = YamlConfig(main_path)
        assert config["import_result"]["env_key"] == "import_test_value"


def test_file_not_found_import():
    """Test behavior when imported file is not found."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as main_temp:
        main_temp.write("import_result: __import__(nonexistent.yaml)\n")
        main_path = main_temp.name
    
    try:
        with pytest.raises(FileNotFoundError):
            YamlConfig(main_path)
    finally:
        os.unlink(main_path)


def test_file_not_found_include():
    """Test behavior when included file is not found."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as main_temp:
        main_temp.write("include_result: __include__(nonexistent.yaml)\n")
        main_path = main_temp.name
    
    try:
        with pytest.raises(FileNotFoundError):
            YamlConfig(main_path)
    finally:
        os.unlink(main_path)