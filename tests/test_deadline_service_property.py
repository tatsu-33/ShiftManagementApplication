"""
Property-based tests for deadline service.

Feature: shift-request-management
Validates: Requirements 2.3, 2.4
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
import uuid

from app.models.user import User, UserRole
from app.models.settings import Settings as SettingsModel
from app.services.deadline_service import DeadlineService
from tests.conftest import get_test_db_session


# Custom strategies for generating test data
@st.composite
def valid_admin_strategy(draw):
    """Generate a valid admin user."""
    admin_id = str(uuid.uuid4())
    return User(
        id=admin_id,
        line_id=draw(st.text(
            min_size=5, 
            max_size=50, 
            alphabet=st.characters(
                min_codepoint=ord('a'),
                max_codepoint=ord('z'),
                blacklist_categories=('Cs',),
                blacklist_characters=['\x00']
            )
        )) + "_" + admin_id[:8],  # Append part of UUID to ensure uniqueness
        name=draw(st.text(
            min_size=3, 
            max_size=50, 
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('z'),
                blacklist_categories=('Cs',),
                blacklist_characters=['\x00']
            )
        )) + "_" + admin_id[:8],  # Append part of UUID to ensure uniqueness
        role=UserRole.ADMIN,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@st.composite
def valid_deadline_day_strategy(draw):
    """Generate a valid deadline day (1-31)."""
    return draw(st.integers(min_value=1, max_value=31))


@pytest.mark.property
@settings(max_examples=100)
@given(
    admin=valid_admin_strategy(),
    deadline_day=valid_deadline_day_strategy()
)
def test_property_6_deadline_change_is_saved(admin: User, deadline_day: int):
    """
    Property 6: 締切日変更は保存される
    
    For any valid deadline day (1-31), when an administrator changes it,
    the new deadline day is correctly saved.
    
    Feature: shift-request-management, Property 6: 締切日変更は保存される
    Validates: Requirements 2.3
    """
    with get_test_db_session() as test_db:
        # Add admin to database
        test_db.add(admin)
        test_db.commit()
        
        # Create deadline service
        service = DeadlineService(test_db)
        
        # Set the deadline day
        result = service.set_deadline_day(deadline_day, admin.id)
        
        # Property: The deadline day should be saved correctly
        assert result.value == str(deadline_day), \
            f"Deadline day should be saved as {deadline_day}, but got {result.value}"
        
        # Verify it can be retrieved
        retrieved_deadline = service.get_deadline_day()
        assert retrieved_deadline == deadline_day, \
            f"Retrieved deadline should be {deadline_day}, but got {retrieved_deadline}"


@pytest.mark.property
@settings(max_examples=100)
@given(
    admin=valid_admin_strategy(),
    deadline_day=valid_deadline_day_strategy()
)
def test_property_7_deadline_change_history_recorded(admin: User, deadline_day: int):
    """
    Property 7: 締切日変更履歴が記録される
    
    For any deadline change, the change timestamp and changer are recorded.
    
    Feature: shift-request-management, Property 7: 締切日変更履歴が記録される
    Validates: Requirements 2.4
    """
    with get_test_db_session() as test_db:
        # Add admin to database
        test_db.add(admin)
        test_db.commit()
        
        # Create deadline service
        service = DeadlineService(test_db)
        
        # Record time before change
        before_change = datetime.utcnow()
        
        # Set the deadline day
        result = service.set_deadline_day(deadline_day, admin.id)
        
        # Record time after change
        after_change = datetime.utcnow()
        
        # Property: Change history should be recorded
        assert result.updated_at is not None, \
            "Updated_at timestamp should be recorded"
        assert isinstance(result.updated_at, datetime), \
            "Updated_at should be a datetime object"
        assert before_change <= result.updated_at <= after_change, \
            f"Updated_at should be between {before_change} and {after_change}, but got {result.updated_at}"
        
        assert result.updated_by == admin.id, \
            f"Updated_by should be {admin.id}, but got {result.updated_by}"
        
        # Verify history can be retrieved
        history = service.get_deadline_history()
        assert len(history) > 0, \
            "History should contain at least one entry"
        assert history[0].updated_by == admin.id, \
            f"History should record admin {admin.id} as updater"
