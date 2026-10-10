"""FastAPI routes for user registration, authentication, and session status."""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from database.user_repository import (
    User,
    UserProfile,
    UserRepository,
    VALID_EXPERIENCE_LEVELS,
    VALID_EXPLANATION_DEPTHS,
)
from dependencies import get_auth_service, get_current_user, get_user_repo
from services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    designation: str = "Plant Personnel"
    skill_set: list[str] = Field(default_factory=list)
    refinery_experience_level: str = "intermediate"
    preferred_explanation_depth: str = "moderate"


class LoginRequest(BaseModel):
    email: str
    password: str


class UserSummary(BaseModel):
    user_id: str
    email: str
    name: str
    designation: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


class ProfileDetail(BaseModel):
    name: str
    designation: str
    skill_set: list[str]
    refinery_experience_level: str
    preferred_explanation_depth: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    is_active: bool
    profile: ProfileDetail | None = None


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repo),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    """Register a new plant user and generate initial session token."""
    clean_email = request.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid email address is required",
        )
    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 6 characters in length",
        )
    if not request.name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name cannot be blank",
        )

    exp_level = request.refinery_experience_level.strip().lower()
    if exp_level not in VALID_EXPERIENCE_LEVELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid experience level. Must be one of {sorted(VALID_EXPERIENCE_LEVELS)}",
        )

    depth = request.preferred_explanation_depth.strip().lower()
    if depth not in VALID_EXPLANATION_DEPTHS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid explanation depth. Must be one of {sorted(VALID_EXPLANATION_DEPTHS)}",
        )

    # Duplicate check
    existing = user_repo.get_user_by_email(clean_email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists",
        )

    pwd_hash = auth_service.hash_password(request.password)
    user = user_repo.create_user(
        email=clean_email,
        password_hash=pwd_hash,
        name=request.name.strip(),
        designation=request.designation.strip() or "Plant Personnel",
        skill_set=request.skill_set,
        refinery_experience_level=exp_level,
        preferred_explanation_depth=depth,
    )

    token = auth_service.create_access_token(user_id=user.user_id, email=user.email)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserSummary(
            user_id=user.user_id,
            email=user.email,
            name=request.name.strip(),
            designation=request.designation.strip() or "Plant Personnel",
        ),
    )


@router.post("/login", response_model=AuthResponse)
def login(
    request: LoginRequest,
    user_repo: UserRepository = Depends(get_user_repo),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    """Authenticate plant user credentials and return a signed session token."""
    clean_email = request.email.strip().lower()
    user = user_repo.get_user_by_email(clean_email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not auth_service.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    profile = user_repo.get_profile(user.user_id)
    token = auth_service.create_access_token(user_id=user.user_id, email=user.email)

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserSummary(
            user_id=user.user_id,
            email=user.email,
            name=profile.name if profile else "",
            designation=profile.designation if profile else "",
        ),
    )


@router.get("/me", response_model=MeResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
) -> MeResponse:
    """Retrieve identity and domain persona for the currently authenticated session."""
    profile = user_repo.get_profile(current_user.user_id)
    prof_detail = None
    if profile:
        prof_detail = ProfileDetail(
            name=profile.name,
            designation=profile.designation,
            skill_set=profile.skill_set,
            refinery_experience_level=profile.refinery_experience_level,
            preferred_explanation_depth=profile.preferred_explanation_depth,
        )

    return MeResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        is_active=current_user.is_active,
        profile=prof_detail,
    )
