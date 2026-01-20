"""Main application with database functionality only."""
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import os

# Import database functions
try:
    from app.database import get_db, init_db
    from app.config import settings
    DB_AVAILABLE = True
except ImportError as e:
    print(f"Database import failed: {e}")
    DB_AVAILABLE = False

app = FastAPI(
    title="Shift Request Management System",
    description="LINE Bot and Web interface for managing shift requests",
    version="1.0.0"
)

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

@app.get("/setup-db")
async def setup_database():
    """Setup database tables (run once after deployment)."""
    if not DB_AVAILABLE:
        return {"status": "error", "message": "Database not available"}
    
    try:
        # Import alembic functions
        from alembic.config import Config
        from alembic import command
        import os
        
        # Run alembic upgrade
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        
        return {"status": "success", "message": "Database tables created successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Database setup failed: {str(e)}"}

@app.get("/create-admin")
async def create_admin_user():
    """Create admin user (run once after database setup)."""
    if not DB_AVAILABLE:
        return {"status": "error", "message": "Database not available"}
    
    try:
        from app.services.auth_service import AuthService
        
        db = next(get_db())
        auth_service = AuthService(db)
        
        # Create admin user
        admin = auth_service.create_admin("admin", "admin123")
        
        return {
            "status": "success", 
            "message": "Admin user created successfully",
            "admin_id": admin.id
        }
    except Exception as e:
        return {"status": "error", "message": f"Admin creation failed: {str(e)}"}

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    print("Application starting up...")
    
    if DB_AVAILABLE:
        try:
            # Skip init_db() for now - will be done manually
            # init_db()
            print("Database available, skipping automatic table creation")
        except Exception as e:
            print(f"Database initialization failed: {e}")
    else:
        print("Database not available, skipping initialization")
    
    print("Application startup complete")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )