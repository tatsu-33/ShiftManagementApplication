"""Database connection test version."""
from fastapi import FastAPI
import os

app = FastAPI(
    title="Shift Request Management System - DB Test",
    description="Testing database connection",
    version="1.0.0"
)

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Shift Request Management System - DB Test"}

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/ping")
async def ping():
    """Simple ping endpoint for Railway health check."""
    return {"ping": "pong"}

@app.get("/test")
async def test():
    """Test endpoint."""
    return {"status": "working", "message": "Application is running correctly"}

@app.get("/env-debug")
async def env_debug():
    """Debug all environment variables."""
    import os
    all_env = dict(os.environ)
    
    # Show first 10 environment variables for debugging
    sample_vars = dict(list(all_env.items())[:10])
    
    # Filter MySQL related variables (case insensitive)
    mysql_vars = {}
    for k, v in all_env.items():
        if 'mysql' in k.lower():
            mysql_vars[k] = v
    
    return {
        "status": "ok", 
        "mysql_vars": mysql_vars,
        "sample_vars": sample_vars,
        "total_env_count": len(all_env),
        "has_port": "PORT" in all_env,
        "port_value": all_env.get("PORT", "Not set")
    }

@app.get("/setup-db")
async def setup_database():
    """Setup database tables (run once after deployment)."""
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

@app.get("/reset-db")
async def reset_database():
    """Reset database by dropping and recreating all tables."""
    try:
        # Import required modules
        from app.database import engine, Base
        
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        
        # Recreate all tables
        Base.metadata.create_all(bind=engine)
        
        return {"status": "success", "message": "Database reset successfully"}
    except Exception as e:
        import traceback
        return {
            "status": "error", 
            "message": f"Database reset failed: {str(e)}",
            "traceback": traceback.format_exc()
        }

@app.get("/create-admin")
async def create_admin_user():
    """Create admin user (run once after database setup)."""
    try:
        # Import required modules
        import sys
        sys.path.insert(0, '/app')
        
        from app.services.auth_service import AuthService
        from app.database import SessionLocal
        from app.models.user import UserRole
        
        db = SessionLocal()
        try:
            auth_service = AuthService(db)
            
            # Create admin user directly without checking existing
            admin = auth_service.create_admin("admin", "admin123")
            
            return {
                "status": "success", 
                "message": "Admin user created successfully",
                "admin_id": admin.id,
                "username": "admin",
                "password": "admin123"
            }
        finally:
            db.close()
            
    except Exception as e:
        import traceback
        return {
            "status": "error", 
            "message": f"Admin creation failed: {str(e)}",
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )