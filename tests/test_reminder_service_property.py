"""
Property-based tests for reminder service.

Feature: shift-request-management
Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
import uuid

print("Loading test_reminder_service_property module...")

from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus
from app.models.settings import Settings as SettingsModel
from app.models.reminder_log import ReminderLog
from app.services.reminder_service import ReminderService
from tests.conftest import get_test_db_session

print("Imports complete...")


# Strategy for generating deadline days (1-28 to avoid month-end issues)
def deadline_days_strategy():
    """Generate valid deadline days."""
    return st.integers(min_value=1, max_value=28)


# Strategy for generating months
def months_strategy():
    """Generate valid months (1-12)."""
    return st.integers(min_value=1, max_value=12)


# Strategy for generating years
def years_strategy():
    """Generate valid years."""
    return st.integers(min_value=2024, max_value=2030)


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    current_day=st.integers(min_value=1, max_value=28),
    deadline_day=deadline_days_strategy(),
    num_workers_with_requests=st.integers(min_value=0, max_value=5),
    num_workers_without_requests=st.integers(min_value=1, max_value=5)
)
def test_property_32_reminders_sent_only_to_workers_without_requests(
    current_day: int,
    deadline_day: int,
    num_workers_with_requests: int,
    num_workers_without_requests: int
):
    """
    Property 32: Reminders are sent only to workers without requests.
    
    For any set of workers and date, when it's 7, 3, or 1 day before the deadline,
    reminders should only be sent to workers who haven't submitted requests for
    the target month.
    
    Feature: shift-request-management, Property 32: Reminders are sent only to workers without requests
    Validates: Requirements 10.1, 10.2, 10.3, 10.5
    """
    # Ensure current_day is before deadline_day to create a valid reminder scenario
    assume(current_day < deadline_day)
    days_until_deadline = deadline_day - current_day
    
    # Only test on reminder days (7, 3, or 1 day before)
    assume(days_until_deadline in [7, 3, 1])
    
    with get_test_db_session() as test_db:
        # Setup: Create admin and deadline setting
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"admin_{uuid.uuid4()}",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = SettingsModel(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value=str(deadline_day),
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        
        # Create workers with requests
        workers_with_requests_ids = set()
        for i in range(num_workers_with_requests):
            worker_id = str(uuid.uuid4())
            worker = User(
                id=worker_id,
                line_id=f"worker_with_{i}_{uuid.uuid4()}",
                name=f"Worker With Request {i}",
                role=UserRole.WORKER
            )
            test_db.add(worker)
            workers_with_requests_ids.add(worker_id)
            
            # Add request for next month
            request = Request(
                id=str(uuid.uuid4()),
                worker_id=worker_id,
                request_date=date(2024, 2, 15),  # Next month
                status=RequestStatus.PENDING,
                created_at=datetime.utcnow()
            )
            test_db.add(request)
        
        # Create workers without requests
        workers_without_requests_ids = set()
        for i in range(num_workers_without_requests):
            worker_id = str(uuid.uuid4())
            worker = User(
                id=worker_id,
                line_id=f"worker_without_{i}_{uuid.uuid4()}",
                name=f"Worker Without Request {i}",
                role=UserRole.WORKER
            )
            test_db.add(worker)
            workers_without_requests_ids.add(worker_id)
        
        test_db.commit()
        
        # Mock notification service to track who received reminders
        sent_to_worker_ids = []
        
        def mock_send_reminder(user_id, deadline_day, days_until_deadline, target_month):
            # Find worker by line_id
            worker = test_db.query(User).filter(User.line_id == user_id).first()
            if worker:
                sent_to_worker_ids.append(worker.id)
            return True
        
        import app.services.reminder_service as rs_module
        original_send_reminder = rs_module.notification_service.send_reminder
        rs_module.notification_service.send_reminder = mock_send_reminder
        
        try:
            # Test: Send reminders
            service = ReminderService(test_db)
            current_date = date(2024, 1, current_day)
            sent_count = service.send_reminders(current_date)
            
            # Verify: Reminders sent only to workers without requests
            assert sent_count == num_workers_without_requests
            assert len(sent_to_worker_ids) == num_workers_without_requests
            
            # Verify: All workers who received reminders are in the "without requests" set
            for worker_id in sent_to_worker_ids:
                assert worker_id in workers_without_requests_ids
                assert worker_id not in workers_with_requests_ids
            
            # Verify: No workers with requests received reminders
            for worker_id in workers_with_requests_ids:
                assert worker_id not in sent_to_worker_ids
        finally:
            # Restore original function
            rs_module.notification_service.send_reminder = original_send_reminder


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    deadline_day=deadline_days_strategy(),
    days_before=st.sampled_from([7, 3, 1]),
    target_month=months_strategy(),
    target_year=years_strategy()
)
def test_property_33_reminders_contain_required_information(
    deadline_day: int,
    days_before: int,
    target_month: int,
    target_year: int
):
    """
    Property 33: Reminders contain required information.
    
    For any reminder sent, it must include the deadline day and days remaining
    until the deadline.
    
    Feature: shift-request-management, Property 33: Reminders contain required information
    Validates: Requirements 10.4
    """
    # Calculate current day based on days_before
    current_day = deadline_day - days_before
    assume(current_day >= 1)
    
    with get_test_db_session() as test_db:
        # Setup: Create admin and deadline setting
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"admin_{uuid.uuid4()}",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = SettingsModel(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value=str(deadline_day),
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        
        # Create a worker without request
        worker_id = str(uuid.uuid4())
        worker = User(
            id=worker_id,
            line_id=f"worker_{uuid.uuid4()}",
            name="Test Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Mock notification service to capture reminder content
        captured_reminders = []
        
        def mock_send_reminder(user_id, deadline_day_param, days_until_deadline, target_month_str):
            captured_reminders.append({
                'user_id': user_id,
                'deadline_day': deadline_day_param,
                'days_until_deadline': days_until_deadline,
                'target_month': target_month_str
            })
            return True
        
        import app.services.reminder_service as rs_module
        original_send_reminder = rs_module.notification_service.send_reminder
        rs_module.notification_service.send_reminder = mock_send_reminder
        
        try:
            # Test: Send reminders
            service = ReminderService(test_db)
            # Use a date in the previous month to ensure target month is correct
            if target_month == 1:
                current_date = date(target_year - 1, 12, current_day)
            else:
                current_date = date(target_year, target_month - 1, current_day)
            
            sent_count = service.send_reminders(current_date)
            
            # Verify: Reminder was sent
            assert sent_count == 1
            assert len(captured_reminders) == 1
            
            # Verify: Reminder contains required information
            reminder = captured_reminders[0]
            assert 'deadline_day' in reminder
            assert 'days_until_deadline' in reminder
            assert 'target_month' in reminder
            
            # Verify: Values are correct
            assert reminder['deadline_day'] == deadline_day
            assert reminder['days_until_deadline'] == days_before
            
            # Verify: Target month string is formatted correctly
            expected_target_month_str = f"{target_year}年{target_month}月"
            assert reminder['target_month'] == expected_target_month_str
        finally:
            # Restore original function
            rs_module.notification_service.send_reminder = original_send_reminder


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    deadline_day=deadline_days_strategy(),
    days_before=st.sampled_from([7, 3, 1]),
    num_workers=st.integers(min_value=1, max_value=5)
)
def test_property_34_reminder_sending_history_is_recorded(
    deadline_day: int,
    days_before: int,
    num_workers: int
):
    """
    Property 34: Reminder sending history is recorded.
    
    For any reminder sent, the sending date/time, target worker, days remaining,
    and target month must be recorded in the reminder_logs table.
    
    Feature: shift-request-management, Property 34: Reminder sending history is recorded
    Validates: Requirements 10.6
    """
    # Calculate current day based on days_before
    current_day = deadline_day - days_before
    assume(current_day >= 1)
    
    with get_test_db_session() as test_db:
        # Setup: Create admin and deadline setting
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"admin_{uuid.uuid4()}",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = SettingsModel(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value=str(deadline_day),
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        
        # Create workers without requests
        worker_ids = []
        for i in range(num_workers):
            worker_id = str(uuid.uuid4())
            worker = User(
                id=worker_id,
                line_id=f"worker_{i}_{uuid.uuid4()}",
                name=f"Worker {i}",
                role=UserRole.WORKER
            )
            test_db.add(worker)
            worker_ids.append(worker_id)
        
        test_db.commit()
        
        # Mock notification service
        def mock_send_reminder(user_id, deadline_day, days_until_deadline, target_month):
            return True
        
        import app.services.reminder_service as rs_module
        original_send_reminder = rs_module.notification_service.send_reminder
        rs_module.notification_service.send_reminder = mock_send_reminder
        
        try:
            # Test: Send reminders
            service = ReminderService(test_db)
            current_date = date(2024, 1, current_day)
            sent_count = service.send_reminders(current_date)
            
            # Verify: Correct number of reminders sent
            assert sent_count == num_workers
            
            # Verify: Reminder logs were created
            logs = test_db.query(ReminderLog).all()
            assert len(logs) == num_workers
            
            # Verify: Each log contains required information
            log_worker_ids = set()
            for log in logs:
                # Verify required fields are present
                assert log.id is not None
                assert log.worker_id is not None
                assert log.sent_at is not None
                assert log.days_before_deadline is not None
                assert log.target_month is not None
                assert log.target_year is not None
                
                # Verify values are correct
                assert log.days_before_deadline == days_before
                assert log.target_month == 2  # Next month from January
                assert log.target_year == 2024
                
                # Verify sent_at is recent (within last minute)
                time_diff = (datetime.utcnow() - log.sent_at).total_seconds()
                assert time_diff < 60  # Less than 60 seconds ago
                
                log_worker_ids.add(log.worker_id)
            
            # Verify: All workers have logs
            assert log_worker_ids == set(worker_ids)
        finally:
            # Restore original function
            rs_module.notification_service.send_reminder = original_send_reminder
