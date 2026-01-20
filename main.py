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

@app.get("/create-admin-direct")
async def create_admin_direct():
    """Create admin user directly without using auth service."""
    try:
        import uuid
        from datetime import datetime
        from app.database import SessionLocal
        from app.models.user import User, UserRole
        from app.services.auth_service import AuthService
        
        db = SessionLocal()
        try:
            # Hash the password
            hashed_password = AuthService.hash_password("admin123")
            
            # Create admin user directly
            admin_user = User(
                id=str(uuid.uuid4()),
                line_id=hashed_password,  # Store hashed password in line_id for admins
                name="admin",
                role=UserRole.ADMIN,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Add to database
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            return {
                "status": "success",
                "message": "Admin user created successfully (direct method)",
                "admin_id": admin_user.id,
                "username": "admin",
                "password": "admin123"
            }
            
        finally:
            db.close()
            
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"Direct admin creation failed: {str(e)}",
            "traceback": traceback.format_exc()
        }

@app.get("/check-users")
async def check_users():
    """Check existing users in database."""
    try:
        from app.database import SessionLocal
        import pymysql
        
        # Direct SQL query to avoid enum issues
        host = os.environ.get("MYSQLHOST")
        port = int(os.environ.get("MYSQLPORT", 3306))
        user = os.environ.get("MYSQLUSER")
        password = os.environ.get("MYSQLPASSWORD")
        database = os.environ.get("MYSQLDATABASE")
        
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name, role FROM users")
            users = cursor.fetchall()
        
        connection.close()
        
        return {
            "status": "success",
            "users": users,
            "count": len(users)
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Check users failed: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )