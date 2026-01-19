"""User model for workers and administrators."""
from sqlalchemy import Column, String, Enum, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    WORKER = "worker"
    ADMIN = "admin"


class User(Base):
    """User model representing workers and administrators."""
    
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    line_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.WORKER)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    requests = relationship("Request", back_populates="worker", foreign_keys="Request.worker_id")
    shifts = relationship("Shift", back_populates="worker", foreign_keys="Shift.worker_id")
    reminder_logs = relationship("ReminderLog", back_populates="worker")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, name={self.name}, role={self.role})>"
    
    def validate(self) -> None:
        """Validate user data."""
        if not self.id:
            raise ValueError("User ID is required")
        if not self.line_id:
            raise ValueError("LINE ID is required")
        if not self.name:
            raise ValueError("Name is required")
        if not self.role:
            raise ValueError("Role is required")
