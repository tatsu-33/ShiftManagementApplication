"""
Property-based tests for data model persistence.

Feature: shift-request-management, Property 31: データ永続化のラウンドトリップ
Validates: Requirements 9.1, 9.2, 9.3
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
import uuid

from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus
from app.models.shift import Shift
from app.models.settings import Settings
from app.models.reminder_log import ReminderLog
from tests.conftest import get_test_db_session


# Custom strategies for generating test data
@st.composite
def user_strategy(draw):
    """Generate random User instances."""
    return User(
        id=str(uuid.uuid4()),
        line_id=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters=['\x00']))),
        name=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters=['\x00']))),
        role=draw(st.sampled_from([UserRole.WORKER, UserRole.ADMIN])),
        created_at=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))),
        updated_at=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)))
    )


@st.composite
def request_strategy(draw, worker_id: str):
    """Generate random Request instances."""
    status = draw(st.sampled_from([RequestStatus.PENDING, RequestStatus.APPROVED, RequestStatus.REJECTED]))
    created_at = draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)))
    
    # For processed requests, generate processed_at and processed_by
    if status in [RequestStatus.APPROVED, RequestStatus.REJECTED]:
        processed_at = draw(st.datetimes(min_value=created_at, max_value=datetime(2030, 12, 31)))
        processed_by = str(uuid.uuid4())
    else:
        processed_at = None
        processed_by = None
    
    return Request(
        id=str(uuid.uuid4()),
        worker_id=worker_id,
        request_date=draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))),
        status=status,
        created_at=created_at,
        processed_at=processed_at,
        processed_by=processed_by
    )


@st.composite
def shift_strategy(draw, worker_id: str, updated_by: str):
    """Generate random Shift instances."""
    created_at = draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)))
    
    return Shift(
        id=str(uuid.uuid4()),
        shift_date=draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))),
        worker_id=worker_id,
        created_at=created_at,
        updated_at=draw(st.datetimes(min_value=created_at, max_value=datetime(2030, 12, 31))),
        updated_by=updated_by
    )


@st.composite
def settings_strategy(draw, updated_by: str):
    """Generate random Settings instances."""
    return Settings(
        id=str(uuid.uuid4()),
        key=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters=['\x00']))),
        value=draw(st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters=['\x00']))),
        updated_at=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))),
        updated_by=updated_by
    )


@st.composite
def reminder_log_strategy(draw, worker_id: str):
    """Generate random ReminderLog instances."""
    return ReminderLog(
        id=str(uuid.uuid4()),
        worker_id=worker_id,
        sent_at=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))),
        days_before_deadline=draw(st.integers(min_value=0, max_value=30)),
        target_month=draw(st.integers(min_value=1, max_value=12)),
        target_year=draw(st.integers(min_value=2020, max_value=2030))
    )


@pytest.mark.property
@settings(max_examples=100)
@given(user_data=user_strategy())
def test_user_persistence_roundtrip(user_data: User):
    """
    Property 31: データ永続化のラウンドトリップ - User
    
    For any User entity, saving to database and then retrieving
    should return equivalent data.
    
    Validates: Requirements 9.3
    """
    with get_test_db_session() as test_db:
        # Save user to database
        test_db.add(user_data)
        test_db.commit()
        
        # Retrieve user from database
        retrieved_user = test_db.query(User).filter(User.id == user_data.id).first()
        
        # Assert round-trip consistency
        assert retrieved_user is not None
        assert retrieved_user.id == user_data.id
        assert retrieved_user.line_id == user_data.line_id
        assert retrieved_user.name == user_data.name
        assert retrieved_user.role == user_data.role
        assert retrieved_user.created_at == user_data.created_at
        assert retrieved_user.updated_at == user_data.updated_at


@pytest.mark.property
@settings(max_examples=100)
@given(user_data=user_strategy(), data=st.data())
def test_request_persistence_roundtrip(user_data: User, data):
    """
    Property 31: データ永続化のラウンドトリップ - Request
    
    For any Request entity, saving to database and then retrieving
    should return equivalent data.
    
    Validates: Requirements 9.1
    """
    with get_test_db_session() as test_db:
        # First create a user (required for foreign key)
        test_db.add(user_data)
        test_db.commit()
        
        # Generate request with the user's ID
        request_data = data.draw(request_strategy(worker_id=user_data.id))
        
        # If request is processed, create processor user
        if request_data.processed_by:
            processor = User(
                id=request_data.processed_by,
                line_id=f"processor_{uuid.uuid4()}",
                name="Processor",
                role=UserRole.ADMIN
            )
            test_db.add(processor)
            test_db.commit()
        
        # Save request to database
        test_db.add(request_data)
        test_db.commit()
        
        # Retrieve request from database
        retrieved_request = test_db.query(Request).filter(Request.id == request_data.id).first()
        
        # Assert round-trip consistency
        assert retrieved_request is not None
        assert retrieved_request.id == request_data.id
        assert retrieved_request.worker_id == request_data.worker_id
        assert retrieved_request.request_date == request_data.request_date
        assert retrieved_request.status == request_data.status
        assert retrieved_request.created_at == request_data.created_at
        assert retrieved_request.processed_at == request_data.processed_at
        assert retrieved_request.processed_by == request_data.processed_by


@pytest.mark.property
@settings(max_examples=100)
@given(user_data=user_strategy(), data=st.data())
def test_shift_persistence_roundtrip(user_data: User, data):
    """
    Property 31: データ永続化のラウンドトリップ - Shift
    
    For any Shift entity, saving to database and then retrieving
    should return equivalent data.
    
    Validates: Requirements 9.2
    """
    with get_test_db_session() as test_db:
        # First create users (worker and updater)
        test_db.add(user_data)
        
        updater = User(
            id=str(uuid.uuid4()),
            line_id=f"updater_{uuid.uuid4()}",
            name="Updater",
            role=UserRole.ADMIN
        )
        test_db.add(updater)
        test_db.commit()
        
        # Generate shift with the user's ID
        shift_data = data.draw(shift_strategy(worker_id=user_data.id, updated_by=updater.id))
        
        # Save shift to database
        test_db.add(shift_data)
        test_db.commit()
        
        # Retrieve shift from database
        retrieved_shift = test_db.query(Shift).filter(Shift.id == shift_data.id).first()
        
        # Assert round-trip consistency
        assert retrieved_shift is not None
        assert retrieved_shift.id == shift_data.id
        assert retrieved_shift.shift_date == shift_data.shift_date
        assert retrieved_shift.worker_id == shift_data.worker_id
        assert retrieved_shift.created_at == shift_data.created_at
        assert retrieved_shift.updated_at == shift_data.updated_at
        assert retrieved_shift.updated_by == shift_data.updated_by


@pytest.mark.property
@settings(max_examples=100)
@given(user_data=user_strategy(), data=st.data())
def test_settings_persistence_roundtrip(user_data: User, data):
    """
    Property 31: データ永続化のラウンドトリップ - Settings
    
    For any Settings entity, saving to database and then retrieving
    should return equivalent data.
    
    Validates: Requirements 9.3
    """
    with get_test_db_session() as test_db:
        # First create a user (required for foreign key)
        test_db.add(user_data)
        test_db.commit()
        
        # Generate settings with the user's ID
        settings_data = data.draw(settings_strategy(updated_by=user_data.id))
        
        # Save settings to database
        test_db.add(settings_data)
        test_db.commit()
        
        # Retrieve settings from database
        retrieved_settings = test_db.query(Settings).filter(Settings.id == settings_data.id).first()
        
        # Assert round-trip consistency
        assert retrieved_settings is not None
        assert retrieved_settings.id == settings_data.id
        assert retrieved_settings.key == settings_data.key
        assert retrieved_settings.value == settings_data.value
        assert retrieved_settings.updated_at == settings_data.updated_at
        assert retrieved_settings.updated_by == settings_data.updated_by


@pytest.mark.property
@settings(max_examples=100)
@given(user_data=user_strategy(), data=st.data())
def test_reminder_log_persistence_roundtrip(user_data: User, data):
    """
    Property 31: データ永続化のラウンドトリップ - ReminderLog
    
    For any ReminderLog entity, saving to database and then retrieving
    should return equivalent data.
    
    Validates: Requirements 9.3
    """
    with get_test_db_session() as test_db:
        # First create a user (required for foreign key)
        test_db.add(user_data)
        test_db.commit()
        
        # Generate reminder log with the user's ID
        reminder_log_data = data.draw(reminder_log_strategy(worker_id=user_data.id))
        
        # Save reminder log to database
        test_db.add(reminder_log_data)
        test_db.commit()
        
        # Retrieve reminder log from database
        retrieved_log = test_db.query(ReminderLog).filter(ReminderLog.id == reminder_log_data.id).first()
        
        # Assert round-trip consistency
        assert retrieved_log is not None
        assert retrieved_log.id == reminder_log_data.id
        assert retrieved_log.worker_id == reminder_log_data.worker_id
        assert retrieved_log.sent_at == reminder_log_data.sent_at
        assert retrieved_log.days_before_deadline == reminder_log_data.days_before_deadline
        assert retrieved_log.target_month == reminder_log_data.target_month
        assert retrieved_log.target_year == reminder_log_data.target_year
