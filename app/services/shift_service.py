"""Shift management service for work schedules."""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Dict, Optional, Any
from datetime import date, datetime
from calendar import monthrange
import uuid

from app.models.shift import Shift
from app.models.user import User
from app.models.request import Request, RequestStatus


class ShiftService:
    """Service for handling shift operations."""
    
    def __init__(self, db: Session):
        """
        Initialize shift service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_shifts_by_month(
        self,
        year: int,
        month: int
    ) -> List[Shift]:
        """
        Get all shifts for a specific month.
        
        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)
            
        Returns:
            List of Shift objects for the specified month
            
        Validates: Requirements 6.1, 6.2
        """
        # Validate month
        if not 1 <= month <= 12:
            raise ValueError(f"Month must be between 1 and 12, got {month}")
        
        # Get first and last day of the month
        first_day = date(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)
        
        # Query shifts in the date range
        query = self.db.query(Shift).filter(
            and_(
                Shift.shift_date >= first_day,
                Shift.shift_date <= last_day
            )
        )
        
        # Order by date
        query = query.order_by(Shift.shift_date.asc())
        
        return query.all()
    
    def get_shifts_by_date_range(
        self,
        start_date: date,
        end_date: date
    ) -> List[Shift]:
        """
        Get all shifts within a date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            List of Shift objects within the date range
            
        Validates: Requirements 6.4
        """
        # Validate date range
        if start_date > end_date:
            raise ValueError(
                f"Start date ({start_date}) must be before or equal to end date ({end_date})"
            )
        
        # Query shifts in the date range
        query = self.db.query(Shift).filter(
            and_(
                Shift.shift_date >= start_date,
                Shift.shift_date <= end_date
            )
        )
        
        # Order by date
        query = query.order_by(Shift.shift_date.asc())
        
        return query.all()
    
    def get_approved_ng_days(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[date, List[str]]:
        """
        Get approved NG days grouped by date.
        
        Args:
            year: Optional year filter
            month: Optional month filter (requires year)
            start_date: Optional start date for range filter
            end_date: Optional end date for range filter
            
        Returns:
            Dictionary mapping dates to lists of worker IDs with approved NG days
            Example: {date(2024, 2, 15): ['worker-id-1', 'worker-id-2']}
            
        Validates: Requirements 6.2, 6.4
        """
        from sqlalchemy import text
        
        try:
            # Build SQL query for approved requests using raw SQL to avoid enum issues
            if year and month:
                # Validate month
                if not 1 <= month <= 12:
                    raise ValueError(f"Month must be between 1 and 12, got {month}")
                
                # Filter by month using raw SQL
                first_day = date(year, month, 1)
                last_day_num = monthrange(year, month)[1]
                last_day = date(year, month, last_day_num)
                
                query = text("""
                    SELECT request_date, worker_id 
                    FROM requests 
                    WHERE status = 'approved' 
                    AND request_date >= :start_date 
                    AND request_date <= :end_date
                    ORDER BY request_date
                """)
                
                result = self.db.execute(query, {
                    'start_date': first_day,
                    'end_date': last_day
                }).fetchall()
                
            elif start_date and end_date:
                # Validate date range
                if start_date > end_date:
                    raise ValueError(
                        f"Start date ({start_date}) must be before or equal to end date ({end_date})"
                    )
                
                # Filter by date range using raw SQL
                query = text("""
                    SELECT request_date, worker_id 
                    FROM requests 
                    WHERE status = 'approved' 
                    AND request_date >= :start_date 
                    AND request_date <= :end_date
                    ORDER BY request_date
                """)
                
                result = self.db.execute(query, {
                    'start_date': start_date,
                    'end_date': end_date
                }).fetchall()
                
            else:
                # No filters - get all approved requests
                query = text("""
                    SELECT request_date, worker_id 
                    FROM requests 
                    WHERE status = 'approved'
                    ORDER BY request_date
                """)
                
                result = self.db.execute(query).fetchall()
            
            # Group by date
            ng_days_by_date: Dict[date, List[str]] = {}
            for row in result:
                request_date = row[0]
                worker_id = row[1]
                
                if request_date not in ng_days_by_date:
                    ng_days_by_date[request_date] = []
                ng_days_by_date[request_date].append(worker_id)
            
            return ng_days_by_date
            
        except Exception as e:
            print(f"ERROR in get_approved_ng_days: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def update_shift(
        self,
        shift_date: date,
        worker_ids: List[str],
        admin_id: str
    ) -> Dict[str, Any]:
        """
        Update shift assignments for a specific date.
        
        This method adds or removes workers from a shift date. It will:
        - Add new workers not currently assigned
        - Remove workers no longer in the list
        - Check for NG day conflicts and return warnings
        - Record change history
        
        Args:
            shift_date: Date of the shift to update
            worker_ids: List of worker IDs to assign to this shift
            admin_id: ID of the admin making the update
            
        Returns:
            Dictionary containing:
                - shifts: List of updated Shift objects
                - warnings: List of warning messages for NG day conflicts
                - changes: Dictionary with 'added' and 'removed' worker IDs
                
        Raises:
            ValueError: If validation fails (invalid admin, invalid workers)
            
        Validates: Requirements 7.1, 7.2, 7.3
        """
        # Validate admin exists
        admin = self.db.query(User).filter(User.id == admin_id).first()
        if not admin:
            raise ValueError(f"Admin with ID {admin_id} not found")
        
        # Validate shift_date
        if not shift_date:
            raise ValueError("Shift date is required")
        
        # Validate worker_ids
        if worker_ids is None:
            raise ValueError("Worker IDs list is required (can be empty)")
        
        # Validate all workers exist
        for worker_id in worker_ids:
            worker = self.db.query(User).filter(User.id == worker_id).first()
            if not worker:
                raise ValueError(f"Worker with ID {worker_id} not found")
        
        # Get current shifts for this date
        current_shifts = self.db.query(Shift).filter(
            Shift.shift_date == shift_date
        ).all()
        
        current_worker_ids = {shift.worker_id for shift in current_shifts}
        new_worker_ids = set(worker_ids)
        
        # Determine changes (Requirement 7.2)
        workers_to_add = new_worker_ids - current_worker_ids
        workers_to_remove = current_worker_ids - new_worker_ids
        
        # Check for NG day warnings (Requirement 7.3)
        warnings = []
        ng_days = self.get_approved_ng_days(
            start_date=shift_date,
            end_date=shift_date
        )
        
        if shift_date in ng_days:
            ng_worker_ids = set(ng_days[shift_date])
            conflicting_workers = new_worker_ids & ng_worker_ids
            
            for worker_id in conflicting_workers:
                worker = self.db.query(User).filter(User.id == worker_id).first()
                worker_name = worker.name if worker else worker_id
                warnings.append(
                    f"Warning: Worker '{worker_name}' has an approved NG day on {shift_date}"
                )
        
        # Remove workers no longer assigned (Requirement 7.1)
        for worker_id in workers_to_remove:
            shift_to_remove = self.db.query(Shift).filter(
                and_(
                    Shift.shift_date == shift_date,
                    Shift.worker_id == worker_id
                )
            ).first()
            
            if shift_to_remove:
                self.db.delete(shift_to_remove)
        
        # Add new workers (Requirement 7.1)
        new_shifts = []
        for worker_id in workers_to_add:
            new_shift = Shift(
                id=str(uuid.uuid4()),
                shift_date=shift_date,
                worker_id=worker_id,
                updated_by=admin_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            new_shift.validate()
            self.db.add(new_shift)
            new_shifts.append(new_shift)
        
        # Update existing shifts' updated_at and updated_by (Requirement 7.2)
        for shift in current_shifts:
            if shift.worker_id in new_worker_ids:
                shift.updated_at = datetime.utcnow()
                shift.updated_by = admin_id
        
        # Commit changes
        try:
            self.db.commit()
            
            # Refresh new shifts
            for shift in new_shifts:
                self.db.refresh(shift)
            
            # Get all current shifts after update
            updated_shifts = self.db.query(Shift).filter(
                Shift.shift_date == shift_date
            ).all()
            
        except Exception as e:
            self.db.rollback()
            raise
        
        return {
            'shifts': updated_shifts,
            'warnings': warnings,
            'changes': {
                'added': list(workers_to_add),
                'removed': list(workers_to_remove)
            }
        }
