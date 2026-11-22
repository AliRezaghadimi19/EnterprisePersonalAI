"""
Application Configuration Module
Loads settings from environment variables and provides structured access.
"""

import os
from typing import List, Optional
from pathlib import Path

# Base directory of the backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "سامانه هوش مصنوعی سازمانی")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "enterprise-secure-master-secret-key-99887766554433221100")
    FERNET_KEY: str = os.getenv("FERNET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
    
    # Super Admin Initial Setup
    SUPER_ADMIN_USERNAME: str = os.getenv("SUPER_ADMIN_USERNAME", "admin")
    SUPER_ADMIN_PASSWORD: str = os.getenv("SUPER_ADMIN_PASSWORD", "Enterprise@Admin123!")
    SUPER_ADMIN_EMAIL: str = os.getenv("SUPER_ADMIN_EMAIL", "admin@enterprise.local")
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{BASE_DIR}/enterprise_ai.db"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    
    # S3 Storage
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "minio_admin")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "Secr3t_M!n!o_P@ssw0rd")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "enterprise-ai-documents")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
    
    # Auth Mode: 'LOCAL_ONLY', 'AD_ONLY', 'BOTH'
    AUTH_MODE: str = os.getenv("AUTH_MODE", "BOTH")
    AUTO_PROVISION_AD_USERS: bool = os.getenv("AUTO_PROVISION_AD_USERS", "true").lower() in ("true", "1")
    
    # AI Defaults
    DEFAULT_RESPONSE_POLICY: str = os.getenv("DEFAULT_RESPONSE_POLICY", "HYBRID")
    DEFAULT_AI_LANGUAGE: str = os.getenv("DEFAULT_AI_LANGUAGE", "fa")

settings = Settings()
