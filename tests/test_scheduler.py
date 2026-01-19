"""Tests for the reminder scheduler."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import time

from app.scheduler.reminder_scheduler import (
    check_and_send_reminders,
    start_scheduler,
    stop_scheduler,
    scheduler
)


class TestReminderScheduler:
    """Test suite for reminder scheduler."""
    
    def test_check_and_send_reminders_creates_session(self):
        """Test that check_and_send_reminders creates and closes a database session."""
        with patch('app.scheduler.reminder_scheduler.SessionLocal') as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db
            
            with patch('app.scheduler.reminder_scheduler.ReminderService') as mock_service_class:
                mock_service = MagicMock()
                mock_service.send_reminders.return_value = 5
                mock_service_class.return_value = mock_service
                
                # Call the function
                check_and_send_reminders()
                
                # Verify session was created and closed
                mock_session_local.assert_called_once()
                mock_db.close.assert_called_once()
    
    def test_check_and_send_reminders_calls_reminder_service(self):
        """Test that check_and_send_reminders calls the reminder service."""
        with patch('app.scheduler.reminder_scheduler.SessionLocal') as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db
            
            with patch('app.scheduler.reminder_scheduler.ReminderService') as mock_service_class:
                mock_service = MagicMock()
                mock_service.send_reminders.return_value = 3
                mock_service_class.return_value = mock_service
                
                # Call the function
                check_and_send_reminders()
                
                # Verify ReminderService was instantiated with the db session
                mock_service_class.assert_called_once_with(mock_db)
                
                # Verify send_reminders was called
                mock_service.send_reminders.assert_called_once()
    
    def test_check_and_send_reminders_handles_errors(self):
        """Test that check_and_send_reminders handles errors gracefully."""
        with patch('app.scheduler.reminder_scheduler.SessionLocal') as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db
            
            with patch('app.scheduler.reminder_scheduler.ReminderService') as mock_service_class:
                # Simulate an error
                mock_service_class.side_effect = Exception("Database error")
                
                # Call the function - should not raise exception
                check_and_send_reminders()
                
                # Verify session was still closed
                mock_db.close.assert_called_once()
    
    def test_scheduler_configuration(self):
        """Test that the scheduler can be configured with the daily reminder job."""
        # Ensure scheduler is stopped
        if scheduler.running:
            scheduler.shutdown(wait=True)
        
        # Clear any existing jobs
        scheduler.remove_all_jobs()
        
        # Add the job (without starting the scheduler)
        from apscheduler.triggers.cron import CronTrigger
        scheduler.add_job(
            check_and_send_reminders,
            trigger=CronTrigger(hour=9, minute=0),
            id='daily_reminder_check',
            name='Daily Reminder Check',
            replace_existing=True
        )
        
        # Verify job was added
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        
        job = jobs[0]
        assert job.id == 'daily_reminder_check'
        assert job.name == 'Daily Reminder Check'
        assert isinstance(job.trigger, CronTrigger)
        
        # Clean up
        scheduler.remove_all_jobs()
    
    def test_start_and_stop_scheduler_integration(self):
        """Test that scheduler can be started and stopped."""
        # Ensure scheduler is stopped
        if scheduler.running:
            scheduler.shutdown(wait=True)
        
        # Clear any existing jobs
        scheduler.remove_all_jobs()
        
        # Start the scheduler
        start_scheduler()
        
        # Verify scheduler is running
        assert scheduler.running
        
        # Verify job was added
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == 'daily_reminder_check'
        
        # Stop the scheduler
        scheduler.shutdown(wait=True)
    
    def test_stop_scheduler_when_not_running(self):
        """Test that stop_scheduler handles an already stopped scheduler gracefully."""
        # Ensure scheduler is stopped
        if scheduler.running:
            scheduler.shutdown(wait=True)
        
        # Call stop_scheduler - should not raise exception
        # This tests that the function handles the case gracefully
        try:
            stop_scheduler()
            # If we get here, the function handled it correctly
            assert True
        except Exception as e:
            pytest.fail(f"stop_scheduler raised an exception: {e}")
