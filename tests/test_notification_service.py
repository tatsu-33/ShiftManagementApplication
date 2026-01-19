"""Unit tests for notification service - External service error handling.

This test module validates:
- LINE API error handling (Requirements 1.6, 5.4, 7.4)
- Retry logic with exponential backoff
- Fallback processing with queueing
"""
import pytest
from unittest.mock import patch, MagicMock, call
from linebot.v3.messaging.exceptions import ApiException

from app.services.notification_service import NotificationService


class TestLineAPIErrorHandling:
    '''Test LINE API error handling with retry and fallback.'''
    
    @patch('app.services.notification_service.MessagingApi')
    @patch('app.services.notification_service.ApiClient')
    def test_successful_message_send(self, mock_api_client, mock_messaging_api):
        '''Test successful message sending without errors.'''
        mock_api_instance = MagicMock()
        mock_api_client.return_value.__enter__.return_value = mock_api_instance
        mock_line_bot = MagicMock()
        mock_messaging_api.return_value = mock_line_bot
        
        service = NotificationService()
        result = service.send_message("user123", "Test message")
        
        assert result is True
        assert service.get_queue_size() == 0
        mock_line_bot.push_message.assert_called_once()
    
    @patch('time.sleep')
    @patch('app.services.notification_service.MessagingApi')
    @patch('app.services.notification_service.ApiClient')
    def test_api_exception_triggers_retry(self, mock_api_client, mock_messaging_api, mock_sleep):
        '''Test that API exceptions trigger retry logic.'''
        mock_api_instance = MagicMock()
        mock_api_client.return_value.__enter__.return_value = mock_api_instance
        mock_line_bot = MagicMock()
        mock_messaging_api.return_value = mock_line_bot
        
        mock_line_bot.push_message.side_effect = [
            ApiException(status=500, reason="Server Error"),
            ApiException(status=500, reason="Server Error"),
            None
        ]
        
        service = NotificationService()
        result = service.send_message("user123", "Test message")
        
        assert result is True
        assert mock_line_bot.push_message.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)
    
    @patch('time.sleep')
    @patch('app.services.notification_service.MessagingApi')
    @patch('app.services.notification_service.ApiClient')
    def test_max_retries_exceeded_enqueues_message(self, mock_api_client, mock_messaging_api, mock_sleep):
        '''Test that messages are enqueued after max retries exceeded.'''
        mock_api_instance = MagicMock()
        mock_api_client.return_value.__enter__.return_value = mock_api_instance
        mock_line_bot = MagicMock()
        mock_messaging_api.return_value = mock_line_bot
        mock_line_bot.push_message.side_effect = ApiException(status=500, reason="Server Error")
        
        service = NotificationService()
        result = service.send_message("user123", "Test message")
        
        assert result is False
        assert service.get_queue_size() == 1
        assert mock_line_bot.push_message.call_count == 4
