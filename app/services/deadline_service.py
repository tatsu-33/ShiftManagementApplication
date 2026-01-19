"""Deadline management service."""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import uuid

from app.models.settings import Settings
from app.config import settings as app_settings
from app.exceptions import InvalidRangeError, MissingFieldError


class DeadlineService:
    """Service for managing application deadline settings."""
    
    DEADLINE_KEY = "application_deadline_day"
    
    def __init__(self, db: Session):
        """Initialize deadline service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_deadline_day(self) -> int:
        """Get the current deadline day setting.
        
        Returns:
            The deadline day (1-31), defaults to 10 if not set
        """
        try:
            setting = self.db.query(Settings).filter(
                Settings.key == self.DEADLINE_KEY
            ).first()
            
            if setting:
                return int(setting.value)
            
            # Return default if not found
            return app_settings.default_deadline_day
            
        except (ValueError, SQLAlchemyError):
            # Return default on any error
            return app_settings.default_deadline_day
    
    def set_deadline_day(self, day: int, admin_id: str) -> Settings:
        """Set or update the deadline day.
        
        Args:
            day: The deadline day (1-31)
            admin_id: ID of the admin making the change
            
        Returns:
            The updated Settings object
            
        Raises:
            InvalidRangeError: If day is not between 1 and 31
            MissingFieldError: If admin_id is empty
        """
        # Validate input
        if not 1 <= day <= 31:
            raise InvalidRangeError("deadline_day", day, 1, 31)
        
        if not admin_id:
            raise MissingFieldError("admin_id")
        
        try:
            # Check if setting exists
            setting = self.db.query(Settings).filter(
                Settings.key == self.DEADLINE_KEY
            ).first()
            
            if setting:
                # Update existing setting
                setting.value = str(day)
                setting.updated_at = datetime.utcnow()
                setting.updated_by = admin_id
            else:
                # Create new setting
                setting = Settings(
                    id=str(uuid.uuid4()),
                    key=self.DEADLINE_KEY,
                    value=str(day),
                    updated_at=datetime.utcnow(),
                    updated_by=admin_id
                )
                self.db.add(setting)
            
            self.db.commit()
            self.db.refresh(setting)
            
            return setting
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise RuntimeError(f"Failed to update deadline: {str(e)}")
    
    def get_deadline_history(self, limit: Optional[int] = None) -> list[Settings]:
        """Get the history of deadline changes.
        
        Args:
            limit: Maximum number of records to return (optional)
            
        Returns:
            List of Settings objects ordered by updated_at descending
        """
        try:
            query = self.db.query(Settings).filter(
                Settings.key == self.DEADLINE_KEY
            ).order_by(Settings.updated_at.desc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
            
        except SQLAlchemyError:
            return []
