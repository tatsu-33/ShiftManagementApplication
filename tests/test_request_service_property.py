"""
Property-based tests for request service.

Feature: shift-request-management
Validates: Requirements 1.3, 1.4, 1.5, 2.5
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
import uuid

from app.models.user import User, UserRole
from app.models.request import Request, RequestStatus
from app.models.settings import Settings as SettingsModel
from app.services.request_service import RequestService
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
        )) + "_" + worker_id[:8],  # Append part of UUID to ensure uniqueness
        name=draw(st.text(
            min_size=3, 
            max_size=50, 
            alphabet=st.characters(
                min_codepoint=ord('A'),
                max_codepoint=ord('z'),
                blacklist_categories=('Cs',),
                blacklist_characters=['\x00']
            )
        )) + "_" + worker_id[:8],  # Append part of UUID to ensure uniqueness
        role=UserRole.WORKER,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@st.composite
def current_date_strategy(draw):
    """Generate a current date before the deadline (day 1-10)."""
    year = draw(st.integers(min_value=2024, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=10))  # Before default deadline
    return date(year, month, day)


@st.composite
def next_month_date_strategy(draw, current_date: date):
    """Generate a date in the next month relative to current_date."""
    next_month = current_date + relativedelta(months=1)
    # Generate a valid day for the next month
    if next_month.month in [1, 3, 5, 7, 8, 10, 12]:
        max_day = 31
    elif next_month.month in [4, 6, 9, 11]:
        max_day = 30
    else:  # February
        if next_month.year % 4 == 0 and (next_month.year % 100 != 0 or next_month.year % 400 == 0):
            max_day = 29
        else:
            max_day = 28
    
    day = draw(st.integers(min_value=1, max_value=max_day))
    return date(next_month.year, next_month.month, day)


@st.composite
def past_deadline_date_strategy(draw):
    """Generate a current date past the deadline (day 11-31)."""
    year = draw(st.integers(min_value=2024, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    
    # Determine max day for the month
    if month in [1, 3, 5, 7, 8, 10, 12]:
        max_day = 31
    elif month in [4, 6, 9, 11]:
        max_day = 30
    else:  # February
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            max_day = 29
        else:
            max_day = 28
    
    day = draw(st.integers(min_value=11, max_value=max_day))  # Past default deadline
    return date(year, month, day)


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_2_request_status_is_pending(worker: User, current_date: date, data):
    """
    Property 2: 申請作成時のステータスは保留中
    
    For any valid date and worker ID, when a new request is created,
    its status is set to "pending".
    
    Validates: Requirements 1.3
    """
    with get_test_db_session() as test_db:
        # Add worker to database
        test_db.add(worker)
        test_db.commit()
        
        # Generate a valid next month date
        request_date = data.draw(next_month_date_strategy(current_date))
        
        # Create request service
        service = RequestService(test_db)
        
        # Create request
        request = service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        # Property: Status should be PENDING
        assert request.status == RequestStatus.PENDING, \
            f"Request status should be PENDING, but got {request.status}"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_3_duplicate_requests_rejected(worker: User, current_date: date, data):
    """
    Property 3: 重複申請は拒否される
    
    For any request, when the same worker attempts to submit another
    request for the same date, the system rejects the request.
    
    Validates: Requirements 1.4
    """
    with get_test_db_session() as test_db:
        # Add worker to database
        test_db.add(worker)
        test_db.commit()
        
        # Generate a valid next month date
        request_date = data.draw(next_month_date_strategy(current_date))
        
        # Create request service
        service = RequestService(test_db)
        
        # Create first request (should succeed)
        first_request = service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=current_date
        )
        assert first_request is not None
        
        # Property: Duplicate request should be rejected
        with pytest.raises(ValueError, match="already exists"):
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_4_required_fields_recorded(worker: User, current_date: date, data):
    """
    Property 4: 申請には必須フィールドが記録される
    
    For any request creation, the requester ID, date, and creation
    timestamp are recorded.
    
    Validates: Requirements 1.5
    """
    with get_test_db_session() as test_db:
        # Add worker to database
        test_db.add(worker)
        test_db.commit()
        
        # Generate a valid next month date
        request_date = data.draw(next_month_date_strategy(current_date))
        
        # Create request service
        service = RequestService(test_db)
        
        # Create request
        request = service.create_request(
            worker_id=worker.id,
            request_date=request_date,
            current_date=current_date
        )
        
        # Property: Required fields should be recorded
        assert request.worker_id == worker.id, \
            "Request should record the worker ID"
        assert request.request_date == request_date, \
            "Request should record the request date"
        assert request.created_at is not None, \
            "Request should record the creation timestamp"
        assert isinstance(request.created_at, datetime), \
            "Created_at should be a datetime object"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    current_date=past_deadline_date_strategy(),
    data=st.data()
)
def test_property_8_past_deadline_requests_rejected(worker: User, current_date: date, data):
    """
    Property 8: 締切日を過ぎた申請は拒否される
    
    For any combination of current date and deadline, when the current
    date is past the deadline, new requests are rejected.
    
    Validates: Requirements 2.5
    """
    with get_test_db_session() as test_db:
        # Add worker to database
        test_db.add(worker)
        test_db.commit()
        
        # Generate a valid next month date
        request_date = data.draw(next_month_date_strategy(current_date))
        
        # Create request service
        service = RequestService(test_db)
        
        # Property: Request past deadline should be rejected
        with pytest.raises(ValueError, match="deadline has passed"):
            service.create_request(
                worker_id=worker.id,
                request_date=request_date,
                current_date=current_date
            )


@pytest.mark.property
@settings(max_examples=100)
@given(
    workers=st.lists(valid_worker_strategy(), min_size=1, max_size=5),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_10_requests_filtered_by_worker(workers: list, current_date: date, data):
    """
    Property 10: 申請一覧は従業員でフィルタされる
    
    For any worker and set of requests, when retrieving requests,
    only that worker's requests are returned.
    
    Feature: shift-request-management, Property 10: 申請一覧は従業員でフィルタされる
    Validates: Requirements 3.1
    """
    with get_test_db_session() as test_db:
        # Add workers to database
        for worker in workers:
            test_db.add(worker)
        test_db.commit()
        
        # Create requests for each worker
        target_worker = workers[0]
        num_requests_per_worker = data.draw(st.integers(min_value=1, max_value=3))
        
        for worker in workers:
            used_dates = set()
            attempts = 0
            created_count = 0
            while created_count < num_requests_per_worker and attempts < num_requests_per_worker * 10:
                request_date = data.draw(next_month_date_strategy(current_date))
                attempts += 1
                if request_date not in used_dates:
                    used_dates.add(request_date)
                    request = Request(
                        id=str(uuid.uuid4()),
                        worker_id=worker.id,
                        request_date=request_date,
                        status=data.draw(st.sampled_from([RequestStatus.PENDING, RequestStatus.APPROVED, RequestStatus.REJECTED])),
                        created_at=datetime.utcnow()
                    )
                    test_db.add(request)
                    created_count += 1
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Get requests for target worker
        requests = service.get_requests_by_worker(target_worker.id)
        
        # Property: All returned requests should belong to the target worker
        assert all(r.worker_id == target_worker.id for r in requests), \
            f"All requests should belong to worker {target_worker.id}"


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_11_request_display_includes_required_fields(worker: User, current_date: date, data):
    """
    Property 11: 申請表示には必須フィールドが含まれる
    
    For any request, when displayed, it includes date, status, and creation timestamp.
    
    Feature: shift-request-management, Property 11: 申請表示には必須フィールドが含まれる
    Validates: Requirements 3.2
    """
    with get_test_db_session() as test_db:
        # Add worker to database
        test_db.add(worker)
        test_db.commit()
        
        # Create multiple requests
        num_requests = data.draw(st.integers(min_value=1, max_value=5))
        used_dates = set()
        attempts = 0
        created_count = 0
        while created_count < num_requests and attempts < num_requests * 10:
            request_date = data.draw(next_month_date_strategy(current_date))
            attempts += 1
            if request_date not in used_dates:
                used_dates.add(request_date)
                request = Request(
                    id=str(uuid.uuid4()),
                    worker_id=worker.id,
                    request_date=request_date,
                    status=data.draw(st.sampled_from([RequestStatus.PENDING, RequestStatus.APPROVED, RequestStatus.REJECTED])),
                    created_at=datetime.utcnow()
                )
                test_db.add(request)
                created_count += 1
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Get requests
        requests = service.get_requests_by_worker(worker.id)
        
        # Property: All requests should have required fields
        for request in requests:
            assert request.request_date is not None, \
                "Request should have a date"
            assert request.status is not None, \
                "Request should have a status"
            assert request.created_at is not None, \
                "Request should have a creation timestamp"


@pytest.mark.property
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.large_base_example])
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_12_requests_sorted_by_date_descending(worker: User, current_date: date, data):
    """
    Property 12: 申請一覧は日付順にソートされる
    
    For any list of requests, when displayed, they are sorted by date descending (newest first).
    
    Feature: shift-request-management, Property 12: 申請一覧は日付順にソートされる
    Validates: Requirements 3.3
    """
    with get_test_db_session() as test_db:
        # Add worker to database
        test_db.add(worker)
        test_db.commit()
        
        # Create multiple requests with different dates
        num_requests = data.draw(st.integers(min_value=2, max_value=5))
        created_dates = []
        for i in range(num_requests):
            request_date = data.draw(next_month_date_strategy(current_date))
            # Ensure unique dates
            while request_date in created_dates:
                request_date = data.draw(next_month_date_strategy(current_date))
            created_dates.append(request_date)
            
            request = Request(
                id=str(uuid.uuid4()),
                worker_id=worker.id,
                request_date=request_date,
                status=data.draw(st.sampled_from([RequestStatus.PENDING, RequestStatus.APPROVED, RequestStatus.REJECTED])),
                created_at=datetime.utcnow()
            )
            test_db.add(request)
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Get requests
        requests = service.get_requests_by_worker(worker.id)
        
        # Property: Requests should be sorted by date descending
        if len(requests) > 1:
            for i in range(len(requests) - 1):
                assert requests[i].request_date >= requests[i + 1].request_date, \
                    f"Requests should be sorted by date descending, but {requests[i].request_date} < {requests[i + 1].request_date}"


@pytest.mark.property
@settings(max_examples=100)
@given(
    workers=st.lists(valid_worker_strategy(), min_size=2, max_size=5),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_13_admin_retrieves_all_requests(workers: list, current_date: date, data):
    """
    Property 13: 管理者は全申請を取得できる
    
    For any set of requests, when an administrator retrieves the request list,
    all workers' requests are returned.
    
    Feature: shift-request-management, Property 13: 管理者は全申請を取得できる
    Validates: Requirements 4.1
    """
    with get_test_db_session() as test_db:
        # Add workers to database
        for worker in workers:
            test_db.add(worker)
        test_db.commit()
        
        # Create requests for each worker
        total_requests = 0
        for worker in workers:
            num_requests = data.draw(st.integers(min_value=1, max_value=3))
            used_dates = set()
            attempts = 0
            created_count = 0
            while created_count < num_requests and attempts < num_requests * 10:
                request_date = data.draw(next_month_date_strategy(current_date))
                attempts += 1
                if request_date not in used_dates:
                    used_dates.add(request_date)
                    request = Request(
                        id=str(uuid.uuid4()),
                        worker_id=worker.id,
                        request_date=request_date,
                        status=data.draw(st.sampled_from([RequestStatus.PENDING, RequestStatus.APPROVED, RequestStatus.REJECTED])),
                        created_at=datetime.utcnow()
                    )
                    test_db.add(request)
                    total_requests += 1
                    created_count += 1
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Get all requests (admin view)
        all_requests = service.get_all_requests()
        
        # Property: Should return all requests from all workers
        assert len(all_requests) == total_requests, \
            f"Admin should retrieve all {total_requests} requests, but got {len(all_requests)}"
        
        # Verify requests from all workers are included
        worker_ids_in_requests = set(r.worker_id for r in all_requests)
        expected_worker_ids = set(w.id for w in workers if any(
            r.worker_id == w.id for r in all_requests
        ))
        assert worker_ids_in_requests == expected_worker_ids, \
            "All workers with requests should be represented"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_15_pending_requests_prioritized(worker: User, current_date: date, data):
    """
    Property 15: 保留中の申請が優先表示される
    
    For any list of requests, when displayed, pending status requests
    appear before other statuses.
    
    Feature: shift-request-management, Property 15: 保留中の申請が優先表示される
    Validates: Requirements 4.3
    """
    with get_test_db_session() as test_db:
        # Add worker to database
        test_db.add(worker)
        test_db.commit()
        
        # Create requests with different statuses
        # Ensure we have at least one pending and one non-pending
        statuses = [RequestStatus.PENDING, RequestStatus.APPROVED, RequestStatus.REJECTED]
        num_requests = data.draw(st.integers(min_value=3, max_value=6))
        
        used_dates = set()
        attempts = 0
        created_count = 0
        while created_count < num_requests and attempts < num_requests * 10:
            request_date = data.draw(next_month_date_strategy(current_date))
            attempts += 1
            if request_date not in used_dates:
                used_dates.add(request_date)
                # Ensure we have at least one of each status
                if created_count < len(statuses):
                    status = statuses[created_count]
                else:
                    status = data.draw(st.sampled_from(statuses))
                
                request = Request(
                    id=str(uuid.uuid4()),
                    worker_id=worker.id,
                    request_date=request_date,
                    status=status,
                    created_at=datetime.utcnow()
                )
                test_db.add(request)
                created_count += 1
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Get all requests
        all_requests = service.get_all_requests()
        
        # Property: Pending requests should appear before non-pending
        if len(all_requests) > 1:
            # Find first non-pending request
            first_non_pending_idx = None
            for i, req in enumerate(all_requests):
                if req.status != RequestStatus.PENDING:
                    first_non_pending_idx = i
                    break
            
            # If there are non-pending requests, verify all pending come before them
            if first_non_pending_idx is not None:
                for i in range(first_non_pending_idx):
                    assert all_requests[i].status == RequestStatus.PENDING, \
                        f"All pending requests should appear before non-pending, but found {all_requests[i].status} at index {i}"


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(
    workers=st.lists(valid_worker_strategy(), min_size=2, max_size=5),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_16_search_returns_matching_requests(workers: list, current_date: date, data):
    """
    Property 16: 検索条件に一致する申請のみが返される
    
    For any search query (worker name or date), only requests matching
    the criteria are returned.
    
    Feature: shift-request-management, Property 16: 検索条件に一致する申請のみが返される
    Validates: Requirements 4.4
    """
    with get_test_db_session() as test_db:
        # Add workers to database
        for worker in workers:
            test_db.add(worker)
        test_db.commit()
        
        # Create requests for each worker
        for worker in workers:
            num_requests = data.draw(st.integers(min_value=1, max_value=3))
            used_dates = set()
            attempts = 0
            created_count = 0
            while created_count < num_requests and attempts < num_requests * 10:
                request_date = data.draw(next_month_date_strategy(current_date))
                attempts += 1
                if request_date not in used_dates:
                    used_dates.add(request_date)
                    request = Request(
                        id=str(uuid.uuid4()),
                        worker_id=worker.id,
                        request_date=request_date,
                        status=data.draw(st.sampled_from([RequestStatus.PENDING, RequestStatus.APPROVED, RequestStatus.REJECTED])),
                        created_at=datetime.utcnow()
                    )
                    test_db.add(request)
                    created_count += 1
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Test worker name search - use a unique part of the first worker's name
        # that won't appear in UUID suffixes
        target_worker = workers[0]
        # Extract the part before the UUID suffix (before the last underscore)
        name_parts = target_worker.name.rsplit('_', 1)
        if len(name_parts) > 1 and len(name_parts[0]) >= 3:
            search_term = name_parts[0][:3]  # Use first 3 chars of the non-UUID part
        else:
            search_term = target_worker.name[:3] if len(target_worker.name) >= 3 else target_worker.name
        
        matching_requests = service.get_all_requests(worker_name=search_term)
        
        # Property: All returned requests should match the search criteria
        for request in matching_requests:
            worker = test_db.query(User).filter(User.id == request.worker_id).first()
            assert search_term.lower() in worker.name.lower(), \
                f"Request worker name '{worker.name}' should contain search term '{search_term}'"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_17_filter_returns_matching_requests(worker: User, current_date: date, data):
    """
    Property 17: フィルター条件に一致する申請のみが返される
    
    For any filter criteria (status or month), only requests matching
    the criteria are returned.
    
    Feature: shift-request-management, Property 17: フィルター条件に一致する申請のみが返される
    Validates: Requirements 4.5
    """
    with get_test_db_session() as test_db:
        # Add worker to database
        test_db.add(worker)
        test_db.commit()
        
        # Create requests with different statuses and months
        statuses = [RequestStatus.PENDING, RequestStatus.APPROVED, RequestStatus.REJECTED]
        num_requests = data.draw(st.integers(min_value=3, max_value=6))
        
        used_dates = set()
        attempts = 0
        created_count = 0
        while created_count < num_requests and attempts < num_requests * 10:
            request_date = data.draw(next_month_date_strategy(current_date))
            attempts += 1
            if request_date not in used_dates:
                used_dates.add(request_date)
                request = Request(
                    id=str(uuid.uuid4()),
                    worker_id=worker.id,
                    request_date=request_date,
                    status=data.draw(st.sampled_from(statuses)),
                    created_at=datetime.utcnow()
                )
                test_db.add(request)
                created_count += 1
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Test status filter
        filter_status = data.draw(st.sampled_from(statuses))
        filtered_requests = service.get_all_requests(status=filter_status)
        
        # Property: All returned requests should match the filter status
        for request in filtered_requests:
            assert request.status == filter_status, \
                f"Request status should be {filter_status}, but got {request.status}"
        
        # Test month filter
        next_month = current_date + relativedelta(months=1)
        month_filtered_requests = service.get_all_requests(
            month=next_month.month,
            year=next_month.year
        )
        
        # Property: All returned requests should be in the filtered month
        for request in month_filtered_requests:
            assert request.request_date.month == next_month.month, \
                f"Request month should be {next_month.month}, but got {request.request_date.month}"
            assert request.request_date.year == next_month.year, \
                f"Request year should be {next_month.year}, but got {request.request_date.year}"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    admin=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_18_approval_updates_status(worker: User, admin: User, current_date: date, data):
    """
    Property 18: 承認時にステータスが更新される
    
    For any pending request, when approved, the status is updated to "approved".
    
    Feature: shift-request-management, Property 18: 承認時にステータスが更新される
    Validates: Requirements 5.1
    """
    with get_test_db_session() as test_db:
        # Add worker and admin to database
        test_db.add(worker)
        # Make admin have a different ID
        admin.id = str(uuid.uuid4())
        admin.line_id = admin.line_id + "_admin"
        admin.name = admin.name + "_admin"
        test_db.add(admin)
        test_db.commit()
        
        # Create a pending request
        request_date = data.draw(next_month_date_strategy(current_date))
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=request_date,
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(request)
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Approve the request
        approved_request = service.approve_request(request.id, admin.id)
        
        # Property: Status should be updated to APPROVED
        assert approved_request.status == RequestStatus.APPROVED, \
            f"Request status should be APPROVED after approval, but got {approved_request.status}"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    admin=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data()
)
def test_property_19_rejection_updates_status(worker: User, admin: User, current_date: date, data):
    """
    Property 19: 却下時にステータスが更新される
    
    For any pending request, when rejected, the status is updated to "rejected".
    
    Feature: shift-request-management, Property 19: 却下時にステータスが更新される
    Validates: Requirements 5.2
    """
    with get_test_db_session() as test_db:
        # Add worker and admin to database
        test_db.add(worker)
        # Make admin have a different ID
        admin.id = str(uuid.uuid4())
        admin.line_id = admin.line_id + "_admin"
        admin.name = admin.name + "_admin"
        test_db.add(admin)
        test_db.commit()
        
        # Create a pending request
        request_date = data.draw(next_month_date_strategy(current_date))
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=request_date,
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(request)
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Reject the request
        rejected_request = service.reject_request(request.id, admin.id)
        
        # Property: Status should be updated to REJECTED
        assert rejected_request.status == RequestStatus.REJECTED, \
            f"Request status should be REJECTED after rejection, but got {rejected_request.status}"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    admin=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data(),
    action=st.sampled_from(['approve', 'reject'])
)
def test_property_20_processing_info_recorded(worker: User, admin: User, current_date: date, data, action: str):
    """
    Property 20: ステータス更新時に処理情報が記録される
    
    For any request status update, the processing timestamp and processor ID are recorded.
    
    Feature: shift-request-management, Property 20: ステータス更新時に処理情報が記録される
    Validates: Requirements 5.3
    """
    with get_test_db_session() as test_db:
        # Add worker and admin to database
        test_db.add(worker)
        # Make admin have a different ID
        admin.id = str(uuid.uuid4())
        admin.line_id = admin.line_id + "_admin"
        admin.name = admin.name + "_admin"
        test_db.add(admin)
        test_db.commit()
        
        # Create a pending request
        request_date = data.draw(next_month_date_strategy(current_date))
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=request_date,
            status=RequestStatus.PENDING,
            created_at=datetime.utcnow()
        )
        test_db.add(request)
        test_db.commit()
        
        # Record time before processing
        before_processing = datetime.utcnow()
        
        # Create request service
        service = RequestService(test_db)
        
        # Process the request (approve or reject)
        if action == 'approve':
            processed_request = service.approve_request(request.id, admin.id)
        else:
            processed_request = service.reject_request(request.id, admin.id)
        
        # Property: Processing information should be recorded
        assert processed_request.processed_at is not None, \
            "Processed_at timestamp should be recorded"
        assert isinstance(processed_request.processed_at, datetime), \
            "Processed_at should be a datetime object"
        assert processed_request.processed_at >= before_processing, \
            "Processed_at should be after or equal to the time before processing"
        
        assert processed_request.processed_by == admin.id, \
            f"Processed_by should be {admin.id}, but got {processed_request.processed_by}"


@pytest.mark.property
@settings(max_examples=100)
@given(
    worker=valid_worker_strategy(),
    admin=valid_worker_strategy(),
    current_date=current_date_strategy(),
    data=st.data(),
    initial_status=st.sampled_from([RequestStatus.APPROVED, RequestStatus.REJECTED]),
    action=st.sampled_from(['approve', 'reject'])
)
def test_property_22_processed_requests_cannot_change_status(
    worker: User, 
    admin: User, 
    current_date: date, 
    data, 
    initial_status: RequestStatus,
    action: str
):
    """
    Property 22: 処理済み申請のステータス変更は拒否される
    
    For any approved or rejected request, when attempting to change status,
    the system rejects the change.
    
    Feature: shift-request-management, Property 22: 処理済み申請のステータス変更は拒否される
    Validates: Requirements 5.5
    """
    with get_test_db_session() as test_db:
        # Add worker and admin to database
        test_db.add(worker)
        # Make admin have a different ID
        admin.id = str(uuid.uuid4())
        admin.line_id = admin.line_id + "_admin"
        admin.name = admin.name + "_admin"
        test_db.add(admin)
        test_db.commit()
        
        # Create a request with already processed status
        request_date = data.draw(next_month_date_strategy(current_date))
        request = Request(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            request_date=request_date,
            status=initial_status,
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
            processed_by=admin.id
        )
        test_db.add(request)
        test_db.commit()
        
        # Create request service
        service = RequestService(test_db)
        
        # Property: Attempting to change status should raise ValueError
        with pytest.raises(ValueError, match="Only pending requests"):
            if action == 'approve':
                service.approve_request(request.id, admin.id)
            else:
                service.reject_request(request.id, admin.id)
