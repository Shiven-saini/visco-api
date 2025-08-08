from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from ..database import get_db
from ..schemas import UserLogin, UserCreate, Token, SuccessResponse, UserResponse
from ..auth import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_DAYS
from .. import models

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if username already exists
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    db_user = models.User(
        username=user.username,
        email=user.email,
        password=user.password,  # Plain text as requested
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return SuccessResponse(
        message="User registered successfully",
        data={"user_id": db_user.id, "username": db_user.username}
    )

@router.post("/login", response_model=Token)
def login_user(user_credentials: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # in seconds
    }

@router.post("/logout", response_model=SuccessResponse)
def logout_user():
    # Since JWT tokens are stateless, logout is handled client-side
    return SuccessResponse(message="Logout successful. Please remove the token from client-side.")
