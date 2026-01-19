"""Unit tests for reminder service."""
import pytest
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
import uuid

from app.services.reminder_service import ReminderService
from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus
from app.models.settings import Settings
from app.models.reminder_log import ReminderLog


class TestReminderService:
    """Test cases for ReminderService."""
    
    def test_calculate_days_until_deadline_before_deadline(self, test_db: Session):
        """Test calculating days until deadline when before deadline."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Test: Current date is Jan 3, deadline is Jan 10
        service = ReminderService(test_db)
        current_date = date(2024, 1, 3)
        days_until = service.calculate_days_until_deadline(current_date)
        
        assert days_until == 7  # 10 - 3 = 7 days
    
    def test_calculate_days_until_deadline_after_deadline(self, test_db: Session):
        """Test calculating days until deadline when after deadline."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Test: Current date is Jan 15, deadline was Jan 10
        service = ReminderService(test_db)
        current_date = date(2024, 1, 15)
        days_until = service.calculate_days_until_deadline(current_date)
        
        assert days_until == -5  # 10 - 15 = -5 days (past deadline)
    
    def test_get_workers_without_requests(self, test_db: Session):
        """Test getting workers who haven't submitted requests for target month."""
        # Setup: Create workers
        worker1_id = str(uuid.uuid4())
        worker1 = User(
            id=worker1_id,
            line_id="worker1_line_id",
            name="Worker 1",
            role=UserRole.WORKER
        )
        
        worker2_id = str(uuid.uuid4())
        worker2 = User(
            id=worker2_id,
            line_id="worker2_line_id",
            name="Worker 2",
            role=UserRole.WORKER
        )
        
        worker3_id = str(uuid.uuid4())
        worker3 = User(
            id=worker3_id,
            line_id="worker3_line_id",
            name="Worker 3",
            role=UserRole.WORKER
        )
        
        test_db.add_all([worker1, worker2, worker3])
        test_db.commit()
        
        # Worker 1 has a request for February 2024
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker1_id,
            request_date=date(2024, 2, 15),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(request1)
        test_db.commit()
        
        # Test: Get workers without requests for February 2024
        service = ReminderService(test_db)
        workers_without = service.get_workers_without_requests(2, 2024)
        
        # Worker 2 and Worker 3 should be returned (no requests for Feb 2024)
        worker_ids = {w.id for w in workers_without}
        assert worker2_id in worker_ids
        assert worker3_id in worker_ids
        assert worker1_id not in worker_ids
        assert len(workers_without) == 2
    
    def test_should_send_reminder_7_days_before(self, test_db: Session):
        """Test reminder should be sent 7 days before deadline."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Test: Current date is Jan 3 (7 days before Jan 10)
        service = ReminderService(test_db)
        current_date = date(2024, 1, 3)
        should_send, days_before = service.should_send_reminder(current_date)
        
        assert should_send is True
        assert days_before == 7
    
    def test_should_send_reminder_3_days_before(self, test_db: Session):
        """Test reminder should be sent 3 days before deadline."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Test: Current date is Jan 7 (3 days before Jan 10)
        service = ReminderService(test_db)
        current_date = date(2024, 1, 7)
        should_send, days_before = service.should_send_reminder(current_date)
        
        assert should_send is True
        assert days_before == 3
    
    def test_should_send_reminder_1_day_before(self, test_db: Session):
        """Test reminder should be sent 1 day before deadline."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Test: Current date is Jan 9 (1 day before Jan 10)
        service = ReminderService(test_db)
        current_date = date(2024, 1, 9)
        should_send, days_before = service.should_send_reminder(current_date)
        
        assert should_send is True
        assert days_before == 1
    
    def test_should_not_send_reminder_other_days(self, test_db: Session):
        """Test reminder should not be sent on other days."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Test: Current date is Jan 5 (5 days before Jan 10 - not a reminder day)
        service = ReminderService(test_db)
        current_date = date(2024, 1, 5)
        should_send, days_before = service.should_send_reminder(current_date)
        
        assert should_send is False
        assert days_before == 5
    
    def test_get_target_month_year(self, test_db: Session):
        """Test getting target month and year (next month)."""
        service = ReminderService(test_db)
        
        # Test: Current date is Jan 15, 2024
        current_date = date(2024, 1, 15)
        target_month, target_year = service.get_target_month_year(current_date)
        
        assert target_month == 2  # February
        assert target_year == 2024
    
    def test_get_target_month_year_december(self, test_db: Session):
        """Test getting target month and year when current month is December."""
        service = ReminderService(test_db)
        
        # Test: Current date is Dec 15, 2024
        current_date = date(2024, 12, 15)
        target_month, target_year = service.get_target_month_year(current_date)
        
        assert target_month == 1  # January
        assert target_year == 2025  # Next year
    
    def test_send_reminders_on_reminder_day(self, test_db: Session, monkeypatch):
        """Test sending reminders on a reminder day."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        
        # Create workers without requests
        worker1_id = str(uuid.uuid4())
        worker1 = User(
            id=worker1_id,
            line_id="worker1_line_id",
            name="Worker 1",
            role=UserRole.WORKER
        )
        
        worker2_id = str(uuid.uuid4())
        worker2 = User(
            id=worker2_id,
            line_id="worker2_line_id",
            name="Worker 2",
            role=UserRole.WORKER
        )
        
        test_db.add_all([worker1, worker2])
        test_db.commit()
        
        # Mock notification service
        sent_notifications = []
        
        def mock_send_reminder(user_id, deadline_day, days_until_deadline, target_month):
            sent_notifications.append({
                'user_id': user_id,
                'deadline_day': deadline_day,
                'days_until_deadline': days_until_deadline,
                'target_month': target_month
            })
            return True
        
        import app.services.reminder_service as rs_module
        monkeypatch.setattr(rs_module.notification_service, 'send_reminder', mock_send_reminder)
        
        # Test: Send reminders on Jan 3 (7 days before Jan 10)
        service = ReminderService(test_db)
        current_date = date(2024, 1, 3)
        sent_count = service.send_reminders(current_date)
        
        # Verify: 2 reminders sent
        assert sent_count == 2
        assert len(sent_notifications) == 2
        
        # Verify notification content
        assert sent_notifications[0]['deadline_day'] == 10
        assert sent_notifications[0]['days_until_deadline'] == 7
        assert sent_notifications[0]['target_month'] == "2024年2月"
        
        # Verify reminder logs were created
        logs = test_db.query(ReminderLog).all()
        assert len(logs) == 2
        
        log_worker_ids = {log.worker_id for log in logs}
        assert worker1_id in log_worker_ids
        assert worker2_id in log_worker_ids
        
        # Verify log details
        for log in logs:
            assert log.days_before_deadline == 7
            assert log.target_month == 2
            assert log.target_year == 2024
    
    def test_send_reminders_not_reminder_day(self, test_db: Session):
        """Test that reminders are not sent on non-reminder days."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Test: Try to send reminders on Jan 5 (5 days before - not a reminder day)
        service = ReminderService(test_db)
        current_date = date(2024, 1, 5)
        sent_count = service.send_reminders(current_date)
        
        # Verify: No reminders sent
        assert sent_count == 0
        
        # Verify: No reminder logs created
        logs = test_db.query(ReminderLog).all()
        assert len(logs) == 0
    
    def test_send_reminders_no_workers_without_requests(self, test_db: Session, monkeypatch):
        """Test sending reminders when all workers have submitted requests."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        
        # Create worker with request for February 2024
        worker_id = str(uuid.uuid4())
        worker = User(
            id=worker_id,
            line_id="worker_line_id",
            name="Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker_id,
            request_date=date(2024, 2, 15),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(request)
        test_db.commit()
        
        # Mock notification service
        sent_notifications = []
        
        def mock_send_reminder(user_id, deadline_day, days_until_deadline, target_month):
            sent_notifications.append({
                'user_id': user_id,
                'deadline_day': deadline_day,
                'days_until_deadline': days_until_deadline,
                'target_month': target_month
            })
            return True
        
        import app.services.reminder_service as rs_module
        monkeypatch.setattr(rs_module.notification_service, 'send_reminder', mock_send_reminder)
        
        # Test: Try to send reminders on Jan 3 (7 days before Jan 10)
        service = ReminderService(test_db)
        current_date = date(2024, 1, 3)
        sent_count = service.send_reminders(current_date)
        
        # Verify: No reminders sent (worker already has request)
        assert sent_count == 0
        assert len(sent_notifications) == 0
        
        # Verify: No reminder logs created
        logs = test_db.query(ReminderLog).all()
        assert len(logs) == 0
    
    def test_send_reminders_notification_failure(self, test_db: Session, monkeypatch):
        """Test handling of notification failures."""
        # Setup: Set deadline to 10th
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id="admin_line_id",
            name="Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        setting = Settings(
            id=str(uuid.uuid4()),
            key="application_deadline_day",
            value="10",
            updated_at=datetime.utcnow(),
            updated_by=admin_id
        )
        test_db.add(setting)
        
        # Create worker without request
        worker_id = str(uuid.uuid4())
        worker = User(
            id=worker_id,
            line_id="worker_line_id",
            name="Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Mock notification service to fail
        def mock_send_reminder_fail(user_id, deadline_day, days_until_deadline, target_month):
            return False
        
        import app.services.reminder_service as rs_module
        monkeypatch.setattr(rs_module.notification_service, 'send_reminder', mock_send_reminder_fail)
        
        # Test: Try to send reminders on Jan 3
        service = ReminderService(test_db)
        current_date = date(2024, 1, 3)
        sent_count = service.send_reminders(current_date)
        
        # Verify: No reminders successfully sent
        assert sent_count == 0
        
        # Verify: No reminder logs created (only created on success)
        logs = test_db.query(ReminderLog).all()
        assert len(logs) == 0
