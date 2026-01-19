"""Unit tests for request service."""
import pytest
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus
from app.models.settings import Settings as SettingsModel
from app.services.request_service import RequestService
from app.exceptions import (
    DuplicateRequestError,
    DeadlineExceededError,
    NotNextMonthError,
    MissingFieldError,
    ResourceNotFoundError,
    InvalidStatusTransitionError
)
import uuid


class TestRequestCreation:
    """Test request creation functionality."""
    
    def test_create_request_success(self, test_db: Session):
        """Test successful request creation with valid data."""
        # Create a test worker
        worker = User(
            id=str(uuid.uuid4()),
            line_id="test_line_id_001",
            name="Test Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Set current date to before deadline (e.g., day 5)
        current_date = date(2025, 1, 5)
        # Request date should be in next month (February)
        request_date = date(2025, 2, 15)
        
        # Create request service
        service = RequestService(test_db)
        
        # Create request
        request = service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        # Verify request was created correctly
        assert request is not None
        assert request.id is not None
        assert request.worker_id == worker.id
        assert request.request_date == request_date
        assert request.status == RequestStatus.PENDING
        assert request.created_at is not None
        assert request.processed_at is None
        assert request.processed_by is None
    
    def test_create_request_not_next_month(self, test_db: Session):
        """Test that request for non-next-month date is rejected."""
        # Create a test worker
        worker = User(
            id=str(uuid.uuid4()),
            line_id="test_line_id_002",
            name="Test Worker 2",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        current_date = date(2025, 1, 5)
        # Request date in current month (should fail)
        request_date = date(2025, 1, 20)
        
        service = RequestService(test_db)
        
        # Should raise NotNextMonthError
        with pytest.raises(NotNextMonthError):
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )
    
    def test_create_request_duplicate(self, test_db: Session):
        """Test that duplicate request is rejected."""
        # Create a test worker
        worker = User(
            id=str(uuid.uuid4()),
            line_id="test_line_id_003",
            name="Test Worker 3",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        current_date = date(2025, 1, 5)
        request_date = date(2025, 2, 15)
        
        service = RequestService(test_db)
        
        # Create first request (should succeed)
        request1 = service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=current_date
        )
        assert request1 is not None
        
        # Try to create duplicate request (should fail)
        with pytest.raises(DuplicateRequestError):
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )
    
    def test_create_request_past_deadline(self, test_db: Session):
        """Test that request past deadline is rejected."""
        # Create a test worker
        worker = User(
            id=str(uuid.uuid4()),
            line_id="test_line_id_004",
            name="Test Worker 4",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Current date is after default deadline (day 10)
        current_date = date(2025, 1, 15)
        request_date = date(2025, 2, 20)
        
        service = RequestService(test_db)
        
        # Should raise DeadlineExceededError
        with pytest.raises(DeadlineExceededError):
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )
    
    def test_create_request_custom_deadline(self, test_db: Session):
        """Test request creation with custom deadline setting."""
        # Create a test worker
        worker = User(
            id=str(uuid.uuid4()),
            line_id="test_line_id_005",
            name="Test Worker 5",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        
        # Create admin for settings
        admin = User(
            id=str(uuid.uuid4()),
            line_id="admin_hash",
            name="admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        
        # Set custom deadline to day 20
        setting = SettingsModel(
            id=str(uuid.uuid4()),
            key="deadline_day",
            value="20",
            updated_by=admin.id
        )
        test_db.add(setting)
        test_db.commit()
        
        # Current date is day 15 (before custom deadline of 20)
        current_date = date(2025, 1, 15)
        request_date = date(2025, 2, 25)
        
        service = RequestService(test_db)
        
        # Should succeed because we're before the custom deadline
        request = service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        assert request is not None
        assert request.status == RequestStatus.PENDING
    
    def test_create_request_missing_worker_id(self, test_db: Session):
        """Test that request without worker_id is rejected."""
        current_date = date(2025, 1, 5)
        request_date = date(2025, 2, 15)
        
        service = RequestService(test_db)
        
        with pytest.raises(MissingFieldError):
            service.create_request(
                worker_id="",
                request_date=request_date,
                current_date=current_date
            )
    
    def test_create_request_nonexistent_worker(self, test_db: Session):
        """Test that request for nonexistent worker is rejected."""
        current_date = date(2025, 1, 5)
        request_date = date(2025, 2, 15)
        
        service = RequestService(test_db)
        
        with pytest.raises(ResourceNotFoundError):
            service.create_request(
                worker_id="nonexistent-worker-id",
                request_date=request_date,
                current_date=current_date
            )


class TestRequestRetrieval:
    """Test request retrieval and filtering functionality."""
    
    def test_get_requests_by_worker(self, test_db: Session):
        """Test retrieving requests for a specific worker."""
        # Create test workers
        worker1 = User(
            id=str(uuid.uuid4()),
            line_id="worker1_line",
            name="Worker One",
            role=UserRole.WORKER
        )
        worker2 = User(
            id=str(uuid.uuid4()),
            line_id="worker2_line",
            name="Worker Two",
            role=UserRole.WORKER
        )
        test_db.add_all([worker1, worker2])
        test_db.commit()
        
        # Create requests for worker1
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker1.id,
            request_date=date(2025, 2, 10),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker1.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.APPROVED,
            created_at=datetime.utcnow()
        )
        # Create request for worker2
        request3 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker2.id,
            request_date=date(2025, 2, 20),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add_all([request1, request2, request3])
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Get requests for worker1
        requests = service.get_requests_by_worker(worker1.id)
        
        assert len(requests) == 2
        assert all(r.worker_id == worker1.id for r in requests)
        # Should be sorted by date descending
        assert requests[0].request_date > requests[1].request_date
    
    def test_get_requests_by_worker_with_status_filter(self, test_db: Session):
        """Test retrieving requests for a worker filtered by status."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="worker_status_line",
            name="Worker Status",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Create requests with different statuses
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 10),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.APPROVED,
            created_at=datetime.utcnow()
        )
        request3 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 20),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add_all([request1, request2, request3])
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Get only pending requests
        pending_requests = service.get_requests_by_worker(worker.id, RequestStatus.PENDING)
        
        assert len(pending_requests) == 2
        assert all(r.status == RequestStatus.PENDING for r in pending_requests)
    
    def test_get_all_requests(self, test_db: Session):
        """Test retrieving all requests."""
        # Create test workers
        worker1 = User(
            id=str(uuid.uuid4()),
            line_id="all_worker1",
            name="All Worker One",
            role=UserRole.WORKER
        )
        worker2 = User(
            id=str(uuid.uuid4()),
            line_id="all_worker2",
            name="All Worker Two",
            role=UserRole.WORKER
        )
        test_db.add_all([worker1, worker2])
        test_db.commit()
        
        # Create requests
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker1.id,
            request_date=date(2025, 2, 10),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker2.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.APPROVED,
            created_at=datetime.utcnow()
        )
        test_db.add_all([request1, request2])
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Get all requests
        all_requests = service.get_all_requests()
        
        assert len(all_requests) == 2
        # Pending should come first
        assert all_requests[0].status == RequestStatus.PENDING
    
    def test_get_all_requests_with_status_filter(self, test_db: Session):
        """Test retrieving all requests filtered by status."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="status_filter_worker",
            name="Status Filter Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Create requests with different statuses
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 10),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.APPROVED,
            created_at=datetime.utcnow()
        )
        test_db.add_all([request1, request2])
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Get only approved requests
        approved_requests = service.get_all_requests(status=RequestStatus.APPROVED)
        
        assert len(approved_requests) == 1
        assert approved_requests[0].status == RequestStatus.APPROVED
    
    def test_get_all_requests_with_worker_name_search(self, test_db: Session):
        """Test searching requests by worker name."""
        # Create test workers
        worker1 = User(
            id=str(uuid.uuid4()),
            line_id="search_worker1",
            name="John Smith",
            role=UserRole.WORKER
        )
        worker2 = User(
            id=str(uuid.uuid4()),
            line_id="search_worker2",
            name="Jane Doe",
            role=UserRole.WORKER
        )
        test_db.add_all([worker1, worker2])
        test_db.commit()
        
        # Create requests
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker1.id,
            request_date=date(2025, 2, 10),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker2.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add_all([request1, request2])
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Search for "John"
        john_requests = service.get_all_requests(worker_name="John")
        
        assert len(john_requests) == 1
        assert john_requests[0].worker.name == "John Smith"
    
    def test_get_all_requests_with_date_filter(self, test_db: Session):
        """Test filtering requests by exact date."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="date_filter_worker",
            name="Date Filter Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Create requests with different dates
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 10),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add_all([request1, request2])
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Filter by specific date
        date_requests = service.get_all_requests(request_date=date(2025, 2, 10))
        
        assert len(date_requests) == 1
        assert date_requests[0].request_date == date(2025, 2, 10)
    
    def test_get_all_requests_with_month_filter(self, test_db: Session):
        """Test filtering requests by month."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="month_filter_worker",
            name="Month Filter Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Create requests in different months
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 10),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 3, 15),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add_all([request1, request2])
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Filter by February 2025
        feb_requests = service.get_all_requests(month=2, year=2025)
        
        assert len(feb_requests) == 1
        assert feb_requests[0].request_date.month == 2
    
    def test_get_requests_by_status(self, test_db: Session):
        """Test retrieving requests by status."""
        worker = User(
            id=str(uuid.uuid4()),
            line_id="by_status_worker",
            name="By Status Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Create requests with different statuses
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 10),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.APPROVED,
            created_at=datetime.utcnow()
        )
        request3 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 20),
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add_all([request1, request2, request3])
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Get pending requests
        pending_requests = service.get_requests_by_status(RequestStatus.PENDING)
        
        assert len(pending_requests) == 2
        assert all(r.status == RequestStatus.PENDING for r in pending_requests)
        # Should be sorted by date descending
        assert pending_requests[0].request_date > pending_requests[1].request_date


class TestRequestApprovalRejection:
    """Test request approval and rejection functionality."""
    
    def test_approve_request_success(self, test_db: Session):
        """Test successful request approval."""
        # Create test worker and admin
        worker = User(
            id=str(uuid.uuid4()),
            line_id="approve_worker",
            name="Approve Worker",
            role=UserRole.WORKER
        )
        admin = User(
            id=str(uuid.uuid4()),
            line_id="approve_admin",
            name="Approve Admin",
            role=UserRole.ADMIN
        )
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create a pending request
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
        
        # Approve the request
        approved_request = service.approve_request(request.id, admin.id)
        
        # Verify approval
        assert approved_request.status == RequestStatus.APPROVED
        assert approved_request.processed_by == admin.id
        assert approved_request.processed_at is not None
        assert isinstance(approved_request.processed_at, datetime)
    
    def test_reject_request_success(self, test_db: Session):
        """Test successful request rejection."""
        # Create test worker and admin
        worker = User(
            id=str(uuid.uuid4()),
            line_id="reject_worker",
            name="Reject Worker",
            role=UserRole.WORKER
        )
        admin = User(
            id=str(uuid.uuid4()),
            line_id="reject_admin",
            name="Reject Admin",
            role=UserRole.ADMIN
        )
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create a pending request
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
        
        # Reject the request
        rejected_request = service.reject_request(request.id, admin.id)
        
        # Verify rejection
        assert rejected_request.status == RequestStatus.REJECTED
        assert rejected_request.processed_by == admin.id
        assert rejected_request.processed_at is not None
        assert isinstance(rejected_request.processed_at, datetime)
    
    def test_approve_already_approved_request(self, test_db: Session):
        """Test that approving an already approved request is rejected."""
        # Create test worker and admin
        worker = User(
            id=str(uuid.uuid4()),
            line_id="double_approve_worker",
            name="Double Approve Worker",
            role=UserRole.WORKER
        )
        admin = User(
            id=str(uuid.uuid4()),
            line_id="double_approve_admin",
            name="Double Approve Admin",
            role=UserRole.ADMIN
        )
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create an already approved request
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.APPROVED,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
            processed_by=admin.id
        )
        test_db.add(request)
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Try to approve again (should fail)
        with pytest.raises(InvalidStatusTransitionError):
            service.approve_request(request.id, admin.id)
    
    def test_reject_already_rejected_request(self, test_db: Session):
        """Test that rejecting an already rejected request is rejected."""
        # Create test worker and admin
        worker = User(
            id=str(uuid.uuid4()),
            line_id="double_reject_worker",
            name="Double Reject Worker",
            role=UserRole.WORKER
        )
        admin = User(
            id=str(uuid.uuid4()),
            line_id="double_reject_admin",
            name="Double Reject Admin",
            role=UserRole.ADMIN
        )
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create an already rejected request
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.REJECTED,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
            processed_by=admin.id
        )
        test_db.add(request)
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Try to reject again (should fail)
        with pytest.raises(InvalidStatusTransitionError):
            service.reject_request(request.id, admin.id)
    
    def test_approve_rejected_request(self, test_db: Session):
        """Test that approving a rejected request is rejected."""
        # Create test worker and admin
        worker = User(
            id=str(uuid.uuid4()),
            line_id="approve_rejected_worker",
            name="Approve Rejected Worker",
            role=UserRole.WORKER
        )
        admin = User(
            id=str(uuid.uuid4()),
            line_id="approve_rejected_admin",
            name="Approve Rejected Admin",
            role=UserRole.ADMIN
        )
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create a rejected request
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.REJECTED,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
            processed_by=admin.id
        )
        test_db.add(request)
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Try to approve (should fail)
        with pytest.raises(InvalidStatusTransitionError):
            service.approve_request(request.id, admin.id)
    
    def test_reject_approved_request(self, test_db: Session):
        """Test that rejecting an approved request is rejected."""
        # Create test worker and admin
        worker = User(
            id=str(uuid.uuid4()),
            line_id="reject_approved_worker",
            name="Reject Approved Worker",
            role=UserRole.WORKER
        )
        admin = User(
            id=str(uuid.uuid4()),
            line_id="reject_approved_admin",
            name="Reject Approved Admin",
            role=UserRole.ADMIN
        )
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create an approved request
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=date(2025, 2, 15),
            status=RequestStatus.APPROVED,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
            processed_by=admin.id
        )
        test_db.add(request)
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Try to reject (should fail)
        with pytest.raises(InvalidStatusTransitionError):
            service.reject_request(request.id, admin.id)
    
    def test_approve_nonexistent_request(self, test_db: Session):
        """Test that approving a nonexistent request is rejected."""
        # Create test admin
        admin = User(
            id=str(uuid.uuid4()),
            line_id="nonexist_admin",
            name="Nonexist Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Try to approve nonexistent request
        with pytest.raises(ResourceNotFoundError):
            service.approve_request("nonexistent-request-id", admin.id)
    
    def test_reject_nonexistent_request(self, test_db: Session):
        """Test that rejecting a nonexistent request is rejected."""
        # Create test admin
        admin = User(
            id=str(uuid.uuid4()),
            line_id="nonexist_reject_admin",
            name="Nonexist Reject Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        test_db.commit()
        
        service = RequestService(test_db)
        
        # Try to reject nonexistent request
        with pytest.raises(ResourceNotFoundError):
            service.reject_request("nonexistent-request-id", admin.id)
    
    def test_approve_with_nonexistent_admin(self, test_db: Session):
        """Test that approving with nonexistent admin is rejected."""
        # Create test worker
        worker = User(
            id=str(uuid.uuid4()),
            line_id="approve_nonadmin_worker",
            name="Approve Nonadmin Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Create a pending request
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
        
        # Try to approve with nonexistent admin
        with pytest.raises(ResourceNotFoundError):
            service.approve_request(request.id, "nonexistent-admin-id")
    
    def test_reject_with_nonexistent_admin(self, test_db: Session):
        """Test that rejecting with nonexistent admin is rejected."""
        # Create test worker
        worker = User(
            id=str(uuid.uuid4()),
            line_id="reject_nonadmin_worker",
            name="Reject Nonadmin Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Create a pending request
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
        
        # Try to reject with nonexistent admin
        with pytest.raises(ResourceNotFoundError):
            service.reject_request(request.id, "nonexistent-admin-id")


