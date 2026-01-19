"""Main application entry point."""
from fastapi import FastAPI, Depends, Request, Header
from sqlalchemy.orm import Session
from app.config import settings
from app.database import init_db, get_db
from app.line_bot.webhook import handle_webhook
from app.scheduler import start_scheduler, stop_scheduler
from app.api.admin import router as admin_router

app = FastAPI(
    title="Shift Request Management System",
    description="LINE Bot and Web interface for managing shift requests",
    version="1.0.0",
    debug=settings.debug
)

# Include admin routes
app.include_router(admin_router)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    try:
        # Initialize database tables
        init_db()
        
        # Start the reminder scheduler
        start_scheduler()
    except Exception as e:
        print(f"Startup error: {e}")
        # Continue startup even if some services fail


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on application shutdown."""
    # Stop the reminder scheduler
    stop_scheduler()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Shift Request Management System"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/ping")
async def ping():
    """Simple ping endpoint for Railway health check."""
    return {"ping": "pong"}


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
