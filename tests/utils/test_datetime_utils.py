"""Test cases for datetime utility functions.

Tests parsing of datetime strings and timezone conversions.
"""
import pytest
from datetime import datetime
import pytz
from quickScheduler.utils.datetime_utils import parse_datetime, convert_to_local


def test_parse_datetime_default_formats():
    """Test parsing datetime strings using default formats."""
    # Test standard format
    dt = parse_datetime("2023-12-25 13:45:30")
    assert dt.year == 2023
    assert dt.month == 12
    assert dt.day == 25
    assert dt.hour == 13
    assert dt.minute == 45
    assert dt.second == 30
    
    # Test ISO format
    dt = parse_datetime("2023-12-25T13:45:30")
    assert dt.year == 2023
    assert dt.hour == 13
    
    # Test with microseconds
    dt = parse_datetime("2023-12-25T13:45:30.123456")
    assert dt.microsecond == 123456
    
    # Test with UTC Z suffix
    dt = parse_datetime("2023-12-25T13:45:30.123456Z")
    assert dt.microsecond == 123456
    
    # Test with timezone offset
    dt = parse_datetime("2023-12-25T13:45:30+0000")
    assert dt.hour == 13
    
    # Test date only
    dt = parse_datetime("2023-12-25")
    assert dt.year == 2023
    assert dt.hour == 0
    assert dt.minute == 0


def test_parse_datetime_custom_formats():
    """Test parsing datetime strings using custom formats."""
    custom_formats = [
        "%m/%d/%Y %H:%M",  # 12/25/2023 13:45
        "%d-%b-%Y",  # 25-Dec-2023
    ]
    
    dt = parse_datetime("12/25/2023 13:45", formats=custom_formats)
    assert dt.year == 2023
    assert dt.month == 12
    assert dt.day == 25
    assert dt.hour == 13
    assert dt.minute == 45
    
    dt = parse_datetime("25-Dec-2023", formats=custom_formats)
    assert dt.year == 2023
    assert dt.month == 12
    assert dt.day == 25


def test_parse_datetime_invalid():
    """Test parsing invalid datetime strings."""
    with pytest.raises(ValueError):
        parse_datetime("invalid-date")
    
    with pytest.raises(ValueError):
        parse_datetime("2023-13-45")  # Invalid month
    
    with pytest.raises(ValueError):
        parse_datetime("2023/12/25")  # Unsupported format


def test_convert_to_local_from_utc():
    """Test converting UTC datetime to local timezone."""
    # Create a UTC datetime
    utc_dt = datetime(2023, 12, 25, 13, 45, 30, tzinfo=pytz.UTC)
    
    # Convert to New York time
    ny_dt = convert_to_local(utc_dt, "America/New_York")
    assert ny_dt.tzinfo.zone == "America/New_York"
    
    # Convert to Shanghai time
    sh_dt = convert_to_local(utc_dt, "Asia/Shanghai")
    assert sh_dt.tzinfo.zone == "Asia/Shanghai"


def test_convert_to_local_from_string():
    """Test converting datetime string to local timezone."""
    dt_str = "2023-12-25T13:45:30Z"
    ny_dt = convert_to_local(dt_str, "America/New_York")
    assert ny_dt.tzinfo.zone == "America/New_York"


def test_convert_to_local_naive_datetime():
    """Test converting naive datetime to local timezone."""
    naive_dt = datetime(2023, 12, 25, 13, 45, 30)
    ny_dt = convert_to_local(naive_dt, "America/New_York")
    assert ny_dt.tzinfo.zone == "America/New_York"


def test_convert_to_local_invalid_timezone():
    """Test converting to invalid timezone."""
    dt = datetime(2023, 12, 25, 13, 45, 30, tzinfo=pytz.UTC)
    with pytest.raises(pytz.exceptions.UnknownTimeZoneError):
        convert_to_local(dt, "Invalid/Timezone")