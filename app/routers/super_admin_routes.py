from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from pydantic import EmailStr
from ..database import get_db
from ..schemas import UserLogin, UserCreate, Token, SuccessResponse, UserResponse
from ..auth import get_current_user, get_current_super_admin, create_access_token, pwd_context, create_user_session, invalidate_user_session, oauth2_scheme
from ..config.settings import settings
from .. import models

import random

from ..utils.otp_utils import send_email_otp_for_verification, send_email_otp, otp_storage
from ..utils.token_utils import get_client_ip

router = APIRouter(prefix="/super-admin", tags=["Super Admin Management"])

@router.post('/login')
async def super_admin_login(
    request: Request,
    email: EmailStr = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):  
    # Check if super admin exists
    super_admin = db.query(models.Super_admin).filter(models.Super_admin.email == email).first()
    if not super_admin:
        raise HTTPException(status_code=400, detail="This User Is Not Available")

    # Verify password
    if not pwd_context.verify(password, super_admin.password_hash):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    # Get device info and IP
    client_ip = get_client_ip()
    user_agent = request.headers.get("user-agent", "Unknown Device")
    
    # Create new session for super admin (using same table but with negative user_id to distinguish)
    session_id = create_user_session(
        db=db, 
        user_id=-super_admin.id,  # Negative ID to distinguish from regular users
        ip_address=client_ip, 
        device_info=f"SuperAdmin: {user_agent}"
    )

    # Generate JWT token with session_id
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    token = create_access_token(
        data={
            "sub": str(super_admin.id),
            "type": str(super_admin.role), 
            "email": super_admin.email,
            "role": super_admin.role,
            "session_id": session_id,
        },
        expires_delta=access_token_expires
    )

    return {
        "message": "Login successful. Previous sessions have been logged out.",
        "access_token": token,
        "token_type": "bearer",
        "session_id": session_id,
        "user": {
            "id": super_admin.id,
            "name": super_admin.name,
            "email": super_admin.email,
            "role": super_admin.role
        }
    }

@router.post('/logout')
async def super_admin_logout(
    current_user: models.Super_admin = Depends(get_current_super_admin),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Logout current super admin by invalidating their session"""
    try:
        from jose import jwt
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        session_id = payload.get("session_id")
        
        if session_id and invalidate_user_session(db, session_id):
            return {"message": "Successfully logged out"}
        else:
            raise HTTPException(status_code=400, detail="Failed to logout")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token or session")

@router.get('/admins')
async def super_admin_see_all_admins(
    current_user: models.Super_admin = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    if current_user.role != "SuperAdmin":
        raise HTTPException(status_code=403, detail="Access denied")

    # Get the Role ID for 'Admin'
    admin_role = db.query(models.Role).filter_by(name="Admin").first()
    if not admin_role:
        raise HTTPException(status_code=404, detail="Admin role not found")

    # Fetch all users with Admin role
    admin_users = db.query(models.User).filter(models.User.role_id == admin_role.id).all()

    result = {
        "super_admin": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email
        },
        "admins": []
    }

    for admin in admin_users:
        # Get latest IP address record for this admin
        admin_ip_record = (
            db.query(models.IPAddress)
            .filter(models.IPAddress.user_id == admin.id)
            .order_by(models.IPAddress.created_at.desc())
            .first()
        )

        # Fetch employees in the same org
        employees = db.query(models.User).filter(
            models.User.org_id == admin.org_id,
            models.User.id != admin.id
        ).all()

        admin_data = {
            "id": admin.id,
            "name": admin.name,
            "email": admin.email,
            "org_id": admin.org_id,
            "ip_address": admin_ip_record.ip_address if admin_ip_record else None,
            "created_at": admin.created_at,
            "last_login": admin_ip_record.last_login if admin_ip_record else None,
            "employees": []
        }

        for emp in employees:
            emp_ip_record = (
                db.query(models.IPAddress)
                .filter(models.IPAddress.user_id == emp.id)
                .order_by(models.IPAddress.created_at.desc())
                .first()
            )

            admin_data["employees"].append({
                "id": emp.id,
                "name": emp.name,
                "email": emp.email,
                "role": emp.role.name,
                "ip_address": emp_ip_record.ip_address if emp_ip_record else None,
                "created_at": emp.created_at,
                "last_login": emp_ip_record.last_login if emp_ip_record else None
            })

        result["admins"].append(admin_data)

    return result

@router.post('/password/forgot/send-otp')
async def super_admin_send_otp_forgot_pass(
    email: EmailStr = Form(...),
    db: Session = Depends(get_db)
    ):
    email_super = db.query(models.Super_admin).filter(models.Super_admin.email == email).first()
    if not email_super:
        raise HTTPException(status_code=400, detail="This User Is Not Available")
    if email_super:
        id_of_user=email_super.id
        role_of_user=email_super.role
        otp = str(random.randint(100000, 999999))

        otp_storage[email] = otp  # Store OTP temporarily

        result = send_email_otp(email, otp)
        if result["status"] == "success":
            otp_user = models.ResetOtp(otp=otp,user_id=id_of_user,role=role_of_user)
            db.add(otp_user)
            db.commit()
            db.refresh(otp_user)
            return {"message": "OTP sent successfully"}
        else:
            raise HTTPException(status_code=500, detail=result["message"])

@router.put('/password/reset')
async def super_admin_reset_password(
    otp: int = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    matched_otp = db.query(models.ResetOtp).filter(models.ResetOtp.otp == otp).first()
    
    if not matched_otp:
        raise HTTPException(status_code=400, detail="This OTP is incorrect. Please enter the correct OTP.")

    # Get the user associated with the OTP
    s_admin = db.query(models.Super_admin).filter(models.Super_admin.id == matched_otp.user_id and models.Super_admin.role == matched_otp.role).first()
    
    if not s_admin:
        raise HTTPException(status_code=404, detail="User not found.")

    # Hash the new password and update the user record
    s_admin.password_hash = pwd_context.hash(password)
    
    db.commit()
    
    return {"message": "Your password has been changed successfully. Please log in with the new password."}

