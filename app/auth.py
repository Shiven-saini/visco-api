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
        "type": data.get("type")  # example: "admin" or "super_admin"
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

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

        # Check user_id and allowed roles
        if user_id_raw is None or user_type not in ["Admin", "Manager", "Viewer"]:
            raise HTTPException(status_code=401, detail="Invalid token or role")

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

        if user_id_raw is None or user_type != "SuperAdmin":
            raise HTTPException(status_code=401, detail="Invalid token for Super Admin")

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
