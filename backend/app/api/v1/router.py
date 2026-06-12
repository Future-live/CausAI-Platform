from fastapi import APIRouter

from app.api.v1 import auth, causal, datasets, favorites, llm, workflows

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(datasets.router)
api_router.include_router(causal.router)
api_router.include_router(llm.router)
api_router.include_router(favorites.router)
api_router.include_router(workflows.router)
