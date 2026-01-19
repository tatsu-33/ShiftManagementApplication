"""Custom exceptions and error handling for the shift request management system.

This module provides user-friendly error messages for validation errors.
Validates: Requirements 1.4, 2.6
"""
from typing import Optional, Dict, Any
from datetime import date


class ValidationError(Exception):
    """Base class for validation errors with user-friendly messages."""
    
    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize validation error.
        
        Args:
            message: User-friendly error message
            error_code: Machine-readable error code
            details: Optional additional error details
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary format for API responses.
        
        Returns:
            Dictionary with error information
        """
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }


class DuplicateRequestError(ValidationError):
    """Error raised when attempting to create a duplicate request.
    
    Validates: Requirement 1.4
    """
    
    def __init__(self, worker_name: str, request_date: date):
        """
        Initialize duplicate request error.
        
        Args:
            worker_name: Name of the worker
            request_date: Date that was already requested
        """
        message = (
            f"{request_date.strftime('%Y年%m月%d日')}は既に申請済みです。\n"
            f"同じ日付を重複して申請することはできません。"
        )
        super().__init__(
            message=message,
            error_code="DUPLICATE_REQUEST",
            details={
                "worker_name": worker_name,
                "request_date": request_date.isoformat()
            }
        )


class DeadlineExceededError(ValidationError):
    """Error raised when attempting to submit a request after the deadline.
    
    Validates: Requirement 2.6
    """
    
    def __init__(self, deadline_day: int, current_date: date):
        """
        Initialize deadline exceeded error.
        
        Args:
            deadline_day: The deadline day of the month (1-31)
            current_date: Current date when the error occurred
        """
        message = (
            f"申請期限を過ぎています。\n"
            f"申請は毎月{deadline_day}日までに提出してください。\n"
            f"現在の日付: {current_date.strftime('%Y年%m月%d日')}"
        )
        super().__init__(
            message=message,
            error_code="DEADLINE_EXCEEDED",
            details={
                "deadline_day": deadline_day,
                "current_date": current_date.isoformat()
            }
        )


class InvalidDateError(ValidationError):
    """Error raised when the request date is invalid."""
    
    def __init__(self, request_date: date, current_date: date, reason: str):
        """
        Initialize invalid date error.
        
        Args:
            request_date: The invalid request date
            current_date: Current date
            reason: Reason why the date is invalid
        """
        message = (
            f"無効な日付です: {request_date.strftime('%Y年%m月%d日')}\n"
            f"{reason}"
        )
        super().__init__(
            message=message,
            error_code="INVALID_DATE",
            details={
                "request_date": request_date.isoformat(),
                "current_date": current_date.isoformat(),
                "reason": reason
            }
        )


class NotNextMonthError(ValidationError):
    """Error raised when the request date is not in the next month."""
    
    def __init__(self, request_date: date, current_date: date):
        """
        Initialize not next month error.
        
        Args:
            request_date: The request date
            current_date: Current date
        """
        next_month = current_date.replace(day=1)
        if current_date.month == 12:
            next_month = next_month.replace(year=current_date.year + 1, month=1)
        else:
            next_month = next_month.replace(month=current_date.month + 1)
        
        message = (
            f"申請できるのは翌月の日付のみです。\n"
            f"申請可能な月: {next_month.strftime('%Y年%m月')}\n"
            f"指定された日付: {request_date.strftime('%Y年%m月%d日')}"
        )
        super().__init__(
            message=message,
            error_code="NOT_NEXT_MONTH",
            details={
                "request_date": request_date.isoformat(),
                "current_date": current_date.isoformat(),
                "next_month": next_month.strftime('%Y-%m')
            }
        )


class MissingFieldError(ValidationError):
    """Error raised when a required field is missing."""
    
    def __init__(self, field_name: str):
        """
        Initialize missing field error.
        
        Args:
            field_name: Name of the missing field
        """
        field_names_ja = {
            "worker_id": "従業員ID",
            "request_date": "申請日",
            "admin_id": "管理者ID",
            "deadline_day": "締切日"
        }
        
        field_display = field_names_ja.get(field_name, field_name)
        message = f"{field_display}は必須項目です。"
        
        super().__init__(
            message=message,
            error_code="MISSING_FIELD",
            details={"field_name": field_name}
        )


class ResourceNotFoundError(ValidationError):
    """Error raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str):
        """
        Initialize resource not found error.
        
        Args:
            resource_type: Type of resource (e.g., "worker", "request", "admin")
            resource_id: ID of the resource
        """
        resource_types_ja = {
            "worker": "従業員",
            "request": "申請",
            "admin": "管理者",
            "shift": "シフト"
        }
        
        resource_display = resource_types_ja.get(resource_type, resource_type)
        message = f"{resource_display}が見つかりません。（ID: {resource_id}）"
        
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            details={
                "resource_type": resource_type,
                "resource_id": resource_id
            }
        )


class InvalidStatusTransitionError(ValidationError):
    """Error raised when attempting an invalid status transition."""
    
    def __init__(self, current_status: str, attempted_action: str):
        """
        Initialize invalid status transition error.
        
        Args:
            current_status: Current status of the request
            attempted_action: Action that was attempted (e.g., "approve", "reject")
        """
        status_names_ja = {
            "pending": "保留中",
            "approved": "承認済み",
            "rejected": "却下"
        }
        
        action_names_ja = {
            "approve": "承認",
            "reject": "却下"
        }
        
        current_status_display = status_names_ja.get(current_status, current_status)
        action_display = action_names_ja.get(attempted_action, attempted_action)
        
        message = (
            f"この申請は既に処理済みです。\n"
            f"現在のステータス: {current_status_display}\n"
            f"保留中の申請のみ{action_display}できます。"
        )
        
        super().__init__(
            message=message,
            error_code="INVALID_STATUS_TRANSITION",
            details={
                "current_status": current_status,
                "attempted_action": attempted_action
            }
        )


class InvalidRangeError(ValidationError):
    """Error raised when a value is outside the valid range."""
    
    def __init__(self, field_name: str, value: Any, min_value: Any, max_value: Any):
        """
        Initialize invalid range error.
        
        Args:
            field_name: Name of the field
            value: The invalid value
            min_value: Minimum valid value
            max_value: Maximum valid value
        """
        field_names_ja = {
            "deadline_day": "締切日"
        }
        
        field_display = field_names_ja.get(field_name, field_name)
        message = (
            f"{field_display}は{min_value}から{max_value}の範囲で指定してください。\n"
            f"指定された値: {value}"
        )
        
        super().__init__(
            message=message,
            error_code="INVALID_RANGE",
            details={
                "field_name": field_name,
                "value": value,
                "min_value": min_value,
                "max_value": max_value
            }
        )


def format_error_for_line(error: ValidationError) -> str:
    """
    Format validation error for LINE message display.
    
    Args:
        error: Validation error to format
        
    Returns:
        Formatted error message suitable for LINE
    """
    # For LINE, we just return the user-friendly message
    # with an emoji prefix for visual clarity
    return f"❌ {error.message}"


def format_error_for_api(error: ValidationError) -> Dict[str, Any]:
    """
    Format validation error for API response.
    
    Args:
        error: Validation error to format
        
    Returns:
        Dictionary suitable for JSON API response
    """
    return error.to_dict()
