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
    
    try:
        # Initialize database
        init_db()
        print("Database initialized successfully")
        
        # Start the reminder scheduler
        start_scheduler()
        print("Scheduler started successfully")
        
    except Exception as e:
        print(f"Startup error: {e}")
        # Continue without failing - Railway will handle retries
    
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


@app.post("/admin/debug/init-db")
async def debug_init_db():
    """Debug endpoint to force database initialization."""
    try:
        from app.database import init_db
        init_db()
        return {
            "status": "success",
            "message": "Database initialized successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database initialization failed: {str(e)}"
        }


@app.get("/admin/debug/tables")
async def debug_tables(db: Session = Depends(get_db)):
    """Debug endpoint to check database tables."""
    from sqlalchemy import text
    
    try:
        # Check if shifts table exists
        result = db.execute(text("SHOW TABLES")).fetchall()
        tables = [row[0] for row in result]
        
        # Check shifts table structure if it exists
        shifts_info = None
        if 'shifts' in tables:
            shifts_result = db.execute(text("DESCRIBE shifts")).fetchall()
            shifts_info = [
                {
                    "field": row[0],
                    "type": row[1],
                    "null": row[2],
                    "key": row[3],
                    "default": row[4],
                    "extra": row[5]
                } for row in shifts_result
            ]
        
        return {
            "status": "ok",
            "tables": tables,
            "shifts_table_exists": 'shifts' in tables,
            "shifts_table_structure": shifts_info
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to check tables: {str(e)}"
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
    return await handle_webhook(request, db, x_line_signature)


@app.get("/admin/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    admin: User = Depends(get_current_admin)
):
    """
    Display admin users management page.
    
    Args:
        request: FastAPI request object
        admin: Current authenticated admin user
        
    Returns:
        HTML users management page
    """
    return templates.TemplateResponse(
        "admin/users.html",
        {"request": request, "admin": admin}
    )


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
