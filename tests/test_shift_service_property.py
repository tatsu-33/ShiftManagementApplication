"""
Property-based tests for shift service.

Feature: shift-request-management
Validates: Requirements 6.2, 6.4
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import date, datetime
from calendar import monthrange
from sqlalchemy.orm import Session
import uuid

from app.models.user import User, UserRole
from app.models.shift import Shift
from app.models.request import Request, RequestStatus
from app.services.shift_service import ShiftService
from tests.conftest import get_test_db_session


# Custom strategies for generating test data
@st.composite
def valid_worker_strategy(draw):
    """Generate a valid worker user."""
    worker_id = str(uuid.uuid4())
    return User(
        id=worker_id,
        line_id=draw(st.text(
            min_size=5, 
            max_size=50, 
            alphabet=st.characters(
                min_codepoint=ord('a'),
                max_codepoint=ord('z'),
                blacklist_categories=('Cs',),
                blacklist_characters=['\x00']
            )
        )) + "_" + worker_id[:8],
        name=draw(st.text(
            min_size=3, 
            max_size=50, 
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('z'),
                blacklist_categories=('Cs',),
                blacklist_characters=['\x00']
            )
        )) + "_" + worker_id[:8],
        role=UserRole.WORKER,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@st.composite
def valid_admin_strategy(draw):
    """Generate a valid admin user."""
    admin_id = str(uuid.uuid4())
    return User(
        id=admin_id,
        line_id=draw(st.text(
            min_size=5, 
            max_size=50, 
            alphabet=st.characters(
                min_codepoint=ord('a'),
                max_codepoint=ord('z'),
                blacklist_categories=('Cs',),
                blacklist_characters=['\x00']
            )
        )) + "_admin_" + admin_id[:8],
        name=draw(st.text(
            min_size=3, 
            max_size=50, 
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('z'),
                blacklist_categories=('Cs',),
                blacklist_characters=['\x00']
            )
        )) + "_admin_" + admin_id[:8],
        role=UserRole.ADMIN,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@st.composite
def valid_date_strategy(draw):
    """Generate a valid date."""
    year = draw(st.integers(min_value=2024, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    max_day = monthrange(year, month)[1]
    day = draw(st.integers(min_value=1, max_value=max_day))
    return date(year, month, day)


@st.composite
def date_range_strategy(draw):
    """Generate a valid date range (start_date, end_date)."""
    start_date = draw(valid_date_strategy())
    # Generate end_date that is after or equal to start_date
    days_ahead = draw(st.integers(min_value=0, max_value=60))
    end_date = date.fromordinal(start_date.toordinal() + days_ahead)
    return (start_date, end_date)


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    workers=st.lists(valid_worker_strategy(), min_size=1, max_size=5),
    admin=valid_admin_strategy(),
    data=st.data()
)
def test_property_23_shift_display_includes_required_info(workers: list, admin: User, data):
    """
    Property 23: シフト表示には必須情報が含まれる
    
    For any shift data, when displayed, it includes each day's scheduled workers
    and approved NG days.
    
    Feature: shift-request-management, Property 23: シフト表示には必須情報が含まれる
    Validates: Requirements 6.2
    """
    with get_test_db_session() as test_db:
        # Add users to database
        for worker in workers:
            test_db.add(worker)
        test_db.add(admin)
        test_db.commit()
        
        # Generate a random month
        year = data.draw(st.integers(min_value=2024, max_value=2030))
        month = data.draw(st.integers(min_value=1, max_value=12))
        
        # Create shifts for the month
        num_shifts = data.draw(st.integers(min_value=1, max_value=10))
        max_day = monthrange(year, month)[1]
        used_shift_keys = set()
        
        for _ in range(num_shifts):
            day = data.draw(st.integers(min_value=1, max_value=max_day))
            shift_date = date(year, month, day)
            
            # Avoid duplicate shift_date + worker_id combinations
            worker = data.draw(st.sampled_from(workers))
            key = (shift_date, worker.id)
            
            if key not in used_shift_keys:
                used_shift_keys.add(key)
                shift = Shift(
                    id=str(uuid.uuid4()),
                    shift_date=shift_date,
                    worker_id=worker.id,
                    updated_by=admin.id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                test_db.add(shift)
        
        # Create some approved NG days for the same month
        # Avoid duplicate request_date + worker_id combinations
        num_ng_days = data.draw(st.integers(min_value=0, max_value=5))
        used_request_keys = set()
        
        for _ in range(num_ng_days):
            day = data.draw(st.integers(min_value=1, max_value=max_day))
            ng_date = date(year, month, day)
            worker = data.draw(st.sampled_from(workers))
            
            key = (ng_date, worker.id)
            if key not in used_request_keys:
                used_request_keys.add(key)
                request = Request(
                    id=str(uuid.uuid4()),
                    worker_id=worker.id,
                    request_date=ng_date,
                    status=RequestStatus.APPROVED,
                    created_at=datetime.utcnow(),
                    processed_at=datetime.utcnow(),
                    processed_by=admin.id
                )
                test_db.add(request)
        
        test_db.commit()
        
        # Create shift service
        service = ShiftService(test_db)
        
        # Get shifts for the month
        shifts = service.get_shifts_by_month(year, month)
        
        # Get approved NG days for the month
        ng_days = service.get_approved_ng_days(year=year, month=month)
        
        # Property: All shifts should have required information
        for shift in shifts:
            assert shift.shift_date is not None, \
                "Shift should have a date"
            assert shift.worker_id is not None, \
                "Shift should have a worker ID"
            assert shift.shift_date.year == year, \
                f"Shift date year should be {year}"
            assert shift.shift_date.month == month, \
                f"Shift date month should be {month}"
        
        # Property: NG days should be grouped by date with worker IDs
        for ng_date, worker_ids in ng_days.items():
            assert ng_date.year == year, \
                f"NG day year should be {year}"
            assert ng_date.month == month, \
                f"NG day month should be {month}"
            assert isinstance(worker_ids, list), \
                "Worker IDs should be in a list"
            assert all(isinstance(wid, str) for wid in worker_ids), \
                "All worker IDs should be strings"


@pytest.mark.property
@settings(max_examples=100)
@given(
    workers=st.lists(valid_worker_strategy(), min_size=1, max_size=5),
    admin=valid_admin_strategy(),
    date_range=date_range_strategy(),
    data=st.data()
)
def test_property_24_shifts_filtered_by_date_range(
    workers: list, 
    admin: User, 
    date_range: tuple, 
    data
):
    """
    Property 24: 日付範囲でシフトがフィルタされる
    
    For any date range, only shifts within that range are returned.
    
    Feature: shift-request-management, Property 24: 日付範囲でシフトがフィルタされる
    Validates: Requirements 6.4
    """
    with get_test_db_session() as test_db:
        # Add users to database
        for worker in workers:
            test_db.add(worker)
        test_db.add(admin)
        test_db.commit()
        
        start_date, end_date = date_range
        
        # Create shifts: some inside range, some outside
        num_shifts_inside = data.draw(st.integers(min_value=1, max_value=5))
        num_shifts_outside = data.draw(st.integers(min_value=1, max_value=5))
        
        shifts_inside = []
        shifts_outside = []
        used_keys = set()
        
        # Create shifts inside the range
        for _ in range(num_shifts_inside):
            # Generate a date within the range
            days_offset = data.draw(st.integers(
                min_value=0, 
                max_value=(end_date.toordinal() - start_date.toordinal())
            ))
            shift_date = date.fromordinal(start_date.toordinal() + days_offset)
            worker = data.draw(st.sampled_from(workers))
            
            key = (shift_date, worker.id)
            if key not in used_keys:
                used_keys.add(key)
                shift = Shift(
                    id=str(uuid.uuid4()),
                    shift_date=shift_date,
                    worker_id=worker.id,
                    updated_by=admin.id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                test_db.add(shift)
                shifts_inside.append(shift)
        
        # Create shifts outside the range (before start_date)
        for _ in range(num_shifts_outside):
            # Generate a date before the range
            days_before = data.draw(st.integers(min_value=1, max_value=30))
            shift_date = date.fromordinal(start_date.toordinal() - days_before)
            worker = data.draw(st.sampled_from(workers))
            
            key = (shift_date, worker.id)
            if key not in used_keys:
                used_keys.add(key)
                shift = Shift(
                    id=str(uuid.uuid4()),
                    shift_date=shift_date,
                    worker_id=worker.id,
                    updated_by=admin.id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                test_db.add(shift)
                shifts_outside.append(shift)
        
        test_db.commit()
        
        # Create shift service
        service = ShiftService(test_db)
        
        # Get shifts by date range
        filtered_shifts = service.get_shifts_by_date_range(start_date, end_date)
        
        # Property: All returned shifts should be within the date range
        for shift in filtered_shifts:
            assert start_date <= shift.shift_date <= end_date, \
                f"Shift date {shift.shift_date} should be within range [{start_date}, {end_date}]"
        
        # Property: Shifts outside the range should not be returned
        outside_shift_ids = {s.id for s in shifts_outside}
        returned_shift_ids = {s.id for s in filtered_shifts}
        
        assert not (outside_shift_ids & returned_shift_ids), \
            "Shifts outside the date range should not be returned"
        
        # Property: All shifts inside the range should be returned
        inside_shift_ids = {s.id for s in shifts_inside}
        assert inside_shift_ids.issubset(returned_shift_ids), \
            "All shifts inside the date range should be returned"


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    workers=st.lists(valid_worker_strategy(), min_size=2, max_size=5),
    admin=valid_admin_strategy(),
    shift_date=valid_date_strategy(),
    data=st.data()
)
def test_property_25_shift_worker_addition_removal(
    workers: list,
    admin: User,
    shift_date: date,
    data
):
    """
    Property 25: シフトの従業員追加・削除が可能
    
    For any shift, workers can be added and removed.
    
    Feature: shift-request-management, Property 25: シフトの従業員追加・削除が可能
    Validates: Requirements 7.1
    """
    with get_test_db_session() as test_db:
        # Add users to database
        for worker in workers:
            test_db.add(worker)
        test_db.add(admin)
        test_db.commit()
        
        # Create shift service
        service = ShiftService(test_db)
        
        # Initial state: Create shifts with some workers
        num_initial_workers = data.draw(st.integers(min_value=1, max_value=len(workers)))
        initial_workers = data.draw(st.lists(
            st.sampled_from(workers),
            min_size=num_initial_workers,
            max_size=num_initial_workers,
            unique_by=lambda w: w.id
        ))
        initial_worker_ids = [w.id for w in initial_workers]
        
        # Add initial workers to shift
        result1 = service.update_shift(
            shift_date=shift_date,
            worker_ids=initial_worker_ids,
            admin_id=admin.id
        )
        
        # Property: All initial workers should be added
        assert len(result1['changes']['added']) == len(initial_worker_ids), \
            "All initial workers should be added"
        assert set(result1['changes']['added']) == set(initial_worker_ids), \
            "Added workers should match initial worker IDs"
        assert len(result1['changes']['removed']) == 0, \
            "No workers should be removed on initial creation"
        
        # Property: Shifts should exist for all initial workers
        assert len(result1['shifts']) == len(initial_worker_ids), \
            "Number of shifts should match number of workers"
        shift_worker_ids = {s.worker_id for s in result1['shifts']}
        assert shift_worker_ids == set(initial_worker_ids), \
            "Shift worker IDs should match initial worker IDs"
        
        # Update state: Add some workers, remove some workers
        # Select a different set of workers
        num_updated_workers = data.draw(st.integers(min_value=0, max_value=len(workers)))
        if num_updated_workers > 0:
            updated_workers = data.draw(st.lists(
                st.sampled_from(workers),
                min_size=num_updated_workers,
                max_size=num_updated_workers,
                unique_by=lambda w: w.id
            ))
        else:
            updated_workers = []
        updated_worker_ids = [w.id for w in updated_workers]
        
        # Update shift with new worker list
        result2 = service.update_shift(
            shift_date=shift_date,
            worker_ids=updated_worker_ids,
            admin_id=admin.id
        )
        
        # Calculate expected changes
        initial_set = set(initial_worker_ids)
        updated_set = set(updated_worker_ids)
        expected_added = updated_set - initial_set
        expected_removed = initial_set - updated_set
        
        # Property: Changes should be correctly tracked
        assert set(result2['changes']['added']) == expected_added, \
            f"Added workers should be {expected_added}, got {set(result2['changes']['added'])}"
        assert set(result2['changes']['removed']) == expected_removed, \
            f"Removed workers should be {expected_removed}, got {set(result2['changes']['removed'])}"
        
        # Property: Final shifts should match updated worker list
        assert len(result2['shifts']) == len(updated_worker_ids), \
            f"Number of shifts should be {len(updated_worker_ids)}, got {len(result2['shifts'])}"
        final_shift_worker_ids = {s.worker_id for s in result2['shifts']}
        assert final_shift_worker_ids == updated_set, \
            f"Final shift worker IDs should be {updated_set}, got {final_shift_worker_ids}"


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    workers=st.lists(valid_worker_strategy(), min_size=1, max_size=3),
    admin=valid_admin_strategy(),
    shift_date=valid_date_strategy(),
    data=st.data()
)
def test_property_26_shift_update_records_change_history(
    workers: list,
    admin: User,
    shift_date: date,
    data
):
    """
    Property 26: シフト更新時に変更履歴が記録される
    
    For any shift update, change history (updated_at, updated_by) is recorded.
    
    Feature: shift-request-management, Property 26: シフト更新時に変更履歴が記録される
    Validates: Requirements 7.2
    """
    with get_test_db_session() as test_db:
        # Add users to database
        for worker in workers:
            test_db.add(worker)
        test_db.add(admin)
        test_db.commit()
        
        # Create shift service
        service = ShiftService(test_db)
        
        # Create initial shift
        worker = data.draw(st.sampled_from(workers))
        result1 = service.update_shift(
            shift_date=shift_date,
            worker_ids=[worker.id],
            admin_id=admin.id
        )
        
        # Property: Initial shift should have updated_by set to admin
        assert len(result1['shifts']) == 1, \
            "Should have one shift"
        initial_shift = result1['shifts'][0]
        assert initial_shift.updated_by == admin.id, \
            f"Initial shift should be updated by admin {admin.id}"
        assert initial_shift.updated_at is not None, \
            "Initial shift should have updated_at timestamp"
        
        initial_updated_at = initial_shift.updated_at
        
        # Wait a tiny bit to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        # Update the shift (keep same worker or change)
        should_change_worker = data.draw(st.booleans())
        if should_change_worker and len(workers) > 1:
            # Pick a different worker
            other_workers = [w for w in workers if w.id != worker.id]
            new_worker = data.draw(st.sampled_from(other_workers))
            new_worker_ids = [new_worker.id]
        else:
            # Keep same worker
            new_worker_ids = [worker.id]
        
        result2 = service.update_shift(
            shift_date=shift_date,
            worker_ids=new_worker_ids,
            admin_id=admin.id
        )
        
        # Property: Updated shifts should have updated_by set to admin
        for shift in result2['shifts']:
            assert shift.updated_by == admin.id, \
                f"Updated shift should be updated by admin {admin.id}"
            assert shift.updated_at is not None, \
                "Updated shift should have updated_at timestamp"
            
            # If this is the same shift (same worker), updated_at should be newer
            if shift.worker_id == worker.id:
                assert shift.updated_at >= initial_updated_at, \
                    f"Updated timestamp {shift.updated_at} should be >= initial {initial_updated_at}"


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    workers=st.lists(valid_worker_strategy(), min_size=1, max_size=3),
    admin=valid_admin_strategy(),
    shift_date=valid_date_strategy(),
    data=st.data()
)
def test_property_27_ng_day_assignment_shows_warning(
    workers: list,
    admin: User,
    shift_date: date,
    data
):
    """
    Property 27: NG日がある従業員の割り当て時に警告が表示される
    
    For any shift assignment, when assigning a worker with an approved NG day,
    a warning is returned.
    
    Feature: shift-request-management, Property 27: NG日がある従業員の割り当て時に警告が表示される
    Validates: Requirements 7.3
    """
    with get_test_db_session() as test_db:
        # Add users to database
        for worker in workers:
            test_db.add(worker)
        test_db.add(admin)
        test_db.commit()
        
        # Randomly decide how many workers have NG days
        num_workers_with_ng = data.draw(st.integers(min_value=0, max_value=len(workers)))
        
        if num_workers_with_ng > 0:
            workers_with_ng = data.draw(st.lists(
                st.sampled_from(workers),
                min_size=num_workers_with_ng,
                max_size=num_workers_with_ng,
                unique_by=lambda w: w.id
            ))
        else:
            workers_with_ng = []
        
        # Create approved NG day requests for selected workers
        for worker in workers_with_ng:
            request = Request(
                id=str(uuid.uuid4()),
                worker_id=worker.id,
                request_date=shift_date,
                status=RequestStatus.APPROVED,
                created_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
                processed_by=admin.id
            )
            test_db.add(request)
        
        test_db.commit()
        
        # Create shift service
        service = ShiftService(test_db)
        
        # Randomly select workers to assign to shift
        num_workers_to_assign = data.draw(st.integers(min_value=1, max_value=len(workers)))
        workers_to_assign = data.draw(st.lists(
            st.sampled_from(workers),
            min_size=num_workers_to_assign,
            max_size=num_workers_to_assign,
            unique_by=lambda w: w.id
        ))
        worker_ids_to_assign = [w.id for w in workers_to_assign]
        
        # Update shift
        result = service.update_shift(
            shift_date=shift_date,
            worker_ids=worker_ids_to_assign,
            admin_id=admin.id
        )
        
        # Calculate expected warnings
        workers_with_ng_ids = {w.id for w in workers_with_ng}
        assigned_worker_ids = set(worker_ids_to_assign)
        expected_conflicts = workers_with_ng_ids & assigned_worker_ids
        
        # Property: Warning should be returned for each worker with NG day
        assert len(result['warnings']) == len(expected_conflicts), \
            f"Should have {len(expected_conflicts)} warnings, got {len(result['warnings'])}"
        
        # Property: Each warning should mention the worker and NG day
        for worker_id in expected_conflicts:
            worker = next(w for w in workers if w.id == worker_id)
            # Check that at least one warning mentions this worker
            worker_mentioned = any(
                worker.name in warning or worker_id in warning
                for warning in result['warnings']
            )
            assert worker_mentioned, \
                f"Warning should mention worker {worker.name} (ID: {worker_id})"
            
            # Check that at least one warning mentions NG day
            ng_day_mentioned = any(
                "NG day" in warning or "NG日" in warning
                for warning in result['warnings']
            )
            assert ng_day_mentioned, \
                "Warning should mention NG day"
        
        # Property: Shifts should still be created despite warnings
        assert len(result['shifts']) == len(worker_ids_to_assign), \
            f"Should have {len(worker_ids_to_assign)} shifts despite warnings"
        
        # Property: If no conflicts, no warnings should be returned
        if len(expected_conflicts) == 0:
            assert len(result['warnings']) == 0, \
                "Should have no warnings when no NG day conflicts"
