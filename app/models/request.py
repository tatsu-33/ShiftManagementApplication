"""Request model for NG day applications."""
from sqlalchemy import Column, String, Date, Enum, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, date
import enum
from app.database import Base


class RequestStatus(str, enum.Enum):
    """Request status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Request(Base):
    """Request model representing NG day applications."""
    
    __tablename__ = "requests"
    
    id = Column(String(36), primary_key=True)
    worker_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    request_date = Column(Date, nullable=False, index=True)
    status = Column(Enum(RequestStatus), nullable=False, default=RequestStatus.PENDING, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Unique constraint: one request per worker per date
    __table_args__ = (
        UniqueConstraint('worker_id', 'request_date', name='uq_worker_request_date'),
    )
    
    # Relationships
    worker = relationship("User", back_populates="requests", foreign_keys=[worker_id])
    processor = relationship("User", foreign_keys=[processed_by])
    
    def __repr__(self) -> str:
        return f"<Request(id={self.id}, worker_id={self.worker_id}, date={self.request_date}, status={self.status})>"
    
    def validate(self) -> None:
        """Validate request data."""
        if not self.id:
            raise ValueError("Request ID is required")
        if not self.worker_id:
            raise ValueError("Worker ID is required")
        if not self.request_date:
            raise ValueError("Request date is required")
        if not self.status:
            raise ValueError("Status is required")
        if not isinstance(self.request_date, date):
            raise ValueError("Request date must be a date object")
        
        # Validate that processed requests have processor and processed_at
        if self.status in [RequestStatus.APPROVED, RequestStatus.REJECTED]:
            if not self.processed_by:
                raise ValueError("Processed requests must have a processor")
            if not self.processed_at:
                raise ValueError("Processed requests must have a processed_at timestamp")
