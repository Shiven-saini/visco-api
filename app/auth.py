from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from . import models
from .database import get_db
from passlib.context import CryptContext


# JWT Configuration
SECRET_KEY = "G4sZ7NnhIjzpLxunrCh14T2N50pwkMJiVMzyF6cVAl8="  # Generated using : openssl rand -base64 32
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

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
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        user_type = payload.get("type")
        org_id = payload.get("org_id")

        # ✅ Check user_id and allowed roles
        if user_id is None or user_type not in ["Admin", "Manager", "Viewer"]:
            raise HTTPException(status_code=401, detail="Invalid token or role")

        # ✅ Fetch user from DB
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # ✅ Check organization match
        if org_id is None or user.org_id != org_id:
            raise HTTPException(status_code=403, detail="Organization mismatch")

        return user
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(password):
    return pwd_context.hash(password)
