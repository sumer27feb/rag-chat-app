import uuid
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.hash import argon2
from typing import Annotated
from pydantic import BaseModel, EmailStr, field_validator
from pydantic.types import StringConstraints
from fastapi_limiter.depends import RateLimiter
import re

# Load variables from .env file
load_dotenv()
# ---- JWT ----
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# --- Models ---
class SignUpIn(BaseModel):
    email: EmailStr
    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=32,
            pattern=r"^[a-zA-Z0-9_]+$"
        )
    ]
    password: Annotated[
        str,
        StringConstraints(
            min_length=8,
            max_length=128
        )
    ]

    # ✅ Custom validator instead of unsupported regex lookaheads
    @field_validator("password")
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        if not re.search(r"[^\w\s]", v):
            raise ValueError("Password must contain a special character")
        return v


class TokenOut(BaseModel):
    access_token: str
    token_type: str


class UserOut(BaseModel):
    user_id: str
    email: EmailStr
    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=32,
            pattern=r"^[a-zA-Z0-9_]+$"
        )
    ]

class RefreshRequest(BaseModel):
    refresh_token: str


# --- Helpers ---
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict):
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_users_col(request: Request):
    return request.app.state.db["users"]


async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if not user_id or token_type != "access":
            raise HTTPException(status_code=401, detail="Invalid token type or payload")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await get_users_col(request).find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# --- Routes ---
@router.post("/signup", response_model=TokenOut, dependencies=[Depends(RateLimiter(times=3, seconds=60))])
async def signup(request: Request, data: SignUpIn):
    users = get_users_col(request)

    email = data.email.lower().strip()
    username = data.username.strip()

    if await users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    if await users.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username already taken")

    user_id = str(uuid.uuid4())
    user_doc = {
        "user_id": user_id,
        "email": email,
        "username": username,
        "password": argon2.hash(data.password),
        "created_at": datetime.now(timezone.utc),
    }
    await users.insert_one(user_doc)

    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/login", response_model=TokenOut, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    users = get_users_col(request)
    user = await users.find_one({"email": form_data.username.lower().strip()})
    if not user or not argon2.verify(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": user["user_id"]})
    refresh_token = create_refresh_token({"sub": user["user_id"]})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=TokenOut)
async def refresh_token(data: RefreshRequest):
    try:
        payload = jwt.decode(data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Create new access token
    new_access_token = create_access_token({"sub": user_id})
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "username": current_user["username"],
    }
