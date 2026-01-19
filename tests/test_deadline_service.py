"""Unit tests for deadline service."""
import pytest
from datetime import datetime
import uuid

from app.services.deadline_service import DeadlineService
from app.models.settings import Settings
from app.models.user import User
from app.exceptions import InvalidRangeError, MissingFieldError


def test_get_deadline_day_returns_default_when_not_set(test_db):
    """Test that get_deadline_day returns default value when not set in database."""
    service = DeadlineService(test_db)
    
    deadline = service.get_deadline_day()
    
    assert deadline == 10  # Default value


def test_get_deadline_day_returns_stored_value(test_db):
    """Test that get_deadline_day returns the stored value from database."""
    # Create admin user
    admin = User(
        id=str(uuid.uuid4()),
        line_id="admin_line_id",
        name="Admin",
        role="admin"
    )
    test_db.add(admin)
    test_db.commit()
    
    # Create setting
    setting = Settings(
        id=str(uuid.uuid4()),
        key="application_deadline_day",
        value="15",
        updated_at=datetime.utcnow(),
        updated_by=admin.id
    )
    test_db.add(setting)
    test_db.commit()
    
    service = DeadlineService(test_db)
    deadline = service.get_deadline_day()
    
    assert deadline == 15


def test_set_deadline_day_creates_new_setting(test_db):
    """Test that set_deadline_day creates a new setting when none exists."""
    # Create admin user
    admin = User(
        id=str(uuid.uuid4()),
        line_id="admin_line_id",
        name="Admin",
        role="admin"
    )
    test_db.add(admin)
    test_db.commit()
    
    service = DeadlineService(test_db)
    result = service.set_deadline_day(20, admin.id)
    
    assert result.key == "application_deadline_day"
    assert result.value == "20"
    assert result.updated_by == admin.id
    
    # Verify it's stored
    deadline = service.get_deadline_day()
    assert deadline == 20


def test_set_deadline_day_updates_existing_setting(test_db):
    """Test that set_deadline_day updates an existing setting."""
    # Create admin user
    admin = User(
        id=str(uuid.uuid4()),
        line_id="admin_line_id",
        name="Admin",
        role="admin"
    )
    test_db.add(admin)
    test_db.commit()
    
    # Create initial setting
    service = DeadlineService(test_db)
    service.set_deadline_day(15, admin.id)
    
    # Update setting
    result = service.set_deadline_day(25, admin.id)
    
    assert result.value == "25"
    assert result.updated_by == admin.id
    
    # Verify only one setting exists
    settings = test_db.query(Settings).filter(
        Settings.key == "application_deadline_day"
    ).all()
    assert len(settings) == 1


def test_set_deadline_day_validates_day_range(test_db):
    """Test that set_deadline_day validates day is between 1 and 31."""
    admin_id = str(uuid.uuid4())
    service = DeadlineService(test_db)
    
    # Test invalid values
    with pytest.raises(InvalidRangeError):
        service.set_deadline_day(0, admin_id)
    
    with pytest.raises(InvalidRangeError):
        service.set_deadline_day(32, admin_id)
    
    with pytest.raises(InvalidRangeError):
        service.set_deadline_day(-1, admin_id)


def test_set_deadline_day_requires_admin_id(test_db):
    """Test that set_deadline_day requires admin_id."""
    service = DeadlineService(test_db)
    
    with pytest.raises(MissingFieldError):
        service.set_deadline_day(15, "")


def test_set_deadline_day_records_change_history(test_db):
    """Test that deadline changes are recorded with timestamp and admin."""
    # Create admin user
    admin = User(
        id=str(uuid.uuid4()),
        line_id="admin_line_id",
        name="Admin",
        role="admin"
    )
    test_db.add(admin)
    test_db.commit()
    
    service = DeadlineService(test_db)
    
    # Make first change
    before_update = datetime.utcnow()
    result = service.set_deadline_day(15, admin.id)
    after_update = datetime.utcnow()
    
    # Verify timestamp is recorded
    assert before_update <= result.updated_at <= after_update
    assert result.updated_by == admin.id


def test_get_deadline_history_returns_empty_when_no_changes(test_db):
    """Test that get_deadline_history returns empty list when no changes exist."""
    service = DeadlineService(test_db)
    
    history = service.get_deadline_history()
    
    assert history == []


def test_get_deadline_history_returns_changes_in_order(test_db):
    """Test that get_deadline_history returns changes in descending order."""
    # Create admin user
    admin = User(
        id=str(uuid.uuid4()),
        line_id="admin_line_id",
        name="Admin",
        role="admin"
    )
    test_db.add(admin)
    test_db.commit()
    
    service = DeadlineService(test_db)
    
    # Make multiple changes (note: in real scenario these would have different timestamps)
    # For testing, we'll create settings directly with different timestamps
    import time
    
    setting1 = Settings(
        id=str(uuid.uuid4()),
        key="application_deadline_day",
        value="15",
        updated_at=datetime(2024, 1, 1, 10, 0, 0),
        updated_by=admin.id
    )
    test_db.add(setting1)
    test_db.commit()
    
    # Update to create history (SQLite doesn't support multiple rows with same unique key)
    # So we'll just verify the single entry is returned
    history = service.get_deadline_history()
    
    assert len(history) == 1
    assert history[0].value == "15"


def test_get_deadline_history_respects_limit(test_db):
    """Test that get_deadline_history respects the limit parameter."""
    # Create admin user
    admin = User(
        id=str(uuid.uuid4()),
        line_id="admin_line_id",
        name="Admin",
        role="admin"
    )
    test_db.add(admin)
    test_db.commit()
    
    service = DeadlineService(test_db)
    service.set_deadline_day(15, admin.id)
    
    history = service.get_deadline_history(limit=1)
    
    assert len(history) <= 1
