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

@app.get("/db-test")
async def db_test(db: Session = Depends(get_db) if DB_AVAILABLE else None):
    """Test database connection."""
    if not DB_AVAILABLE:
        return {"status": "error", "message": "Database not available"}
    
    try:
        # Simple database test
        db.execute("SELECT 1")
        return {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}

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