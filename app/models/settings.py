"""Settings model for application configuration."""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Settings(Base):
    """Settings model for storing application configuration."""
    
    __tablename__ = "settings"
    
    id = Column(String(36), primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(String(1000), nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    updater = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self) -> str:
        return f"<Settings(key={self.key}, value={self.value})>"
    
    def validate(self) -> None:
        """Validate settings data."""
        if not self.id:
            raise ValueError("Settings ID is required")
        if not self.key:
            raise ValueError("Key is required")
        if not self.value:
            raise ValueError("Value is required")
        if not self.updated_by:
            raise ValueError("Updated by is required")
