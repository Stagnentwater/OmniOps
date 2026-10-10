"""FastAPI routes for user profile retrieval and updates."""

from __future__ import annotations

import logging
from datetime import datetime
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
from dependencies import get_current_user, get_user_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileResponse(BaseModel):
    user_id: str
    name: str
    skill_set: list[str]
    designation: str
    refinery_experience_level: str
    preferred_explanation_depth: str
    created_at: str
    updated_at: str


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    designation: str | None = None
    skill_set: list[str] | None = None
    refinery_experience_level: str | None = None
    preferred_explanation_depth: str | None = None


def _serialize_profile(profile: UserProfile) -> ProfileResponse:
    """Format UserProfile dataclass into ProfileResponse API model."""
    return ProfileResponse(
        user_id=profile.user_id,
        name=profile.name,
        skill_set=profile.skill_set,
        designation=profile.designation,
        refinery_experience_level=profile.refinery_experience_level,
        preferred_explanation_depth=profile.preferred_explanation_depth,
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat(),
    )


@router.get("", response_model=ProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
) -> ProfileResponse:
    """Retrieve the domain persona profile for the authenticated user."""
    profile = user_repo.get_profile(current_user.user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )
    return _serialize_profile(profile)


@router.put("", response_model=ProfileResponse)
def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
) -> ProfileResponse:
    """Update profile fields for the authenticated user, enforcing ownership and validation."""
    if request.name is not None and not request.name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name cannot be empty",
        )

    if request.refinery_experience_level is not None:
        exp = request.refinery_experience_level.strip().lower()
        if exp not in VALID_EXPERIENCE_LEVELS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid experience level '{exp}'. Must be one of {sorted(VALID_EXPERIENCE_LEVELS)}",
            )

    if request.preferred_explanation_depth is not None:
        depth = request.preferred_explanation_depth.strip().lower()
        if depth not in VALID_EXPLANATION_DEPTHS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid explanation depth '{depth}'. Must be one of {sorted(VALID_EXPLANATION_DEPTHS)}",
            )

    try:
        updated = user_repo.update_profile(
            user_id=current_user.user_id,
            name=request.name.strip() if request.name is not None else None,
            designation=request.designation.strip() if request.designation is not None else None,
            skill_set=request.skill_set,
            refinery_experience_level=request.refinery_experience_level,
            preferred_explanation_depth=request.preferred_explanation_depth,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    return _serialize_profile(updated)
