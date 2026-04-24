"""Auth router — OAuth2 password flow issuing JWTs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.config import get_settings
from app.security import authenticate_user, create_access_token

router = APIRouter(tags=["auth"])


@router.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends()) -> dict:
    user = authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        subject=user["username"],
        settings=get_settings(),
        roles=user["roles"],
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "roles": user["roles"],
    }
