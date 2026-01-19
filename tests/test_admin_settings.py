"""Unit tests for admin settings page."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from main import app
from app.models.user import User, UserRole
from app.models.settings import Settings
from app.services.auth_service import AuthService
from app.api.admin import sessions


@pytest.fixture
def admin_user(test_db: Session):
    """Create an admin user for testing."""
    auth_service = AuthService(test_db)
    admin = auth_service.create_admin("testadmin", "testpassword123")
    test_db.commit()
    return admin


@pytest.fixture
def authenticated_client(admin_user: User):
    """Create an authenticated test client."""
    client = TestClient(app)
    
    # Create session
    session_id = "test_session_" + str(uuid.uuid4())
    sessions[session_id] = admin_user.id
    
    # Set cookie
    client.cookies.set("session_id", session_id)
    
    yield client
    
    # Cleanup
    if session_id in sessions:
        del sessions[session_id]


def test_settings_page_requires_authentication(test_db: Session):
    """Test that settings page requires authentication."""
    client = TestClient(app)
    
    response = client.get("/admin/settings")
    
    # Should redirect to login or return 401
    assert response.status_code in [401, 303]


def test_settings_page_displays_for_authenticated_admin(
    authenticated_client: TestClient,
    admin_user: User
):
    """Test that settings page displays for authenticated admin."""
    response = authenticated_client.get("/admin/settings")
    
    assert response.status_code == 200
    assert "設定" in response.text
    assert "締切日設定" in response.text
    assert admin_user.name in response.text


def test_get_deadline_setting_returns_default(
    authenticated_client: TestClient,
    test_db: Session
):
    """Test getting deadline setting returns default when not set."""
    response = authenticated_client.get("/admin/api/settings/deadline")
    
    assert response.status_code == 200
    data = response.json()
    assert "deadline_day" in data
    assert data["deadline_day"] == 10  # Default value


def test_get_deadline_setting_returns_stored_value(
    authenticated_client: TestClient,
    admin_user: User,
    test_db: Session
):
    """Test getting deadline setting returns stored value."""
    # Create a setting
    setting = Settings(
        id=str(uuid.uuid4()),
        key="application_deadline_day",
        value="15",
        updated_at=datetime.utcnow(),
        updated_by=admin_user.id
    )
    test_db.add(setting)
    test_db.commit()
    
    response = authenticated_client.get("/admin/api/settings/deadline")
    
    assert response.status_code == 200
    data = response.json()
    assert data["deadline_day"] == 15


def test_update_deadline_setting_creates_new(
    authenticated_client: TestClient,
    admin_user: User,
    test_db: Session
):
    """Test updating deadline setting creates new record when none exists."""
    response = authenticated_client.put(
        "/admin/api/settings/deadline",
        json={"deadline_day": 20}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["deadline_day"] == 20
    assert "updated_at" in data
    assert data["updated_by"] == admin_user.id
    
    # Verify in database
    setting = test_db.query(Settings).filter(
        Settings.key == "application_deadline_day"
    ).first()
    assert setting is not None
    assert setting.value == "20"
    assert setting.updated_by == admin_user.id


def test_update_deadline_setting_updates_existing(
    authenticated_client: TestClient,
    admin_user: User,
    test_db: Session
):
    """Test updating deadline setting updates existing record."""
    # Create initial setting
    setting = Settings(
        id=str(uuid.uuid4()),
        key="application_deadline_day",
        value="10",
        updated_at=datetime.utcnow(),
        updated_by=admin_user.id
    )
    test_db.add(setting)
    test_db.commit()
    
    # Update it
    response = authenticated_client.put(
        "/admin/api/settings/deadline",
        json={"deadline_day": 25}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["deadline_day"] == 25
    
    # Verify only one setting exists
    settings = test_db.query(Settings).filter(
        Settings.key == "application_deadline_day"
    ).all()
    assert len(settings) == 1
    assert settings[0].value == "25"


def test_update_deadline_setting_validates_range(
    authenticated_client: TestClient,
    test_db: Session
):
    """Test that deadline setting validates day range."""
    # Test invalid values
    response = authenticated_client.put(
        "/admin/api/settings/deadline",
        json={"deadline_day": 0}
    )
    assert response.status_code == 400
    assert "between 1 and 31" in response.json()["detail"]
    
    response = authenticated_client.put(
        "/admin/api/settings/deadline",
        json={"deadline_day": 32}
    )
    assert response.status_code == 400
    assert "between 1 and 31" in response.json()["detail"]
    
    response = authenticated_client.put(
        "/admin/api/settings/deadline",
        json={"deadline_day": -5}
    )
    assert response.status_code == 400
    assert "between 1 and 31" in response.json()["detail"]


def test_update_deadline_setting_requires_authentication(test_db: Session):
    """Test that updating deadline requires authentication."""
    client = TestClient(app)
    
    response = client.put(
        "/admin/api/settings/deadline",
        json={"deadline_day": 15}
    )
    
    assert response.status_code == 401


def test_get_deadline_history_returns_empty_when_no_changes(
    authenticated_client: TestClient,
    test_db: Session
):
    """Test that deadline history returns empty list when no changes exist."""
    response = authenticated_client.get("/admin/api/settings/deadline/history")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_deadline_history_returns_changes(
    authenticated_client: TestClient,
    admin_user: User,
    test_db: Session
):
    """Test that deadline history returns current setting with updater info."""
    # Create a setting
    setting = Settings(
        id=str(uuid.uuid4()),
        key="application_deadline_day",
        value="15",
        updated_at=datetime(2024, 1, 2, 10, 0, 0),
        updated_by=admin_user.id
    )
    test_db.add(setting)
    test_db.commit()
    
    response = authenticated_client.get("/admin/api/settings/deadline/history")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    
    # Should include the current setting
    assert data[0]["value"] == "15"
    
    # Should include updater name
    assert data[0]["updater_name"] == admin_user.name


def test_get_deadline_history_respects_limit(
    authenticated_client: TestClient,
    admin_user: User,
    test_db: Session
):
    """Test that deadline history respects limit parameter."""
    # Create a setting
    setting = Settings(
        id=str(uuid.uuid4()),
        key="application_deadline_day",
        value="12",
        updated_at=datetime(2024, 1, 3, 10, 0, 0),
        updated_by=admin_user.id
    )
    test_db.add(setting)
    test_db.commit()
    
    response = authenticated_client.get("/admin/api/settings/deadline/history?limit=1")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 1


def test_get_deadline_history_requires_authentication(test_db: Session):
    """Test that getting deadline history requires authentication."""
    client = TestClient(app)
    
    response = client.get("/admin/api/settings/deadline/history")
    
    assert response.status_code == 401


def test_settings_page_integration(
    authenticated_client: TestClient,
    admin_user: User,
    test_db: Session
):
    """Test full integration of settings page functionality."""
    # 1. Load settings page
    response = authenticated_client.get("/admin/settings")
    assert response.status_code == 200
    
    # 2. Get current deadline (should be default)
    response = authenticated_client.get("/admin/api/settings/deadline")
    assert response.status_code == 200
    assert response.json()["deadline_day"] == 10
    
    # 3. Update deadline
    response = authenticated_client.put(
        "/admin/api/settings/deadline",
        json={"deadline_day": 20}
    )
    assert response.status_code == 200
    assert response.json()["deadline_day"] == 20
    
    # 4. Verify deadline was updated
    response = authenticated_client.get("/admin/api/settings/deadline")
    assert response.status_code == 200
    assert response.json()["deadline_day"] == 20
    
    # 5. Check history (should show current setting)
    response = authenticated_client.get("/admin/api/settings/deadline/history")
    assert response.status_code == 200
    history = response.json()
    assert len(history) >= 1
    # The most recent entry should be 20
    assert history[0]["value"] == "20"
    assert history[0]["updater_name"] == admin_user.name
