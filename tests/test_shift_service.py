"""Unit tests for shift service."""
import pytest
from datetime import date
from sqlalchemy.orm import Session
import uuid

from app.services.shift_service import ShiftService
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus


class TestShiftService:
    """Test cases for ShiftService."""
    
    def test_get_shifts_by_month(self, test_db: Session):
        """Test retrieving shifts by month."""
        # Create test users
        worker1_id = str(uuid.uuid4())
        worker1 = User(
            id=worker1_id,
            line_id=f"line_{worker1_id}",
            name="Worker 1",
            role=UserRole.WORKER
        )
        
        worker2_id = str(uuid.uuid4())
        worker2 = User(
            id=worker2_id,
            line_id=f"line_{worker2_id}",
            name="Worker 2",
            role=UserRole.WORKER
        )
        
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"line_{admin_id}",
            name="Admin",
            role=UserRole.ADMIN
        )
        
        test_db.add_all([worker1, worker2, admin])
        test_db.commit()
        
        # Create test shifts for February 2024
        shift1 = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 2, 15),
            worker_id=worker1_id,
            updated_by=admin_id
        )
        
        shift2 = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 2, 20),
            worker_id=worker2_id,
            updated_by=admin_id
        )
        
        # Create a shift in a different month
        shift3 = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 3, 10),
            worker_id=worker1_id,
            updated_by=admin_id
        )
        
        test_db.add_all([shift1, shift2, shift3])
        test_db.commit()
        
        # Test get_shifts_by_month
        service = ShiftService(test_db)
        shifts = service.get_shifts_by_month(2024, 2)
        
        # Should return only February shifts
        assert len(shifts) == 2
        assert all(shift.shift_date.month == 2 for shift in shifts)
        assert all(shift.shift_date.year == 2024 for shift in shifts)
        
        # Should be ordered by date
        assert shifts[0].shift_date < shifts[1].shift_date
    
    def test_get_shifts_by_month_invalid_month(self, test_db: Session):
        """Test that invalid month raises ValueError."""
        service = ShiftService(test_db)
        
        with pytest.raises(ValueError, match="Month must be between 1 and 12"):
            service.get_shifts_by_month(2024, 13)
        
        with pytest.raises(ValueError, match="Month must be between 1 and 12"):
            service.get_shifts_by_month(2024, 0)
    
    def test_get_shifts_by_date_range(self, test_db: Session):
        """Test retrieving shifts by date range."""
        # Create test users
        worker_id = str(uuid.uuid4())
        worker = User(
            id=worker_id,
            line_id=f"line_{worker_id}",
            name="Worker",
            role=UserRole.WORKER
        )
        
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"line_{admin_id}",
            name="Admin",
            role=UserRole.ADMIN
        )
        
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create test shifts
        shift1 = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 2, 10),
            worker_id=worker_id,
            updated_by=admin_id
        )
        
        shift2 = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 2, 15),
            worker_id=worker_id,
            updated_by=admin_id
        )
        
        shift3 = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 2, 25),
            worker_id=worker_id,
            updated_by=admin_id
        )
        
        test_db.add_all([shift1, shift2, shift3])
        test_db.commit()
        
        # Test get_shifts_by_date_range
        service = ShiftService(test_db)
        shifts = service.get_shifts_by_date_range(
            date(2024, 2, 12),
            date(2024, 2, 20)
        )
        
        # Should return only shifts in range
        assert len(shifts) == 1
        assert shifts[0].shift_date == date(2024, 2, 15)
    
    def test_get_shifts_by_date_range_invalid_range(self, test_db: Session):
        """Test that invalid date range raises ValueError."""
        service = ShiftService(test_db)
        
        with pytest.raises(ValueError, match="Start date .* must be before or equal to end date"):
            service.get_shifts_by_date_range(
                date(2024, 2, 20),
                date(2024, 2, 10)
            )
    
    def test_get_approved_ng_days_by_month(self, test_db: Session):
        """Test retrieving approved NG days by month."""
        # Create test users
        worker1_id = str(uuid.uuid4())
        worker1 = User(
            id=worker1_id,
            line_id=f"line_{worker1_id}",
            name="Worker 1",
            role=UserRole.WORKER
        )
        
        worker2_id = str(uuid.uuid4())
        worker2 = User(
            id=worker2_id,
            line_id=f"line_{worker2_id}",
            name="Worker 2",
            role=UserRole.WORKER
        )
        
        test_db.add_all([worker1, worker2])
        test_db.commit()
        
        # Create test requests
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker1_id,
            request_date=date(2024, 2, 15),
            status=RequestStatus.APPROVED
        )
        
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker2_id,
            request_date=date(2024, 2, 15),
            status=RequestStatus.APPROVED
        )
        
        request3 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker1_id,
            request_date=date(2024, 2, 20),
            status=RequestStatus.APPROVED
        )
        
        # Pending request (should not be included)
        request4 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker2_id,
            request_date=date(2024, 2, 25),
            status=RequestStatus.PENDING
        )
        
        # Request in different month (should not be included)
        request5 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker1_id,
            request_date=date(2024, 3, 10),
            status=RequestStatus.APPROVED
        )
        
        test_db.add_all([request1, request2, request3, request4, request5])
        test_db.commit()
        
        # Test get_approved_ng_days
        service = ShiftService(test_db)
        ng_days = service.get_approved_ng_days(year=2024, month=2)
        
        # Should return approved NG days grouped by date
        assert len(ng_days) == 2
        assert date(2024, 2, 15) in ng_days
        assert date(2024, 2, 20) in ng_days
        
        # Feb 15 should have 2 workers
        assert len(ng_days[date(2024, 2, 15)]) == 2
        assert worker1_id in ng_days[date(2024, 2, 15)]
        assert worker2_id in ng_days[date(2024, 2, 15)]
        
        # Feb 20 should have 1 worker
        assert len(ng_days[date(2024, 2, 20)]) == 1
        assert worker1_id in ng_days[date(2024, 2, 20)]
    
    def test_get_approved_ng_days_by_date_range(self, test_db: Session):
        """Test retrieving approved NG days by date range."""
        # Create test user
        worker_id = str(uuid.uuid4())
        worker = User(
            id=worker_id,
            line_id=f"line_{worker_id}",
            name="Worker",
            role=UserRole.WORKER
        )
        
        test_db.add(worker)
        test_db.commit()
        
        # Create test requests
        request1 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker_id,
            request_date=date(2024, 2, 10),
            status=RequestStatus.APPROVED
        )
        
        request2 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker_id,
            request_date=date(2024, 2, 15),
            status=RequestStatus.APPROVED
        )
        
        request3 = Request(
            id=str(uuid.uuid4()),
            worker_id=worker_id,
            request_date=date(2024, 2, 25),
            status=RequestStatus.APPROVED
        )
        
        test_db.add_all([request1, request2, request3])
        test_db.commit()
        
        # Test get_approved_ng_days with date range
        service = ShiftService(test_db)
        ng_days = service.get_approved_ng_days(
            start_date=date(2024, 2, 12),
            end_date=date(2024, 2, 20)
        )
        
        # Should return only NG days in range
        assert len(ng_days) == 1
        assert date(2024, 2, 15) in ng_days
    
    def test_get_approved_ng_days_invalid_month(self, test_db: Session):
        """Test that invalid month raises ValueError."""
        service = ShiftService(test_db)
        
        with pytest.raises(ValueError, match="Month must be between 1 and 12"):
            service.get_approved_ng_days(year=2024, month=13)
    
    def test_get_approved_ng_days_invalid_date_range(self, test_db: Session):
        """Test that invalid date range raises ValueError."""
        service = ShiftService(test_db)
        
        with pytest.raises(ValueError, match="Start date .* must be before or equal to end date"):
            service.get_approved_ng_days(
                start_date=date(2024, 2, 20),
                end_date=date(2024, 2, 10)
            )
    
    def test_update_shift_add_workers(self, test_db: Session):
        """Test adding workers to a shift."""
        # Create test users
        worker1_id = str(uuid.uuid4())
        worker1 = User(
            id=worker1_id,
            line_id=f"line_{worker1_id}",
            name="Worker 1",
            role=UserRole.WORKER
        )
        
        worker2_id = str(uuid.uuid4())
        worker2 = User(
            id=worker2_id,
            line_id=f"line_{worker2_id}",
            name="Worker 2",
            role=UserRole.WORKER
        )
        
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"line_{admin_id}",
            name="Admin",
            role=UserRole.ADMIN
        )
        
        test_db.add_all([worker1, worker2, admin])
        test_db.commit()
        
        # Update shift with new workers
        service = ShiftService(test_db)
        result = service.update_shift(
            shift_date=date(2024, 2, 15),
            worker_ids=[worker1_id, worker2_id],
            admin_id=admin_id
        )
        
        # Verify shifts were created
        assert len(result['shifts']) == 2
        assert len(result['warnings']) == 0
        assert len(result['changes']['added']) == 2
        assert len(result['changes']['removed']) == 0
        assert worker1_id in result['changes']['added']
        assert worker2_id in result['changes']['added']
        
        # Verify shifts in database
        shifts = test_db.query(Shift).filter(
            Shift.shift_date == date(2024, 2, 15)
        ).all()
        assert len(shifts) == 2
        worker_ids_in_db = {shift.worker_id for shift in shifts}
        assert worker1_id in worker_ids_in_db
        assert worker2_id in worker_ids_in_db
    
    def test_update_shift_remove_workers(self, test_db: Session):
        """Test removing workers from a shift."""
        # Create test users
        worker1_id = str(uuid.uuid4())
        worker1 = User(
            id=worker1_id,
            line_id=f"line_{worker1_id}",
            name="Worker 1",
            role=UserRole.WORKER
        )
        
        worker2_id = str(uuid.uuid4())
        worker2 = User(
            id=worker2_id,
            line_id=f"line_{worker2_id}",
            name="Worker 2",
            role=UserRole.WORKER
        )
        
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"line_{admin_id}",
            name="Admin",
            role=UserRole.ADMIN
        )
        
        test_db.add_all([worker1, worker2, admin])
        test_db.commit()
        
        # Create existing shifts
        shift1 = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 2, 15),
            worker_id=worker1_id,
            updated_by=admin_id
        )
        
        shift2 = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 2, 15),
            worker_id=worker2_id,
            updated_by=admin_id
        )
        
        test_db.add_all([shift1, shift2])
        test_db.commit()
        
        # Update shift to remove worker2
        service = ShiftService(test_db)
        result = service.update_shift(
            shift_date=date(2024, 2, 15),
            worker_ids=[worker1_id],
            admin_id=admin_id
        )
        
        # Verify worker2 was removed
        assert len(result['shifts']) == 1
        assert result['shifts'][0].worker_id == worker1_id
        assert len(result['changes']['added']) == 0
        assert len(result['changes']['removed']) == 1
        assert worker2_id in result['changes']['removed']
        
        # Verify in database
        shifts = test_db.query(Shift).filter(
            Shift.shift_date == date(2024, 2, 15)
        ).all()
        assert len(shifts) == 1
        assert shifts[0].worker_id == worker1_id
    
    def test_update_shift_ng_day_warning(self, test_db: Session):
        """Test that NG day warning is returned when assigning worker with approved NG day."""
        # Create test users
        worker_id = str(uuid.uuid4())
        worker = User(
            id=worker_id,
            line_id=f"line_{worker_id}",
            name="Worker 1",
            role=UserRole.WORKER
        )
        
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"line_{admin_id}",
            name="Admin",
            role=UserRole.ADMIN
        )
        
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create approved NG day request
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker_id,
            request_date=date(2024, 2, 15),
            status=RequestStatus.APPROVED
        )
        
        test_db.add(request)
        test_db.commit()
        
        # Update shift with worker who has NG day
        service = ShiftService(test_db)
        result = service.update_shift(
            shift_date=date(2024, 2, 15),
            worker_ids=[worker_id],
            admin_id=admin_id
        )
        
        # Verify warning was returned
        assert len(result['warnings']) == 1
        assert "Worker 1" in result['warnings'][0]
        assert "approved NG day" in result['warnings'][0]
        assert "2024-02-15" in result['warnings'][0]
        
        # Verify shift was still created (warning, not error)
        assert len(result['shifts']) == 1
        assert result['shifts'][0].worker_id == worker_id
    
    def test_update_shift_change_history(self, test_db: Session):
        """Test that change history is recorded when updating shifts."""
        # Create test users
        worker_id = str(uuid.uuid4())
        worker = User(
            id=worker_id,
            line_id=f"line_{worker_id}",
            name="Worker",
            role=UserRole.WORKER
        )
        
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"line_{admin_id}",
            name="Admin",
            role=UserRole.ADMIN
        )
        
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create initial shift
        shift = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 2, 15),
            worker_id=worker_id,
            updated_by=admin_id
        )
        
        test_db.add(shift)
        test_db.commit()
        
        original_updated_at = shift.updated_at
        
        # Update shift (keep same worker)
        service = ShiftService(test_db)
        result = service.update_shift(
            shift_date=date(2024, 2, 15),
            worker_ids=[worker_id],
            admin_id=admin_id
        )
        
        # Verify updated_at and updated_by were updated
        updated_shift = result['shifts'][0]
        assert updated_shift.updated_at > original_updated_at
        assert updated_shift.updated_by == admin_id
    
    def test_update_shift_invalid_admin(self, test_db: Session):
        """Test that invalid admin ID raises ValueError."""
        service = ShiftService(test_db)
        
        with pytest.raises(ValueError, match="Admin with ID .* not found"):
            service.update_shift(
                shift_date=date(2024, 2, 15),
                worker_ids=[],
                admin_id="invalid-admin-id"
            )
    
    def test_update_shift_invalid_worker(self, test_db: Session):
        """Test that invalid worker ID raises ValueError."""
        # Create admin
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"line_{admin_id}",
            name="Admin",
            role=UserRole.ADMIN
        )
        
        test_db.add(admin)
        test_db.commit()
        
        service = ShiftService(test_db)
        
        with pytest.raises(ValueError, match="Worker with ID .* not found"):
            service.update_shift(
                shift_date=date(2024, 2, 15),
                worker_ids=["invalid-worker-id"],
                admin_id=admin_id
            )
    
    def test_update_shift_empty_worker_list(self, test_db: Session):
        """Test updating shift with empty worker list removes all workers."""
        # Create test users
        worker_id = str(uuid.uuid4())
        worker = User(
            id=worker_id,
            line_id=f"line_{worker_id}",
            name="Worker",
            role=UserRole.WORKER
        )
        
        admin_id = str(uuid.uuid4())
        admin = User(
            id=admin_id,
            line_id=f"line_{admin_id}",
            name="Admin",
            role=UserRole.ADMIN
        )
        
        test_db.add_all([worker, admin])
        test_db.commit()
        
        # Create existing shift
        shift = Shift(
            id=str(uuid.uuid4()),
            shift_date=date(2024, 2, 15),
            worker_id=worker_id,
            updated_by=admin_id
        )
        
        test_db.add(shift)
        test_db.commit()
        
        # Update shift with empty list
        service = ShiftService(test_db)
        result = service.update_shift(
            shift_date=date(2024, 2, 15),
            worker_ids=[],
            admin_id=admin_id
        )
        
        # Verify all workers were removed
        assert len(result['shifts']) == 0
        assert len(result['changes']['removed']) == 1
        assert worker_id in result['changes']['removed']
        
        # Verify in database
        shifts = test_db.query(Shift).filter(
            Shift.shift_date == date(2024, 2, 15)
        ).all()
        assert len(shifts) == 0
