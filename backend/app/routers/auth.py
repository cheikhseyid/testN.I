from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import TOKEN_TTL, _unauthorized, authenticate, create_token, get_admin
from ..db import get_db
from ..models import Admin
from .signalements import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/login", response_model=TokenOut)
@limiter.limit("5/minute")
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)):
    admin = authenticate(db, body.email, body.password)
    if admin is None:
        raise _unauthorized("Email ou mot de passe incorrect")
    return TokenOut(access_token=create_token(admin), expires_in=int(TOKEN_TTL.total_seconds()))


@router.get("/me")
def me(admin: Admin = Depends(get_admin)):
    return {"id": admin.id, "email": admin.email}
