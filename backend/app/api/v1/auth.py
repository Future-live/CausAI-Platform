from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import clear_auth_cookies, decode_token, get_current_user, set_auth_cookies
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AuthResponse, RefreshTokenRequest, UserCreate, UserLogin, UserRead
from app.schemas.common import MessageResponse
from app.services.auth import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user = register_user(db, payload)
    tokens = set_auth_cookies(response, user.id, settings)
    return AuthResponse(user=UserRead.model_validate(user), **tokens)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user = authenticate_user(db, payload)
    tokens = set_auth_cookies(response, user.id, settings)
    return AuthResponse(user=UserRead.model_validate(user), **tokens)


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response, settings: Settings = Depends(get_settings)) -> MessageResponse:
    clear_auth_cookies(response, settings)
    return MessageResponse(message="已退出登录")


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    token = request.cookies.get(settings.refresh_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_token(token, "refresh", settings)
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    tokens = set_auth_cookies(response, user.id, settings)
    return AuthResponse(user=UserRead.model_validate(user), **tokens)


@router.post("/token/refresh", response_model=AuthResponse)
def refresh_with_token(
    payload: RefreshTokenRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user_id = decode_token(payload.refresh_token, "refresh", settings)
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    tokens = set_auth_cookies(response, user.id, settings)
    return AuthResponse(user=UserRead.model_validate(user), **tokens)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
