"""
Enterprise AI Assistant Platform - FastAPI Main Application
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.exceptions import PersianAppException
from app.services.seeder import seed_database
from app.api.v1.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB schema & seed default roles, groups, settings, admin
    seed_database()
    yield
    # Shutdown logic if needed

app = FastAPI(
    title="سامانه هوش مصنوعی سازمانی",
    description="سرویس جامع مدیریت هوش مصنوعی، مدل‌های زبانی، سهمیه‌ها و پایگاه دانش سازمانی",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Persian Exception Handler
@app.exception_handler(PersianAppException)
async def persian_app_exception_handler(request: Request, exc: PersianAppException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Translate common validation errors into Persian
    errors = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"] if loc != "body")
        errors.append(f"فیلد '{field}': {err['msg']}")
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "اطلاعات ورودی نامعتبر است.",
            "error_code": "VALIDATION_ERROR",
            "errors": errors
        }
    )

# Include API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["سلامت سامانه"], summary="بررسی وضعیت فعال بودن سرور")
def health_check():
    return {
        "status": "healthy",
        "service": "Enterprise AI Assistant Backend",
        "version": "1.0.0",
        "language": "fa"
    }

@app.get(f"{settings.API_V1_STR}/health", tags=["سلامت سامانه"], summary="بررسی سلامت API v1")
def api_v1_health_check():
    return {
        "status": "healthy",
        "api_version": "v1",
        "auth_mode": settings.AUTH_MODE
    }
