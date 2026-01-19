"""Tests for admin login functionality."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.services.auth_service import AuthService
from main import app


# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin.db"
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
    """Create test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_client(test_db):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_admin(test_db):
    """Create test admin user."""
    db = TestingSessionLocal()
    try:
        auth_service = AuthService(db)
        admin = auth_service.create_admin("testadmin", "testpassword123")
        db.commit()
        return admin
    finally:
        db.close()


def test_login_page_loads(test_client):
    """Test that login page loads successfully."""
    response = test_client.get("/admin/login")
    assert response.status_code == 200
    assert "管理者ログイン" in response.text


def test_login_with_valid_credentials(test_client, test_admin):
    """Test login with valid credentials."""
    response = test_client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "testpassword123"},
        follow_redirects=False
    )
    
    # Should redirect to dashboard
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/dashboard"
    
    # Should set session cookie
    assert "session_id" in response.cookies


def test_login_with_invalid_credentials(test_client, test_admin):
    """Test login with invalid credentials."""
    response = test_client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "wrongpassword"},
        follow_redirects=False
    )
    
    # Should return 401 with error message
    assert response.status_code == 401
    assert "Invalid username or password" in response.text


def test_login_with_nonexistent_user(test_client):
    """Test login with non-existent user."""
    response = test_client.post(
        "/admin/login",
        data={"username": "nonexistent", "password": "password"},
        follow_redirects=False
    )
    
    # Should return 401 with error message
    assert response.status_code == 401
    assert "Invalid username or password" in response.text


def test_dashboard_requires_authentication(test_client):
    """Test that dashboard requires authentication."""
    response = test_client.get("/admin/dashboard", follow_redirects=False)
    
    # Should return 401 unauthorized
    assert response.status_code == 401


def test_dashboard_accessible_after_login(test_client, test_admin):
    """Test that dashboard is accessible after login."""
    # Login first
    login_response = test_client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "testpassword123"},
        follow_redirects=False
    )
    
    # Get session cookie
    session_cookie = login_response.cookies.get("session_id")
    
    # Access dashboard with session
    response = test_client.get(
        "/admin/dashboard",
        cookies={"session_id": session_cookie}
    )
    
    assert response.status_code == 200
    assert "testadmin" in response.text


def test_logout(test_client, test_admin):
    """Test logout functionality."""
    # Login first
    login_response = test_client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "testpassword123"},
        follow_redirects=False
    )
    
    session_cookie = login_response.cookies.get("session_id")
    
    # Logout
    logout_response = test_client.post(
        "/admin/logout",
        cookies={"session_id": session_cookie},
        follow_redirects=False
    )
    
    # Should redirect to login
    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/admin/login"
    
    # Try to access dashboard with old session - should fail
    dashboard_response = test_client.get(
        "/admin/dashboard",
        cookies={"session_id": session_cookie},
        follow_redirects=False
    )
    assert dashboard_response.status_code == 401


def test_redirect_to_dashboard_if_already_logged_in(test_client, test_admin):
    """Test that accessing login page redirects to dashboard if already logged in."""
    # Login first
    login_response = test_client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "testpassword123"},
        follow_redirects=False
    )
    
    session_cookie = login_response.cookies.get("session_id")
    
    # Try to access login page again
    response = test_client.get(
        "/admin/login",
        cookies={"session_id": session_cookie},
        follow_redirects=False
    )
    
    # Should redirect to dashboard
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/dashboard"
