"""
API v1 Router Aggregator
Combines Auth, AD Settings, System Settings, and all subsequent phase routers.
"""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.ad_settings import router as ad_router
from app.api.v1.system_settings import router as settings_router
from app.api.v1.users import router as users_router
from app.api.v1.groups import router as groups_router
from app.api.v1.roles import router as roles_router
from app.api.v1.ai_providers import router as ai_providers_router
from app.api.v1.ai_models import router as ai_models_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.chat import router as chat_router
from app.api.v1.admin import router as admin_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(ad_router)
api_router.include_router(settings_router)
api_router.include_router(users_router)
api_router.include_router(groups_router)
api_router.include_router(roles_router)
api_router.include_router(ai_providers_router)
api_router.include_router(ai_models_router)
api_router.include_router(knowledge_router)
api_router.include_router(chat_router)
api_router.include_router(admin_router)
