"""Application configuration settings."""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    
    # LINE Bot Configuration
    line_channel_access_token: str
    line_channel_secret: str
    line_api_max_retries: int = 3
    line_api_retry_delay: int = 1
    line_api_timeout: int = 10
    
    # Admin Authentication
    admin_username: str = "admin"
    admin_password_hash: str
    
    # Application Settings
    secret_key: str
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api"
    api_version: str = "v1"
    
    # Deadline Settings
    default_deadline_day: int = 10
    
    # Scheduler Settings
    reminder_days_before: List[int] = [7, 3, 1]
    
    # CORS Settings
    cors_origins: List[str] = []
    
    # Session Settings
    session_cookie_secure: bool = False
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "lax"
    session_max_age: int = 86400
    
    # Security Headers (Production)
    hsts_max_age: int = 31536000
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True
    
    # Rate Limiting (Production)
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def database_url(self) -> str:
        """Construct database URL from configuration."""
        # Use SQLite if DB_USER is 'sqlite'
        if self.db_user.lower() == 'sqlite':
            return f"sqlite:///./{self.db_name}.db"
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.debug


# Global settings instance
settings = Settings()
