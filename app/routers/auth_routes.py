from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from pydantic import EmailStr
from typing import Annotated
from ..database import get_db
from ..schemas import UserLogin, UserCreate, Token, SuccessResponse, UserResponse
from ..auth import hash_password, get_current_user, create_access_token, pwd_context, oauth2_scheme, create_user_session, invalidate_user_session
from ..config.settings import settings
from .. import models

import random

from ..utils.otp_utils import send_email_otp_for_verification, send_email_otp, otp_storage
from ..utils.token_utils import get_client_ip

router = APIRouter(tags=["Authentication & Session Management"])

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

    # --- BEGIN: auto-create Admin role if missing (temporary for testing) ---
    # Original implementation (commented out so tests can be reverted):
    # admin_role = db.query(models.Role).filter_by(name="Admin").first()
    # if not admin_role:
    #     raise HTTPException(status_code=500, detail="Admin role not found")

    # New behavior: create the Admin role automatically if it doesn't exist.
    admin_role = db.query(models.Role).filter_by(name="Admin").first()
    if not admin_role:
        admin_role = models.Role(name="Admin")
        db.add(admin_role)
        db.flush()  # ensure admin_role.id is populated
    # --- END: auto-create Admin role if missing (temporary for testing) ---

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
    return {"msg": "Admin registered and organization created successfully.","user_id" : user.id,"org_id":user.org_id,"email":user.email}

@router.post("/login")
async def login_user(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: Session = Depends(get_db),
):

    email: EmailStr | None = None
    
    try:
        email = form_data.username
    except Exception:
        # If not a valid email, keep the message generic to avoid user enumeration
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or password",
        )

    password = form_data.password

    # Lookup user
    user = (
        db.query(models.User)
        .filter(models.User.email == str(email))
        .first()
    )
    if not user:
        # Generic error to avoid leaking which field failed
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or password",
        )

    # Verify password
    if not pwd_context.verify(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or password",
        )

    # Get device info and IP
    client_ip = get_client_ip()
    user_agent = request.headers.get("user-agent", "Unknown Device")
    
    # Create new session (this will invalidate all previous sessions for this user)
    session_id = create_user_session(
        db=db, 
        user_id=user.id, 
        ip_address=client_ip, 
        device_info=user_agent
    )

    # Update or create IP record (keeping existing functionality)
    ip_record = (
        db.query(models.IPAddress)
        .filter(models.IPAddress.user_id == user.id)
        .first()
    )
    now = datetime.utcnow()
    if ip_record:
        ip_record.ip_address = client_ip
        ip_record.last_login = now
    else:
        ip_record = models.IPAddress(
            user_id=user.id,
            ip_address=client_ip,
            last_login=now,
        )
        db.add(ip_record)

    db.commit()
    db.refresh(user)
    db.refresh(ip_record)

    # Create JWT with session_id
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    token = create_access_token(
        data={
            "sub": str(user.id),
            "type": str(user.role.name),
            "email": user.email,
            "org_id": user.org_id,
            "session_id": session_id,  # Add session_id to token
        },
        expires_delta=access_token_expires,
    )

    # IMPORTANT: keep these keys for Swagger UI
    return {
        "message": "Login successful. Previous sessions have been logged out.",
        "access_token": token,
        "token_type": "bearer",
        "session_id": session_id,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.name,
            "account_created_date": user.created_at,
        },
        "ip_address": ip_record.ip_address,
        "last_login": ip_record.last_login,
    }

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

@router.put("/admin-change-password", response_model=SuccessResponse)
async def admin_change_password(
    email: EmailStr = Form(...),
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Ensure the user is changing their own password
    if current_user.email != email:
        raise HTTPException(status_code=403, detail="You can only change your own password")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not pwd_context.verify(old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match")

    # Update the password
    user.password_hash = pwd_context.hash(new_password)
    db.commit()

    return {"message": "Password changed successfully"}

@router.post("/admin-send-otp-forgot-password")
async def admin_send_otp_forgot_pass(
    email: EmailStr = Form(...),
    db: Session = Depends(get_db)
    ):
    email_user = db.query(models.User).filter(models.User.email == email).first()
    if not email_user:
        raise HTTPException(status_code=400, detail="This User Is Not Available")
    if email_user:
        id_of_user=email_user.id
        otp = str(random.randint(100000, 999999))

        otp_storage[email] = otp  # Store OTP temporarily

        result = send_email_otp(email, otp)
        if result["status"] == "success":
            otp_user = models.ResetOtp(otp=otp,user_id=id_of_user)
            db.add(otp_user)
            db.commit()
            db.refresh(otp_user)
            return {"message": "OTP sent successfully"}
        else:
            raise HTTPException(status_code=500, detail=result["message"])

@router.post("/logout")
async def logout_user(
    current_user: models.User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Logout current user by invalidating their session and revoking WireGuard config"""
    try:
        from jose import jwt
        from ..services.wireguard_service import WireGuardService
        from ..utils.system_utils import remove_peer_from_wg_config
        
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        session_id = payload.get("session_id")
        
        logout_successful = False
        wireguard_revoked = False
        wireguard_error = None
        freed_ip = None
        
        # Invalidate user session
        if session_id and invalidate_user_session(db, session_id):
            logout_successful = True
        
        # Revoke WireGuard configuration if exists (using same logic as wireguard delete endpoint)
        wg_service = WireGuardService()
        config = wg_service.get_user_config(db, current_user)
        if config:
            try:
                # Store IP before deletion
                freed_ip = config.allocated_ip
                
                # Remove peer from server config (same as wireguard delete endpoint)
                if not remove_peer_from_wg_config(config.public_key):
                    wireguard_error = "Failed to remove peer from server WireGuard configuration"
                    print(f"Failed to remove peer from server config for user {current_user.email}")
                else:
                    # Remove from database (same as wireguard delete endpoint)
                    if wg_service.revoke_config(db, current_user):
                        wireguard_revoked = True
                        print(f"WireGuard config revoked for user {current_user.email}, IP {freed_ip} freed")
                    else:
                        wireguard_error = "Failed to revoke WireGuard configuration from database"
                        print(f"Failed to revoke WireGuard config from database for user {current_user.email}")
                
            except Exception as wg_error:
                wireguard_error = f"Error during WireGuard cleanup: {str(wg_error)}"
                print(f"Error revoking WireGuard config for user {current_user.email}: {wg_error}")
                # Don't fail the logout if WireGuard cleanup fails
        
        if logout_successful:
            response_data = {"message": "Successfully logged out"}
            if wireguard_revoked:
                response_data["wireguard_status"] = "WireGuard configuration revoked and IP freed"
                response_data["freed_ip"] = freed_ip
            elif config and wireguard_error:
                response_data["wireguard_status"] = f"Warning: {wireguard_error}"
            elif config:
                response_data["wireguard_status"] = "Warning: WireGuard configuration cleanup failed"
            else:
                response_data["wireguard_status"] = "No WireGuard configuration to revoke"
                
            return response_data
        else:
            raise HTTPException(status_code=400, detail="Failed to logout")
            
    except Exception as e:
        print(f"Logout error for user {current_user.email}: {e}")
        raise HTTPException(status_code=400, detail="Invalid token or session")

@router.post("/logout-all-devices")
async def logout_all_devices(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout user from all devices by invalidating all their sessions"""
    # Invalidate all active sessions for this user
    updated_count = db.query(models.UserSession).filter(
        models.UserSession.user_id == current_user.id,
        models.UserSession.is_active == True
    ).update({"is_active": False})
    
    db.commit()
    
    return {"message": f"Successfully logged out from all devices. {updated_count} sessions invalidated."}

@router.get("/active-sessions")
async def get_active_sessions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all active sessions for the current user"""
    sessions = db.query(models.UserSession).filter(
        models.UserSession.user_id == current_user.id,
        models.UserSession.is_active == True,
        models.UserSession.expires_at > datetime.utcnow()
    ).all()
    
    session_data = []
    for session in sessions:
        session_data.append({
            "session_id": session.session_id,
            "device_info": session.device_info,
            "ip_address": session.ip_address,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "expires_at": session.expires_at
        })
    
    return {
        "active_sessions_count": len(session_data),
        "sessions": session_data
    }

@router.delete("/session/{session_id}")
async def terminate_session(
    session_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Terminate a specific session (can only terminate your own sessions)"""
    session = db.query(models.UserSession).filter(
        models.UserSession.session_id == session_id,
        models.UserSession.user_id == current_user.id,
        models.UserSession.is_active == True
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or already inactive")
    
    session.is_active = False
    db.commit()
    
    return {"message": f"Session {session_id} has been terminated"}

@router.put("/reset-password")
async def reset_password(
    otp: int = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    matched_otp = db.query(models.ResetOtp).filter(models.ResetOtp.otp == otp).first()
    
    if not matched_otp:
        raise HTTPException(status_code=400, detail="This OTP is incorrect. Please enter the correct OTP.")

    # Get the user associated with the OTP
    user = db.query(models.User).filter(models.User.id == matched_otp.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Hash the new password and update the user record
    user.password_hash = pwd_context.hash(password)
    
    db.commit()
    
    return {"message": "Your password has been changed successfully. Please log in with the new password."}
