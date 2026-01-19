"""Admin web interface routes."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Form, Query, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
import secrets
from app.database import get_db
from app.services.auth_service import AuthService
from app.services.request_service import RequestService
from app.services.notification_service import NotificationService
from app.services.shift_service import ShiftService
from app.services.deadline_service import DeadlineService
from app.models.user import User, UserRole
from app.models.request import RequestStatus
from app.exceptions import ValidationError, format_error_for_api


# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Session storage (in-memory for now, should use Redis in production)
sessions = {}


def get_session_id(request: Request) -> Optional[str]:
    """
    Get session ID from cookie.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Session ID if exists, None otherwise
    """
    return request.cookies.get("session_id")


def get_current_admin(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated admin user.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        Admin user object
        
    Raises:
        HTTPException: If not authenticated or not admin
        
    Validates: Requirements 8.2, 8.3, 8.4
    """
    session_id = get_session_id(request)
    
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    admin_id = sessions[session_id]
    auth_service = AuthService(db)
    admin = auth_service.get_admin_by_id(admin_id)
    
    if not admin:
        # Invalid session, remove it
        if session_id in sessions:
            del sessions[session_id]
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return admin


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Display admin login page.
    
    Args:
        request: FastAPI request object
        
    Returns:
        HTML login form
        
    Validates: Requirements 8.2
    """
    # Check if already logged in
    session_id = get_session_id(request)
    if session_id and session_id in sessions:
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request, "error": None}
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Process admin login.
    
    Args:
        request: FastAPI request object
        username: Admin username
        password: Admin password
        db: Database session
        
    Returns:
        Redirect to dashboard on success, login page with error on failure
        
    Validates: Requirements 8.2, 8.3
    """
    auth_service = AuthService(db)
    admin = auth_service.authenticate_admin(username, password)
    
    if not admin:
        # Return to login page with error
        return templates.TemplateResponse(
            "admin/login.html",
            {
                "request": request,
                "error": "Invalid username or password"
            },
            status_code=401
        )
    
    # Create session
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = admin.id
    
    # Create response with redirect
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=86400  # 24 hours
    )
    
    return response


@router.post("/logout")
async def logout(request: Request):
    """
    Logout admin user.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Redirect to login page
        
    Validates: Requirements 8.2
    """
    session_id = get_session_id(request)
    
    if session_id and session_id in sessions:
        del sessions[session_id]
    
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("session_id")
    
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    admin: User = Depends(get_current_admin)
):
    """
    Display admin dashboard.
    
    Args:
        request: FastAPI request object
        admin: Current authenticated admin user
        
    Returns:
        HTML dashboard page
        
    Validates: Requirements 8.2, 8.3, 8.4
    """
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {"request": request, "admin": admin}
    )


@router.get("/requests", response_class=HTMLResponse)
async def requests_page(
    request: Request,
    admin: User = Depends(get_current_admin)
):
    """
    Display admin requests management page.
    
    Args:
        request: FastAPI request object
        admin: Current authenticated admin user
        
    Returns:
        HTML requests management page
        
    Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5
    """
    return templates.TemplateResponse(
        "admin/requests.html",
        {"request": request, "admin": admin}
    )


@router.get("/api/requests")
async def get_requests(
    status: Optional[str] = Query(None),
    worker_name: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all requests with optional filtering.
    
    Args:
        status: Optional status filter (pending, approved, rejected)
        worker_name: Optional worker name search
        month: Optional month filter (1-12)
        year: Optional year filter
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON list of requests with worker and processor information
        
    Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5
    """
    request_service = RequestService(db)
    
    # Convert status string to enum if provided
    status_enum = None
    if status:
        try:
            status_enum = RequestStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Get requests with filters
    requests = request_service.get_all_requests(
        status=status_enum,
        worker_name=worker_name,
        month=month,
        year=year
    )
    
    # Format response with worker and processor names
    result = []
    for req in requests:
        result.append({
            "id": req.id,
            "worker_id": req.worker_id,
            "worker_name": req.worker.name,
            "request_date": req.request_date.isoformat(),
            "status": req.status.value,
            "created_at": req.created_at.isoformat(),
            "processed_at": req.processed_at.isoformat() if req.processed_at else None,
            "processed_by": req.processed_by,
            "processor_name": req.processor.name if req.processor else None
        })
    
    return JSONResponse(content=result)


@router.post("/api/requests/{request_id}/approve")
async def approve_request(
    request_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Approve a pending request.
    
    Args:
        request_id: ID of the request to approve
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON response with updated request
        
    Raises:
        HTTPException: If request not found or cannot be approved
        
    Validates: Requirements 5.1, 5.2
    """
    request_service = RequestService(db)
    notification_service = NotificationService()
    
    try:
        # Approve the request
        updated_request = request_service.approve_request(request_id, admin.id)
        
        # Send notification to worker
        try:
            # Get worker's LINE ID
            worker = db.query(User).filter(User.id == updated_request.worker_id).first()
            if worker and worker.line_id:
                notification_service.send_approval_notification(
                    worker.line_id,
                    updated_request.request_date.strftime('%Y年%m月%d日')
                )
        except Exception as e:
            # Log notification error but don't fail the approval
            print(f"Failed to send approval notification: {e}")
        
        return JSONResponse(content={
            "id": updated_request.id,
            "status": updated_request.status.value,
            "processed_at": updated_request.processed_at.isoformat(),
            "processed_by": updated_request.processed_by
        })
    except ValidationError as e:
        # Return user-friendly error message
        return JSONResponse(
            status_code=400,
            content=format_error_for_api(e)
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "システムエラーが発生しました。",
                    "details": {}
                }
            }
        )


@router.post("/api/requests/{request_id}/reject")
async def reject_request(
    request_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Reject a pending request.
    
    Args:
        request_id: ID of the request to reject
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON response with updated request
        
    Raises:
        HTTPException: If request not found or cannot be rejected
        
    Validates: Requirements 5.1, 5.2
    """
    request_service = RequestService(db)
    notification_service = NotificationService()
    
    try:
        # Reject the request
        updated_request = request_service.reject_request(request_id, admin.id)
        
        # Send notification to worker
        try:
            # Get worker's LINE ID
            worker = db.query(User).filter(User.id == updated_request.worker_id).first()
            if worker and worker.line_id:
                notification_service.send_rejection_notification(
                    worker.line_id,
                    updated_request.request_date.strftime('%Y年%m月%d日')
                )
        except Exception as e:
            # Log notification error but don't fail the rejection
            print(f"Failed to send rejection notification: {e}")
        
        return JSONResponse(content={
            "id": updated_request.id,
            "status": updated_request.status.value,
            "processed_at": updated_request.processed_at.isoformat(),
            "processed_by": updated_request.processed_by
        })
    except ValidationError as e:
        # Return user-friendly error message
        return JSONResponse(
            status_code=400,
            content=format_error_for_api(e)
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "システムエラーが発生しました。",
                    "details": {}
                }
            }
        )


@router.get("/shifts", response_class=HTMLResponse)
async def shifts_page(
    request: Request,
    admin: User = Depends(get_current_admin)
):
    """
    Display admin shift management page.
    
    Args:
        request: FastAPI request object
        admin: Current authenticated admin user
        
    Returns:
        HTML shift management page
        
    Validates: Requirements 6.1, 6.2, 6.3
    """
    return templates.TemplateResponse(
        "admin/shifts.html",
        {"request": request, "admin": admin}
    )


@router.get("/api/workers")
async def get_workers(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all workers.
    
    Args:
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON list of workers
        
    Validates: Requirements 6.1, 7.1
    """
    workers = db.query(User).filter(User.role == UserRole.WORKER).all()
    
    result = []
    for worker in workers:
        result.append({
            "id": worker.id,
            "name": worker.name,
            "line_id": worker.line_id
        })
    
    return JSONResponse(content=result)


@router.get("/api/shifts")
async def get_shifts(
    year: int = Query(...),
    month: int = Query(...),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all shifts for a specific month.
    
    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON list of shifts with worker information
        
    Validates: Requirements 6.1, 6.2
    """
    shift_service = ShiftService(db)
    
    try:
        shifts = shift_service.get_shifts_by_month(year, month)
        
        # Format response with worker names
        result = []
        for shift in shifts:
            result.append({
                "id": shift.id,
                "shift_date": shift.shift_date.isoformat(),
                "worker_id": shift.worker_id,
                "worker_name": shift.worker.name,
                "updated_at": shift.updated_at.isoformat(),
                "updated_by": shift.updated_by
            })
        
        return JSONResponse(content=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/ng-days")
async def get_ng_days(
    year: int = Query(...),
    month: int = Query(...),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get approved NG days for a specific month.
    
    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON object mapping dates to lists of worker IDs with approved NG days
        
    Validates: Requirements 6.2, 6.4
    """
    shift_service = ShiftService(db)
    
    try:
        ng_days = shift_service.get_approved_ng_days(year=year, month=month)
        
        # Convert date keys to ISO format strings
        result = {}
        for date_key, worker_ids in ng_days.items():
            result[date_key.isoformat()] = worker_ids
        
        return JSONResponse(content=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/shifts/{shift_date}")
async def update_shift(
    shift_date: date,
    worker_ids: List[str] = Body(..., embed=True),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update shift assignments for a specific date.
    
    Args:
        shift_date: Date of the shift to update
        worker_ids: List of worker IDs to assign to this shift
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON response with updated shifts and warnings
        
    Raises:
        HTTPException: If validation fails
        
    Validates: Requirements 7.1, 7.2, 7.3
    """
    shift_service = ShiftService(db)
    notification_service = NotificationService()
    
    try:
        # Update the shift
        result = shift_service.update_shift(shift_date, worker_ids, admin.id)
        
        # Send notifications to affected workers
        try:
            for worker_id in result['changes']['added']:
                worker = db.query(User).filter(User.id == worker_id).first()
                if worker and worker.line_id:
                    notification_service.send_shift_notification(
                        worker.line_id,
                        shift_date.strftime('%Y年%m月%d日')
                    )
        except Exception as e:
            # Log notification error but don't fail the update
            print(f"Failed to send shift notification: {e}")
        
        # Format response
        shifts_data = []
        for shift in result['shifts']:
            shifts_data.append({
                "id": shift.id,
                "shift_date": shift.shift_date.isoformat(),
                "worker_id": shift.worker_id,
                "worker_name": shift.worker.name,
                "updated_at": shift.updated_at.isoformat(),
                "updated_by": shift.updated_by
            })
        
        return JSONResponse(content={
            "shifts": shifts_data,
            "warnings": result['warnings'],
            "changes": result['changes']
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    admin: User = Depends(get_current_admin)
):
    """
    Display admin settings page.
    
    Args:
        request: FastAPI request object
        admin: Current authenticated admin user
        
    Returns:
        HTML settings page
        
    Validates: Requirements 2.2
    """
    return templates.TemplateResponse(
        "admin/settings.html",
        {"request": request, "admin": admin}
    )


@router.get("/api/settings/deadline")
async def get_deadline_setting(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get current deadline day setting.
    
    Args:
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON response with deadline_day
        
    Validates: Requirements 2.2
    """
    deadline_service = DeadlineService(db)
    deadline_day = deadline_service.get_deadline_day()
    
    return JSONResponse(content={"deadline_day": deadline_day})


@router.put("/api/settings/deadline")
async def update_deadline_setting(
    deadline_day: int = Body(..., embed=True),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update deadline day setting.
    
    Args:
        deadline_day: New deadline day (1-31)
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON response with updated setting
        
    Raises:
        HTTPException: If validation fails
        
    Validates: Requirements 2.3, 2.4
    """
    deadline_service = DeadlineService(db)
    
    try:
        setting = deadline_service.set_deadline_day(deadline_day, admin.id)
        
        return JSONResponse(content={
            "deadline_day": int(setting.value),
            "updated_at": setting.updated_at.isoformat(),
            "updated_by": setting.updated_by
        })
    except ValidationError as e:
        # Return user-friendly error message
        return JSONResponse(
            status_code=400,
            content=format_error_for_api(e)
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "システムエラーが発生しました。",
                    "details": {}
                }
            }
        )


@router.get("/api/settings/deadline/history")
async def get_deadline_history(
    limit: Optional[int] = Query(10),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get deadline change history.
    
    Args:
        limit: Maximum number of records to return (default: 10)
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON list of deadline changes with updater information
        
    Validates: Requirements 2.4
    """
    deadline_service = DeadlineService(db)
    history = deadline_service.get_deadline_history(limit=limit)
    
    # Format response with updater names
    result = []
    for setting in history:
        result.append({
            "id": setting.id,
            "value": setting.value,
            "updated_at": setting.updated_at.isoformat(),
            "updated_by": setting.updated_by,
            "updater_name": setting.updater.name if setting.updater else "Unknown"
        })
    
    return JSONResponse(content=result)
