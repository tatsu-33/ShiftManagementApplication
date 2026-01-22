"""Main application entry point."""
from fastapi import FastAPI, Depends, Request, Header, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.config import settings
from app.database import init_db, get_db
from app.line_bot.webhook import handle_webhook
from app.scheduler import start_scheduler, stop_scheduler
from app.api.admin import router as admin_router
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

# Import admin authentication function
from app.api.admin import get_current_admin

app = FastAPI(
    title="Shift Request Management System",
    description="LINE Bot and Web interface for managing shift requests",
    version="1.0.0",
    debug=settings.debug
)

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include admin routes (only if database is available)
try:
    app.include_router(admin_router)
    print("Admin routes included successfully")
except Exception as e:
    print(f"Failed to include admin routes: {e}")
    # Continue without admin routes


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    print("Application starting up...")
    
    # Skip database and scheduler initialization for now
    # This will be done manually after deployment
    print("Skipping database initialization during startup")
    print("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on application shutdown."""
    # Stop the reminder scheduler
    stop_scheduler()


@app.get("/")
async def root():
    """Redirect to admin login."""
    return RedirectResponse(url="/admin/login", status_code=302)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/ping")
async def ping():
    """Simple ping endpoint for Railway health check."""
    return {"ping": "pong"}


@app.get("/admin/check-schema")
async def check_schema(db: Session = Depends(get_db)):
    """Check database schema for enum definitions."""
    from sqlalchemy import text
    
    try:
        # Check table schema for requests table
        schema_result = db.execute(text("DESCRIBE requests")).fetchall()
        
        # Check enum values defined in the schema
        enum_result = db.execute(text("""
            SELECT COLUMN_NAME, COLUMN_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'requests' 
            AND COLUMN_NAME = 'status'
        """)).fetchall()
        
        # Check current data
        data_result = db.execute(text("""
            SELECT id, status, HEX(status) as status_hex
            FROM requests 
            WHERE id = '8167ce09-5be2-48c8-bbd3-d4b24077e3aa'
        """)).fetchall()
        
        return {
            "status": "ok",
            "table_schema": [
                {
                    "field": row[0],
                    "type": row[1],
                    "null": row[2],
                    "key": row[3],
                    "default": row[4],
                    "extra": row[5]
                } for row in schema_result
            ],
            "enum_definition": [
                {
                    "column_name": row[0],
                    "column_type": row[1]
                } for row in enum_result
            ],
            "current_data": [
                {
                    "id": row[0],
                    "status": row[1],
                    "status_hex": row[2]
                } for row in data_result
            ]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to check schema: {str(e)}"
        }


@app.get("/admin/delete-problematic-record")
async def delete_problematic_record(db: Session = Depends(get_db)):
    """Delete the problematic record as a last resort."""
    from sqlalchemy import text
    
    try:
        # Delete the problematic record
        result = db.execute(text("""
            DELETE FROM requests 
            WHERE id = '8167ce09-5be2-48c8-bbd3-d4b24077e3aa'
        """))
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Problematic record deleted",
            "records_deleted": result.rowcount
        }
        
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "message": f"Failed to delete record: {str(e)}"
        }


@app.get("/admin/check-enum-values")
async def check_enum_values(db: Session = Depends(get_db)):
    """Check current enum values in database."""
    from sqlalchemy import text
    
    try:
        # Check request status values
        result1 = db.execute(text("SELECT DISTINCT status FROM requests")).fetchall()
        
        # Check user role values
        result2 = db.execute(text("SELECT DISTINCT role FROM users")).fetchall()
        
        # Check specific user's requests
        result3 = db.execute(text("""
            SELECT r.id, r.status, r.request_date, u.name 
            FROM requests r 
            JOIN users u ON r.worker_id = u.id 
            WHERE u.line_id = 'Ufc7676629c0bd73b842ef540c297f117'
        """)).fetchall()
        
        return {
            "status": "ok",
            "request_statuses": [row[0] for row in result1],
            "user_roles": [row[0] for row in result2],
            "user_requests": [
                {
                    "id": row[0],
                    "status": row[1], 
                    "request_date": str(row[2]),
                    "user_name": row[3]
                } for row in result3
            ]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to check enum values: {str(e)}"
        }


@app.get("/admin/fix-enum-values")
async def fix_enum_values(db: Session = Depends(get_db)):
    """Fix enum values in database (convert lowercase to uppercase)."""
    from sqlalchemy import text
    
    try:
        # Fix request status enum values
        result = db.execute(text("""
            UPDATE requests 
            SET status = CASE 
                WHEN status = 'pending' THEN 'PENDING'
                WHEN status = 'approved' THEN 'APPROVED' 
                WHEN status = 'rejected' THEN 'REJECTED'
                ELSE status
            END
            WHERE status IN ('pending', 'approved', 'rejected')
        """))
        
        # Fix user role enum values
        result2 = db.execute(text("""
            UPDATE users 
            SET role = CASE 
                WHEN role = 'worker' THEN 'WORKER'
                WHEN role = 'admin' THEN 'ADMIN'
                ELSE role
            END
            WHERE role IN ('worker', 'admin')
        """))
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Enum values fixed successfully",
            "requests_updated": result.rowcount,
            "users_updated": result2.rowcount
        }
        
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "message": f"Failed to fix enum values: {str(e)}"
        }


@app.get("/test/deadline-config")
async def test_deadline_config(db: Session = Depends(get_db)):
    """Test deadline configuration (no auth required)."""
    from app.services.deadline_service import DeadlineService
    
    try:
        deadline_service = DeadlineService(db)
        deadline_day = deadline_service.get_deadline_day()
        
        # Also check if there's a setting in the database
        from app.models.settings import Settings
        setting = db.query(Settings).filter(
            Settings.key == "application_deadline_day"
        ).first()
        
        return {
            "status": "ok",
            "deadline_config": {
                "current_deadline_day": deadline_day,
                "setting_exists": setting is not None,
                "setting_value": setting.value if setting else None,
                "setting_updated_at": setting.updated_at.isoformat() if setting else None
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/webhook/line")
async def line_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_line_signature: str = Header(None)
):
    """
    LINE Bot webhook endpoint.
    
    This endpoint receives events from LINE Platform and processes them.
    
    Args:
        request: FastAPI request object
        db: Database session
        x_line_signature: LINE signature header for verification
        
    Returns:
        Success response
        
    Validates: Requirements 1.1
    """
    # Log the incoming request for debugging
    body = await request.body()
    print(f"LINE webhook received: {body.decode('utf-8')}")
    print(f"X-Line-Signature: {x_line_signature}")
    
    return await handle_webhook(request, db, x_line_signature)


@app.get("/test-template")
async def test_template():
    """Simple test endpoint without authentication"""
    return HTMLResponse(content="<h1>Simple HTML Test - This should work</h1>")


@app.get("/admin/users", response_class=HTMLResponse)
async def users_page(
    request: Request
    # admin: User = Depends(get_current_admin)  # 一時的に認証を無効化
):
    """
    Display admin users management page.
    
    Args:
        request: FastAPI request object
        admin: Current authenticated admin user
        
    Returns:
        HTML users management page
    """
    print(f"DEBUG: users_page called without auth")
    print(f"DEBUG: Template directory: app/templates")
    
    try:
        response = templates.TemplateResponse(
            "admin/users.html",
            {"request": request, "admin": None}
        )
        print("DEBUG: Template response created successfully")
        return response
    except Exception as e:
        print(f"DEBUG: Template error: {e}")
        return HTMLResponse(content=f"<h1>Template Error: {e}</h1>", status_code=500)


@app.get("/admin/api/users")
async def get_all_users(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all users (workers and admins).
    
    Args:
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON list of all users
    """
    users = db.query(User).all()
    
    result = []
    for user in users:
        result.append({
            "id": user.id,
            "name": user.name,
            "line_id": user.line_id if user.role == UserRole.WORKER else "管理者",
            "role": user.role.value,
            "created_at": user.created_at.isoformat()
        })
    
    return JSONResponse(content=result)


@app.post("/admin/api/users")
async def create_user(
    name: str = Form(...),
    line_id: str = Form(...),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new worker user.
    
    Args:
        name: Worker name
        line_id: LINE user ID
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON response with created user info
    """
    try:
        auth_service = AuthService(db)
        
        # Register new worker
        worker = auth_service.register_worker(line_id, name)
        
        return JSONResponse(content={
            "status": "success",
            "message": "ユーザーが正常に作成されました",
            "user": {
                "id": worker.id,
                "name": worker.name,
                "line_id": worker.line_id,
                "role": worker.role.value,
                "created_at": worker.created_at.isoformat()
            }
        })
        
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": str(e)
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"ユーザー作成に失敗しました: {str(e)}"
            }
        )


@app.delete("/admin/api/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a user.
    
    Args:
        user_id: ID of the user to delete
        admin: Current authenticated admin user
        db: Database session
        
    Returns:
        JSON response
    """
    try:
        # Find the user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": "ユーザーが見つかりません"
                }
            )
        
        # Don't allow deleting admin users
        if user.role == UserRole.ADMIN:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "管理者ユーザーは削除できません"
                }
            )
        
        # Delete the user
        db.delete(user)
        db.commit()
        
        return JSONResponse(content={
            "status": "success",
            "message": "ユーザーが正常に削除されました"
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"ユーザー削除に失敗しました: {str(e)}"
            }
        )


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug
    )
