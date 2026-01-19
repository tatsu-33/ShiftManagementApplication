"""Property-based tests for LINE webhook calendar generation."""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import date
from dateutil.relativedelta import relativedelta
from unittest.mock import Mock, patch
import calendar as cal_module

from app.line_bot.webhook import generate_calendar_flex_message


# Strategy for generating random dates
dates_strategy = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2030, 12, 31)
)


class TestCalendarGenerationProperties:
    """Property-based tests for calendar generation."""
    
    @given(current_date=dates_strategy)
    @settings(max_examples=100)
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_property_1_calendar_contains_only_next_month_dates(
        self,
        mock_request_service,
        mock_auth_service,
        current_date
    ):
        """
        Property 1: Calendar contains only next month dates.
        
        For any current date, the generated calendar should contain only dates
        from the next month, and should not include dates from the current month
        or the month after next.
        
        Feature: shift-request-management, Property 1: カレンダーは翌月の日付のみを含む
        Validates: Requirements 1.2
        """
        # Mock database session
        mock_db = Mock()
        
        # Mock services to return no existing requests
        mock_auth_service.return_value.get_worker_by_line_id.return_value = None
        mock_request_service.return_value.get_requests_by_worker.return_value = []
        
        # Generate calendar
        flex_message = generate_calendar_flex_message(
            user_id="test_user",
            db=mock_db,
            current_date=current_date
        )
        
        # Calculate expected next month
        next_month_date = current_date + relativedelta(months=1)
        expected_year = next_month_date.year
        expected_month = next_month_date.month
        
        # Verify header contains correct year and month
        header_text = flex_message["header"]["contents"][0]["text"]
        month_names_ja = [
            "1月", "2月", "3月", "4月", "5月", "6月",
            "7月", "8月", "9月", "10月", "11月", "12月"
        ]
        expected_month_name = month_names_ja[expected_month - 1]
        
        assert f"{expected_year}年{expected_month_name}" in header_text, \
            f"Header should contain {expected_year}年{expected_month_name}, but got: {header_text}"
        
        # Extract all dates from calendar buttons
        body_contents = flex_message["body"]["contents"]
        calendar_dates = []
        
        for row in body_contents:
            if row["type"] == "box" and "contents" in row:
                for item in row["contents"]:
                    if item["type"] == "button" and "action" in item:
                        # Extract date from postback data
                        data = item["action"]["data"]
                        if "date=" in data:
                            date_str = data.split("date=")[1].split("&")[0]
                            try:
                                button_date = date.fromisoformat(date_str)
                                calendar_dates.append(button_date)
                            except ValueError:
                                pass
        
        # Verify all dates are from next month
        for calendar_date in calendar_dates:
            assert calendar_date.year == expected_year, \
                f"Date {calendar_date} has wrong year. Expected {expected_year}, got {calendar_date.year}"
            assert calendar_date.month == expected_month, \
                f"Date {calendar_date} has wrong month. Expected {expected_month}, got {calendar_date.month}"
        
        # Verify we have the correct number of days for the month
        expected_days_in_month = cal_module.monthrange(expected_year, expected_month)[1]
        assert len(calendar_dates) == expected_days_in_month, \
            f"Calendar should have {expected_days_in_month} dates, but has {len(calendar_dates)}"
        
        # Verify all days from 1 to last day of month are present
        calendar_days = sorted([d.day for d in calendar_dates])
        expected_days = list(range(1, expected_days_in_month + 1))
        assert calendar_days == expected_days, \
            f"Calendar should have days {expected_days}, but has {calendar_days}"
