from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from pydantic import EmailStr
from ..database import get_db
from ..schemas import UserLogin, UserCreate, Token, SuccessResponse, UserResponse
from ..auth import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_DAYS
from .. import models

import random

from ..utils.otp_utils import send_email_otp_for_verification

router = APIRouter(prefix="/auth", tags=["Authentication"])

# @router.post("/login", response_model=Token)
# def login_user(user_credentials: UserLogin, db: Session = Depends(get_db)):
#     user = authenticate_user(db, user_credentials.username, user_credentials.password)
    
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
    
#     access_token_expires = timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
#     access_token = create_access_token(
#         data={"sub": user.username}, expires_delta=access_token_expires
#     )
    
#     return {
#         "access_token": access_token,
#         "token_type": "bearer",
#         "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # in seconds
#     }

# @router.post("/register", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
# def register_user(user: UserCreate, db: Session = Depends(get_db)):
#     # Check if username already exists
#     db_user = db.query(models.User).filter(models.User.username == user.username).first()
#     if db_user:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Username already registered"
#         )
    
#     # Check if email already exists
#     db_user = db.query(models.User).filter(models.User.email == user.email).first()
#     if db_user:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Email already registered"
#         )
    
#     # Create new user
#     db_user = models.User(
#         username=user.username,
#         email=user.email,
#         password=user.password,  # Plain text as requested
#         first_name=user.first_name,
#         last_name=user.last_name
#     )
    
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
    
#     return SuccessResponse(
#         message="User registered successfully",
#         data={"user_id": db_user.id, "username": db_user.username}
#     )

@router.post("/admin-register")
async def register(
    name: str = Form(...),
    email: str = Form(...),
    company_name:str = Form(...),
    password: str = Form(...), 
    db: Session = Depends(get_db)):

    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered in the database.")

    # Fetch Admin role
    admin_role = db.query(models.Role).filter_by(name="Admin").first()
    if not admin_role:
        raise HTTPException(status_code=500, detail="Admin role not found")

    # Create user first (so we can set org.created_by = user.id properly)
    user = models.User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role_id=admin_role.id
    )
    db.add(user)
    db.flush()  # get user.id

    # Create organization
    org = models.Organization(
        name=f"{company_name}",
        created_by=user.id
    )
    db.add(org)
    db.flush()  # get org.id

    # Update user with org_id
    user.org_id = org.id

    db.commit()
    return {"msg": "Admin registered and organization created successfully."}

@router.post("/send-otp-account-verification")
async def send_otp_verification_account(
    email: EmailStr = Form(...),
    db: Session = Depends(get_db)
):
    otp = str(random.randint(100000, 999999))

    db.query(models.Verify_otp).filter(models.Verify_otp.email == email).delete()

    otp_record = models.Verify_otp(
        email=email,
        otp=otp,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )

    db.add(otp_record)
    db.commit()

    result = send_email_otp_for_verification(email, otp)
    if result.get("status") == "success":
        return {"message": "OTP sent successfully to your email address."}
    else:
        raise HTTPException(status_code=500, detail=result.get("message", "Failed to send OTP"))

@router.post("/verify-your-account")
async def verify_your_account(
    email: EmailStr = Form(...),
    otp: int = Form(...),
    db: Session = Depends(get_db)
):
    otp_record = db.query(models.Verify_otp).filter(
        models. Verify_otp.email == email,
        models.Verify_otp.otp == otp
    ).first()

    if not otp_record:
        raise HTTPException(status_code=400, detail="Incorrect OTP.")

    if otp_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    # Optional: Mark this email as verified or just allow sign-up now
    db.delete(otp_record)
    db.commit()

    return {"message": "OTP verified successfully. You can now proceed to sign up."}


@router.post("/logout", response_model=SuccessResponse)
def logout_user():
    # Since JWT tokens are stateless, logout is handled client-side
    return SuccessResponse(message="Logout successful. Please remove the token from client-side.")
