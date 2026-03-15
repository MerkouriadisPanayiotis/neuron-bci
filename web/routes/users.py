"""NEURON — User Profile API Routes."""

from typing import List

from fastapi import APIRouter, HTTPException

from web import db
from web.models import UserCreate, UserResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserResponse])
async def list_users():
    users = db.list_users()
    result = []
    for u in users:
        profile = db.get_neural_profile(u["id"])
        result.append(UserResponse(
            id=u["id"],
            name=u["name"],
            created_at=u["created_at"] or "",
            avatar_color=u["avatar_color"] or "#6366f1",
            preferences=u["preferences"] or "{}",
            has_profile=profile is not None,
            learning_phase=profile["learning_phase"] if profile else 0,
            confidence=profile["confidence"] if profile else {},
        ))
    return result


@router.post("", response_model=UserResponse)
async def create_user(body: UserCreate):
    try:
        user = db.create_user(name=body.name, avatar_color=body.avatar_color)
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail="User name already exists")
        raise
    return UserResponse(
        id=user["id"],
        name=user["name"],
        created_at=user["created_at"] or "",
        avatar_color=user["avatar_color"] or "#6366f1",
        preferences=user["preferences"] or "{}",
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    profile = db.get_neural_profile(user_id)
    return UserResponse(
        id=user["id"],
        name=user["name"],
        created_at=user["created_at"] or "",
        avatar_color=user["avatar_color"] or "#6366f1",
        preferences=user["preferences"] or "{}",
        has_profile=profile is not None,
        learning_phase=profile["learning_phase"] if profile else 0,
        confidence=profile["confidence"] if profile else {},
    )


@router.delete("/{user_id}")
async def delete_user(user_id: str):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete_user(user_id)
    return {"status": "deleted"}
