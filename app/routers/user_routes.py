from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..schemas import UserResponse, UserUpdate, SuccessResponse
from ..dependencies import get_current_user
from .. import models

router = APIRouter(prefix="/users", tags=["User Management"])

@router.get("/profile", response_model=UserResponse)
def get_user_profile(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.get("/all", response_model=List[UserResponse])
def list_all_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    users = db.query(models.User).all()
    return users

@router.put("/profile", response_model=SuccessResponse)
def update_user_profile(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if email already exists (if being updated)
    if user_update.email and user_update.email != current_user.email:
        existing_user = db.query(models.User).filter(models.User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Update user fields
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return SuccessResponse(
        message="User profile updated successfully",
        data={"user_id": current_user.id}
    )

@router.delete("/profile", response_model=SuccessResponse)
def delete_user_account(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db.delete(current_user)
    db.commit()
    
    return SuccessResponse(
        message="User account deleted successfully",
        data={"deleted_user_id": current_user.id}
    )
