"""Utility functions for datetime parsing and timezone handling.

This module provides functions for:
1. Parsing datetime strings in various formats
2. Converting between UTC and local timezones
"""
from datetime import datetime, date, time, timedelta
from click import Option
import pytz
from typing import Optional, Union
from tzlocal import get_localzone

def parse_time(time_str : str, format : Optional[list[str]] = None) -> time:
    """Parse a time string using specified formats.

    Args:
        time_str: The time string to parse
        format: List of format strings to try. If None, uses default formats.
    Returns:
        time: Parsed time object
    Raises:
        ValueError: If time_str cannot be parsed with any format
    """
    if format is None:
        format = [
            "%H:%M:%S",  # 13:45:30
            "%H:%M",  # 13:45
            "%H:%M:%S.%f",  # 13:45:30.123456
        ]
    for fmt in format:
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Could not parse time string '{time_str}' with any of the formats: {format}")


def parse_timedelta(timedelta_str: str) -> timedelta:
    """Parse a timedelta string."""
    parts = timedelta_str.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = map(float, parts)
        return timedelta(hours=hours, minutes=minutes, seconds=seconds)
    elif len(parts) == 2:
        minutes, seconds = map(float, parts)
        return timedelta(minutes=minutes, seconds=seconds)
    elif len(parts) == 1:
        seconds = float(parts[0])
        return timedelta(seconds=seconds)
    else:
        raise ValueError(f"Invalid timedelta format: {timedelta_str}")


def parse_datetime(datetime_str: str, formats: Optional[list[str]] = None) -> datetime:
    """Parse a datetime string using specified formats.
    
    Args:
        datetime_str: The datetime string to parse
        formats: List of format strings to try. If None, uses default formats.
        
    Returns:
        datetime: Parsed datetime object
        
    Raises:
        ValueError: If datetime_str cannot be parsed with any format
    """
    if formats is None:
        formats = [
            "%Y-%m-%d %H:%M:%S",  # 2023-12-25 13:45:30
            "%Y-%m-%dT%H:%M:%S",  # 2023-12-25T13:45:30
            "%Y-%m-%dT%H:%M:%S.%f",  # 2023-12-25T13:45:30.123456
            "%Y-%m-%dT%H:%M:%S.%fZ",  # 2023-12-25T13:45:30.123456Z
            "%Y-%m-%dT%H:%M:%S%z",  # 2023-12-25T13:45:30+0000
            "%Y-%m-%d",  # 2023-12-25
        ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
            
    raise ValueError(
        f"Could not parse datetime string '{datetime_str}' with any of the formats: {formats}"
    )

def parse_date(date_str : str, formats : Optional[list[str]] = None) -> date:
    """Parse a date string using specified formats.

    Args:
        date_str: The date string to parse
        formats: List of format strings to try. If None, uses default formats.
    Returns:
        date: Parsed date object
    Raises:
        ValueError: If date_str cannot be parsed with any format
    """
    if formats is None:
        formats = [
            "%Y-%m-%d",  # 2023-12-25
            "%Y%m%d"
        ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse date string '{date_str}' with any of the formats: {formats}")

def convert_to_local(dt: Union[datetime, str], timezone: str = "UTC") -> datetime:
    """Convert a UTC datetime to local time.
    
    Args:
        dt: Datetime object or string to convert
        timezone: Target timezone name (e.g. 'America/New_York', 'Asia/Shanghai')
        
    Returns:
        datetime: Datetime in local timezone
        
    Raises:
        pytz.exceptions.UnknownTimeZoneError: If timezone name is invalid
        ValueError: If dt is a string and cannot be parsed
    """
    if isinstance(dt, str):
        dt = parse_datetime(dt)
        
    # If datetime is naive, assume it's UTC
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    target_tz = pytz.timezone(timezone)
    return dt.astimezone(target_tz)

def get_local_timezone() -> str:
    """Get the local timezone name.

    Returns:
        str: Local timezone name (e.g. 'America/New_York', 'Asia/Shanghai')
    """
    return str(get_localzone())