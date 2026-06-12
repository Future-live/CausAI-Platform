from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserRead(BaseModel):
    id: str
    username: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserRead
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
