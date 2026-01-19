"""Reminder service for checking and managing reminder notifications."""
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
import uuid
import logging

from app.models.user import User, UserRole
from app.models.request import Request
from app.models.reminder_log import ReminderLog
from app.services.deadline_service import DeadlineService
from app.services.notification_service import notification_service
from app.config import settings


# Configure logging
logger = logging.getLogger(__name__)


class ReminderService:
    """Service for managing reminder notifications."""
    
    def __init__(self, db: Session):
        """Initialize reminder service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.deadline_service = DeadlineService(db)
    
    def calculate_days_until_deadline(self, current_date: date = None) -> int:
        """Calculate the number of days until the next deadline.
        
        Args:
            current_date: The current date (defaults to today)
            
        Returns:
            Number of days until the deadline (can be negative if past deadline)
        """
        if current_date is None:
            current_date = date.today()
        
        deadline_day = self.deadline_service.get_deadline_day()
        
        # Get the deadline date for the current month
        try:
            deadline_date = date(current_date.year, current_date.month, deadline_day)
        except ValueError:
            # Handle case where deadline_day doesn't exist in current month (e.g., Feb 31)
            # Use the last day of the month instead
            next_month = current_date.replace(day=1) + relativedelta(months=1)
            deadline_date = next_month - relativedelta(days=1)
        
        # Calculate days until deadline
        days_until = (deadline_date - current_date).days
        
        return days_until
    
    def get_workers_without_requests(self, target_month: int, target_year: int) -> List[User]:
        """Get all workers who haven't submitted requests for the target month.
        
        Args:
            target_month: The target month (1-12)
            target_year: The target year
            
        Returns:
            List of User objects who haven't submitted requests for the target month
        """
        # Get all workers (users with role WORKER)
        all_workers = self.db.query(User).filter(
            User.role == UserRole.WORKER
        ).all()
        
        # Get workers who have submitted at least one request for the target month
        workers_with_requests = self.db.query(User).join(
            Request, User.id == Request.worker_id
        ).filter(
            and_(
                User.role == UserRole.WORKER,
                Request.request_date >= date(target_year, target_month, 1),
                Request.request_date < date(target_year, target_month, 1) + relativedelta(months=1)
            )
        ).distinct().all()
        
        # Get the set of worker IDs who have submitted requests
        workers_with_requests_ids = {worker.id for worker in workers_with_requests}
        
        # Filter out workers who have already submitted requests
        workers_without_requests = [
            worker for worker in all_workers 
            if worker.id not in workers_with_requests_ids
        ]
        
        return workers_without_requests
    
    def should_send_reminder(self, current_date: date = None) -> Tuple[bool, int]:
        """Check if a reminder should be sent today.
        
        Args:
            current_date: The current date (defaults to today)
            
        Returns:
            Tuple of (should_send, days_before_deadline)
            - should_send: True if reminder should be sent (7, 3, or 1 day before)
            - days_before_deadline: Number of days before deadline
        """
        if current_date is None:
            current_date = date.today()
        
        days_until = self.calculate_days_until_deadline(current_date)
        
        # Check if it's one of the reminder days
        reminder_days = settings.reminder_days_before
        should_send = days_until in reminder_days
        
        return should_send, days_until
    
    def get_target_month_year(self, current_date: date = None) -> Tuple[int, int]:
        """Get the target month and year for reminders.
        
        The target month is the next month (the month workers should submit requests for).
        
        Args:
            current_date: The current date (defaults to today)
            
        Returns:
            Tuple of (target_month, target_year)
        """
        if current_date is None:
            current_date = date.today()
        
        # Target month is next month
        next_month_date = current_date + relativedelta(months=1)
        
        return next_month_date.month, next_month_date.year
    
    def send_reminders(self, current_date: date = None) -> int:
        """Send reminder notifications to workers who haven't submitted requests.
        
        This method:
        1. Checks if today is a reminder day (7, 3, or 1 day before deadline)
        2. Gets workers who haven't submitted requests for next month
        3. Sends LINE notifications with deadline and days remaining
        4. Records sending history in reminder_logs table
        
        Args:
            current_date: The current date (defaults to today)
            
        Returns:
            Number of reminders successfully sent
            
        Validates: Requirements 10.4, 10.6
        """
        if current_date is None:
            current_date = date.today()
        
        # Check if we should send reminders today
        should_send, days_until = self.should_send_reminder(current_date)
        
        if not should_send:
            logger.info(
                f"Not a reminder day. Days until deadline: {days_until}. "
                f"Reminder days: {settings.reminder_days_before}"
            )
            return 0
        
        # Get target month and year
        target_month, target_year = self.get_target_month_year(current_date)
        
        # Get workers without requests for target month
        workers_without_requests = self.get_workers_without_requests(
            target_month, target_year
        )
        
        if not workers_without_requests:
            logger.info(
                f"No workers need reminders for {target_year}-{target_month:02d}"
            )
            return 0
        
        # Get deadline day
        deadline_day = self.deadline_service.get_deadline_day()
        
        # Format target month for display (e.g., "2024年2月")
        target_month_str = f"{target_year}年{target_month}月"
        
        # Send reminders and record history
        sent_count = 0
        
        for worker in workers_without_requests:
            try:
                # Send LINE notification
                success = notification_service.send_reminder(
                    user_id=worker.line_id,
                    deadline_day=deadline_day,
                    days_until_deadline=days_until,
                    target_month=target_month_str
                )
                
                if success:
                    # Record in reminder_logs table
                    reminder_log = ReminderLog(
                        id=str(uuid.uuid4()),
                        worker_id=worker.id,
                        sent_at=datetime.utcnow(),
                        days_before_deadline=days_until,
                        target_month=target_month,
                        target_year=target_year
                    )
                    
                    self.db.add(reminder_log)
                    sent_count += 1
                    
                    logger.info(
                        f"Sent reminder to worker {worker.id} ({worker.name}) "
                        f"for {target_year}-{target_month:02d}, "
                        f"{days_until} days before deadline"
                    )
                else:
                    logger.warning(
                        f"Failed to send reminder to worker {worker.id} ({worker.name})"
                    )
                    
            except Exception as e:
                logger.error(
                    f"Error sending reminder to worker {worker.id}: {str(e)}"
                )
        
        # Commit all reminder logs
        try:
            self.db.commit()
            logger.info(
                f"Successfully sent {sent_count}/{len(workers_without_requests)} "
                f"reminders for {target_year}-{target_month:02d}"
            )
        except Exception as e:
            logger.error(f"Error committing reminder logs: {str(e)}")
            self.db.rollback()
            return 0
        
        return sent_count
