"""Unit tests for error handling in the shift request management system.

This test module validates error handling for:
- Invalid dates (Requirement 1.4)
- Duplicate requests (Requirement 1.4)
- Deadline exceeded (Requirement 2.5, 2.6)
- Database errors (Requirement 9.4)
"""
import pytest
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from unittest.mock import patch, MagicMock
import uuid

from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus
from app.models.settings import Settings as SettingsModel
from app.services.request_service import RequestService
from app.services.deadline_service import DeadlineService
from app.exceptions import (
    DuplicateRequestError,
    DeadlineExceededError,
    NotNextMonthError,
    MissingFieldError,
    ResourceNotFoundError,
    InvalidRangeError
)


class TestInvalidDateErrors:
    """Test error handling for invalid dates.
    
    Validates: Requirement 1.4
    """
    
    def test_request_for_current_month_rejected(self, test_db: Session):
        """Test that request for current month date is rejected."""
        # Create a test worker
        worker = User(
            id=str(uuid.uuid4()),
            line_id="invalid_date_worker_1",
            name="Invalid Date Worker 1",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Current date
        current_date = date(2025, 1, 15)
        # Request date in current month (should fail)
        request_date = date(2025, 1, 25)
        
        service = RequestService(test_db)
        
        # Should raise NotNextMonthError
        with pytest.raises(NotNextMonthError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )
        
        # Verify error message contains useful information
        error = exc_info.value
        assert error.error_code == "NOT_NEXT_MONTH"
        assert "翌月" in error.message
        assert request_date.isoformat() in str(error.details)
    
    def test_request_for_past_month_rejected(self, test_db: Session):
        """Test that request for past month date is rejected."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="invalid_date_worker_2",
            name="Invalid Date Worker 2",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        current_date = date(2025, 2, 10)
        # Request date in past month (should fail)
        request_date = date(2025, 1, 20)
        
        service = RequestService(test_db)
        
        with pytest.raises(NotNextMonthError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )
        
        error = exc_info.value
        assert error.error_code == "NOT_NEXT_MONTH"
    
    def test_request_for_two_months_ahead_rejected(self, test_db: Session):
        """Test that request for two months ahead is rejected."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="invalid_date_worker_3",
            name="Invalid Date Worker 3",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        current_date = date(2025, 1, 10)
        # Request date two months ahead (should fail)
        request_date = date(2025, 3, 15)
        
        service = RequestService(test_db)
        
        with pytest.raises(NotNextMonthError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )
        
        error = exc_info.value
        assert error.error_code == "NOT_NEXT_MONTH"
    
    def test_request_with_missing_date_rejected(self, test_db: Session):
        """Test that request without date is rejected."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="missing_date_worker",
            name="Missing Date Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        service = RequestService(test_db)
        
        with pytest.raises(MissingFieldError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=None,
                current_date=date(2025, 1, 5)
            )
        
        error = exc_info.value
        assert error.error_code == "MISSING_FIELD"
        assert "request_date" in str(error.details)


class TestDuplicateRequestErrors:
    """Test error handling for duplicate requests.
    
    Validates: Requirement 1.4
    """
    
    def test_duplicate_request_same_worker_same_date(self, test_db: Session):
        """Test that duplicate request for same worker and date is rejected."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="duplicate_worker_1",
            name="Duplicate Worker 1",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        current_date = date(2025, 1, 5)
        request_date = date(2025, 2, 15)
        
        service = RequestService(test_db)
        
        # Create first request (should succeed)
        first_request = service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=current_date
        )
        assert first_request is not None
        assert first_request.status == RequestStatus.PENDING
        
        # Try to create duplicate request (should fail)
        with pytest.raises(DuplicateRequestError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )
        
        # Verify error details
        error = exc_info.value
        assert error.error_code == "DUPLICATE_REQUEST"
        assert "既に申請済み" in error.message
        assert worker.name in str(error.details)
        assert request_date.isoformat() in str(error.details)
    
    def test_duplicate_request_different_workers_same_date_allowed(self, test_db: Session):
        """Test that different workers can request the same date."""
        worker1 = User(
            id=str(uuid.uuid4()),
            line_id="duplicate_worker_2a",
            name="Duplicate Worker 2A",
            role=UserRole.WORKER
        )
        worker2 = User(
            id=str(uuid.uuid4()),
            line_id="duplicate_worker_2b",
            name="Duplicate Worker 2B",
            role=UserRole.WORKER
        )
        test_db.add_all([worker1, worker2])
        test_db.commit()
        
        current_date = date(2025, 1, 5)
        request_date = date(2025, 2, 15)
        
        service = RequestService(test_db)
        
        # Create request for worker1
        request1 = service.create_request(
            worker_id=worker1.id,
            request_date=request_date,
            current_date=current_date
        )
        
        # Create request for worker2 with same date (should succeed)
        request2 = service.create_request(
            worker_id=worker2.id,
            request_date=request_date,
            current_date=current_date
        )
        
        assert request1.id != request2.id
        assert request1.worker_id != request2.worker_id
        assert request1.request_date == request2.request_date
    
    def test_duplicate_request_same_worker_different_dates_allowed(self, test_db: Session):
        """Test that same worker can request different dates."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="duplicate_worker_3",
            name="Duplicate Worker 3",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        current_date = date(2025, 1, 5)
        request_date1 = date(2025, 2, 15)
        request_date2 = date(2025, 2, 20)
        
        service = RequestService(test_db)
        
        # Create first request
        request1 = service.create_request(
            worker_id=worker.id,
            request_date=request_date1,
            current_date=current_date
        )
        
        # Create second request with different date (should succeed)
        request2 = service.create_request(
            worker_id=worker.id,
            request_date=request_date2,
            current_date=current_date
        )
        
        assert request1.id != request2.id
        assert request1.request_date != request2.request_date
        assert request1.worker_id == request2.worker_id


class TestDeadlineExceededErrors:
    """Test error handling for deadline exceeded scenarios.
    
    Validates: Requirements 2.5, 2.6
    """
    
    def test_request_after_default_deadline_rejected(self, test_db: Session):
        """Test that request after default deadline (day 10) is rejected."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="deadline_worker_1",
            name="Deadline Worker 1",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Current date is after default deadline (day 10)
        current_date = date(2025, 1, 15)
        request_date = date(2025, 2, 20)
        
        service = RequestService(test_db)
        
        with pytest.raises(DeadlineExceededError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )
        
        # Verify error details
        error = exc_info.value
        assert error.error_code == "DEADLINE_EXCEEDED"
        assert "申請期限を過ぎています" in error.message
        assert "10日" in error.message
        assert error.details["deadline_day"] == 10
        assert error.details["current_date"] == current_date.isoformat()
    
    def test_request_on_deadline_day_allowed(self, test_db: Session):
        """Test that request on the deadline day is allowed."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="deadline_worker_2",
            name="Deadline Worker 2",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Current date is exactly the deadline day
        current_date = date(2025, 1, 10)
        request_date = date(2025, 2, 20)
        
        service = RequestService(test_db)
        
        # Should succeed
        request = service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        assert request is not None
        assert request.status == RequestStatus.PENDING
    
    def test_request_after_custom_deadline_rejected(self, test_db: Session):
        """Test that request after custom deadline is rejected."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="deadline_worker_3",
            name="Deadline Worker 3",
            role=UserRole.WORKER
        )
        admin = User(
            id=str(uuid.uuid4()),
            line_id="deadline_admin",
            name="Deadline Admin",
            role=UserRole.ADMIN
        )
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Set custom deadline to day 20
        setting = SettingsModel(
            id=str(uuid.uuid4()),
            key="deadline_day",
            value="20",
            updated_by=admin.id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Current date is after custom deadline (day 20)
        current_date = date(2025, 1, 25)
        request_date = date(2025, 2, 15)
        
        service = RequestService(test_db)
        
        with pytest.raises(DeadlineExceededError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )
        
        error = exc_info.value
        assert error.error_code == "DEADLINE_EXCEEDED"
        assert "20日" in error.message
    
    def test_request_before_custom_deadline_allowed(self, test_db: Session):
        """Test that request before custom deadline is allowed."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="deadline_worker_4",
            name="Deadline Worker 4",
            role=UserRole.WORKER
        )
        admin = User(
            id=str(uuid.uuid4()),
            line_id="deadline_admin_2",
            name="Deadline Admin 2",
            role=UserRole.ADMIN
        )
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Set custom deadline to day 25
        setting = SettingsModel(
            id=str(uuid.uuid4()),
            key="deadline_day",
            value="25",
            updated_by=admin.id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Current date is before custom deadline
        current_date = date(2025, 1, 20)
        request_date = date(2025, 2, 15)
        
        service = RequestService(test_db)
        
        # Should succeed
        request = service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        assert request is not None
        assert request.status == RequestStatus.PENDING
    
    def test_invalid_deadline_day_range(self, test_db: Session):
        """Test that invalid deadline day values are rejected."""
        admin = User(
            id=str(uuid.uuid4()),
            line_id="invalid_deadline_admin",
            name="Invalid Deadline Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        test_db.commit()
        
        service = DeadlineService(test_db)
        
        # Test deadline day too low (0)
        with pytest.raises(InvalidRangeError) as exc_info:
            service.set_deadline_day(0, admin.id)
        
        error = exc_info.value
        assert error.error_code == "INVALID_RANGE"
        assert error.details["field_name"] == "deadline_day"
        
        # Test deadline day too high (32)
        with pytest.raises(InvalidRangeError):
            service.set_deadline_day(32, admin.id)


class TestDatabaseErrors:
    """Test error handling for database errors.
    
    Validates: Requirement 9.4
    """
    
    def test_database_connection_error_handling(self, test_db: Session):
        """Test that database connection errors are handled gracefully."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="db_error_worker_1",
            name="DB Error Worker 1",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Mock database commit to raise OperationalError
        with patch.object(test_db, 'commit', side_effect=OperationalError("", "", "")):
            with pytest.raises(OperationalError):
                service.create_request(
                    worker_id=worker.id,
                    request_date=date(2025, 2, 15),
                    current_date=date(2025, 1, 5)
                )
        
        # Verify that no request was created (rollback occurred)
        requests = test_db.query(Request).filter(Request.worker_id == worker.id).all()
        assert len(requests) == 0
    
    def test_database_integrity_error_on_duplicate(self, test_db: Session):
        """Test that database integrity errors for duplicates are handled."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="db_error_worker_2",
            name="DB Error Worker 2",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Create first request
        request_date = date(2025, 2, 15)
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=request_date,
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(request1)
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Try to create duplicate - should be caught by application logic
        with pytest.raises(DuplicateRequestError):
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=date(2025, 1, 5)
            )
    
    def test_database_rollback_on_error(self, test_db: Session):
        """Test that database transactions are rolled back on error."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="db_error_worker_3",
            name="DB Error Worker 3",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Get initial request count
        initial_count = test_db.query(Request).count()
        
        # Mock commit to raise an exception
        with patch.object(test_db, 'commit', side_effect=Exception("Database error")):
            with pytest.raises(Exception):
                service.create_request(
                    worker_id=worker.id,
                    request_date=date(2025, 2, 15),
                    current_date=date(2025, 1, 5)
                )
        
        # Verify no new requests were added (rollback occurred)
        final_count = test_db.query(Request).count()
        assert final_count == initial_count
    
    def test_missing_worker_id_error(self, test_db: Session):
        """Test that missing worker_id is handled."""
        service = RequestService(test_db)
        
        with pytest.raises(MissingFieldError) as exc_info:
            service.create_request(
                worker_id="",
                request_date=date(2025, 2, 15),
                current_date=date(2025, 1, 5)
            )
        
        error = exc_info.value
        assert error.error_code == "MISSING_FIELD"
        assert "worker_id" in str(error.details)
    
    def test_nonexistent_worker_error(self, test_db: Session):
        """Test that nonexistent worker is handled."""
        service = RequestService(test_db)
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            service.create_request(
                worker_id="nonexistent-worker-id",
                request_date=date(2025, 2, 15),
                current_date=date(2025, 1, 5)
            )
        
        error = exc_info.value
        assert error.error_code == "RESOURCE_NOT_FOUND"
        assert error.details["resource_type"] == "worker"
        assert error.details["resource_id"] == "nonexistent-worker-id"
    
    def test_nonexistent_request_approval_error(self, test_db: Session):
        """Test that approving nonexistent request is handled."""
        admin = User(
            id=str(uuid.uuid4()),
            line_id="db_error_admin",
            name="DB Error Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        test_db.commit()
        
        service = RequestService(test_db)
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            service.approve_request("nonexistent-request-id", admin.id)
        
        error = exc_info.value
        assert error.error_code == "RESOURCE_NOT_FOUND"
        assert error.details["resource_type"] == "request"
    
    def test_nonexistent_admin_approval_error(self, test_db: Session):
        """Test that approving with nonexistent admin is handled."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="db_error_worker_4",
            name="DB Error Worker 4",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(request)
        test_db.commit()
        
        service = RequestService(test_db)
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            service.approve_request(request.id, "nonexistent-admin-id")
        
        error = exc_info.value
        assert error.error_code == "RESOURCE_NOT_FOUND"
        assert error.details["resource_type"] == "admin"


class TestErrorMessageFormatting:
    """Test that error messages are user-friendly and informative."""
    
    def test_duplicate_request_error_message_format(self, test_db: Session):
        """Test that duplicate request error has proper Japanese message."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="format_worker_1",
            name="山田太郎",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        request_date = date(2025, 2, 15)
        service = RequestService(test_db)
        
        # Create first request
        service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=date(2025, 1, 5)
        )
        
        # Try duplicate
        with pytest.raises(DuplicateRequestError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=date(2025, 1, 5)
            )
        
        error = exc_info.value
        # Check that message is in Japanese and contains key information
        assert "既に申請済み" in error.message
        assert "2025年02月15日" in error.message
        assert "重複" in error.message
    
    def test_deadline_exceeded_error_message_format(self, test_db: Session):
        """Test that deadline exceeded error has proper Japanese message."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="format_worker_2",
            name="佐藤花子",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        service = RequestService(test_db)
        
        with pytest.raises(DeadlineExceededError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=date(2025, 2, 15),
                current_date=date(2025, 1, 15)
            )
        
        error = exc_info.value
        # Check that message is in Japanese and contains key information
        assert "申請期限を過ぎています" in error.message
        assert "10日" in error.message
        assert "2025年01月15日" in error.message
    
    def test_not_next_month_error_message_format(self, test_db: Session):
        """Test that not next month error has proper Japanese message."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="format_worker_3",
            name="鈴木一郎",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        service = RequestService(test_db)
        
        with pytest.raises(NotNextMonthError) as exc_info:
            service.create_request(
                worker_id=worker.id,
                request_date=date(2025, 1, 20),
                current_date=date(2025, 1, 10)
            )
        
        error = exc_info.value
        # Check that message is in Japanese and contains key information
        assert "翌月" in error.message
        assert "2025年02月" in error.message
        assert "2025年01月20日" in error.message
