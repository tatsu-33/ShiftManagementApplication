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
    
    # Filter MySQL related variables
    mysql_vars = {k: v for k, v in all_env.items() if 'MYSQL' in k.upper()}
    
    return {
        "status": "ok", 
        "mysql_vars": mysql_vars,
        "total_env_count": len(all_env)
    }

@app.get("/db-connect-test")
async def db_connect_test():
    """Test basic database connection."""
    try:
        import pymysql
        
        # Get database connection info
        host = os.environ.get("MYSQLHOST")
        port = int(os.environ.get("MYSQLPORT", 3306))
        user = os.environ.get("MYSQLUSER")
        password = os.environ.get("MYSQLPASSWORD")
        database = os.environ.get("MYSQLDATABASE")
        
        if not all([host, user, password, database]):
            return {"status": "error", "message": "Missing database environment variables"}
        
        # Test connection
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        # Test query
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
        
        connection.close()
        
        return {
            "status": "success", 
            "message": "Database connection successful",
            "test_result": result
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Database connection failed: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )