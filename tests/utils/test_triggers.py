"""Test cases for the triggers module.
Tests the different trigger types (Immediate, Daily, Interval) and their functionality.
"""
import pytest
from datetime import datetime, time, date, timedelta
import pytz
from quickScheduler.utils.triggers import (
    TriggerType, TriggerConfig, BaseTrigger,
    ImmediateTrigger, DailyTrigger, IntervalTrigger
)


# Fixtures for common test data
@pytest.fixture
def utc_timezone():
    return "UTC"


@pytest.fixture
def ny_timezone():
    return "America/New_York"


@pytest.fixture
def tokyo_timezone():
    return "Asia/Tokyo"


@pytest.fixture
def basic_config():
    return TriggerConfig()


@pytest.fixture
def daily_config(utc_timezone):
    return TriggerConfig(
        timezone=utc_timezone,
        run_time=time(12, 0, 0),  # Noon UTC
    )


@pytest.fixture
def interval_config(utc_timezone):
    return TriggerConfig(
        timezone=utc_timezone,
        start_time=time(9, 0, 0),  # 9 AM
        end_time=time(17, 0, 0),   # 5 PM
        interval=timedelta(hours=1)  # Every hour
    )

@pytest.fixture
def interval_config_with_dates(utc_timezone):
    return TriggerConfig(
        timezone=utc_timezone,
        start_time=time(9, 0, 0),  # 9 AM
        end_time=time(17, 0, 0),   # 5 PM
        interval=timedelta(hours=1),  # Every hour
        dates=[date(2023, 1, 1), date(2023, 1, 3)]
    )


@pytest.fixture
def weekday_config(utc_timezone):
    return TriggerConfig(
        timezone=utc_timezone,
        run_time=time(12, 0, 0),  # Noon UTC
        weekdays={1, 2, 3, 4, 5}  # Monday to Friday
    )


@pytest.fixture
def specific_dates_config(utc_timezone):
    today = date.today()
    return TriggerConfig(
        timezone=utc_timezone,
        run_time=time(12, 0, 0),  # Noon UTC
        dates=[today, today + timedelta(days=1), today + timedelta(days=7)]
    )


# Test TriggerConfig validation
class TestTriggerConfig:
    def test_timezone_validation(self):
        # Valid timezone
        config = TriggerConfig(timezone="UTC")
        assert config.timezone == "UTC"
        
        # Invalid timezone
        with pytest.raises(ValueError, match="Invalid timezone"):
            TriggerConfig(timezone="Invalid/Timezone")
    
    def test_weekdays_validation(self):
        # Valid weekdays
        config = TriggerConfig(weekdays={1, 2, 3})
        assert config.weekdays == {1, 2, 3}
        
        # Invalid weekday
        with pytest.raises(ValueError, match="Weekdays must be between 1 and 7"):
            TriggerConfig(weekdays={0, 1, 2})
        
        with pytest.raises(ValueError, match="Weekdays must be between 1 and 7"):
            TriggerConfig(weekdays={1, 2, 8})
    
    def test_interval_validation(self):
        # Valid configuration
        config = TriggerConfig(
            start_time=time(9, 0),
            end_time=time(17, 0),
            interval=timedelta(hours=1)
        )
        assert config.start_time == time(9, 0)
        assert config.end_time == time(17, 0)
        assert config.interval == timedelta(hours=1)
        
        # Missing interval
        with pytest.raises(ValueError, match="Interval must be provided"):
            TriggerConfig(start_time=time(9, 0), end_time=time(17, 0))
        
        # Missing end_time
        with pytest.raises(ValueError, match="End time must be provided"):
            TriggerConfig(start_time=time(9, 0), interval=timedelta(hours=1))
        
        # End time before start time
        with pytest.raises(ValueError, match="End time must be after start time"):
            TriggerConfig(
                start_time=time(17, 0),
                end_time=time(9, 0),
                interval=timedelta(hours=1)
            )


# Test ImmediateTrigger
class TestImmediateTrigger:
    def test_initialization(self, basic_config):
        trigger = ImmediateTrigger(TriggerType.IMMEDIATE, basic_config)
        assert trigger.trigger_type == TriggerType.IMMEDIATE
        assert trigger.config == basic_config
    
    def test_invalid_trigger_type(self, basic_config):
        with pytest.raises(ValueError, match="Expected trigger type immediate"):
            ImmediateTrigger(TriggerType.DAILY, basic_config)
    
    def test_get_next_run(self, basic_config):
        trigger = ImmediateTrigger(TriggerType.IMMEDIATE, basic_config)
        
        # First call should return the current time
        now = datetime.now(pytz.UTC)
        next_run = trigger.get_next_run(now)
        assert next_run == now
        
        # Subsequent calls should return None
        assert trigger.get_next_run(now) is None
    
    def test_should_run(self, basic_config):
        trigger = ImmediateTrigger(TriggerType.IMMEDIATE, basic_config)
        
        # Should run at the current time
        now = datetime.now(pytz.UTC)
        assert trigger.should_run(now) is True
        
        # Should not run after the first time
        assert trigger.should_run(now) is False


# Test DailyTrigger
class TestDailyTrigger:
    def test_initialization(self, daily_config):
        trigger = DailyTrigger(TriggerType.DAILY, daily_config)
        assert trigger.trigger_type == TriggerType.DAILY
        assert trigger.config == daily_config
    
    def test_invalid_trigger_type(self, daily_config):
        with pytest.raises(ValueError, match="Expected trigger type daily"):
            DailyTrigger(TriggerType.IMMEDIATE, daily_config)
    
    def test_missing_run_time(self, basic_config):
        with pytest.raises(ValueError, match="Run time must be provided"):
            DailyTrigger(TriggerType.DAILY, basic_config)
    
    def test_get_next_run_same_day(self, daily_config):
        trigger = DailyTrigger(TriggerType.DAILY, daily_config)
        
        # Test with a time before the run time
        now = datetime(2023, 1, 1, 10, 0, 0, tzinfo=pytz.UTC)  # 10 AM
        next_run = trigger.get_next_run(now)
        
        expected = datetime(2023, 1, 1, 12, 0, 0, tzinfo=pytz.UTC)  # Noon
        assert next_run == expected
    
    def test_get_next_run_next_day(self, daily_config):
        trigger = DailyTrigger(TriggerType.DAILY, daily_config)
        
        # Test with a time after the run time
        now = datetime(2023, 1, 1, 14, 0, 0, tzinfo=pytz.UTC)  # 2 PM
        next_run = trigger.get_next_run(now)
        
        expected = datetime(2023, 1, 2, 12, 0, 0, tzinfo=pytz.UTC)  # Noon next day
        assert next_run == expected
    
    def test_weekday_filtering(self, weekday_config):
        trigger = DailyTrigger(TriggerType.DAILY, weekday_config)
        
        # Test with a Saturday (not in weekdays)
        saturday = datetime(2023, 1, 7, 10, 0, 0, tzinfo=pytz.UTC)  # Saturday
        next_run = trigger.get_next_run(saturday)
        
        # Should skip to Monday
        expected = datetime(2023, 1, 9, 12, 0, 0, tzinfo=pytz.UTC)  # Monday noon
        assert next_run == expected
    
    def test_date_filtering(self, specific_dates_config):
        trigger = DailyTrigger(TriggerType.DAILY, specific_dates_config)
        
        # Get today's date
        today = date.today()
        now = datetime.combine(today, time(10, 0, 0), tzinfo = pytz.UTC)
        run_time = datetime.combine(today, time(12, 0, 0), tzinfo = pytz.UTC)
        assert trigger.should_run(run_time, now) is True

        # Test with a date not in the allowed dates
        invalid_date = today + timedelta(days=2)  # Not in the dates list
        now = datetime.combine(invalid_date, time(10, 0, 0), tzinfo = pytz.UTC)
        next_run = trigger.get_next_run(now)
        
        # Should skip to the next valid date (today + 7 days)
        expected_date = today + timedelta(days=7)
        expected = datetime.combine(expected_date, time(12, 0, 0))
        expected = pytz.UTC.localize(expected)
        
        assert next_run == expected
    
    def test_timezone_handling(self, ny_timezone):
        # Create a config with New York timezone
        config = TriggerConfig(
            timezone=ny_timezone,
            run_time=time(12, 0, 0),  # Noon NY time
        )
        
        trigger = DailyTrigger(TriggerType.DAILY, config)
        
        # Test with a UTC time
        now = datetime(2023, 1, 1, 15, 0, 0, tzinfo=pytz.UTC)  # 3 PM UTC (10 AM NY)
        next_run = trigger.get_next_run(now)
        
        # Expected: Noon NY time converted to UTC
        ny_tz = pytz.timezone(ny_timezone)
        expected_local = datetime.combine(date(2023, 1, 1), time(12, 0, 0))
        expected_local = ny_tz.localize(expected_local)
        expected = expected_local.astimezone(pytz.UTC)
        
        assert next_run == expected
    
    def test_should_run(self, daily_config):
        trigger = DailyTrigger(TriggerType.DAILY, daily_config)
        
        # Should run at noon UTC
        current_date = datetime.now(pytz.UTC).date()
        run_time = datetime.combine(current_date, time(12, 0), tzinfo=pytz.UTC)
        now_time = datetime.combine(current_date, time(11, 0), tzinfo=pytz.UTC)
        assert trigger.should_run(run_time, now_time) is True
        
        now_time = datetime.combine(current_date, time(12, 10), tzinfo=pytz.UTC)
        assert trigger.should_run(run_time, now_time) is False

        # Should not run at other times
        not_run_time = datetime.combine(current_date, time(13, 0), tzinfo=pytz.UTC)
        assert trigger.should_run(not_run_time) is False


# Test IntervalTrigger
class TestIntervalTrigger:
    def test_initialization(self, interval_config):
        trigger = IntervalTrigger(TriggerType.INTERVAL, interval_config)
        assert trigger.trigger_type == TriggerType.INTERVAL
        assert trigger.config == interval_config
    
    def test_invalid_trigger_type(self, interval_config):
        with pytest.raises(ValueError, match="Expected trigger type interval"):
            IntervalTrigger(TriggerType.IMMEDIATE, interval_config)
    
    def test_missing_config_values(self):
        # Missing start_time
        with pytest.raises(ValueError, match="Start time must be provided"):
            config = TriggerConfig(
                end_time=time(17, 0),
                interval=timedelta(hours=1)
            )
            IntervalTrigger(TriggerType.INTERVAL, config)
        
        # Missing end_time
        with pytest.raises(ValueError, match="End time must be provided"):
            config = TriggerConfig(
                start_time=time(9, 0),
                interval=timedelta(hours=1)
            )
            IntervalTrigger(TriggerType.INTERVAL, config)
        
        # Missing interval
        with pytest.raises(ValueError, match="Interval must be provided"):
            config = TriggerConfig(
                start_time=time(9, 0),
                end_time=time(17, 0)
            )
            IntervalTrigger(TriggerType.INTERVAL, config)
    
    def test_get_next_run_before_start(self, interval_config):
        trigger = IntervalTrigger(TriggerType.INTERVAL, interval_config)
        
        # Test with a time before the start time
        now = datetime(2023, 1, 1, 8, 0, 0, tzinfo=pytz.UTC)  # 8 AM (before 9 AM)
        next_run = trigger.get_next_run(now)
        
        expected = datetime(2023, 1, 1, 9, 0, 0, tzinfo=pytz.UTC)  # 9 AM
        assert next_run == expected
    
    def test_get_next_run_during_interval(self, interval_config):
        trigger = IntervalTrigger(TriggerType.INTERVAL, interval_config)
        
        # Test with a time during the interval period
        now = datetime(2023, 1, 1, 10, 30, 0, tzinfo=pytz.UTC)  # 10:30 AM
        next_run = trigger.get_next_run(now)
        
        expected = datetime(2023, 1, 1, 11, 0, 0, tzinfo=pytz.UTC)  # 11 AM
        assert next_run == expected
    
    def test_get_next_run_after_end(self, interval_config):
        trigger = IntervalTrigger(TriggerType.INTERVAL, interval_config)
        
        # Test with a time after the end time
        now = datetime(2023, 1, 1, 18, 0, 0, tzinfo=pytz.UTC)  # 6 PM (after 5 PM)
        next_run = trigger.get_next_run(now)
        
        expected = datetime(2023, 1, 2, 9, 0, 0, tzinfo=pytz.UTC)  # 9 AM next day
        assert next_run == expected
    
    def test_weekday_filtering(self, interval_config):
        # Modify config to only run on weekdays
        config = TriggerConfig(
            timezone=interval_config.timezone,
            start_time=interval_config.start_time,
            end_time=interval_config.end_time,
            interval=interval_config.interval,
            weekdays={1, 2, 3, 4, 5}  # Monday to Friday
        )
        
        trigger = IntervalTrigger(TriggerType.INTERVAL, config)
        
        # Test with a Saturday
        saturday = datetime(2023, 1, 7, 10, 0, 0, tzinfo=pytz.UTC)  # Saturday
        next_run = trigger.get_next_run(saturday)
        
        # Should skip to Monday
        expected = datetime(2023, 1, 9, 9, 0, 0, tzinfo=pytz.UTC)  # Monday 9 AM
        assert next_run == expected
    
    def test_timezone_handling(self, interval_config, ny_timezone):
        # Create a config with New York timezone
        config = TriggerConfig(
            timezone=ny_timezone,
            start_time=time(9, 0, 0),  # 9 AM NY time
            end_time=time(17, 0, 0),   # 5 PM NY time
            interval=timedelta(hours=1)
        )
        
        trigger = IntervalTrigger(TriggerType.INTERVAL, config)
        
        # Test with a UTC time (when it's 8 AM in New York)
        now = datetime(2023, 1, 1, 13, 0, 0, tzinfo=pytz.UTC)  # 1 PM UTC (8 AM NY)
        next_run = trigger.get_next_run(now)
        
        # Expected: 9 AM NY time converted to UTC
        ny_tz = pytz.timezone(ny_timezone)
        expected_local = datetime.combine(date(2023, 1, 1), time(9, 0, 0))
        expected_local = ny_tz.localize(expected_local)
        expected = expected_local.astimezone(pytz.UTC)
        
        assert next_run == expected
    
    def test_should_run(self, interval_config):
        trigger = IntervalTrigger(TriggerType.INTERVAL, interval_config)
        
        # Should run at interval points
        current_date = datetime.now(pytz.UTC).date()
        current_date = datetime.now(pytz.UTC).date()
        run_time = datetime.combine(current_date, time(10, 0, 0), tzinfo=pytz.UTC)  # 10 AM
        now_time = datetime.combine(current_date, time(9, 30, 0), tzinfo=pytz.UTC)  # 9:30 AM
        assert trigger.should_run(run_time, now = now_time) is True
        
        # Should not run between intervals
        not_run_time = datetime.combine(current_date, time(10, 30, 0), tzinfo=pytz.UTC)  # 10:30 AM
        now_time = datetime.combine(current_date, time(9, 30, 0), tzinfo=pytz.UTC)  # 9:30 AM
        assert trigger.should_run(not_run_time, now_time) is False
        
        # Should not run outside of start/end time
        outside_time = datetime.combine(current_date, time(8, 0, 0), tzinfo=pytz.UTC)  # 8 AM
        now_time = datetime.combine(current_date, time(9, 30, 0), tzinfo=pytz.UTC)  # 9:30 AM
        assert trigger.should_run(outside_time) is False

class TestIntervalTriggerWithDates:
    def test_get_next_run_before_start(self, interval_config_with_dates):
        trigger = IntervalTrigger(TriggerType.INTERVAL, interval_config_with_dates)
        
        # Test with a time after the end time
        now = datetime(2023, 1, 1, 8, 0, 0, tzinfo=pytz.UTC)  # 6 PM (after 5 PM)
        next_run = trigger.get_next_run(now)
        
        expected = datetime(2023, 1, 1, 9, 0, 0, tzinfo=pytz.UTC)  # 9 AM next day
        assert next_run == expected
    
    def test_get_next_run_after_start_before_end(self, interval_config_with_dates):
        trigger = IntervalTrigger(TriggerType.INTERVAL, interval_config_with_dates)
        
        # Test with a time after the end time
        now = datetime(2023, 1, 1, 10, 0, 0, tzinfo=pytz.UTC)  # 6 PM (after 5 PM)
        next_run = trigger.get_next_run(now)
        expected = datetime(2023, 1, 1, 11, 0, 0, tzinfo=pytz.UTC)  # 9 AM next day
        assert next_run == expected

        now = datetime(2023, 1, 1, 9, 59, 30, tzinfo=pytz.UTC)  # 6 PM (after 5 PM)
        next_run = trigger.get_next_run(now)
        expected = datetime(2023, 1, 1, 10, 0, 0, tzinfo=pytz.UTC)  # 9 AM next day
        assert next_run == expected

    def test_get_next_run_after_end(self, interval_config_with_dates):
        trigger = IntervalTrigger(TriggerType.INTERVAL, interval_config_with_dates)
        
        # Test with a time after the end time
        now = datetime(2023, 1, 1, 18, 0, 0, tzinfo=pytz.UTC)  # 6 PM (after 5 PM)
        next_run = trigger.get_next_run(now)
        
        expected = datetime(2023, 1, 3, 9, 0, 0, tzinfo=pytz.UTC)  # 9 AM next day
        assert next_run == expected

        now = datetime(2023, 1, 3, 18, 0, 0, tzinfo=pytz.UTC)  # 6 PM (after 5 PM)
        next_run = trigger.get_next_run(now)
        assert next_run is None