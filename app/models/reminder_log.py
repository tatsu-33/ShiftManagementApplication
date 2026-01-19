"""ReminderLog model for tracking reminder notifications."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ReminderLog(Base):
    """ReminderLog model for tracking reminder notifications sent to workers."""
    
    __tablename__ = "reminder_logs"
    
    id = Column(String(36), primary_key=True)
    worker_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    days_before_deadline = Column(Integer, nullable=False)
    target_month = Column(Integer, nullable=False)
    target_year = Column(Integer, nullable=False)
    
    # Relationships
    worker = relationship("User", back_populates="reminder_logs")
    
    def __repr__(self) -> str:
        return f"<ReminderLog(id={self.id}, worker_id={self.worker_id}, target={self.target_year}-{self.target_month})>"
    
    def validate(self) -> None:
        """Validate reminder log data."""
        if not self.id:
            raise ValueError("ReminderLog ID is required")
        if not self.worker_id:
            raise ValueError("Worker ID is required")
        if self.days_before_deadline is None:
            raise ValueError("Days before deadline is required")
        if not self.target_month:
            raise ValueError("Target month is required")
        if not self.target_year:
            raise ValueError("Target year is required")
        if not (1 <= self.target_month <= 12):
            raise ValueError("Target month must be between 1 and 12")
        if self.target_year < 2000:
            raise ValueError("Target year must be 2000 or later")
        if self.days_before_deadline < 0:
            raise ValueError("Days before deadline must be non-negative")
