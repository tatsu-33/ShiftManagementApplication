"""Tests for LINE webhook handler."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from linebot.exceptions import InvalidSignatureError
import json

from main import app
from app.database import get_db


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = Mock()
    return db


@pytest.fixture
def valid_line_event():
    """Create a valid LINE webhook event payload."""
    return {
        "events": [
            {
                "type": "message",
                "replyToken": "test_reply_token",
                "source": {
                    "userId": "U1234567890abcdef",
                    "type": "user"
                },
                "timestamp": 1234567890123,
                "message": {
                    "type": "text",
                    "id": "test_message_id",
                    "text": "Hello"
                }
            }
        ]
    }


class TestLineWebhook:
    """Test LINE webhook handler."""
    
    def test_webhook_missing_signature(self, client):
        """Test webhook rejects requests without signature header."""
        response = client.post(
            "/webhook/line",
            json={"events": []},
            headers={}
        )
        
        assert response.status_code == 400
        assert "signature" in response.json()["detail"].lower()
    
    @patch('app.line_bot.webhook.webhook_handler')
    def test_webhook_invalid_signature(self, mock_handler, client):
        """Test webhook rejects requests with invalid signature."""
        # Mock webhook_handler.handle to raise InvalidSignatureError
        mock_handler.handle.side_effect = InvalidSignatureError("Invalid signature")
        
        response = client.post(
            "/webhook/line",
            json={"events": []},
            headers={"X-Line-Signature": "invalid_signature"}
        )
        
        assert response.status_code == 400
        assert "signature" in response.json()["detail"].lower()
    
    @patch('app.line_bot.webhook.webhook_handler')
    def test_webhook_valid_request(self, mock_handler, client, valid_line_event):
        """Test webhook accepts valid requests with correct signature."""
        # Mock webhook_handler.handle to succeed
        mock_handler.handle.return_value = None
        
        response = client.post(
            "/webhook/line",
            json=valid_line_event,
            headers={"X-Line-Signature": "valid_signature"}
        )
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        # Verify webhook_handler.handle was called
        mock_handler.handle.assert_called_once()
    
    @patch('app.line_bot.webhook.line_bot_api')
    @patch('app.line_bot.webhook.webhook_handler')
    def test_text_message_handler(self, mock_handler, mock_api):
        """Test text message event handler."""
        from app.line_bot.webhook import handle_text_message
        from linebot.models import MessageEvent, TextMessage, SourceUser
        
        # Create mock event
        event = Mock(spec=MessageEvent)
        event.source = Mock(spec=SourceUser)
        event.source.user_id = "U1234567890abcdef"
        event.message = Mock(spec=TextMessage)
        event.message.text = "Test message"
        event.reply_token = "test_reply_token"
        
        # Call handler
        handle_text_message(event)
        
        # Verify reply was sent
        mock_api.reply_message.assert_called_once()
        call_args = mock_api.reply_message.call_args
        assert call_args[0][0] == "test_reply_token"
    
    @patch('app.line_bot.webhook.line_bot_api')
    @patch('app.line_bot.webhook.webhook_handler')
    def test_postback_handler(self, mock_handler, mock_api):
        """Test postback event handler."""
        from app.line_bot.webhook import handle_postback
        from linebot.models import PostbackEvent, SourceUser
        
        # Create mock event
        event = Mock(spec=PostbackEvent)
        event.source = Mock(spec=SourceUser)
        event.source.user_id = "U1234567890abcdef"
        event.postback = Mock()
        event.postback.data = "action=test"
        event.reply_token = "test_reply_token"
        
        # Call handler
        handle_postback(event)
        
        # Verify reply was sent
        mock_api.reply_message.assert_called_once()
        call_args = mock_api.reply_message.call_args
        assert call_args[0][0] == "test_reply_token"
    
    @patch('app.line_bot.webhook.line_bot_api')
    @patch('app.line_bot.webhook.webhook_handler')
    def test_follow_handler(self, mock_handler, mock_api):
        """Test follow event handler."""
        from app.line_bot.webhook import handle_follow
        from linebot.models import FollowEvent, SourceUser
        
        # Create mock event
        event = Mock(spec=FollowEvent)
        event.source = Mock(spec=SourceUser)
        event.source.user_id = "U1234567890abcdef"
        event.reply_token = "test_reply_token"
        
        # Call handler
        handle_follow(event)
        
        # Verify welcome message was sent
        mock_api.reply_message.assert_called_once()
        call_args = mock_api.reply_message.call_args
        assert call_args[0][0] == "test_reply_token"
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_get_user_profile_success(self, mock_api):
        """Test getting user profile successfully."""
        from app.line_bot.webhook import get_user_profile
        
        # Mock profile response
        mock_profile = Mock()
        mock_profile.display_name = "Test User"
        mock_profile.user_id = "U1234567890abcdef"
        mock_profile.picture_url = "https://example.com/picture.jpg"
        mock_profile.status_message = "Hello"
        mock_api.get_profile.return_value = mock_profile
        
        # Get profile
        profile = get_user_profile("U1234567890abcdef")
        
        # Verify
        assert profile is not None
        assert profile["display_name"] == "Test User"
        assert profile["user_id"] == "U1234567890abcdef"
        mock_api.get_profile.assert_called_once_with("U1234567890abcdef")
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_get_user_profile_error(self, mock_api):
        """Test getting user profile with error."""
        from app.line_bot.webhook import get_user_profile
        
        # Mock API error (use generic Exception instead of LineBotApiError)
        mock_api.get_profile.side_effect = Exception("API Error")
        
        # Get profile
        profile = get_user_profile("U1234567890abcdef")
        
        # Verify returns None on error
        assert profile is None
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_send_message_success(self, mock_api):
        """Test sending message successfully."""
        from app.line_bot.webhook import send_message
        
        # Send message
        result = send_message("U1234567890abcdef", "Test message")
        
        # Verify
        assert result is True
        mock_api.push_message.assert_called_once()
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_send_message_error(self, mock_api):
        """Test sending message with error."""
        from app.line_bot.webhook import send_message
        
        # Mock API error (use generic Exception instead of LineBotApiError)
        mock_api.push_message.side_effect = Exception("API Error")
        
        # Send message
        result = send_message("U1234567890abcdef", "Test message")
        
        # Verify returns False on error
        assert result is False


class TestCalendarGeneration:
    """Test calendar UI generation functionality."""
    
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_generate_calendar_flex_message_structure(self, mock_request_service, mock_auth_service, mock_db):
        """Test calendar flex message has correct structure."""
        from app.line_bot.webhook import generate_calendar_flex_message
        from datetime import date
        
        # Mock services
        mock_auth_service.return_value.get_worker_by_line_id.return_value = None
        mock_request_service.return_value.get_requests_by_worker.return_value = []
        
        # Generate calendar for a specific date
        current_date = date(2024, 1, 15)
        flex_message = generate_calendar_flex_message("U1234567890abcdef", mock_db, current_date)
        
        # Verify structure
        assert flex_message["type"] == "bubble"
        assert "header" in flex_message
        assert "body" in flex_message
        assert "footer" in flex_message
        
        # Verify header contains next month (February 2024)
        header_text = flex_message["header"]["contents"][0]["text"]
        assert "2024" in header_text
        assert "2月" in header_text
    
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_generate_calendar_shows_next_month_only(self, mock_request_service, mock_auth_service, mock_db):
        """Test calendar shows only next month dates."""
        from app.line_bot.webhook import generate_calendar_flex_message
        from datetime import date
        
        # Mock services
        mock_auth_service.return_value.get_worker_by_line_id.return_value = None
        mock_request_service.return_value.get_requests_by_worker.return_value = []
        
        # Generate calendar for January 2024
        current_date = date(2024, 1, 15)
        flex_message = generate_calendar_flex_message("U1234567890abcdef", mock_db, current_date)
        
        # Calendar should show February 2024
        # Verify by checking the header
        header_text = flex_message["header"]["contents"][0]["text"]
        assert "2024年2月" in header_text
    
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_generate_calendar_disables_requested_dates(self, mock_request_service, mock_auth_service, mock_db):
        """Test calendar disables already requested dates."""
        from app.line_bot.webhook import generate_calendar_flex_message
        from datetime import date
        from app.models.request import Request, RequestStatus
        
        # Mock worker
        mock_worker = Mock()
        mock_worker.id = "worker123"
        mock_auth_service.return_value.get_worker_by_line_id.return_value = mock_worker
        
        # Mock existing request for February 14, 2024
        mock_request = Mock(spec=Request)
        mock_request.request_date = date(2024, 2, 14)
        mock_request.status = RequestStatus.PENDING
        mock_request_service.return_value.get_requests_by_worker.return_value = [mock_request]
        
        # Generate calendar for January 2024
        current_date = date(2024, 1, 15)
        flex_message = generate_calendar_flex_message("U1234567890abcdef", mock_db, current_date)
        
        # Find buttons in the calendar body
        body_contents = flex_message["body"]["contents"]
        
        # Look for buttons with date 14
        found_disabled = False
        for row in body_contents:
            if row["type"] == "box" and "contents" in row:
                for item in row["contents"]:
                    if item["type"] == "button":
                        if item["action"]["label"] == "14":
                            # Check if it's disabled (gray color)
                            if item["color"] == "#aaaaaa":
                                found_disabled = True
                                # Verify the action is request_disabled
                                assert "request_disabled" in item["action"]["data"]
        
        assert found_disabled, "Date 14 should be disabled"
    
    @patch('app.line_bot.webhook.line_bot_api')
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_show_calendar_sends_flex_message(self, mock_request_service, mock_auth_service, mock_api, mock_db):
        """Test show_calendar sends a flex message."""
        from app.line_bot.webhook import show_calendar
        
        # Mock services
        mock_auth_service.return_value.get_worker_by_line_id.return_value = None
        mock_request_service.return_value.get_requests_by_worker.return_value = []
        
        # Show calendar
        result = show_calendar("U1234567890abcdef", "test_reply_token", mock_db)
        
        # Verify
        assert result is True
        mock_api.reply_message.assert_called_once()
        
        # Verify FlexSendMessage was sent
        call_args = mock_api.reply_message.call_args
        assert call_args[0][0] == "test_reply_token"
        # The second argument should be a FlexSendMessage
        flex_message = call_args[0][1]
        assert hasattr(flex_message, 'alt_text')
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_show_calendar_handles_error(self, mock_api, mock_db):
        """Test show_calendar handles errors gracefully."""
        from app.line_bot.webhook import show_calendar
        
        # Mock API error
        mock_api.reply_message.side_effect = Exception("API Error")
        
        # Show calendar
        result = show_calendar("U1234567890abcdef", "test_reply_token", mock_db)
        
        # Verify returns False on error
        assert result is False




class TestRequestListDisplay:
    """Test request list display functionality."""
    
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_generate_request_list_flex_message_structure(self, mock_request_service, mock_auth_service, mock_db):
        """Test request list flex message has correct structure."""
        from app.line_bot.webhook import generate_request_list_flex_message
        
        # Mock worker
        mock_worker = Mock()
        mock_worker.id = "worker123"
        mock_auth_service.return_value.get_worker_by_line_id.return_value = mock_worker
        
        # Mock empty request list
        mock_request_service.return_value.get_requests_by_worker.return_value = []
        
        # Generate request list
        flex_message = generate_request_list_flex_message("U1234567890abcdef", mock_db)
        
        # Verify structure
        assert flex_message["type"] == "bubble"
        assert "header" in flex_message
        assert "body" in flex_message
        assert "footer" in flex_message
        
        # Verify header
        header_text = flex_message["header"]["contents"][0]["text"]
        assert "申請一覧" in header_text
    
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_generate_request_list_shows_all_requests(self, mock_request_service, mock_auth_service, mock_db):
        """Test request list shows all worker requests."""
        from app.line_bot.webhook import generate_request_list_flex_message
        from datetime import date, datetime
        from app.models.request import Request, RequestStatus
        
        # Mock worker
        mock_worker = Mock()
        mock_worker.id = "worker123"
        mock_auth_service.return_value.get_worker_by_line_id.return_value = mock_worker
        
        # Mock requests with different statuses
        mock_request1 = Mock(spec=Request)
        mock_request1.request_date = date(2024, 2, 15)
        mock_request1.status = RequestStatus.PENDING
        mock_request1.created_at = datetime(2024, 1, 10, 10, 30)
        
        mock_request2 = Mock(spec=Request)
        mock_request2.request_date = date(2024, 2, 20)
        mock_request2.status = RequestStatus.APPROVED
        mock_request2.created_at = datetime(2024, 1, 11, 14, 15)
        
        mock_request3 = Mock(spec=Request)
        mock_request3.request_date = date(2024, 2, 25)
        mock_request3.status = RequestStatus.REJECTED
        mock_request3.created_at = datetime(2024, 1, 12, 9, 0)
        
        mock_request_service.return_value.get_requests_by_worker.return_value = [
            mock_request1, mock_request2, mock_request3
        ]
        
        # Generate request list
        flex_message = generate_request_list_flex_message("U1234567890abcdef", mock_db)
        
        # Verify header shows count
        count_text = flex_message["header"]["contents"][1]["text"]
        assert "3" in count_text
        
        # Verify body contains request items
        body_contents = flex_message["body"]["contents"]
        assert len(body_contents) == 3
    
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_generate_request_list_color_codes_by_status(self, mock_request_service, mock_auth_service, mock_db):
        """Test request list color codes requests by status."""
        from app.line_bot.webhook import generate_request_list_flex_message
        from datetime import date, datetime
        from app.models.request import Request, RequestStatus
        
        # Mock worker
        mock_worker = Mock()
        mock_worker.id = "worker123"
        mock_auth_service.return_value.get_worker_by_line_id.return_value = mock_worker
        
        # Mock requests with different statuses
        mock_request_pending = Mock(spec=Request)
        mock_request_pending.request_date = date(2024, 2, 15)
        mock_request_pending.status = RequestStatus.PENDING
        mock_request_pending.created_at = datetime(2024, 1, 10, 10, 30)
        
        mock_request_approved = Mock(spec=Request)
        mock_request_approved.request_date = date(2024, 2, 20)
        mock_request_approved.status = RequestStatus.APPROVED
        mock_request_approved.created_at = datetime(2024, 1, 11, 14, 15)
        
        mock_request_rejected = Mock(spec=Request)
        mock_request_rejected.request_date = date(2024, 2, 25)
        mock_request_rejected.status = RequestStatus.REJECTED
        mock_request_rejected.created_at = datetime(2024, 1, 12, 9, 0)
        
        mock_request_service.return_value.get_requests_by_worker.return_value = [
            mock_request_pending, mock_request_approved, mock_request_rejected
        ]
        
        # Generate request list
        flex_message = generate_request_list_flex_message("U1234567890abcdef", mock_db)
        
        # Verify body contains colored status texts
        body_contents = flex_message["body"]["contents"]
        
        # Check first item (pending - orange)
        pending_item = body_contents[0]
        status_text = pending_item["contents"][0]["contents"][1]
        assert status_text["text"] == "保留中"
        assert status_text["color"] == "#FFA500"
        
        # Check second item (approved - green)
        approved_item = body_contents[1]
        status_text = approved_item["contents"][0]["contents"][1]
        assert status_text["text"] == "承認済み"
        assert status_text["color"] == "#17c950"
        
        # Check third item (rejected - red)
        rejected_item = body_contents[2]
        status_text = rejected_item["contents"][0]["contents"][1]
        assert status_text["text"] == "却下"
        assert status_text["color"] == "#ff0000"
    
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_generate_request_list_includes_required_fields(self, mock_request_service, mock_auth_service, mock_db):
        """Test request list includes date, status, and created_at."""
        from app.line_bot.webhook import generate_request_list_flex_message
        from datetime import date, datetime
        from app.models.request import Request, RequestStatus
        
        # Mock worker
        mock_worker = Mock()
        mock_worker.id = "worker123"
        mock_auth_service.return_value.get_worker_by_line_id.return_value = mock_worker
        
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.request_date = date(2024, 2, 15)
        mock_request.status = RequestStatus.PENDING
        mock_request.created_at = datetime(2024, 1, 10, 10, 30)
        
        mock_request_service.return_value.get_requests_by_worker.return_value = [mock_request]
        
        # Generate request list
        flex_message = generate_request_list_flex_message("U1234567890abcdef", mock_db)
        
        # Verify body contains required fields
        body_contents = flex_message["body"]["contents"]
        request_item = body_contents[0]
        
        # Check date is present
        date_text = request_item["contents"][0]["contents"][0]["text"]
        assert "2024年02月15日" in date_text
        
        # Check status is present
        status_text = request_item["contents"][0]["contents"][1]["text"]
        assert "保留中" in status_text
        
        # Check created_at is present
        created_text = request_item["contents"][1]["text"]
        assert "申請日時" in created_text
        assert "2024/01/10 10:30" in created_text
    
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_generate_request_list_empty_requests(self, mock_request_service, mock_auth_service, mock_db):
        """Test request list handles empty request list."""
        from app.line_bot.webhook import generate_request_list_flex_message
        
        # Mock worker
        mock_worker = Mock()
        mock_worker.id = "worker123"
        mock_auth_service.return_value.get_worker_by_line_id.return_value = mock_worker
        
        # Mock empty request list
        mock_request_service.return_value.get_requests_by_worker.return_value = []
        
        # Generate request list
        flex_message = generate_request_list_flex_message("U1234567890abcdef", mock_db)
        
        # Verify shows "no requests" message
        body_contents = flex_message["body"]["contents"]
        assert len(body_contents) == 1
        no_requests_text = body_contents[0]["contents"][0]["text"]
        assert "申請がありません" in no_requests_text
    
    @patch('app.line_bot.webhook.AuthService')
    def test_generate_request_list_worker_not_found(self, mock_auth_service, mock_db):
        """Test request list handles worker not found."""
        from app.line_bot.webhook import generate_request_list_flex_message
        
        # Mock worker not found
        mock_auth_service.return_value.get_worker_by_line_id.return_value = None
        
        # Generate request list
        flex_message = generate_request_list_flex_message("U1234567890abcdef", mock_db)
        
        # Verify shows error message
        body_contents = flex_message["body"]["contents"]
        error_text = body_contents[0]["text"]
        assert "ユーザー情報が見つかりません" in error_text
    
    @patch('app.line_bot.webhook.line_bot_api')
    @patch('app.line_bot.webhook.AuthService')
    @patch('app.line_bot.webhook.RequestService')
    def test_show_request_list_sends_flex_message(self, mock_request_service, mock_auth_service, mock_api, mock_db):
        """Test show_request_list sends a flex message."""
        from app.line_bot.webhook import show_request_list
        
        # Mock worker
        mock_worker = Mock()
        mock_worker.id = "worker123"
        mock_auth_service.return_value.get_worker_by_line_id.return_value = mock_worker
        
        # Mock empty request list
        mock_request_service.return_value.get_requests_by_worker.return_value = []
        
        # Show request list
        result = show_request_list("U1234567890abcdef", "test_reply_token", mock_db)
        
        # Verify
        assert result is True
        mock_api.reply_message.assert_called_once()
        
        # Verify FlexSendMessage was sent
        call_args = mock_api.reply_message.call_args
        assert call_args[0][0] == "test_reply_token"
        flex_message = call_args[0][1]
        assert hasattr(flex_message, 'alt_text')
        assert flex_message.alt_text == "申請一覧"
    
    @patch('app.line_bot.webhook.line_bot_api')
    def test_show_request_list_handles_error(self, mock_api, mock_db):
        """Test show_request_list handles errors gracefully."""
        from app.line_bot.webhook import show_request_list
        
        # Mock API error
        mock_api.reply_message.side_effect = Exception("API Error")
        
        # Show request list
        result = show_request_list("U1234567890abcdef", "test_reply_token", mock_db)
        
        # Verify returns False on error
        assert result is False
