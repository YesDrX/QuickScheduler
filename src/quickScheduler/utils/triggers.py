import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, time, date, timedelta
from enum import Enum
from typing import Optional, Set, List, Union
import pytz
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Dict
from quickScheduler.utils.datetime_utils import parse_time, parse_timedelta, parse_date

class _GlobalCalendarFileLoader:
    _all_calendars = {}
    @classmethod
    def load(cls, calendar_file : str):
        if calendar_file and os.path.exists(calendar_file):
            if calendar_file not in cls._all_calendars:
                logging.info(f"loading calendar file :{calendar_file}")
                with open(calendar_file, 'r') as file:
                    dates = file.readlines()
                cls._all_calendars[calendar_file] = [parse_date(date_str.strip()) for date_str in dates]
            return cls._all_calendars[calendar_file]

class TriggerType(str, Enum):
    IMMEDIATE = "immediate"
    DAILY = "daily"
    INTERVAL = "interval"

class TriggerConfig(BaseModel):
    timezone: Optional[str] = "UTC"
    run_time: Optional[time] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    interval: Optional[timedelta] = None
    weekdays: Set[int] = Field(default_factory=lambda: {1, 2, 3, 4, 5, 6, 7})
    dates: Optional[List[date]] = None
    calendar_file: Optional[str] = None
    
    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v):
        if v not in pytz.all_timezones:
            raise ValueError(f"Invalid timezone: {v}")
        return v
    
    @field_validator('weekdays')
    @classmethod
    def validate_weekdays(cls, v):
        for day in v:
            if day not in range(1, 8):
                raise ValueError(f"Weekdays must be between 1 and 7, got {day}")
        return v
    
    @model_validator(mode='after')
    def validate_model(self):
        # Validate interval and time settings
        if self.start_time is not None and self.interval is None:
            raise ValueError("Interval must be provided if start_time is set")
        
        if self.start_time is not None and self.end_time is None:
            raise ValueError("End time must be provided if start_time is set")
        
        if self.end_time is not None and self.start_time is not None and self.end_time < self.start_time:
            raise ValueError("End time must be after start time")
        
        return self

    @field_validator('run_time', 'start_time', 'end_time', mode='before')
    @classmethod
    def parse_time_fields(cls, v):
        if isinstance(v, str):
            return parse_time(v)
        return v

    @field_validator('interval', mode='before')
    @classmethod
    def parse_interval_field(cls, v):
        if isinstance(v, str):
            return parse_timedelta(v)
        return v
    
    @field_validator('calendar_file', mode='before')
    @classmethod
    def parse_calendar_file_field(cls, v):
        if isinstance(v, str) and os.path.exists(v):
            _GlobalCalendarFileLoader.load(v)
            return v
        return None
    
    @field_validator('dates', mode='before')
    @classmethod
    def parse_dates_field(cls, v):
        return [parse_date(date_str) if isinstance(date_str, str) else date_str for date_str in v]
    
    def get_dates(self):
        rst = getattr(self, "dates", None)
        if rst is None and self.calendar_file is not None:
            rst = _GlobalCalendarFileLoader.load(self.calendar_file)
        return rst

class BaseTrigger(ABC):
    def __init__(self, trigger_type: TriggerType, config: Optional[TriggerConfig]):
        self.trigger_type = trigger_type
        self.config = config
        self._validate_config()
    
    def _validate_config(self):
        """Validate that the config matches the trigger type requirements"""
        pass
    
    @abstractmethod
    def get_next_run(self, now: Optional[datetime] = None) -> Optional[datetime]:
        """
        Get the next run time in UTC
        
        Args:
            now: Optional datetime in UTC to use as the reference point.
                 If None, the current time will be used.
        
        Returns:
            Optional[datetime]: The next run time in UTC, or None if there is no next run
        """
        pass
    
    def should_run(self, dt: datetime, now : Optional[datetime] = None) -> bool:
        """Determine if the trigger should run at the given datetime (in UTC)"""
        next_run = self.get_next_run(now)
        if next_run is None:
            return False
        
        # Convert to seconds precision for comparison
        dt_seconds = dt.replace(microsecond=0)
        next_run_seconds = next_run.replace(microsecond=0)
        
        # For immediate trigger, allow exact match or very small tolerance
        if isinstance(self, ImmediateTrigger):
            time_diff = abs((dt_seconds - next_run_seconds).total_seconds())
            return time_diff <= 1
        
        # For scheduled triggers (Daily/Interval), check if we're at the scheduled time
        # with a 5-second tolerance window
        time_diff = abs((dt_seconds - next_run_seconds).total_seconds())
        return time_diff <= 5

class ImmediateTrigger(BaseTrigger):
    """A trigger that fires immediately, but only once"""
    
    def __init__(self, trigger_type: TriggerType, config: Optional[TriggerConfig]):
        super().__init__(trigger_type, config)
        self._has_triggered = False
    
    def _validate_config(self):
        if self.trigger_type != TriggerType.IMMEDIATE:
            raise ValueError(f"Expected trigger type immediate, got {self.trigger_type}")
    
    def get_next_run(self, now: Optional[datetime] = None) -> Optional[datetime]:
        if self._has_triggered:
            return None
        self._has_triggered = True
        return now if now is not None else datetime.now(pytz.UTC)

class DailyTrigger(BaseTrigger):
    """A trigger that fires at a specific time each day, filtered by weekdays and dates"""
    
    def __init__(self, trigger_type: TriggerType, config: TriggerConfig):
        super().__init__(trigger_type, config)
    
    def _validate_config(self):
        if self.trigger_type != TriggerType.DAILY:
            raise ValueError(f"Expected trigger type daily, got {self.trigger_type}")
        if self.config.run_time is None:
            raise ValueError("Run time must be provided for daily trigger")
    
    def get_next_run(self, now: Optional[datetime] = None) -> Optional[datetime]:
        # Use provided now or get current time
        if now is None:
            now = datetime.now(pytz.UTC)
        elif not now.tzinfo or now.tzinfo.utcoffset(now) is None:
            # Ensure now is timezone-aware and in UTC
            now = pytz.UTC.localize(now)
        
        # Convert to the specified timezone
        tz = pytz.timezone(self.config.timezone)
        now_local = now.astimezone(tz)
        
        # Create a datetime with today's date and the configured run time
        run_dt_local = datetime.combine(now_local.date(), self.config.run_time)
        run_dt_local = tz.localize(run_dt_local)
        
        # If the run time has already passed today, start from tomorrow
        if run_dt_local <= now_local:
            next_date = now_local.date() + timedelta(days=1)
        else:
            next_date = now_local.date()
        
        # Find the next valid date according to weekdays and dates filters
        max_days_to_check = 366  # Check up to a year ahead
        config_dates = self.config.get_dates()
        for _ in range(max_days_to_check):
            # Check if the day of the week is in the allowed weekdays
            weekday = next_date.isoweekday()  # 1 for Monday, 7 for Sunday
            
            # Check if the date is in the allowed dates (if dates filter is provided)
            date_valid = config_dates is None or next_date in config_dates
            
            if weekday in self.config.weekdays and date_valid:
                # Found a valid date
                run_dt_local = datetime.combine(next_date, self.config.run_time)
                run_dt_local = tz.localize(run_dt_local)
                return run_dt_local.astimezone(pytz.UTC)
            
            next_date += timedelta(days=1)
        
        # If no valid date found within a year, return None
        return None

class IntervalTrigger(BaseTrigger):
    """A trigger that fires at regular intervals between a start and end time each day"""
    
    def __init__(self, trigger_type: TriggerType, config: TriggerConfig):
        super().__init__(trigger_type, config)

    
    def _validate_config(self):
        if self.trigger_type != TriggerType.INTERVAL:
            raise ValueError(f"Expected trigger type interval, got {self.trigger_type}")
        if self.config.start_time is None:
            raise ValueError("Start time must be provided for interval trigger")
        if self.config.end_time is None:
            raise ValueError("End time must be provided for interval trigger")
        if self.config.interval is None:
            raise ValueError("Interval must be provided for interval trigger")
    
    def get_next_run(self, now: Optional[datetime] = None) -> Optional[datetime]:
        # Use provided now or get current time
        if now is None:
            now = datetime.now(pytz.UTC)
        elif not now.tzinfo or now.tzinfo.utcoffset(now) is None:
            # Ensure now is timezone-aware and in UTC
            now = pytz.UTC.localize(now)
        
        # Convert to the specified timezone
        tz = pytz.timezone(self.config.timezone)
        now_local = now.astimezone(tz)
        
        # Find the next valid date according to weekdays filter
        current_date = now_local.date()
        max_days_to_check = 366  # Check up to a year ahead
        config_dates = self.config.get_dates()

        valid_date = False
        for _ in range(max_days_to_check):
            weekday = current_date.isoweekday()
            valid_date = (config_dates is None or current_date in config_dates) and weekday in self.config.weekdays
            if valid_date: break
            current_date += timedelta(days=1)
        if not valid_date: return None

        # Create datetime objects for today's start and end times
        for _ in range(max_days_to_check):
            weekday = current_date.isoweekday()
            valid_date = (config_dates is None or current_date in config_dates) and weekday in self.config.weekdays
            if not valid_date:
                current_date += timedelta(days=1)
                continue
            
            start_dt_local = datetime.combine(current_date, self.config.start_time)
            start_dt_local = tz.localize(start_dt_local)
            end_dt_local   = datetime.combine(current_date, self.config.end_time)
            end_dt_local   = tz.localize(end_dt_local)
            
            # If we're before the start time, return the start time
            if now_local < start_dt_local:
                return start_dt_local.astimezone(pytz.UTC)
            
            # If we're between start and end time, find the next interval
            if now_local < end_dt_local:
                # Calculate how many intervals have passed
                time_since_start = now_local - start_dt_local
                intervals_passed = time_since_start // self.config.interval
                next_interval    = intervals_passed + 1
                
                # Calculate the next run time
                next_run_local   = start_dt_local + (next_interval * self.config.interval)
                
                # If the next run is still before the end time, return it
                if next_run_local <= end_dt_local:
                    return next_run_local.astimezone(pytz.UTC)
                
            # Move to the next day
            current_date += timedelta(days=1)
        
        # If no valid time found within a year, return None
        return None

def build_trigger(trigger_type : Any, trigger_config : Optional[Dict] = None):
    if str(trigger_type).lower() == TriggerType.IMMEDIATE:
        return ImmediateTrigger(TriggerType.IMMEDIATE, None)
    elif str(trigger_type).lower() == TriggerType.DAILY:
        assert trigger_config is not None, f"trigger_config must be provided for trigger type {trigger_type}"
        return DailyTrigger(TriggerType.DAILY, TriggerConfig(**trigger_config))
    elif str(trigger_type).lower() == TriggerType.INTERVAL:
        assert trigger_config is not None, f"trigger_config must be provided for trigger type {trigger_type}"
        return IntervalTrigger(TriggerType.INTERVAL, TriggerConfig(**trigger_config))
    else:
        raise ValueError(f"Unknown trigger type: {trigger_type}")