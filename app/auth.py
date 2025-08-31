from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from . import models
from .database import get_db
from .config.settings import settings
from passlib.context import CryptContext
import uuid


# JWT Configuration from settings
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({
        "exp": expire,
        "type": data.get("type"),  # example: "admin" or "super_admin"
        "session_id": data.get("session_id")  # Add session_id to JWT
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

def create_user_session(db: Session, user_id: int, ip_address: str = None, device_info: str = None) -> str:
    """Create a new session for user and invalidate all previous sessions"""
    # Invalidate all existing sessions for this user
    db.query(models.UserSession).filter(
        models.UserSession.user_id == user_id,
        models.UserSession.is_active == True
    ).update({"is_active": False})
    
    # Create new session
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    new_session = models.UserSession(
        session_id=session_id,
        user_id=user_id,
        device_info=device_info,
        ip_address=ip_address,
        expires_at=expires_at
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return session_id

def invalidate_user_session(db: Session, session_id: str) -> bool:
    """Invalidate a specific session"""
    session = db.query(models.UserSession).filter(
        models.UserSession.session_id == session_id,
        models.UserSession.is_active == True
    ).first()
    
    if session:
        session.is_active = False
        db.commit()
        return True
    return False

def is_session_valid(db: Session, session_id: str) -> bool:
    """Check if session is valid and active"""
    session = db.query(models.UserSession).filter(
        models.UserSession.session_id == session_id,
        models.UserSession.is_active == True,
        models.UserSession.expires_at > datetime.utcnow()
    ).first()
    
    if session:
        # Update last activity
        session.last_activity = datetime.utcnow()
        db.commit()
        return True
    return False

def verify_token(token: str):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_raw = payload.get("sub")
        user_type = payload.get("type")
        org_id_raw = payload.get("org_id")
        session_id = payload.get("session_id")

        # Check user_id, session_id and allowed roles
        if user_id_raw is None or user_type not in ["Admin", "Manager", "Viewer"] or session_id is None:
            raise HTTPException(status_code=401, detail="Invalid token or role")

        # Validate session
        if not is_session_valid(db, session_id):
            raise HTTPException(status_code=401, detail="Session expired or invalid. Please login again.")

        # Ensure numeric types for DB query comparisons (Postgres needs int for integer columns)
        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid token user id")

        org_id = None
        if org_id_raw is not None:
            try:
                org_id = int(org_id_raw)
            except (TypeError, ValueError):
                raise HTTPException(status_code=401, detail="Invalid token org id")

        # Fetch user from DB
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check organization match
        if org_id is None or user.org_id != org_id:
            raise HTTPException(status_code=403, detail="Organization mismatch")

        return user
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")

def get_current_super_admin(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_raw = payload.get("sub")
        user_type = payload.get("type")
        session_id = payload.get("session_id")

        if user_id_raw is None or user_type != "SuperAdmin" or session_id is None:
            raise HTTPException(status_code=401, detail="Invalid token for Super Admin")

        # Validate session for super admin
        if not is_session_valid(db, session_id):
            raise HTTPException(status_code=401, detail="Session expired or invalid. Please login again.")

        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid token user id")

        sadmin = db.query(models.Super_admin).filter(models.Super_admin.id == user_id).first()
        if not sadmin:
            raise HTTPException(status_code=404, detail="User not found")
        return sadmin
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(password):
    return pwd_context.hash(password)
