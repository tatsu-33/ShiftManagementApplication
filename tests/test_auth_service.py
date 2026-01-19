"""Unit tests for authentication service."""
import pytest
from sqlalchemy.orm import Session
from app.services.auth_service import AuthService
from app.models.user import User, UserRole


class TestAuthService:
    """Test cases for AuthService."""
    
    def test_get_worker_by_line_id_returns_worker(self, test_db: Session):
        """Test getting worker by LINE ID returns correct worker."""
        # Create a test worker
        worker = User(
            id="test-worker-1",
            line_id="line123",
            name="Test Worker",
            role=UserRole.WORKER
        )
        test_db.add(worker)
        test_db.commit()
        
        # Test retrieval
        auth_service = AuthService(test_db)
        result = auth_service.get_worker_by_line_id("line123")
        
        assert result is not None
        assert result.id == "test-worker-1"
        assert result.line_id == "line123"
        assert result.name == "Test Worker"
        assert result.role == UserRole.WORKER
    
    def test_get_worker_by_line_id_returns_none_for_nonexistent(self, test_db: Session):
        """Test getting worker by non-existent LINE ID returns None."""
        auth_service = AuthService(test_db)
        result = auth_service.get_worker_by_line_id("nonexistent")
        
        assert result is None
    
    def test_get_worker_by_line_id_returns_none_for_empty_line_id(self, test_db: Session):
        """Test getting worker with empty LINE ID returns None."""
        auth_service = AuthService(test_db)
        result = auth_service.get_worker_by_line_id("")
        
        assert result is None
    
    def test_get_worker_by_line_id_ignores_admin_users(self, test_db: Session):
        """Test getting worker by LINE ID ignores admin users."""
        # Create an admin with a LINE ID
        admin = User(
            id="test-admin-1",
            line_id="admin123",
            name="Test Admin",
            role=UserRole.ADMIN
        )
        test_db.add(admin)
        test_db.commit()
        
        # Test retrieval - should return None since it's an admin
        auth_service = AuthService(test_db)
        result = auth_service.get_worker_by_line_id("admin123")
        
        assert result is None
    
    def test_register_worker_creates_new_worker(self, test_db: Session):
        """Test registering a new worker creates user in database."""
        auth_service = AuthService(test_db)
        worker = auth_service.register_worker("newline123", "New Worker")
        
        assert worker is not None
        assert worker.id is not None
        assert worker.line_id == "newline123"
        assert worker.name == "New Worker"
        assert worker.role == UserRole.WORKER
        
        # Verify it's in the database
        db_worker = test_db.query(User).filter(User.line_id == "newline123").first()
        assert db_worker is not None
        assert db_worker.id == worker.id
    
    def test_register_worker_raises_error_for_empty_line_id(self, test_db: Session):
        """Test registering worker with empty LINE ID raises ValueError."""
        auth_service = AuthService(test_db)
        
        with pytest.raises(ValueError, match="LINE ID is required"):
            auth_service.register_worker("", "Test Worker")
    
    def test_register_worker_raises_error_for_empty_name(self, test_db: Session):
        """Test registering worker with empty name raises ValueError."""
        auth_service = AuthService(test_db)
        
        with pytest.raises(ValueError, match="Name is required"):
            auth_service.register_worker("line123", "")
    
    def test_register_worker_raises_error_for_duplicate_line_id(self, test_db: Session):
        """Test registering worker with duplicate LINE ID raises ValueError."""
        # Create existing worker
        existing = User(
            id="existing-1",
            line_id="duplicate123",
            name="Existing Worker",
            role=UserRole.WORKER
        )
        test_db.add(existing)
        test_db.commit()
        
        # Try to register with same LINE ID
        auth_service = AuthService(test_db)
        
        with pytest.raises(ValueError, match="LINE ID duplicate123 is already registered"):
            auth_service.register_worker("duplicate123", "New Worker")
    
    def test_get_or_create_worker_returns_existing_worker(self, test_db: Session):
        """Test get_or_create_worker returns existing worker without creating new one."""
        # Create existing worker
        existing = User(
            id="existing-2",
            line_id="existing123",
            name="Existing Worker",
            role=UserRole.WORKER
        )
        test_db.add(existing)
        test_db.commit()
        
        # Get or create
        auth_service = AuthService(test_db)
        worker, created = auth_service.get_or_create_worker("existing123", "Different Name")
        
        assert created is False
        assert worker.id == "existing-2"
        assert worker.name == "Existing Worker"  # Name should not change
    
    def test_get_or_create_worker_creates_new_worker(self, test_db: Session):
        """Test get_or_create_worker creates new worker when not exists."""
        auth_service = AuthService(test_db)
        worker, created = auth_service.get_or_create_worker("newworker123", "New Worker")
        
        assert created is True
        assert worker is not None
        assert worker.line_id == "newworker123"
        assert worker.name == "New Worker"
        assert worker.role == UserRole.WORKER
        
        # Verify it's in the database
        db_worker = test_db.query(User).filter(User.line_id == "newworker123").first()
        assert db_worker is not None


class TestAdminAuthentication:
    """Test cases for admin authentication functionality."""
    
    def test_hash_password_creates_valid_hash(self):
        """Test password hashing creates a valid hash."""
        password = "test_password_123"
        hashed = AuthService.hash_password(password)
        
        assert hashed is not None
        assert '$' in hashed
        parts = hashed.split('$')
        assert len(parts) == 2
        assert len(parts[0]) == 64  # salt length
        assert len(parts[1]) == 64  # hash length
    
    def test_hash_password_creates_different_hashes(self):
        """Test password hashing creates different hashes for same password."""
        password = "test_password_123"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)
        
        assert hash1 != hash2  # Different salts should produce different hashes
    
    def test_hash_password_raises_error_for_empty_password(self):
        """Test password hashing raises error for empty password."""
        with pytest.raises(ValueError, match="Password is required"):
            AuthService.hash_password("")
    
    def test_verify_password_returns_true_for_correct_password(self):
        """Test password verification returns True for correct password."""
        password = "correct_password"
        hashed = AuthService.hash_password(password)
        
        assert AuthService.verify_password(password, hashed) is True
    
    def test_verify_password_returns_false_for_incorrect_password(self):
        """Test password verification returns False for incorrect password."""
        password = "correct_password"
        hashed = AuthService.hash_password(password)
        
        assert AuthService.verify_password("wrong_password", hashed) is False
    
    def test_verify_password_returns_false_for_empty_password(self):
        """Test password verification returns False for empty password."""
        hashed = AuthService.hash_password("test_password")
        
        assert AuthService.verify_password("", hashed) is False
    
    def test_verify_password_returns_false_for_empty_hash(self):
        """Test password verification returns False for empty hash."""
        assert AuthService.verify_password("test_password", "") is False
    
    def test_verify_password_returns_false_for_invalid_hash_format(self):
        """Test password verification returns False for invalid hash format."""
        assert AuthService.verify_password("test_password", "invalid_hash") is False
    
    def test_create_admin_creates_new_admin(self, test_db: Session):
        """Test creating a new admin account."""
        auth_service = AuthService(test_db)
        admin = auth_service.create_admin("admin_user", "admin_password")
        
        assert admin is not None
        assert admin.id is not None
        assert admin.name == "admin_user"
        assert admin.role == UserRole.ADMIN
        assert '$' in admin.line_id  # Password should be hashed
        
        # Verify it's in the database
        db_admin = test_db.query(User).filter(User.name == "admin_user").first()
        assert db_admin is not None
        assert db_admin.role == UserRole.ADMIN
    
    def test_create_admin_raises_error_for_empty_username(self, test_db: Session):
        """Test creating admin with empty username raises ValueError."""
        auth_service = AuthService(test_db)
        
        with pytest.raises(ValueError, match="Username is required"):
            auth_service.create_admin("", "password")
    
    def test_create_admin_raises_error_for_empty_password(self, test_db: Session):
        """Test creating admin with empty password raises ValueError."""
        auth_service = AuthService(test_db)
        
        with pytest.raises(ValueError, match="Password is required"):
            auth_service.create_admin("admin_user", "")
    
    def test_create_admin_raises_error_for_duplicate_username(self, test_db: Session):
        """Test creating admin with duplicate username raises ValueError."""
        auth_service = AuthService(test_db)
        
        # Create first admin
        auth_service.create_admin("duplicate_admin", "password1")
        
        # Try to create another with same username
        with pytest.raises(ValueError, match="Admin username duplicate_admin already exists"):
            auth_service.create_admin("duplicate_admin", "password2")
    
    def test_authenticate_admin_returns_admin_for_correct_credentials(self, test_db: Session):
        """Test admin authentication returns admin for correct credentials."""
        auth_service = AuthService(test_db)
        
        # Create admin
        created_admin = auth_service.create_admin("test_admin", "test_password")
        
        # Authenticate
        authenticated = auth_service.authenticate_admin("test_admin", "test_password")
        
        assert authenticated is not None
        assert authenticated.id == created_admin.id
        assert authenticated.name == "test_admin"
        assert authenticated.role == UserRole.ADMIN
    
    def test_authenticate_admin_returns_none_for_incorrect_password(self, test_db: Session):
        """Test admin authentication returns None for incorrect password."""
        auth_service = AuthService(test_db)
        
        # Create admin
        auth_service.create_admin("test_admin", "correct_password")
        
        # Try to authenticate with wrong password
        authenticated = auth_service.authenticate_admin("test_admin", "wrong_password")
        
        assert authenticated is None
    
    def test_authenticate_admin_returns_none_for_nonexistent_username(self, test_db: Session):
        """Test admin authentication returns None for non-existent username."""
        auth_service = AuthService(test_db)
        
        authenticated = auth_service.authenticate_admin("nonexistent", "password")
        
        assert authenticated is None
    
    def test_authenticate_admin_returns_none_for_empty_username(self, test_db: Session):
        """Test admin authentication returns None for empty username."""
        auth_service = AuthService(test_db)
        
        authenticated = auth_service.authenticate_admin("", "password")
        
        assert authenticated is None
    
    def test_authenticate_admin_returns_none_for_empty_password(self, test_db: Session):
        """Test admin authentication returns None for empty password."""
        auth_service = AuthService(test_db)
        
        authenticated = auth_service.authenticate_admin("admin", "")
        
        assert authenticated is None
    
    def test_get_admin_by_id_returns_admin(self, test_db: Session):
        """Test getting admin by ID returns correct admin."""
        auth_service = AuthService(test_db)
        
        # Create admin
        created_admin = auth_service.create_admin("test_admin", "password")
        
        # Get by ID
        admin = auth_service.get_admin_by_id(created_admin.id)
        
        assert admin is not None
        assert admin.id == created_admin.id
        assert admin.name == "test_admin"
        assert admin.role == UserRole.ADMIN
    
    def test_get_admin_by_id_returns_none_for_nonexistent_id(self, test_db: Session):
        """Test getting admin by non-existent ID returns None."""
        auth_service = AuthService(test_db)
        
        admin = auth_service.get_admin_by_id("nonexistent-id")
        
        assert admin is None
    
    def test_get_admin_by_id_returns_none_for_worker_id(self, test_db: Session):
        """Test getting admin by worker ID returns None."""
        auth_service = AuthService(test_db)
        
        # Create a worker
        worker = auth_service.register_worker("line123", "Test Worker")
        
        # Try to get as admin
        admin = auth_service.get_admin_by_id(worker.id)
        
        assert admin is None
    
    def test_get_admin_by_id_returns_none_for_empty_id(self, test_db: Session):
        """Test getting admin with empty ID returns None."""
        auth_service = AuthService(test_db)
        
        admin = auth_service.get_admin_by_id("")
        
        assert admin is None
    
    def test_verify_admin_permission_returns_true_for_admin(self, test_db: Session):
        """Test verifying admin permission returns True for admin user."""
        auth_service = AuthService(test_db)
        
        # Create admin
        admin = auth_service.create_admin("test_admin", "password")
        
        # Verify permission
        has_permission = auth_service.verify_admin_permission(admin.id)
        
        assert has_permission is True
    
    def test_verify_admin_permission_returns_false_for_worker(self, test_db: Session):
        """Test verifying admin permission returns False for worker."""
        auth_service = AuthService(test_db)
        
        # Create worker
        worker = auth_service.register_worker("line123", "Test Worker")
        
        # Verify permission
        has_permission = auth_service.verify_admin_permission(worker.id)
        
        assert has_permission is False
    
    def test_verify_admin_permission_returns_false_for_nonexistent_user(self, test_db: Session):
        """Test verifying admin permission returns False for non-existent user."""
        auth_service = AuthService(test_db)
        
        has_permission = auth_service.verify_admin_permission("nonexistent-id")
        
        assert has_permission is False
    
    def test_verify_admin_permission_returns_false_for_empty_id(self, test_db: Session):
        """Test verifying admin permission returns False for empty ID."""
        auth_service = AuthService(test_db)
        
        has_permission = auth_service.verify_admin_permission("")
        
        assert has_permission is False


class TestUnauthenticatedAccess:
    """
    Test cases for unauthenticated access scenarios.
    Validates: Requirements 8.2, 8.4
    """
    
    def test_authenticate_admin_fails_without_credentials(self, test_db: Session):
        """Test that authentication fails when no credentials are provided."""
        auth_service = AuthService(test_db)
        
        # Try to authenticate with None values
        result = auth_service.authenticate_admin(None, None)
        assert result is None
        
        # Try to authenticate with empty strings
        result = auth_service.authenticate_admin("", "")
        assert result is None
    
    def test_get_admin_by_id_fails_for_unauthenticated_user(self, test_db: Session):
        """Test that getting admin by ID fails for non-existent/unauthenticated user."""
        auth_service = AuthService(test_db)
        
        # Try to get admin with invalid ID (simulating unauthenticated access)
        result = auth_service.get_admin_by_id("invalid-session-id")
        assert result is None
        
        # Try to get admin with None ID
        result = auth_service.get_admin_by_id(None)
        assert result is None
    
    def test_verify_admin_permission_fails_for_unauthenticated_user(self, test_db: Session):
        """Test that permission verification fails for unauthenticated users."""
        auth_service = AuthService(test_db)
        
        # Try to verify permission with invalid user ID
        has_permission = auth_service.verify_admin_permission("unauthenticated-user-id")
        assert has_permission is False
        
        # Try to verify permission with None
        has_permission = auth_service.verify_admin_permission(None)
        assert has_permission is False
    
    def test_authenticate_admin_fails_with_invalid_credentials(self, test_db: Session):
        """Test that authentication fails with invalid username/password combinations."""
        auth_service = AuthService(test_db)
        
        # Create a valid admin
        auth_service.create_admin("valid_admin", "valid_password")
        
        # Try various invalid credential combinations
        assert auth_service.authenticate_admin("valid_admin", "wrong_password") is None
        assert auth_service.authenticate_admin("wrong_admin", "valid_password") is None
        assert auth_service.authenticate_admin("wrong_admin", "wrong_password") is None
    
    def test_authenticate_admin_fails_with_sql_injection_attempt(self, test_db: Session):
        """Test that authentication is protected against SQL injection attempts."""
        auth_service = AuthService(test_db)
        
        # Create a valid admin
        auth_service.create_admin("admin", "password")
        
        # Try SQL injection patterns
        sql_injection_attempts = [
            "admin' OR '1'='1",
            "admin'--",
            "admin' OR 1=1--",
            "'; DROP TABLE users--"
        ]
        
        for injection in sql_injection_attempts:
            result = auth_service.authenticate_admin(injection, "password")
            assert result is None, f"SQL injection attempt should fail: {injection}"


class TestInsufficientPermissions:
    """
    Test cases for insufficient permission scenarios.
    Validates: Requirements 8.3, 8.4
    """
    
    def test_worker_cannot_be_retrieved_as_admin(self, test_db: Session):
        """Test that worker users cannot be retrieved through admin functions."""
        auth_service = AuthService(test_db)
        
        # Create a worker
        worker = auth_service.register_worker("worker_line_123", "Worker User")
        
        # Try to get worker as admin
        admin = auth_service.get_admin_by_id(worker.id)
        assert admin is None
    
    def test_worker_does_not_have_admin_permission(self, test_db: Session):
        """Test that worker users do not have admin permissions."""
        auth_service = AuthService(test_db)
        
        # Create a worker
        worker = auth_service.register_worker("worker_line_456", "Worker User")
        
        # Verify worker does not have admin permission
        has_permission = auth_service.verify_admin_permission(worker.id)
        assert has_permission is False
    
    def test_worker_cannot_authenticate_as_admin(self, test_db: Session):
        """Test that worker users cannot authenticate through admin authentication."""
        auth_service = AuthService(test_db)
        
        # Create a worker
        worker = auth_service.register_worker("worker_line_789", "Worker User")
        
        # Try to authenticate worker as admin (using worker's name as username)
        result = auth_service.authenticate_admin("Worker User", "any_password")
        assert result is None
    
    def test_multiple_workers_all_lack_admin_permission(self, test_db: Session):
        """Test that multiple worker users all lack admin permissions."""
        auth_service = AuthService(test_db)
        
        # Create multiple workers
        worker1 = auth_service.register_worker("line_001", "Worker 1")
        worker2 = auth_service.register_worker("line_002", "Worker 2")
        worker3 = auth_service.register_worker("line_003", "Worker 3")
        
        # Verify none have admin permission
        assert auth_service.verify_admin_permission(worker1.id) is False
        assert auth_service.verify_admin_permission(worker2.id) is False
        assert auth_service.verify_admin_permission(worker3.id) is False
    
    def test_admin_permission_check_distinguishes_roles(self, test_db: Session):
        """Test that permission check correctly distinguishes between admin and worker roles."""
        auth_service = AuthService(test_db)
        
        # Create an admin and a worker
        admin = auth_service.create_admin("admin_user", "admin_pass")
        worker = auth_service.register_worker("worker_line", "Worker User")
        
        # Verify admin has permission
        assert auth_service.verify_admin_permission(admin.id) is True
        
        # Verify worker does not have permission
        assert auth_service.verify_admin_permission(worker.id) is False
    
    def test_deleted_or_invalid_user_has_no_admin_permission(self, test_db: Session):
        """Test that deleted or invalid user IDs have no admin permissions."""
        auth_service = AuthService(test_db)
        
        # Test with various invalid user IDs
        invalid_ids = [
            "deleted-user-id",
            "never-existed-id",
            "random-string-123",
            "00000000-0000-0000-0000-000000000000"
        ]
        
        for invalid_id in invalid_ids:
            has_permission = auth_service.verify_admin_permission(invalid_id)
            assert has_permission is False, f"Invalid user ID should not have permission: {invalid_id}"
    
    def test_worker_line_id_cannot_be_used_for_admin_auth(self, test_db: Session):
        """Test that worker LINE IDs cannot be used for admin authentication."""
        auth_service = AuthService(test_db)
        
        # Create a worker with a LINE ID
        worker = auth_service.register_worker("worker_line_special", "Special Worker")
        
        # Try to authenticate using worker's LINE ID
        result = auth_service.authenticate_admin("worker_line_special", "any_password")
        assert result is None
        
        # Try to authenticate using worker's name
        result = auth_service.authenticate_admin("Special Worker", "any_password")
        assert result is None

