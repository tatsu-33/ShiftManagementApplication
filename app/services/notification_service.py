"""Notification service for LINE messaging."""
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.messaging.exceptions import ApiException
from typing import Optional, Dict, Any
from datetime import datetime
import logging
import time
from collections import deque

from app.config import settings


# Configure logging
logger = logging.getLogger(__name__)


class NotificationQueue:
    """Simple in-memory queue for failed notifications with retry logic."""
    
    def __init__(self, max_retries: int = 3):
        """
        Initialize notification queue.
        
        Args:
            max_retries: Maximum number of retry attempts
        """
        self.queue: deque = deque()
        self.max_retries = max_retries
    
    def enqueue(self, user_id: str, message: str, retry_count: int = 0):
        """
        Add a notification to the queue.
        
        Args:
            user_id: LINE user ID
            message: Message text
            retry_count: Current retry count
        """
        self.queue.append({
            'user_id': user_id,
            'message': message,
            'retry_count': retry_count,
            'enqueued_at': datetime.utcnow()
        })
        logger.info(f"Enqueued notification for user {user_id}, retry count: {retry_count}")
    
    def dequeue(self) -> Optional[Dict[str, Any]]:
        """
        Remove and return the next notification from the queue.
        
        Returns:
            Notification dictionary or None if queue is empty
        """
        if self.queue:
            return self.queue.popleft()
        return None
    
    def size(self) -> int:
        """
        Get the current queue size.
        
        Returns:
            Number of items in queue
        """
        return len(self.queue)


class NotificationService:
    """Service for sending LINE notifications with retry and queueing."""
    
    def __init__(self):
        """Initialize notification service with LINE Messaging API."""
        # Configure LINE Messaging API
        self.configuration = Configuration(
            access_token=settings.line_channel_access_token
        )
        
        # Initialize queue for failed messages
        self.queue = NotificationQueue(max_retries=3)
        
        # Retry configuration
        self.retry_delays = [1, 2, 5]  # Exponential backoff in seconds
    
    def _send_message_with_retry(
        self,
        user_id: str,
        message: str,
        retry_count: int = 0
    ) -> bool:
        """
        Send a LINE message with retry logic.
        
        Args:
            user_id: LINE user ID
            message: Message text to send
            retry_count: Current retry attempt number
            
        Returns:
            True if message sent successfully, False otherwise
            
        Validates: Requirements 1.6, 5.4, 7.4
        """
        try:
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                
                # Create push message request
                push_message_request = PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=message)]
                )
                
                # Send message
                line_bot_api.push_message(push_message_request)
                
                logger.info(f"Successfully sent message to user {user_id}")
                return True
                
        except ApiException as e:
            logger.error(
                f"LINE API error sending message to {user_id}: "
                f"Status {e.status}, Body: {e.body}"
            )
            
            # Check if we should retry
            if retry_count < self.queue.max_retries:
                # Wait before retry (exponential backoff)
                delay = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
                logger.info(f"Retrying in {delay} seconds (attempt {retry_count + 1})")
                time.sleep(delay)
                
                # Retry
                return self._send_message_with_retry(user_id, message, retry_count + 1)
            else:
                # Max retries reached, enqueue for later
                logger.warning(
                    f"Max retries reached for user {user_id}, adding to queue"
                )
                self.queue.enqueue(user_id, message, retry_count)
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error sending message to {user_id}: {str(e)}")
            
            # Enqueue for retry
            if retry_count < self.queue.max_retries:
                self.queue.enqueue(user_id, message, retry_count)
            
            return False
    
    def send_message(self, user_id: str, message: str) -> bool:
        """
        Send a LINE message to a user.
        
        Args:
            user_id: LINE user ID
            message: Message text to send
            
        Returns:
            True if message sent successfully, False otherwise
            
        Validates: Requirements 1.6, 5.4, 7.4
        """
        if not user_id:
            logger.error("Cannot send message: user_id is required")
            return False
        
        if not message:
            logger.error("Cannot send message: message text is required")
            return False
        
        return self._send_message_with_retry(user_id, message)
    
    def send_request_confirmation(
        self,
        user_id: str,
        request_date: str
    ) -> bool:
        """
        Send confirmation message when a request is created.
        
        Args:
            user_id: LINE user ID of the worker
            request_date: Date of the NG day request
            
        Returns:
            True if message sent successfully, False otherwise
            
        Validates: Requirement 1.6
        """
        message = (
            f"NG日申請を受け付けました。\n"
            f"日付: {request_date}\n"
            f"ステータス: 保留中\n\n"
            f"管理者の承認をお待ちください。"
        )
        
        return self.send_message(user_id, message)
    
    def send_approval_notification(
        self,
        user_id: str,
        request_date: str
    ) -> bool:
        """
        Send notification when a request is approved.
        
        Args:
            user_id: LINE user ID of the worker
            request_date: Date of the approved NG day
            
        Returns:
            True if message sent successfully, False otherwise
            
        Validates: Requirement 5.4
        """
        message = (
            f"NG日申請が承認されました。\n"
            f"日付: {request_date}\n"
            f"ステータス: 承認済み\n\n"
            f"この日はシフトに入りません。"
        )
        
        return self.send_message(user_id, message)
    
    def send_rejection_notification(
        self,
        user_id: str,
        request_date: str
    ) -> bool:
        """
        Send notification when a request is rejected.
        
        Args:
            user_id: LINE user ID of the worker
            request_date: Date of the rejected NG day
            
        Returns:
            True if message sent successfully, False otherwise
            
        Validates: Requirement 5.4
        """
        message = (
            f"NG日申請が却下されました。\n"
            f"日付: {request_date}\n"
            f"ステータス: 却下\n\n"
            f"詳細については管理者にお問い合わせください。"
        )
        
        return self.send_message(user_id, message)
    
    def send_shift_notification(
        self,
        user_id: str,
        shift_date: str
    ) -> bool:
        """
        Send notification when a shift is confirmed.
        
        Args:
            user_id: LINE user ID of the worker
            shift_date: Date of the shift
            
        Returns:
            True if message sent successfully, False otherwise
            
        Validates: Requirement 7.4
        """
        message = (
            f"シフトが確定しました。\n"
            f"日付: {shift_date}\n\n"
            f"詳細はシフト表をご確認ください。"
        )
        
        return self.send_message(user_id, message)
    
    def send_reminder(
        self,
        user_id: str,
        deadline_day: int,
        days_until_deadline: int,
        target_month: str
    ) -> bool:
        """
        Send reminder notification for upcoming deadline.
        
        Args:
            user_id: LINE user ID of the worker
            deadline_day: Deadline day of the month
            days_until_deadline: Number of days until deadline
            target_month: Target month for the request (e.g., "2024年2月")
            
        Returns:
            True if message sent successfully, False otherwise
            
        Validates: Requirements 10.4
        """
        message = (
            f"【リマインダー】\n"
            f"{target_month}のNG日申請締切が近づいています。\n\n"
            f"締切日: 毎月{deadline_day}日\n"
            f"残り: {days_until_deadline}日\n\n"
            f"まだ申請されていない場合は、お早めにご申請ください。"
        )
        
        return self.send_message(user_id, message)
    
    def process_queue(self) -> int:
        """
        Process queued notifications.
        
        This method should be called periodically to retry failed notifications.
        
        Returns:
            Number of successfully processed notifications
            
        Validates: Error handling with queueing
        """
        processed_count = 0
        queue_size = self.queue.size()
        
        if queue_size == 0:
            return 0
        
        logger.info(f"Processing {queue_size} queued notifications")
        
        # Process all items currently in queue
        for _ in range(queue_size):
            item = self.queue.dequeue()
            if item is None:
                break
            
            user_id = item['user_id']
            message = item['message']
            retry_count = item['retry_count']
            
            # Try to send
            success = self._send_message_with_retry(user_id, message, retry_count)
            
            if success:
                processed_count += 1
        
        logger.info(f"Successfully processed {processed_count}/{queue_size} queued notifications")
        return processed_count
    
    def get_queue_size(self) -> int:
        """
        Get the current size of the notification queue.
        
        Returns:
            Number of notifications in queue
        """
        return self.queue.size()


# Global notification service instance
notification_service = NotificationService()
