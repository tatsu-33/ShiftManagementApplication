"""Reminder scheduler for daily reminder checks."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from app.database import SessionLocal
from app.services.reminder_service import ReminderService


# Configure logging
logger = logging.getLogger(__name__)


# Global scheduler instance
scheduler = AsyncIOScheduler()


def check_and_send_reminders():
    """
    Check and send reminder notifications.
    
    This function is called by the scheduler daily.
    It creates a database session, checks if reminders should be sent,
    and sends them to workers who haven't submitted requests.
    
    Validates: Requirements 10.1, 10.2, 10.3
    """
    logger.info("Starting daily reminder check...")
    
    db = SessionLocal()
    try:
        reminder_service = ReminderService(db)
        sent_count = reminder_service.send_reminders()
        
        logger.info(f"Daily reminder check completed. Sent {sent_count} reminders.")
        
    except Exception as e:
        logger.error(f"Error during reminder check: {str(e)}", exc_info=True)
    finally:
        db.close()


def start_scheduler():
    """
    Start the reminder scheduler.
    
    Configures the scheduler to run the reminder check daily at 9:00 AM.
    This ensures reminders are sent at a consistent time each day.
    """
    # Add job to run daily at 9:00 AM
    scheduler.add_job(
        check_and_send_reminders,
        trigger=CronTrigger(hour=9, minute=0),
        id='daily_reminder_check',
        name='Daily Reminder Check',
        replace_existing=True
    )
    
    logger.info("Reminder scheduler configured to run daily at 9:00 AM")
    
    # Start the scheduler
    scheduler.start()
    logger.info("Reminder scheduler started")


def stop_scheduler():
    """
    Stop the reminder scheduler.
    
    This should be called during application shutdown to gracefully
    stop the scheduler and any running jobs.
    """
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Reminder scheduler stopped")
    else:
        logger.info("Reminder scheduler was not running")
