from fastapi import APIRouter

from app.api.routes.admin_foods import router as admin_foods_router
from app.api.routes.auth import router as auth_router
from app.api.routes.foods import router as foods_router
from app.api.routes.plans import router as plans_router
from app.api.routes.profiles import router as profiles_router
from app.api.routes.recipes import router as recipes_router
from app.api.routes.servings import router as servings_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(profiles_router)
api_router.include_router(recipes_router)
api_router.include_router(plans_router)
api_router.include_router(foods_router)
api_router.include_router(servings_router)
api_router.include_router(admin_foods_router)
