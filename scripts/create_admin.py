"""Script to create an admin user."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.auth_service import AuthService


def create_admin(username: str, password: str):
    """
    Create an admin user.
    
    Args:
        username: Admin username
        password: Admin password
    """
    db = SessionLocal()
    try:
        auth_service = AuthService(db)
        
        # Check if admin already exists
        from app.models.user import User, UserRole
        existing_admin = db.query(User).filter(
            User.name == username,
            User.role == UserRole.ADMIN
        ).first()
        
        if existing_admin:
            print(f"Admin user '{username}' already exists!")
            return
        
        # Create admin
        admin = auth_service.create_admin(username, password)
        print(f"Admin user created successfully!")
        print(f"Username: {admin.name}")
        print(f"ID: {admin.id}")
        
    except Exception as e:
        print(f"Error creating admin: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_admin.py <username> <password>")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    create_admin(username, password)
