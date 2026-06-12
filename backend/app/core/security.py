from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.user import User

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_token(subject: str, token_type: str, expires_delta: timedelta, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str, settings: Settings) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return str(payload["sub"])


def create_auth_tokens(user_id: str, settings: Settings) -> dict[str, str]:
    access_token = create_token(
        user_id,
        "access",
        timedelta(minutes=settings.jwt_access_token_minutes),
        settings,
    )
    refresh_token = create_token(
        user_id,
        "refresh",
        timedelta(days=settings.jwt_refresh_token_days),
        settings,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def set_auth_cookies(response: Response, user_id: str, settings: Settings) -> dict[str, str]:
    tokens = create_auth_tokens(user_id, settings)
    response.set_cookie(
        settings.access_cookie_name,
        tokens["access_token"],
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.jwt_access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        tokens["refresh_token"],
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.jwt_refresh_token_days * 24 * 60 * 60,
        path="/",
    )
    return tokens


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.access_cookie_name, path="/")
    response.delete_cookie(settings.refresh_cookie_name, path="/")


def _token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    settings: Settings,
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return request.cookies.get(settings.access_cookie_name)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    token = _token_from_request(request, credentials, settings)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_token(token, "access", settings)
    try:
        UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user
