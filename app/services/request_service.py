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
            # Use raw SQL to avoid enum conversion issues
            from sqlalchemy import text
            
            insert_sql = text("""
                INSERT INTO requests (id, worker_id, request_date, status, created_at)
                VALUES (:id, :worker_id, :request_date, :status, :created_at)
            """)
            
            self.db.execute(insert_sql, {
                "id": new_request.id,
                "worker_id": new_request.worker_id,
                "request_date": new_request.request_date,
                "status": new_request.status.value,  # Use the string value
                "created_at": new_request.created_at
            })
            
            self.db.commit()
            logger.info(f"Request saved successfully using raw SQL: {new_request.id}")
            
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
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Use raw SQL to avoid enum conversion issues
            from sqlalchemy import text
            
            if status:
                query_sql = text("""
                    SELECT id, worker_id, request_date, status, created_at, processed_at, processed_by
                    FROM requests 
                    WHERE worker_id = :worker_id AND status = :status
                    ORDER BY request_date DESC
                """)
                result = self.db.execute(query_sql, {"worker_id": worker_id, "status": status.value}).fetchall()
            else:
                query_sql = text("""
                    SELECT id, worker_id, request_date, status, created_at, processed_at, processed_by
                    FROM requests 
                    WHERE worker_id = :worker_id
                    ORDER BY request_date DESC
                """)
                result = self.db.execute(query_sql, {"worker_id": worker_id}).fetchall()
            
            # Manually create Request objects
            requests = []
            for row in result:
                request = Request()
                request.id = row[0]
                request.worker_id = row[1]
                request.request_date = row[2]
                # Map string status to enum
                status_str = row[3]
                if status_str == "pending":
                    request.status = RequestStatus.PENDING
                elif status_str == "approved":
                    request.status = RequestStatus.APPROVED
                elif status_str == "rejected":
                    request.status = RequestStatus.REJECTED
                else:
                    logger.warning(f"Unknown status: {status_str}")
                    continue
                    
                request.created_at = row[4]
                request.processed_at = row[5]
                request.processed_by = row[6]
                requests.append(request)
            
            logger.info(f"Retrieved {len(requests)} requests for worker {worker_id}")
            return requests
            
        except Exception as e:
            logger.error(f"Error getting requests for worker {worker_id}: {str(e)}")
            # Fallback to empty list
            return []
    
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
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Use raw SQL to avoid enum conversion issues
            from sqlalchemy import text
            
            # Build WHERE conditions
            where_conditions = []
            params = {}
            
            if status:
                where_conditions.append("r.status = :status")
                params["status"] = status.value
            
            if worker_name:
                where_conditions.append("u.name LIKE :worker_name")
                params["worker_name"] = f"%{worker_name}%"
            
            if request_date:
                where_conditions.append("r.request_date = :request_date")
                params["request_date"] = request_date
            
            if month and year:
                where_conditions.append("YEAR(r.request_date) = :year AND MONTH(r.request_date) = :month")
                params["year"] = year
                params["month"] = month
            elif month:
                current_year = datetime.now().year
                where_conditions.append("YEAR(r.request_date) = :year AND MONTH(r.request_date) = :month")
                params["year"] = current_year
                params["month"] = month
            
            # Build the complete query
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            query_sql = text(f"""
                SELECT r.id, r.worker_id, r.request_date, r.status, r.created_at, r.processed_at, r.processed_by,
                       u.name as worker_name, p.name as processor_name
                FROM requests r
                JOIN users u ON r.worker_id = u.id
                LEFT JOIN users p ON r.processed_by = p.id
                WHERE {where_clause}
                ORDER BY 
                    CASE WHEN r.status = 'pending' THEN 0 ELSE 1 END,
                    r.request_date DESC
            """)
            
            result = self.db.execute(query_sql, params).fetchall()
            
            # Manually create Request objects with relationships
            requests = []
            for row in result:
                request = Request()
                request.id = row[0]
                request.worker_id = row[1]
                request.request_date = row[2]
                
                # Map string status to enum
                status_str = row[3]
                if status_str == "pending":
                    request.status = RequestStatus.PENDING
                elif status_str == "approved":
                    request.status = RequestStatus.APPROVED
                elif status_str == "rejected":
                    request.status = RequestStatus.REJECTED
                else:
                    logger.warning(f"Unknown status: {status_str}")
                    continue
                    
                request.created_at = row[4]
                request.processed_at = row[5]
                request.processed_by = row[6]
                
                # Create mock worker and processor objects for the relationship
                from app.models.user import User as UserModel
                worker = UserModel()
                worker.id = request.worker_id
                worker.name = row[7]
                request.worker = worker
                
                if row[8]:  # processor_name
                    processor = UserModel()
                    processor.id = request.processed_by
                    processor.name = row[8]
                    request.processor = processor
                else:
                    request.processor = None
                
                requests.append(request)
            
            logger.info(f"Retrieved {len(requests)} requests with filters")
            return requests
            
        except Exception as e:
            logger.error(f"Error getting all requests: {str(e)}")
            # Fallback to empty list
            return []
    
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
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Use raw SQL to avoid enum conversion issues
            from sqlalchemy import text
            
            # Validate admin exists
            admin_check = self.db.execute(text("""
                SELECT id FROM users WHERE id = :admin_id AND role = 'ADMIN'
            """), {"admin_id": admin_id}).fetchone()
            
            if not admin_check:
                raise ResourceNotFoundError("admin", admin_id)
            
            # Get the request and check status
            request_check = self.db.execute(text("""
                SELECT id, status FROM requests WHERE id = :request_id
            """), {"request_id": request_id}).fetchone()
            
            if not request_check:
                raise ResourceNotFoundError("request", request_id)
            
            # Check if already processed (Requirement 5.5)
            if request_check[1] != "pending":
                raise InvalidStatusTransitionError(request_check[1], "approve")
            
            # Update status to approved (Requirement 5.1)
            update_result = self.db.execute(text("""
                UPDATE requests 
                SET status = 'approved', processed_at = :processed_at, processed_by = :processed_by
                WHERE id = :request_id
            """), {
                "request_id": request_id,
                "processed_at": datetime.utcnow(),
                "processed_by": admin_id
            })
            
            self.db.commit()
            
            # Get the updated request
            updated_request = self.db.execute(text("""
                SELECT r.id, r.worker_id, r.request_date, r.status, r.created_at, r.processed_at, r.processed_by,
                       u.name as worker_name
                FROM requests r
                JOIN users u ON r.worker_id = u.id
                WHERE r.id = :request_id
            """), {"request_id": request_id}).fetchone()
            
            # Create Request object
            request = Request()
            request.id = updated_request[0]
            request.worker_id = updated_request[1]
            request.request_date = updated_request[2]
            request.status = RequestStatus.APPROVED
            request.created_at = updated_request[4]
            request.processed_at = updated_request[5]
            request.processed_by = updated_request[6]
            
            # Create mock worker object
            from app.models.user import User as UserModel
            worker = UserModel()
            worker.id = request.worker_id
            worker.name = updated_request[7]
            request.worker = worker
            
            logger.info(f"Request {request_id} approved successfully")
            return request
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error approving request {request_id}: {str(e)}")
            raise
    
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
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Use raw SQL to avoid enum conversion issues
            from sqlalchemy import text
            
            # Validate admin exists
            admin_check = self.db.execute(text("""
                SELECT id FROM users WHERE id = :admin_id AND role = 'ADMIN'
            """), {"admin_id": admin_id}).fetchone()
            
            if not admin_check:
                raise ResourceNotFoundError("admin", admin_id)
            
            # Get the request and check status
            request_check = self.db.execute(text("""
                SELECT id, status FROM requests WHERE id = :request_id
            """), {"request_id": request_id}).fetchone()
            
            if not request_check:
                raise ResourceNotFoundError("request", request_id)
            
            # Check if already processed (Requirement 5.5)
            if request_check[1] != "pending":
                raise InvalidStatusTransitionError(request_check[1], "reject")
            
            # Update status to rejected (Requirement 5.2)
            update_result = self.db.execute(text("""
                UPDATE requests 
                SET status = 'rejected', processed_at = :processed_at, processed_by = :processed_by
                WHERE id = :request_id
            """), {
                "request_id": request_id,
                "processed_at": datetime.utcnow(),
                "processed_by": admin_id
            })
            
            self.db.commit()
            
            # Get the updated request
            updated_request = self.db.execute(text("""
                SELECT r.id, r.worker_id, r.request_date, r.status, r.created_at, r.processed_at, r.processed_by,
                       u.name as worker_name
                FROM requests r
                JOIN users u ON r.worker_id = u.id
                WHERE r.id = :request_id
            """), {"request_id": request_id}).fetchone()
            
            # Create Request object
            request = Request()
            request.id = updated_request[0]
            request.worker_id = updated_request[1]
            request.request_date = updated_request[2]
            request.status = RequestStatus.REJECTED
            request.created_at = updated_request[4]
            request.processed_at = updated_request[5]
            request.processed_by = updated_request[6]
            
            # Create mock worker object
            from app.models.user import User as UserModel
            worker = UserModel()
            worker.id = request.worker_id
            worker.name = updated_request[7]
            request.worker = worker
            
            logger.info(f"Request {request_id} rejected successfully")
            return request
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error rejecting request {request_id}: {str(e)}")
            raise
        
        return request

