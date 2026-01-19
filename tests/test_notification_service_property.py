"""
Property-based tests for notification service.

Feature: shift-request-management
Validates: Requirements 1.6, 5.4, 7.4
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from unittest.mock import Mock, patch, MagicMock, call
import uuid

from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus
from app.models.shift import Shift
from app.services.notification_service import NotificationService
from tests.conftest import get_test_db_session


# Mock the LINE API at function level for each test
@pytest.fixture
def mock_line_api():
    """Mock LINE API for property tests."""
    with patch('app.services.notification_service.ApiClient') as mock_api_client, \
         patch('app.services.notification_service.MessagingApi') as mock_messaging_api:
        
        # Setup mock instances
        mock_api_instance = MagicMock()
        mock_messaging_instance = MagicMock()
        
        # Configure the context manager behavior
        mock_api_client.return_value.__enter__.return_value = mock_api_instance
        mock_api_client.return_value.__exit__.return_value = None
        
        # Configure MessagingApi to return our mock
        mock_messaging_api.return_value = mock_messaging_instance
        
        # Make push_message succeed by default
        mock_messaging_instance.push_message.return_value = None
        
        yield {
            'api_client': mock_api_client,
            'messaging_api': mock_messaging_api,
            'api_instance': mock_api_instance,
            'messaging_instance': mock_messaging_instance
        }


# Custom strategies for generating test data
@st.composite
def valid_worker_strategy(draw):
    """Generate a valid worker user."""
    worker_id = str(uuid.uuid4())
    return User(
        id=worker_id,
        line_id=draw(st.text(
            min_size=5, 
            max_size=50, 
            alphabet=st.characters(
                min_codepoint=ord('a'),
                max_codepoint=ord('z'),
                blacklist_categories=('Cs',),
                blacklist_characters=['\x00']
            )
        )) + "_" + worker_id[:8],
        name=draw(st.text(
            min_size=3, 
            max_size=50, 
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('z'),
                blacklist_categories=('Cs',),
                blacklist_characters=['\x00']
            )
        )) + "_" + worker_id[:8],
        role=UserRole.WORKER,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@st.composite
def current_date_strategy(draw):
    """Generate a current date."""
    year = draw(st.integers(min_value=2024, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=10))
    return date(year, month, day)


@st.composite
def next_month_date_strategy(draw, current_date: date):
    """Generate a date in the next month relative to current_date."""
    next_month = current_date + relativedelta(months=1)
    # Generate a valid day for the next month
    if next_month.month in [1, 3, 5, 7, 8, 10, 12]:
        max_day = 31
    elif next_month.month in [4, 6, 9, 11]:
        max_day = 30
    else:  # February
        if next_month.year % 4 == 0 and (next_month.year % 100 != 0 or next_month.year % 400 == 0):
            max_day = 29
        else:
            max_day = 28
    
    day = draw(st.integers(min_value=1, max_value=max_day))
    return date(next_month.year, next_month.month, day)


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_5_request_creation_sends_confirmation(
    mock_line_api,
    worker: User,
    current_date: date,
    data
):
    """
    Property 5: 申請作成時に確認通知が送信される
    
    For any request creation, a LINE confirmation message is sent.
    
    Feature: shift-request-management, Property 5: 申請作成時に確認通知が送信される
    Validates: Requirements 1.6
    """
    # Generate a valid next month date
    request_date = data.draw(next_month_date_strategy(current_date))
    
    # Create notification service
    service = NotificationService()
    
    # Send request confirmation
    result = service.send_request_confirmation(
        user_id=worker.line_id,
        request_date=str(request_date)
    )
    
    # Property: Confirmation notification should be sent
    assert result is True, \
        "Request confirmation should be sent successfully"
    
    # Verify that push_message was called
    mock_messaging_instance = mock_line_api['messaging_instance']
    assert mock_messaging_instance.push_message.called, \
        "push_message should be called to send confirmation"
    
    # Verify the message contains the request date
    call_args = mock_messaging_instance.push_message.call_args
    assert call_args is not None, "push_message should have been called with arguments"
    
    # Get the PushMessageRequest object
    push_request = call_args[0][0] if call_args[0] else call_args[1].get('push_message_request')
    assert push_request is not None, "PushMessageRequest should be provided"
    assert push_request.to == worker.line_id, "Message should be sent to the correct user"
    assert len(push_request.messages) > 0, "Message should contain text"
    
    # Verify message content contains date and status
    message_text = push_request.messages[0].text
    assert str(request_date) in message_text, \
        "Confirmation message should contain the request date"
    assert "保留中" in message_text or "pending" in message_text.lower(), \
        "Confirmation message should mention pending status"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data(),
    action=st.sampled_from(['approve', 'reject'])
)
def test_property_21_status_update_sends_notification(
    mock_line_api,
    worker: User,
    current_date: date,
    data,
    action: str
):
    """
    Property 21: ステータス更新時に通知が送信される
    
    For any request status update, a LINE notification is sent to the worker.
    
    Feature: shift-request-management, Property 21: ステータス更新時に通知が送信される
    Validates: Requirements 5.4
    """
    # Generate a valid next month date
    request_date = data.draw(next_month_date_strategy(current_date))
    
    # Create notification service
    service = NotificationService()
    
    # Send status update notification
    if action == 'approve':
        result = service.send_approval_notification(
            user_id=worker.line_id,
            request_date=str(request_date)
        )
        expected_status = "承認"
    else:
        result = service.send_rejection_notification(
            user_id=worker.line_id,
            request_date=str(request_date)
        )
        expected_status = "却下"
    
    # Property: Status update notification should be sent
    assert result is True, \
        f"Status update notification should be sent successfully for {action}"
    
    # Verify that push_message was called
    mock_api_instance = mock_line_api['api_instance']
    assert mock_api_instance.push_message.called, \
        "push_message should be called to send status update notification"
    
    # Verify the message contains the request date and status
    call_args = mock_api_instance.push_message.call_args
    assert call_args is not None, "push_message should have been called with arguments"
    
    # Get the PushMessageRequest object
    push_request = call_args[0][0] if call_args[0] else call_args[1].get('push_message_request')
    assert push_request is not None, "PushMessageRequest should be provided"
    assert push_request.to == worker.line_id, "Message should be sent to the correct user"
    assert len(push_request.messages) > 0, "Message should contain text"
    
    # Verify message content contains date and status
    message_text = push_request.messages[0].text
    assert str(request_date) in message_text, \
        "Status update message should contain the request date"
    assert expected_status in message_text, \
        f"Status update message should mention {expected_status} status"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_28_shift_confirmation_sends_notification(
    mock_line_api,
    worker: User,
    current_date: date,
    data
):
    """
    Property 28: シフト確定時に通知が送信される
    
    For any shift confirmation, a LINE notification is sent to affected workers.
    
    Feature: shift-request-management, Property 28: シフト確定時に通知が送信される
    Validates: Requirements 7.4
    """
    # Generate a shift date
    shift_date = data.draw(next_month_date_strategy(current_date))
    
    # Create notification service
    service = NotificationService()
    
    # Send shift notification
    result = service.send_shift_notification(
        user_id=worker.line_id,
        shift_date=str(shift_date)
    )
    
    # Property: Shift notification should be sent
    assert result is True, \
        "Shift notification should be sent successfully"
    
    # Verify that push_message was called
    mock_api_instance = mock_line_api['api_instance']
    assert mock_api_instance.push_message.called, \
        "push_message should be called to send shift notification"
    
    # Verify the message contains the shift date
    call_args = mock_api_instance.push_message.call_args
    assert call_args is not None, "push_message should have been called with arguments"
    
    # Get the PushMessageRequest object
    push_request = call_args[0][0] if call_args[0] else call_args[1].get('push_message_request')
    assert push_request is not None, "PushMessageRequest should be provided"
    assert push_request.to == worker.line_id, "Message should be sent to the correct user"
    assert len(push_request.messages) > 0, "Message should contain text"
    
    # Verify message content contains date
    message_text = push_request.messages[0].text
    assert str(shift_date) in message_text, \
        "Shift notification should contain the shift date"
    assert "シフト" in message_text or "shift" in message_text.lower(), \
        "Shift notification should mention shift"
