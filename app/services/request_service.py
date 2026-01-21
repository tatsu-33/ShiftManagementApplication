"""Request management service for NG day applications."""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_
from typing import Optional, List
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import uuid

from app.models.request import Request, RequestStatus
from app.models.user import User
from app.models.settings import Settings as SettingsModel
from app.exceptions import (
    DuplicateRequestError,
    DeadlineExceededError,
    NotNextMonthError,
    MissingFieldError,
    ResourceNotFoundError,
    InvalidStatusTransitionError
)


class RequestService:
    """Service for handling request operations."""
    
    def __init__(self, db: Session):
        """
        Initialize request service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def _get_deadline_day(self) -> int:
        """
        Get the current deadline day setting.
        
        Returns:
            Deadline day (1-31), defaults to 10 if not set
        """
        setting = self.db.query(SettingsModel).filter(
            SettingsModel.key == "application_deadline_day"
        ).first()
        
        if setting:
            try:
                return int(setting.value)
            except ValueError:
                return 10  # Default
        
        return 10  # Default deadline day
    
    def _is_next_month(self, request_date: date, current_date: date) -> bool:
        """
        Check if the request date is in the next month.
        
        Args:
            request_date: Date being requested
            current_date: Current date
            
        Returns:
            True if request_date is in the next month, False otherwise
        """
        next_month = current_date + relativedelta(months=1)
        return (request_date.year == next_month.year and 
                request_date.month == next_month.month)
    
    def _is_past_deadline(self, current_date: date) -> bool:
        """
        Check if the current date is past the deadline for next month's requests.
        
        Args:
            current_date: Current date
            
        Returns:
            True if past deadline, False otherwise
        """
        deadline_day = self._get_deadline_day()
        return current_date.day > deadline_day
    
    def create_request(
        self,
        worker_id: str,
        request_date: date,
        current_date: Optional[date] = None
    ) -> Request:
        """
        Create a new NG day request.
        
        Args:
            worker_id: ID of the worker making the request
            request_date: Date for which NG day is requested
            current_date: Current date (defaults to today if not provided)
            
        Returns:
            Newly created Request object
            
        Raises:
            MissingFieldError: If required fields are missing
            ResourceNotFoundError: If worker not found
            NotNextMonthError: If request date is not in next month
            DeadlineExceededError: If past deadline
            DuplicateRequestError: If duplicate request
            
        Validates: Requirements 1.3, 1.4, 1.5, 2.5
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Use today's date if current_date not provided
        if current_date is None:
            current_date = date.today()
        
        logger.info(f"Creating request: worker_id={worker_id}, request_date={request_date}, current_date={current_date}")
        
        # Validate worker_id
        if not worker_id:
            raise MissingFieldError("worker_id")
        
        # Validate request_date
        if not request_date:
            raise MissingFieldError("request_date")
        
        # Check if worker exists
        worker = self.db.query(User).filter(User.id == worker_id).first()
        if not worker:
            logger.error(f"Worker not found: {worker_id}")
            raise ResourceNotFoundError("worker", worker_id)
        
        logger.info(f"Worker found: {worker.name} (ID: {worker.id})")
        
        # Validate that request date is in the next month (Requirement 1.2)
        if not self._is_next_month(request_date, current_date):
            logger.error(f"Request date not in next month: {request_date} vs {current_date}")
            raise NotNextMonthError(request_date, current_date)
        
        # Check if past deadline (Requirement 2.5, 2.6)
        deadline_day = self._get_deadline_day()
        logger.info(f"Current deadline day: {deadline_day}")
        
        if self._is_past_deadline(current_date):
            logger.error(f"Past deadline: current_date.day={current_date.day} > deadline_day={deadline_day}")
            raise DeadlineExceededError(deadline_day, current_date)
        
        logger.info(f"Deadline check passed: current_date.day={current_date.day} <= deadline_day={deadline_day}")
        
        # Check for duplicate request (Requirement 1.4)
        existing_request = self.db.query(Request).filter(
            Request.worker_id == worker_id,
            Request.request_date == request_date
        ).first()
        
        if existing_request:
            logger.error(f"Duplicate request found: worker={worker.name}, date={request_date}")
            raise DuplicateRequestError(worker.name, request_date)
        
        # Create new request with pending status (Requirement 1.3)
        new_request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker_id,
            request_date=request_date,
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        logger.info(f"Created request object: {new_request.id}")
        
        # Validate the request object
        new_request.validate()
        
        # Save to database (Requirement 1.5)
        try:
            self.db.add(new_request)
            self.db.commit()
            self.db.refresh(new_request)
            logger.info(f"Request saved successfully: {new_request.id}")
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"IntegrityError saving request: {str(e)}")
            # Handle unique constraint violation
            if "uq_worker_request_date" in str(e):
                raise DuplicateRequestError(worker.name, request_date)
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error saving request: {str(e)}")
            raise
        
        return new_request
        
        return new_request
    
    def get_requests_by_worker(
        self,
        worker_id: str,
        status: Optional[RequestStatus] = None
    ) -> List[Request]:
        """
        Get all requests for a specific worker, optionally filtered by status.
        
        Args:
            worker_id: ID of the worker
            status: Optional status filter
            
        Returns:
            List of Request objects sorted by request_date descending
            
        Validates: Requirements 3.1, 3.2, 3.3
        """
        query = self.db.query(Request).filter(Request.worker_id == worker_id)
        
        if status:
            query = query.filter(Request.status == status)
        
        # Sort by request_date descending (newest first)
        query = query.order_by(Request.request_date.desc())
        
        return query.all()
    
    def get_all_requests(
        self,
        status: Optional[RequestStatus] = None,
        worker_name: Optional[str] = None,
        request_date: Optional[date] = None,
        month: Optional[int] = None,
        year: Optional[int] = None
    ) -> List[Request]:
        """
        Get all requests with optional filtering and search.
        
        Args:
            status: Optional status filter
            worker_name: Optional worker name search (partial match)
            request_date: Optional exact date filter
            month: Optional month filter (1-12)
            year: Optional year filter
            
        Returns:
            List of Request objects sorted by status priority and date
            
        Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5
        """
        # Start with base query joining with User for name search
        query = self.db.query(Request).join(User, Request.worker_id == User.id)
        
        # Apply filters
        if status:
            query = query.filter(Request.status == status)
        
        if worker_name:
            # Partial match search on worker name
            query = query.filter(User.name.ilike(f"%{worker_name}%"))
        
        if request_date:
            # Exact date match
            query = query.filter(Request.request_date == request_date)
        
        if month and year:
            # Filter by month and year
            query = query.filter(
                and_(
                    Request.request_date >= date(year, month, 1),
                    Request.request_date < date(year + (1 if month == 12 else 0), (month % 12) + 1, 1)
                )
            )
        elif month:
            # Filter by month only (current year assumed)
            current_year = datetime.now().year
            query = query.filter(
                and_(
                    Request.request_date >= date(current_year, month, 1),
                    Request.request_date < date(current_year + (1 if month == 12 else 0), (month % 12) + 1, 1)
                )
            )
        
        # Sort: pending first, then by request_date descending
        query = query.order_by(
            (Request.status == RequestStatus.PENDING).desc(),
            Request.request_date.desc()
        )
        
        return query.all()
    
    def get_requests_by_status(
        self,
        status: RequestStatus
    ) -> List[Request]:
        """
        Get all requests with a specific status.
        
        Args:
            status: Request status to filter by
            
        Returns:
            List of Request objects sorted by request_date descending
            
        Validates: Requirements 4.1, 4.3
        """
        query = self.db.query(Request).filter(Request.status == status)
        query = query.order_by(Request.request_date.desc())
        
        return query.all()
    
    def approve_request(
        self,
        request_id: str,
        admin_id: str
    ) -> Request:
        """
        Approve a pending request.
        
        Args:
            request_id: ID of the request to approve
            admin_id: ID of the admin approving the request
            
        Returns:
            Updated Request object
            
        Raises:
            ResourceNotFoundError: If request or admin not found
            InvalidStatusTransitionError: If request already processed
            
        Validates: Requirements 5.1, 5.3, 5.5
        """
        # Validate admin exists
        admin = self.db.query(User).filter(User.id == admin_id).first()
        if not admin:
            raise ResourceNotFoundError("admin", admin_id)
        
        # Get the request
        request = self.db.query(Request).filter(Request.id == request_id).first()
        if not request:
            raise ResourceNotFoundError("request", request_id)
        
        # Check if already processed (Requirement 5.5)
        if request.status != RequestStatus.PENDING:
            raise InvalidStatusTransitionError(request.status.value, "approve")
        
        # Update status to approved (Requirement 5.1)
        request.status = RequestStatus.APPROVED
        
        # Record processing information (Requirement 5.3)
        request.processed_at = datetime.utcnow()
        request.processed_by = admin_id
        
        # Validate the updated request
        request.validate()
        
        # Save to database
        try:
            self.db.commit()
            self.db.refresh(request)
        except Exception as e:
            self.db.rollback()
            raise
        
        return request
    
    def reject_request(
        self,
        request_id: str,
        admin_id: str
    ) -> Request:
        """
        Reject a pending request.
        
        Args:
            request_id: ID of the request to reject
            admin_id: ID of the admin rejecting the request
            
        Returns:
            Updated Request object
            
        Raises:
            ResourceNotFoundError: If request or admin not found
            InvalidStatusTransitionError: If request already processed
            
        Validates: Requirements 5.2, 5.3, 5.5
        """
        # Validate admin exists
        admin = self.db.query(User).filter(User.id == admin_id).first()
        if not admin:
            raise ResourceNotFoundError("admin", admin_id)
        
        # Get the request
        request = self.db.query(Request).filter(Request.id == request_id).first()
        if not request:
            raise ResourceNotFoundError("request", request_id)
        
        # Check if already processed (Requirement 5.5)
        if request.status != RequestStatus.PENDING:
            raise InvalidStatusTransitionError(request.status.value, "reject")
        
        # Update status to rejected (Requirement 5.2)
        request.status = RequestStatus.REJECTED
        
        # Record processing information (Requirement 5.3)
        request.processed_at = datetime.utcnow()
        request.processed_by = admin_id
        
        # Validate the updated request
        request.validate()
        
        # Save to database
        try:
            self.db.commit()
            self.db.refresh(request)
        except Exception as e:
            self.db.rollback()
            raise
        
        return request

