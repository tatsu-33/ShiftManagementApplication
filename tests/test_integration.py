"""Integration tests for end-to-end flows."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime
from unittest.mock import patch, Mock
import json

from main import app
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus
from app.models.settings import Settings as SettingsModel
from app.services.auth_service import AuthService
from app.services.request_service import RequestService


# Create test database engine
engine = None
TestingSessionLocal = None


def get_test_engine():
    """Get or create test engine."""
    global engine, TestingSessionLocal
    if engine is None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine


@pytest.fixture(scope="function")
def test_db():
    """Create test database."""
    global engine, TestingSessionLocal
    
    # Create new engine for each test
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    db = TestingSessionLocal()
    
    # Override get_db dependency
    def override_get_db():
        try:
            yield db
        finally:
            pass  # Don't close here, let fixture handle it
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield db
    
    # Cleanup
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture
def test_client(test_db):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_worker(test_db):
    """Create test worker user."""
    auth_service = AuthService(test_db)
    worker = auth_service.register_worker("U1234567890abcdef", "Test Worker")
    test_db.commit()
    return worker


@pytest.fixture
def test_admin(test_db):
    """Create test admin user."""
    auth_service = AuthService(test_db)
    admin = auth_service.create_admin("testadmin", "testpassword123")
    test_db.commit()
    return admin


@pytest.fixture
def test_settings(test_db):
    """Create test settings."""
    import uuid
    setting = SettingsModel(
        id=str(uuid.uuid4()),
        key="deadline_day",
        value="10",
        updated_by="system"
    )
    test_db.add(setting)
    test_db.commit()
    return setting


class TestEndToEndRequestFlow:
    """Test complete request flow from creation to approval."""
    
    @patch('app.line_bot.webhook.line_bot_api')
    @patch('app.services.notification_service.line_bot_api')
    def test_complete_request_approval_flow(
        self,
        mock_notification_api,
        mock_webhook_api,
        test_client,
        test_db,
        test_worker,
        test_admin,
        test_settings
    ):
        """
        Test complete flow: worker creates request -> admin approves -> worker receives notification.
        
        This integration test validates:
        - Request creation through service
        - Admin authentication and authorization
        - Request approval through admin API
        - Notification sending
        """
        # Step 1: Worker creates a request (simulating LINE bot interaction)
        request_service = RequestService(test_db)
        
        # Create request for next month
        current_date = date(2024, 1, 5)  # Before deadline
        request_date = date(2024, 2, 15)  # Next month
        
        new_request = request_service.create_request(
            worker_id=test_worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        # Verify request was created with pending status
        assert new_request.status == RequestStatus.PENDING
        assert new_request.worker_id == test_worker.id
        assert new_request.request_date == request_date
        
        # Step 2: Admin logs in
        login_response = test_client.post(
            "/admin/login",
            data={"username": "testadmin", "password": "testpassword123"},
            follow_redirects=False
        )
        
        assert login_response.status_code == 303
        session_cookie = login_response.cookies.get("session_id")
        assert session_cookie is not None
        
        # Step 3: Admin views requests
        requests_response = test_client.get(
            "/admin/requests",
            cookies={"session_id": session_cookie}
        )
        
        assert requests_response.status_code == 200
        assert "Test Worker" in requests_response.text
        assert "2024-02-15" in requests_response.text
        
        # Step 4: Admin approves the request
        approve_response = test_client.post(
            f"/admin/requests/{new_request.id}/approve",
            cookies={"session_id": session_cookie},
            follow_redirects=False
        )
        
        assert approve_response.status_code == 303
        
        # Step 5: Verify request status was updated
        test_db.refresh(new_request)
        assert new_request.status == RequestStatus.APPROVED
        assert new_request.processed_by == test_admin.id
        assert new_request.processed_at is not None
        
        # Step 6: Verify notification was sent
        mock_notification_api.push_message.assert_called_once()
        call_args = mock_notification_api.push_message.call_args
        assert call_args[0][0] == test_worker.line_id
        
        # Verify notification message contains approval info
        message = call_args[0][1]
        assert hasattr(message, 'text')
        assert "承認" in message.text
        assert "2024年02月15日" in message.text
    
    @patch('app.line_bot.webhook.line_bot_api')
    @patch('app.services.notification_service.line_bot_api')
    def test_complete_request_rejection_flow(
        self,
        mock_notification_api,
        mock_webhook_api,
        test_client,
        test_db,
        test_worker,
        test_admin,
        test_settings
    ):
        """
        Test complete flow: worker creates request -> admin rejects -> worker receives notification.
        """
        # Step 1: Worker creates a request
        request_service = RequestService(test_db)
        
        current_date = date(2024, 1, 5)
        request_date = date(2024, 2, 20)
        
        new_request = request_service.create_request(
            worker_id=test_worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        assert new_request.status == RequestStatus.PENDING
        
        # Step 2: Admin logs in
        login_response = test_client.post(
            "/admin/login",
            data={"username": "testadmin", "password": "testpassword123"},
            follow_redirects=False
        )
        
        session_cookie = login_response.cookies.get("session_id")
        
        # Step 3: Admin rejects the request
        reject_response = test_client.post(
            f"/admin/requests/{new_request.id}/reject",
            cookies={"session_id": session_cookie},
            follow_redirects=False
        )
        
        assert reject_response.status_code == 303
        
        # Step 4: Verify request status was updated
        test_db.refresh(new_request)
        assert new_request.status == RequestStatus.REJECTED
        assert new_request.processed_by == test_admin.id
        assert new_request.processed_at is not None
        
        # Step 5: Verify notification was sent
        mock_notification_api.push_message.assert_called_once()
        call_args = mock_notification_api.push_message.call_args
        assert call_args[0][0] == test_worker.line_id
        
        # Verify notification message contains rejection info
        message = call_args[0][1]
        assert hasattr(message, 'text')
        assert "却下" in message.text
        assert "2024年02月20日" in message.text
    
    def test_duplicate_request_prevention(
        self,
        test_client,
        test_db,
        test_worker,
        test_settings
    ):
        """
        Test that duplicate requests are prevented.
        """
        request_service = RequestService(test_db)
        
        current_date = date(2024, 1, 5)
        request_date = date(2024, 2, 15)
        
        # Create first request
        first_request = request_service.create_request(
            worker_id=test_worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        assert first_request.status == RequestStatus.PENDING
        
        # Try to create duplicate request
        from app.exceptions import DuplicateRequestError
        
        with pytest.raises(DuplicateRequestError) as exc_info:
            request_service.create_request(
                worker_id=test_worker.id,
                request_date=request_date,
                current_date=current_date
            )
        
        assert "already has a request" in str(exc_info.value)
    
    def test_deadline_enforcement(
        self,
        test_client,
        test_db,
        test_worker,
        test_settings
    ):
        """
        Test that requests after deadline are rejected.
        """
        request_service = RequestService(test_db)
        
        # Try to create request after deadline (day 11, deadline is day 10)
        current_date = date(2024, 1, 11)
        request_date = date(2024, 2, 15)
        
        from app.exceptions import DeadlineExceededError
        
        with pytest.raises(DeadlineExceededError) as exc_info:
            request_service.create_request(
                worker_id=test_worker.id,
                request_date=request_date,
                current_date=current_date
            )
        
        assert "deadline" in str(exc_info.value).lower()


class TestLINEWebhookIntegration:
    """Test LINE webhook processing integration."""
    
    @patch('app.line_bot.webhook.webhook_handler')
    @patch('app.line_bot.webhook.line_bot_api')
    def test_webhook_text_message_processing(
        self,
        mock_api,
        mock_handler,
        test_client,
        test_db,
        test_worker
    ):
        """
        Test complete webhook processing for text messages.
        """
        # Mock webhook_handler.handle to succeed
        mock_handler.handle.return_value = None
        
        # Create valid LINE event
        line_event = {
            "events": [
                {
                    "type": "message",
                    "replyToken": "test_reply_token",
                    "source": {
                        "userId": test_worker.line_id,
                        "type": "user"
                    },
                    "timestamp": 1234567890123,
                    "message": {
                        "type": "text",
                        "id": "test_message_id",
                        "text": "申請"
                    }
                }
            ]
        }
        
        # Send webhook request
        response = test_client.post(
            "/webhook/line",
            json=line_event,
            headers={"X-Line-Signature": "valid_signature"}
        )
        
        # Verify webhook was processed
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        # Verify webhook_handler.handle was called
        mock_handler.handle.assert_called_once()
    
    @patch('app.line_bot.webhook.webhook_handler')
    @patch('app.line_bot.webhook.line_bot_api')
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_webhook_postback_request_creation(
        self,
        mock_request_service,
        mock_auth_service,
        mock_api,
        mock_handler,
        test_client,
        test_db,
        test_worker
    ):
        """
        Test webhook processing for postback events (date selection).
        """
        # Mock services
        mock_auth_service.return_value.get_worker_by_line_id.return_value = test_worker
        
        mock_request = Mock(spec=Request)
        mock_request.id = "request123"
        mock_request.request_date = date(2024, 2, 15)
        mock_request.status = RequestStatus.PENDING
        mock_request_service.return_value.create_request.return_value = mock_request
        
        # Mock webhook_handler.handle to succeed
        mock_handler.handle.return_value = None
        
        # Create postback event for date selection
        line_event = {
            "events": [
                {
                    "type": "postback",
                    "replyToken": "test_reply_token",
                    "source": {
                        "userId": test_worker.line_id,
                        "type": "user"
                    },
                    "timestamp": 1234567890123,
                    "postback": {
                        "data": "action=request_date&date=2024-02-15"
                    }
                }
            ]
        }
        
        # Send webhook request
        response = test_client.post(
            "/webhook/line",
            json=line_event,
            headers={"X-Line-Signature": "valid_signature"}
        )
        
        # Verify webhook was processed
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    @patch('app.line_bot.webhook.webhook_handler')
    def test_webhook_invalid_signature_rejection(
        self,
        mock_handler,
        test_client
    ):
        """
        Test that webhook rejects requests with invalid signatures.
        """
        from linebot.exceptions import InvalidSignatureError
        
        # Mock webhook_handler.handle to raise InvalidSignatureError
        mock_handler.handle.side_effect = InvalidSignatureError("Invalid signature")
        
        line_event = {
            "events": []
        }
        
        # Send webhook request with invalid signature
        response = test_client.post(
            "/webhook/line",
            json=line_event,
            headers={"X-Line-Signature": "invalid_signature"}
        )
        
        # Verify request was rejected
        assert response.status_code == 400
        assert "signature" in response.json()["detail"].lower()
    
    @patch('app.line_bot.webhook.webhook_handler')
    def test_webhook_missing_signature_rejection(
        self,
        mock_handler,
        test_client
    ):
        """
        Test that webhook rejects requests without signature header.
        """
        line_event = {
            "events": []
        }
        
        # Send webhook request without signature header
        response = test_client.post(
            "/webhook/line",
            json=line_event,
            headers={}
        )
        
        # Verify request was rejected
        assert response.status_code == 400
        assert "signature" in response.json()["detail"].lower()


class TestAdminAuthenticationFlow:
    """Test admin authentication and authorization flow."""
    
    def test_complete_admin_login_flow(
        self,
        test_client,
        test_db,
        test_admin
    ):
        """
        Test complete admin login and access flow.
        """
        # Step 1: Access login page
        login_page_response = test_client.get("/admin/login")
        assert login_page_response.status_code == 200
        assert "管理者ログイン" in login_page_response.text
        
        # Step 2: Submit login credentials
        login_response = test_client.post(
            "/admin/login",
            data={"username": "testadmin", "password": "testpassword123"},
            follow_redirects=False
        )
        
        # Verify redirect to dashboard
        assert login_response.status_code == 303
        assert login_response.headers["location"] == "/admin/dashboard"
        
        # Verify session cookie was set
        session_cookie = login_response.cookies.get("session_id")
        assert session_cookie is not None
        
        # Step 3: Access dashboard with session
        dashboard_response = test_client.get(
            "/admin/dashboard",
            cookies={"session_id": session_cookie}
        )
        
        assert dashboard_response.status_code == 200
        assert "testadmin" in dashboard_response.text
        
        # Step 4: Access protected resources
        requests_response = test_client.get(
            "/admin/requests",
            cookies={"session_id": session_cookie}
        )
        
        assert requests_response.status_code == 200
        
        shifts_response = test_client.get(
            "/admin/shifts",
            cookies={"session_id": session_cookie}
        )
        
        assert shifts_response.status_code == 200
        
        settings_response = test_client.get(
            "/admin/settings",
            cookies={"session_id": session_cookie}
        )
        
        assert settings_response.status_code == 200
    
    def test_admin_login_with_invalid_credentials(
        self,
        test_client,
        test_db,
        test_admin
    ):
        """
        Test admin login fails with invalid credentials.
        """
        # Try to login with wrong password
        login_response = test_client.post(
            "/admin/login",
            data={"username": "testadmin", "password": "wrongpassword"},
            follow_redirects=False
        )
        
        # Verify login failed
        assert login_response.status_code == 401
        assert "Invalid username or password" in login_response.text
        
        # Verify no session cookie was set
        assert "session_id" not in login_response.cookies
    
    def test_unauthorized_access_to_admin_pages(
        self,
        test_client,
        test_db
    ):
        """
        Test that admin pages require authentication.
        """
        # Try to access dashboard without authentication
        dashboard_response = test_client.get(
            "/admin/dashboard",
            follow_redirects=False
        )
        
        assert dashboard_response.status_code == 401
        
        # Try to access requests page without authentication
        requests_response = test_client.get(
            "/admin/requests",
            follow_redirects=False
        )
        
        assert requests_response.status_code == 401
        
        # Try to access shifts page without authentication
        shifts_response = test_client.get(
            "/admin/shifts",
            follow_redirects=False
        )
        
        assert shifts_response.status_code == 401
        
        # Try to access settings page without authentication
        settings_response = test_client.get(
            "/admin/settings",
            follow_redirects=False
        )
        
        assert settings_response.status_code == 401
    
    def test_admin_logout_flow(
        self,
        test_client,
        test_db,
        test_admin
    ):
        """
        Test complete admin logout flow.
        """
        # Step 1: Login
        login_response = test_client.post(
            "/admin/login",
            data={"username": "testadmin", "password": "testpassword123"},
            follow_redirects=False
        )
        
        session_cookie = login_response.cookies.get("session_id")
        assert session_cookie is not None
        
        # Step 2: Verify access to dashboard
        dashboard_response = test_client.get(
            "/admin/dashboard",
            cookies={"session_id": session_cookie}
        )
        
        assert dashboard_response.status_code == 200
        
        # Step 3: Logout
        logout_response = test_client.post(
            "/admin/logout",
            cookies={"session_id": session_cookie},
            follow_redirects=False
        )
        
        # Verify redirect to login page
        assert logout_response.status_code == 303
        assert logout_response.headers["location"] == "/admin/login"
        
        # Step 4: Verify session is invalidated
        dashboard_response_after_logout = test_client.get(
            "/admin/dashboard",
            cookies={"session_id": session_cookie},
            follow_redirects=False
        )
        
        assert dashboard_response_after_logout.status_code == 401
    
    def test_admin_session_persistence(
        self,
        test_client,
        test_db,
        test_admin
    ):
        """
        Test that admin session persists across multiple requests.
        """
        # Login
        login_response = test_client.post(
            "/admin/login",
            data={"username": "testadmin", "password": "testpassword123"},
            follow_redirects=False
        )
        
        session_cookie = login_response.cookies.get("session_id")
        
        # Make multiple requests with same session
        for _ in range(5):
            response = test_client.get(
                "/admin/dashboard",
                cookies={"session_id": session_cookie}
            )
            assert response.status_code == 200
            assert "testadmin" in response.text


class TestRequestSearchAndFilter:
    """Test request search and filter functionality."""
    
    def test_admin_search_requests_by_worker_name(
        self,
        test_client,
        test_db,
        test_admin,
        test_settings
    ):
        """
        Test admin can search requests by worker name.
        """
        # Create multiple workers and requests
        auth_service = AuthService(test_db)
        request_service = RequestService(test_db)
        
        worker1 = auth_service.register_worker("U111", "田中太郎")
        worker2 = auth_service.register_worker("U222", "佐藤花子")
        test_db.commit()
        
        current_date = date(2024, 1, 5)
        
        request1 = request_service.create_request(
            worker_id=worker1.id,
            request_date=date(2024, 2, 15),
            current_date=current_date
        )
        
        request2 = request_service.create_request(
            worker_id=worker2.id,
            request_date=date(2024, 2, 20),
            current_date=current_date
        )
        
        # Login as admin
        login_response = test_client.post(
            "/admin/login",
            data={"username": "testadmin", "password": "testpassword123"},
            follow_redirects=False
        )
        
        session_cookie = login_response.cookies.get("session_id")
        
        # Search for "田中"
        search_response = test_client.get(
            "/admin/requests?search=田中",
            cookies={"session_id": session_cookie}
        )
        
        assert search_response.status_code == 200
        assert "田中太郎" in search_response.text
        assert "佐藤花子" not in search_response.text
    
    def test_admin_filter_requests_by_status(
        self,
        test_client,
        test_db,
        test_admin,
        test_settings
    ):
        """
        Test admin can filter requests by status.
        """
        # Create worker and multiple requests
        auth_service = AuthService(test_db)
        request_service = RequestService(test_db)
        
        worker = auth_service.register_worker("U123", "Test Worker")
        test_db.commit()
        
        current_date = date(2024, 1, 5)
        
        # Create pending request
        pending_request = request_service.create_request(
            worker_id=worker.id,
            request_date=date(2024, 2, 15),
            current_date=current_date
        )
        
        # Create and approve another request
        approved_request = request_service.create_request(
            worker_id=worker.id,
            request_date=date(2024, 2, 20),
            current_date=current_date
        )
        
        request_service.approve_request(approved_request.id, test_admin.id)
        
        # Login as admin
        login_response = test_client.post(
            "/admin/login",
            data={"username": "testadmin", "password": "testpassword123"},
            follow_redirects=False
        )
        
        session_cookie = login_response.cookies.get("session_id")
        
        # Filter for pending requests
        pending_response = test_client.get(
            "/admin/requests?status=pending",
            cookies={"session_id": session_cookie}
        )
        
        assert pending_response.status_code == 200
        assert "2024-02-15" in pending_response.text
        
        # Filter for approved requests
        approved_response = test_client.get(
            "/admin/requests?status=approved",
            cookies={"session_id": session_cookie}
        )
        
        assert approved_response.status_code == 200
        assert "2024-02-20" in approved_response.text


class TestDataPersistence:
    """Test data persistence across operations."""
    
    def test_request_data_persists_after_creation(
        self,
        test_db,
        test_worker,
        test_settings
    ):
        """
        Test that request data persists correctly in database.
        """
        request_service = RequestService(test_db)
        
        current_date = date(2024, 1, 5)
        request_date = date(2024, 2, 15)
        
        # Create request
        new_request = request_service.create_request(
            worker_id=test_worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        request_id = new_request.id
        
        # Clear session to force database read
        test_db.expire_all()
        
        # Retrieve request from database
        retrieved_request = test_db.query(Request).filter(
            Request.id == request_id
        ).first()
        
        # Verify all fields persisted correctly
        assert retrieved_request is not None
        assert retrieved_request.worker_id == test_worker.id
        assert retrieved_request.request_date == request_date
        assert retrieved_request.status == RequestStatus.PENDING
        assert retrieved_request.created_at is not None
        assert retrieved_request.processed_at is None
        assert retrieved_request.processed_by is None
    
    def test_request_status_update_persists(
        self,
        test_db,
        test_worker,
        test_admin,
        test_settings
    ):
        """
        Test that request status updates persist correctly.
        """
        request_service = RequestService(test_db)
        
        current_date = date(2024, 1, 5)
        request_date = date(2024, 2, 15)
        
        # Create request
        new_request = request_service.create_request(
            worker_id=test_worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        request_id = new_request.id
        
        # Approve request
        request_service.approve_request(request_id, test_admin.id)
        
        # Clear session
        test_db.expire_all()
        
        # Retrieve updated request
        updated_request = test_db.query(Request).filter(
            Request.id == request_id
        ).first()
        
        # Verify status update persisted
        assert updated_request.status == RequestStatus.APPROVED
        assert updated_request.processed_by == test_admin.id
        assert updated_request.processed_at is not None
    
    def test_user_data_persists_after_registration(
        self,
        test_db
    ):
        """
        Test that user data persists correctly after registration.
        """
        auth_service = AuthService(test_db)
        
        line_id = "U9876543210fedcba"
        name = "New Worker"
        
        # Register worker
        new_worker = auth_service.register_worker(line_id, name)
        worker_id = new_worker.id
        
        # Clear session
        test_db.expire_all()
        
        # Retrieve worker from database
        retrieved_worker = test_db.query(User).filter(
            User.id == worker_id
        ).first()
        
        # Verify all fields persisted correctly
        assert retrieved_worker is not None
        assert retrieved_worker.line_id == line_id
        assert retrieved_worker.name == name
        assert retrieved_worker.role == UserRole.WORKER
        assert retrieved_worker.created_at is not None
