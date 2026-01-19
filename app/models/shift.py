"""Shift model for work schedules."""
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.database import Base


class Shift(Base):
    """Shift model representing work schedules."""
    
    __tablename__ = "shifts"
    
    id = Column(String(36), primary_key=True)
    shift_date = Column(Date, nullable=False, index=True)
    worker_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Unique constraint: one shift per worker per date
    __table_args__ = (
        UniqueConstraint('shift_date', 'worker_id', name='uq_shift_date_worker'),
    )
    
    # Relationships
    worker = relationship("User", back_populates="shifts", foreign_keys=[worker_id])
    updater = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self) -> str:
        return f"<Shift(id={self.id}, date={self.shift_date}, worker_id={self.worker_id})>"
    
    def validate(self) -> None:
        """Validate shift data."""
        if not self.id:
            raise ValueError("Shift ID is required")
        if not self.shift_date:
            raise ValueError("Shift date is required")
        if not self.worker_id:
            raise ValueError("Worker ID is required")
        if not self.updated_by:
            raise ValueError("Updated by is required")
        if not isinstance(self.shift_date, date):
            raise ValueError("Shift date must be a date object")
