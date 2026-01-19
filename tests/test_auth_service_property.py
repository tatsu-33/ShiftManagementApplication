"""
Property-based tests for authentication service.

Feature: shift-request-management, Property 29: LINE IDで従業員が識別される
Validates: Requirements 8.1
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from sqlalchemy.orm import Session
import uuid

from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from tests.conftest import get_test_db_session


# Custom strategies for generating test data
@st.composite
def line_id_strategy(draw):
    """Generate random LINE IDs."""
    # LINE IDs are typically alphanumeric strings
    return draw(st.text(
        min_size=1, 
        max_size=100, 
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),  # Uppercase, lowercase, digits
            blacklist_characters=['\x00']
        )
    ))


@st.composite
def worker_name_strategy(draw):
    """Generate random worker names."""
    return draw(st.text(
        min_size=1, 
        max_size=100, 
        alphabet=st.characters(
            blacklist_categories=('Cs',),  # Exclude surrogates
            blacklist_characters=['\x00']
        )
    ))


@pytest.mark.property
@settings(max_examples=100)
@given(
    line_id=line_id_strategy(),
    worker_name=worker_name_strategy()
)
def test_line_id_identifies_worker(line_id: str, worker_name: str):
    """
    Property 29: LINE IDで従業員が識別される
    
    For any LINE ID, when a worker is registered with that LINE ID,
    the system correctly identifies and retrieves that worker.
    
    This property ensures that:
    1. A worker can be registered with a LINE ID
    2. The same worker can be retrieved using that LINE ID
    3. The retrieved worker has the correct attributes
    
    Validates: Requirements 8.1
    """
    with get_test_db_session() as test_db:
        auth_service = AuthService(test_db)
        
        # Register a worker with the generated LINE ID
        registered_worker = auth_service.register_worker(line_id, worker_name)
        
        # Verify registration succeeded
        assert registered_worker is not None
        assert registered_worker.line_id == line_id
        assert registered_worker.name == worker_name
        assert registered_worker.role == UserRole.WORKER
        
        # Retrieve the worker by LINE ID
        retrieved_worker = auth_service.get_worker_by_line_id(line_id)
        
        # Property: The system correctly identifies the worker by LINE ID
        assert retrieved_worker is not None, f"Worker with LINE ID {line_id} should be retrievable"
        assert retrieved_worker.id == registered_worker.id, "Retrieved worker should have same ID"
        assert retrieved_worker.line_id == line_id, "Retrieved worker should have correct LINE ID"
        assert retrieved_worker.name == worker_name, "Retrieved worker should have correct name"
        assert retrieved_worker.role == UserRole.WORKER, "Retrieved worker should have WORKER role"


@pytest.mark.property
@settings(max_examples=100)
@given(
    line_id=line_id_strategy(),
    worker_name=worker_name_strategy()
)
def test_line_id_uniquely_identifies_worker(line_id: str, worker_name: str):
    """
    Property 29: LINE IDで従業員が識別される (Uniqueness)
    
    For any LINE ID, the system ensures that LINE ID uniquely identifies
    a single worker. Attempting to register another worker with the same
    LINE ID should fail.
    
    This property ensures that:
    1. Each LINE ID maps to exactly one worker
    2. Duplicate LINE IDs are rejected
    
    Validates: Requirements 8.1
    """
    with get_test_db_session() as test_db:
        auth_service = AuthService(test_db)
        
        # Register first worker with the LINE ID
        first_worker = auth_service.register_worker(line_id, worker_name)
        assert first_worker is not None
        
        # Attempt to register another worker with the same LINE ID
        with pytest.raises(ValueError, match=f"LINE ID {line_id} is already registered"):
            auth_service.register_worker(line_id, "Different Name")
        
        # Verify the original worker is still retrievable
        retrieved_worker = auth_service.get_worker_by_line_id(line_id)
        assert retrieved_worker is not None
        assert retrieved_worker.id == first_worker.id
        assert retrieved_worker.name == worker_name  # Original name preserved


@pytest.mark.property
@settings(max_examples=100)
@given(
    line_id=line_id_strategy(),
    worker_name=worker_name_strategy()
)
def test_line_id_only_identifies_workers_not_admins(line_id: str, worker_name: str):
    """
    Property 29: LINE IDで従業員が識別される (Role filtering)
    
    For any LINE ID, the get_worker_by_line_id function should only
    return users with WORKER role, not ADMIN role.
    
    This property ensures that:
    1. Admin users are not returned by worker lookup
    2. Role-based filtering works correctly
    
    Validates: Requirements 8.1
    """
    with get_test_db_session() as test_db:
        # Create an admin user with a LINE ID
        admin_user = User(
            id=str(uuid.uuid4()),
            line_id=line_id,
            name=worker_name,
            role=UserRole.ADMIN
        )
        test_db.add(admin_user)
        test_db.commit()
        
        # Attempt to retrieve as worker
        auth_service = AuthService(test_db)
        retrieved_worker = auth_service.get_worker_by_line_id(line_id)
        
        # Property: Admin users should not be returned by worker lookup
        assert retrieved_worker is None, "Admin users should not be identified as workers"


@pytest.mark.property
@settings(max_examples=100)
@given(
    existing_line_id=line_id_strategy(),
    existing_name=worker_name_strategy(),
    different_name=worker_name_strategy()
)
def test_get_or_create_worker_identifies_existing(
    existing_line_id: str, 
    existing_name: str,
    different_name: str
):
    """
    Property 29: LINE IDで従業員が識別される (Get or Create)
    
    For any LINE ID with an existing worker, get_or_create_worker
    should identify and return the existing worker without creating
    a new one.
    
    This property ensures that:
    1. Existing workers are correctly identified
    2. No duplicate workers are created
    3. Existing worker data is preserved
    
    Validates: Requirements 8.1
    """
    with get_test_db_session() as test_db:
        auth_service = AuthService(test_db)
        
        # Create an existing worker
        existing_worker = auth_service.register_worker(existing_line_id, existing_name)
        original_id = existing_worker.id
        
        # Call get_or_create with the same LINE ID but different name
        retrieved_worker, created = auth_service.get_or_create_worker(
            existing_line_id, 
            different_name
        )
        
        # Property: Existing worker should be identified and returned
        assert created is False, "Should not create new worker when one exists"
        assert retrieved_worker.id == original_id, "Should return existing worker's ID"
        assert retrieved_worker.line_id == existing_line_id, "Should have correct LINE ID"
        assert retrieved_worker.name == existing_name, "Should preserve original name"
        
        # Verify no duplicate was created in database
        all_workers = test_db.query(User).filter(
            User.line_id == existing_line_id
        ).all()
        assert len(all_workers) == 1, "Should have exactly one worker with this LINE ID"


@pytest.mark.property
@settings(max_examples=100)
@given(
    new_line_id=line_id_strategy(),
    new_name=worker_name_strategy()
)
def test_get_or_create_worker_creates_when_not_exists(
    new_line_id: str,
    new_name: str
):
    """
    Property 29: LINE IDで従業員が識別される (Create when missing)
    
    For any LINE ID without an existing worker, get_or_create_worker
    should create a new worker and correctly identify them.
    
    This property ensures that:
    1. New workers are created when they don't exist
    2. The created worker can be identified by LINE ID
    
    Validates: Requirements 8.1, 8.5
    """
    with get_test_db_session() as test_db:
        auth_service = AuthService(test_db)
        
        # Verify worker doesn't exist
        existing = auth_service.get_worker_by_line_id(new_line_id)
        assume(existing is None)  # Skip if somehow exists
        
        # Call get_or_create
        created_worker, created = auth_service.get_or_create_worker(new_line_id, new_name)
        
        # Property: New worker should be created
        assert created is True, "Should create new worker when none exists"
        assert created_worker is not None
        assert created_worker.line_id == new_line_id
        assert created_worker.name == new_name
        assert created_worker.role == UserRole.WORKER
        
        # Verify the worker can be identified by LINE ID
        retrieved_worker = auth_service.get_worker_by_line_id(new_line_id)
        assert retrieved_worker is not None
        assert retrieved_worker.id == created_worker.id
