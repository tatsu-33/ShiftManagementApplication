"""Authentication service for LINE ID and admin authentication."""
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import hashlib
import secrets
from app.models.user import User, UserRole


class AuthService:
    """Service for handling authentication operations."""
    
    def __init__(self, db: Session):
        """
        Initialize authentication service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_worker_by_line_id(self, line_id: str) -> Optional[User]:
        """
        Get worker by LINE ID.
        
        Args:
            line_id: LINE user ID
            
        Returns:
            User object if found, None otherwise
            
        Validates: Requirements 8.1
        """
        if not line_id:
            return None
        
        return self.db.query(User).filter(
            User.line_id == line_id,
            User.role == UserRole.WORKER
        ).first()
    
    def register_worker(self, line_id: str, name: str) -> User:
        """
        Register a new worker.
        
        Args:
            line_id: LINE user ID
            name: Worker name
            
        Returns:
            Newly created User object
            
        Raises:
            ValueError: If line_id or name is empty, or if LINE ID already exists
            
        Validates: Requirements 8.5
        """
        if not line_id:
            raise ValueError("LINE ID is required")
        if not name:
            raise ValueError("Name is required")
        
        # Check if LINE ID already exists
        existing_user = self.db.query(User).filter(User.line_id == line_id).first()
        if existing_user:
            raise ValueError(f"LINE ID {line_id} is already registered")
        
        # Create new worker
        new_worker = User(
            id=str(uuid.uuid4()),
            line_id=line_id,
            name=name,
            role=UserRole.WORKER
        )
        
        # Validate before saving
        new_worker.validate()
        
        # Save to database
        self.db.add(new_worker)
        self.db.commit()
        self.db.refresh(new_worker)
        
        return new_worker
    
    def get_or_create_worker(self, line_id: str, name: str) -> tuple[User, bool]:
        """
        Get existing worker or create new one if not exists.
        
        Args:
            line_id: LINE user ID
            name: Worker name (used only if creating new worker)
            
        Returns:
            Tuple of (User object, created flag)
            created flag is True if new worker was created, False if existing worker was returned
            
        Validates: Requirements 8.1, 8.5
        """
        # Try to get existing worker
        worker = self.get_worker_by_line_id(line_id)
        
        if worker:
            return worker, False
        
        # Create new worker if not found
        worker = self.register_worker(line_id, name)
        return worker, True
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using PBKDF2-HMAC-SHA256.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password in format: salt$hash
            
        Validates: Requirements 8.2
        """
        if not password:
            raise ValueError("Password is required")
        
        # Generate a random salt
        salt = secrets.token_hex(32)
        
        # Hash the password with the salt
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # iterations
        )
        
        # Return salt and hash combined
        return f"{salt}${pwd_hash.hex()}"
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hashed password.
        
        Args:
            password: Plain text password to verify
            hashed_password: Hashed password in format: salt$hash
            
        Returns:
            True if password matches, False otherwise
            
        Validates: Requirements 8.2
        """
        if not password or not hashed_password:
            return False
        
        try:
            # Split salt and hash
            salt, stored_hash = hashed_password.split('$')
            
            # Hash the provided password with the stored salt
            pwd_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000  # iterations
            )
            
            # Compare hashes
            return pwd_hash.hex() == stored_hash
        except (ValueError, AttributeError):
            return False
    
    def authenticate_admin(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate an administrator by username and password.
        
        Args:
            username: Admin username
            password: Admin password (plain text)
            
        Returns:
            User object if authentication successful, None otherwise
            
        Validates: Requirements 8.2, 8.3
        """
        if not username or not password:
            return None
        
        # Get admin user by username (stored in name field)
        admin = self.db.query(User).filter(
            User.name == username,
            User.role == UserRole.ADMIN
        ).first()
        
        if not admin:
            return None
        
        # Verify password (stored in line_id field for admins)
        if not self.verify_password(password, admin.line_id):
            return None
        
        return admin
    
    def get_admin_by_id(self, admin_id: str) -> Optional[User]:
        """
        Get administrator by ID.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            User object if found and is admin, None otherwise
            
        Validates: Requirements 8.3
        """
        if not admin_id:
            return None
        
        admin = self.db.query(User).filter(
            User.id == admin_id,
            User.role == UserRole.ADMIN
        ).first()
        
        return admin
    
    def verify_admin_permission(self, user_id: str) -> bool:
        """
        Verify that a user has admin permissions.
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if user is an admin, False otherwise
            
        Validates: Requirements 8.3, 8.4
        """
        if not user_id:
            return False
        
        admin = self.get_admin_by_id(user_id)
        return admin is not None
    
    def create_admin(self, username: str, password: str, admin_id: Optional[str] = None) -> User:
        """
        Create a new administrator account.
        
        Args:
            username: Admin username
            password: Admin password (plain text, will be hashed)
            admin_id: Optional admin ID, will be generated if not provided
            
        Returns:
            Newly created User object with admin role
            
        Raises:
            ValueError: If username or password is empty, or if username already exists
            
        Validates: Requirements 8.2, 8.3
        """
        if not username:
            raise ValueError("Username is required")
        if not password:
            raise ValueError("Password is required")
        
        # Check if username already exists
        existing_admin = self.db.query(User).filter(
            User.name == username,
            User.role == UserRole.ADMIN
        ).first()
        
        if existing_admin:
            raise ValueError(f"Admin username {username} already exists")
        
        # Hash the password
        hashed_password = self.hash_password(password)
        
        # Create new admin (store hashed password in line_id field)
        new_admin = User(
            id=admin_id or str(uuid.uuid4()),
            line_id=hashed_password,  # Store hashed password here for admins
            name=username,
            role=UserRole.ADMIN
        )
        
        # Save to database
        self.db.add(new_admin)
        self.db.commit()
        self.db.refresh(new_admin)
        
        return new_admin

