from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from pydantic import EmailStr
from ..database import get_db
from ..schemas import UserLogin, UserCreate, Token, SuccessResponse, UserResponse
from ..auth import authenticate_user, get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_DAYS, pwd_context
from .. import models

import random

from ..utils.otp_utils import send_email_otp_for_verification, send_email_otp, otp_storage
from ..utils.token_utils import get_client_ip

ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter(prefix="/me", tags=["User Profile Details"])

@router.get('/profile')
async def get_my_profile_detail(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Fetch latest IP record for the logged-in user
    ip_data = db.query(models.IPAddress).filter(
        models.IPAddress.user_id == current_user.id
    ).order_by(models.IPAddress.last_login.desc()).first()

    return {
        "organization_id": current_user.org_id,
        "organization_name": current_user.org.name if current_user.org else None,
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "role": current_user.role.name if current_user.role else None,
            "ip_address": ip_data.ip_address if ip_data else None,
            "created_at": ip_data.created_at if ip_data else None,
            "last_login": ip_data.last_login if ip_data else None
        }
    }
