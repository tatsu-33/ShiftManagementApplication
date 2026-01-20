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

@app.get("/create-admin-sql")
async def create_admin_sql():
    """Create admin user using pure SQL to avoid enum issues."""
    try:
        import uuid
        import pymysql
        from datetime import datetime
        from app.services.auth_service import AuthService
        
        # Get database connection info
        host = os.environ.get("MYSQLHOST")
        port = int(os.environ.get("MYSQLPORT", 3306))
        user = os.environ.get("MYSQLUSER")
        password = os.environ.get("MYSQLPASSWORD")
        database = os.environ.get("MYSQLDATABASE")
        
        # Hash the password
        hashed_password = AuthService.hash_password("admin123")
        
        # Generate UUID
        admin_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        try:
            with connection.cursor() as cursor:
                # Insert admin user with correct enum value
                sql = """
                INSERT INTO users (id, line_id, name, role, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    admin_id,
                    hashed_password,
                    "admin",
                    "ADMIN",  # Use the correct enum string value
                    now,
                    now
                ))
                connection.commit()
                
            return {
                "status": "success",
                "message": "Admin user created successfully (SQL method)",
                "admin_id": admin_id,
                "username": "admin",
                "password": "admin123"
            }
            
        finally:
            connection.close()
            
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"SQL admin creation failed: {str(e)}",
            "traceback": traceback.format_exc()
        }

@app.get("/check-schema")
async def check_schema():
    """Check the actual database schema for users table."""
    try:
        import pymysql
        
        # Get database connection info
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
        
        try:
            with connection.cursor() as cursor:
                # Show table structure
                cursor.execute("DESCRIBE users")
                columns = cursor.fetchall()
                
                # Show create table statement
                cursor.execute("SHOW CREATE TABLE users")
                create_table = cursor.fetchone()
                
            return {
                "status": "success",
                "columns": columns,
                "create_table": create_table[1] if create_table else None
            }
            
        finally:
            connection.close()
            
    except Exception as e:
        return {"status": "error", "message": f"Check schema failed: {str(e)}"}

@app.get("/fix-enum-schema")
async def fix_enum_schema():
    """Fix the enum schema to match application expectations."""
    try:
        import pymysql
        
        # Get database connection info
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
        
        try:
            with connection.cursor() as cursor:
                # Alter the table to use correct enum values
                sql = "ALTER TABLE users MODIFY COLUMN role ENUM('WORKER', 'ADMIN') NOT NULL"
                cursor.execute(sql)
                connection.commit()
                
                # Update existing admin user to use correct enum value
                sql = "UPDATE users SET role = 'ADMIN' WHERE name = 'admin'"
                cursor.execute(sql)
                connection.commit()
                
                # Verify the changes
                cursor.execute("DESCRIBE users")
                columns = cursor.fetchall()
                
                cursor.execute("SELECT id, name, role FROM users WHERE name = 'admin'")
                admin_user = cursor.fetchone()
                
            return {
                "status": "success",
                "message": "Enum schema fixed successfully",
                "role_column": [col for col in columns if col[0] == 'role'][0],
                "admin_user": admin_user
            }
            
        finally:
            connection.close()
            
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"Fix enum schema failed: {str(e)}",
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