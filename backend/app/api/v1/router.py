from fastapi import APIRouter

from app.api.v1 import auth, causal, datasets, llm

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(datasets.router)
api_router.include_router(causal.router)
api_router.include_router(llm.router)
