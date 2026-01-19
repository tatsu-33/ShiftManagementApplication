"""Tests for admin request management interface."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import uuid

from main import app
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus
from app.services.auth_service import AuthService
from app.api.admin import sessions


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin_requests.db"
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
def db():
    """Create test database and tables."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)
    sessions.clear()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_user(db):
    """Create admin user for testing."""
    auth_service = AuthService(db)
    admin = User(
        id=str(uuid.uuid4()),
        line_id="admin_line_id",
        name="Test Admin",
        role=UserRole.ADMIN,
        password_hash=auth_service.hash_password("admin123"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def worker_user(db):
    """Create worker user for testing."""
    worker = User(
        id=str(uuid.uuid4()),
        line_id="worker_line_id",
        name="Test Worker",
        role=UserRole.WORKER,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


@pytest.fixture
def authenticated_client(client, admin_user):
    """Create authenticated client with admin session."""
    # Login
    response = client.post(
        "/admin/login",
        data={"username": admin_user.name, "password": "admin123"}
    )
    assert response.status_code == 303
    return client


def test_requests_page_requires_authentication(client):
    """Test that requests page requires authentication."""
    response = client.get("/admin/requests")
    assert response.status_code == 401


def test_requests_page_loads(authenticated_client):
    """Test that requests page loads for authenticated admin."""
    response = authenticated_client.get("/admin/requests")
    assert response.status_code == 200
    assert "申請管理" in response.text


def test_get_all_requests_empty(authenticated_client, db):
    """Test getting all requests when none exist."""
    response = authenticated_client.get("/admin/api/requests")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_all_requests_with_data(authenticated_client, db, worker_user):
    """Test getting all requests with data."""
    # Create test requests
    next_month = date.today() + relativedelta(months=1)
    
    request1 = Request(
        id=str(uuid.uuid4()),
        worker_id=worker_user.id,
        request_date=next_month.replace(day=15),
        status=RequestStatus.PENDING,
        created_at=datetime.utcnow()
    )
    request2 = Request(
        id=str(uuid.uuid4()),
        worker_id=worker_user.id,
        request_date=next_month.replace(day=20),
        status=RequestStatus.APPROVED,
        created_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
        processed_by=worker_user.id
    )
    
    db.add(request1)
    db.add(request2)
    db.commit()
    
    # Get all requests
    response = authenticated_client.get("/admin/api/requests")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Check that pending request comes first (priority sorting)
    assert data[0]["status"] == "pending"
    assert data[0]["worker_name"] == worker_user.name
    assert data[1]["status"] == "approved"


def test_filter_requests_by_status(authenticated_client, db, worker_user):
    """Test filtering requests by status."""
    next_month = date.today() + relativedelta(months=1)
    
    # Create requests with different statuses
    pending_request = Request(
        id=str(uuid.uuid4()),
        worker_id=worker_user.id,
        request_date=next_month.replace(day=15),
        status=RequestStatus.PENDING,
        created_at=datetime.utcnow()
    )
    approved_request = Request(
        id=str(uuid.uuid4()),
        worker_id=worker_user.id,
        request_date=next_month.replace(day=20),
        status=RequestStatus.APPROVED,
        created_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
        processed_by=worker_user.id
    )
    
    db.add(pending_request)
    db.add(approved_request)
    db.commit()
    
    # Filter by pending status
    response = authenticated_client.get("/admin/api/requests?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "pending"
    
    # Filter by approved status
    response = authenticated_client.get("/admin/api/requests?status=approved")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "approved"


def test_search_requests_by_worker_name(authenticated_client, db):
    """Test searching requests by worker name."""
    # Create workers with different names
    worker1 = User(
        id=str(uuid.uuid4()),
        line_id="worker1_line_id",
        name="田中太郎",
        role=UserRole.WORKER,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    worker2 = User(
        id=str(uuid.uuid4()),
        line_id="worker2_line_id",
        name="佐藤花子",
        role=UserRole.WORKER,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(worker1)
    db.add(worker2)
    db.commit()
    
    next_month = date.today() + relativedelta(months=1)
    
    request1 = Request(
        id=str(uuid.uuid4()),
        worker_id=worker1.id,
        request_date=next_month.replace(day=15),
        status=RequestStatus.PENDING,
        created_at=datetime.utcnow()
    )
    request2 = Request(
        id=str(uuid.uuid4()),
        worker_id=worker2.id,
        request_date=next_month.replace(day=20),
        status=RequestStatus.PENDING,
        created_at=datetime.utcnow()
    )
    
    db.add(request1)
    db.add(request2)
    db.commit()
    
    # Search by partial name
    response = authenticated_client.get("/admin/api/requests?worker_name=田中")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["worker_name"] == "田中太郎"


def test_approve_request(authenticated_client, db, worker_user, admin_user):
    """Test approving a pending request."""
    next_month = date.today() + relativedelta(months=1)
    
    request = Request(
        id=str(uuid.uuid4()),
        worker_id=worker_user.id,
        request_date=next_month.replace(day=15),
        status=RequestStatus.PENDING,
        created_at=datetime.utcnow()
    )
    
    db.add(request)
    db.commit()
    
    # Approve the request
    response = authenticated_client.post(f"/admin/api/requests/{request.id}/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["processed_by"] == admin_user.id
    
    # Verify in database
    db.refresh(request)
    assert request.status == RequestStatus.APPROVED
    assert request.processed_by == admin_user.id
    assert request.processed_at is not None


def test_reject_request(authenticated_client, db, worker_user, admin_user):
    """Test rejecting a pending request."""
    next_month = date.today() + relativedelta(months=1)
    
    request = Request(
        id=str(uuid.uuid4()),
        worker_id=worker_user.id,
        request_date=next_month.replace(day=15),
        status=RequestStatus.PENDING,
        created_at=datetime.utcnow()
    )
    
    db.add(request)
    db.commit()
    
    # Reject the request
    response = authenticated_client.post(f"/admin/api/requests/{request.id}/reject")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["processed_by"] == admin_user.id
    
    # Verify in database
    db.refresh(request)
    assert request.status == RequestStatus.REJECTED
    assert request.processed_by == admin_user.id
    assert request.processed_at is not None


def test_cannot_approve_already_processed_request(authenticated_client, db, worker_user, admin_user):
    """Test that already processed requests cannot be approved again."""
    next_month = date.today() + relativedelta(months=1)
    
    request = Request(
        id=str(uuid.uuid4()),
        worker_id=worker_user.id,
        request_date=next_month.replace(day=15),
        status=RequestStatus.APPROVED,
        created_at=datetime.utcnow(),
        processed_at=datetime.utcnow(),
        processed_by=admin_user.id
    )
    
    db.add(request)
    db.commit()
    
    # Try to approve again
    response = authenticated_client.post(f"/admin/api/requests/{request.id}/approve")
    assert response.status_code == 400
    assert "Cannot approve request" in response.json()["detail"]


def test_approve_nonexistent_request(authenticated_client):
    """Test approving a nonexistent request."""
    fake_id = str(uuid.uuid4())
    response = authenticated_client.post(f"/admin/api/requests/{fake_id}/approve")
    assert response.status_code == 400
    assert "not found" in response.json()["detail"]
