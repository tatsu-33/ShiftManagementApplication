"""Tests for admin shift management endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime
import uuid

from app.database import Base, get_db
from app.models.user import User, UserRole
from app.models.shift import Shift
from app.models.request import Request, RequestStatus
from main import app


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin_shifts.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def test_db():
    """Create test database and tables."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_user(test_db):
    """Create admin user for testing."""
    admin = User(
        id=str(uuid.uuid4()),
        line_id="admin_line_id",
        name="Test Admin",
        role=UserRole.ADMIN,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)
    return admin


@pytest.fixture
def worker_users(test_db):
    """Create worker users for testing."""
    workers = []
    for i in range(3):
        worker = User(
            id=str(uuid.uuid4()),
            line_id=f"worker_{i}_line_id",
            name=f"Worker {i}",
            role=UserRole.WORKER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        test_db.add(worker)
        workers.append(worker)
    
    test_db.commit()
    for worker in workers:
        test_db.refresh(worker)
    
    return workers


@pytest.fixture
def authenticated_client(client, admin_user, test_db):
    """Create authenticated client with admin session."""
    # Import sessions from admin module
    from app.api.admin import sessions
    
    # Create session
    session_id = "test_session_id"
    sessions[session_id] = admin_user.id
    
    # Set cookie
    client.cookies.set("session_id", session_id)
    
    yield client
    
    # Cleanup
    if session_id in sessions:
        del sessions[session_id]


def test_shifts_page_requires_authentication(client):
    """Test that shifts page requires authentication."""
    response = client.get("/admin/shifts")
    assert response.status_code == 401


def test_shifts_page_loads(authenticated_client):
    """Test that shifts page loads for authenticated admin."""
    response = authenticated_client.get("/admin/shifts")
    assert response.status_code == 200
    assert "シフト管理" in response.text


def test_get_workers(authenticated_client, worker_users):
    """Test getting all workers."""
    response = authenticated_client.get("/admin/api/workers")
    assert response.status_code == 200
    
    workers = response.json()
    assert len(workers) == 3
    assert all("id" in w and "name" in w and "line_id" in w for w in workers)


def test_get_shifts_by_month(authenticated_client, admin_user, worker_users, test_db):
    """Test getting shifts for a specific month."""
    # Create some shifts
    shift_date = date(2024, 2, 15)
    shift = Shift(
        id=str(uuid.uuid4()),
        shift_date=shift_date,
        worker_id=worker_users[0].id,
        updated_by=admin_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    test_db.add(shift)
    test_db.commit()
    
    # Get shifts
    response = authenticated_client.get("/admin/api/shifts?year=2024&month=2")
    assert response.status_code == 200
    
    shifts = response.json()
    assert len(shifts) == 1
    assert shifts[0]["shift_date"] == "2024-02-15"
    assert shifts[0]["worker_name"] == "Worker 0"


def test_get_ng_days(authenticated_client, worker_users, test_db):
    """Test getting approved NG days for a month."""
    # Create approved request
    request = Request(
        id=str(uuid.uuid4()),
        worker_id=worker_users[0].id,
        request_date=date(2024, 2, 20),
        status=RequestStatus.APPROVED,
        created_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
        processed_by=worker_users[0].id
    )
    test_db.add(request)
    test_db.commit()
    
    # Get NG days
    response = authenticated_client.get("/admin/api/ng-days?year=2024&month=2")
    assert response.status_code == 200
    
    ng_days = response.json()
    assert "2024-02-20" in ng_days
    assert worker_users[0].id in ng_days["2024-02-20"]


def test_update_shift(authenticated_client, admin_user, worker_users, test_db):
    """Test updating shift assignments."""
    shift_date = date(2024, 2, 15)
    
    # Update shift with two workers
    response = authenticated_client.put(
        f"/admin/api/shifts/{shift_date.isoformat()}",
        json={"worker_ids": [worker_users[0].id, worker_users[1].id]}
    )
    assert response.status_code == 200
    
    result = response.json()
    assert len(result["shifts"]) == 2
    assert len(result["changes"]["added"]) == 2
    assert len(result["changes"]["removed"]) == 0


def test_update_shift_with_ng_day_warning(authenticated_client, admin_user, worker_users, test_db):
    """Test that updating shift with NG day shows warning."""
    shift_date = date(2024, 2, 20)
    
    # Create approved NG day request
    request = Request(
        id=str(uuid.uuid4()),
        worker_id=worker_users[0].id,
        request_date=shift_date,
        status=RequestStatus.APPROVED,
        created_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
        processed_by=admin_user.id
    )
    test_db.add(request)
    test_db.commit()
    
    # Try to assign worker with NG day
    response = authenticated_client.put(
        f"/admin/api/shifts/{shift_date.isoformat()}",
        json={"worker_ids": [worker_users[0].id]}
    )
    assert response.status_code == 200
    
    result = response.json()
    assert len(result["warnings"]) > 0
    assert "NG day" in result["warnings"][0] or "NG日" in result["warnings"][0]


def test_update_shift_remove_workers(authenticated_client, admin_user, worker_users, test_db):
    """Test removing workers from shift."""
    shift_date = date(2024, 2, 15)
    
    # Create initial shift
    shift = Shift(
        id=str(uuid.uuid4()),
        shift_date=shift_date,
        worker_id=worker_users[0].id,
        updated_by=admin_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    test_db.add(shift)
    test_db.commit()
    
    # Update to remove all workers
    response = authenticated_client.put(
        f"/admin/api/shifts/{shift_date.isoformat()}",
        json={"worker_ids": []}
    )
    assert response.status_code == 200
    
    result = response.json()
    assert len(result["shifts"]) == 0
    assert len(result["changes"]["removed"]) == 1
    assert worker_users[0].id in result["changes"]["removed"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
