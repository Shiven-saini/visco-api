from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from pydantic import EmailStr
from ..database import get_db
from ..schemas import Token, SuccessResponse, UserResponse,SubscriptionCreate
from ..auth import get_current_user, create_access_token, pwd_context
from ..config.settings import settings
from .. import models

import random

from ..utils.otp_utils import send_email_otp_for_verification, send_email_otp, otp_storage
from ..utils.token_utils import get_client_ip

ACCESS_TOKEN_EXPIRE_MINUTES = 720

router = APIRouter(tags=["Subscription And Payment"])

# Create subscription
@router.post("/subscriptions")
async def create_subscription(sub: SubscriptionCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == sub.user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ✅ Check if the user's role is Admin or Manager
    if user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription can only be created for Admin or Manager users."
        )
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=sub.duration_days)

    subscription = Subscription(
        user_id=sub.user_id,
        organization_id=sub.organization_id,
        plan=sub.plan,
        status="active",
        start_date=start_date,
        end_date=end_date,
        active=True,
        max_users=sub.max_users,
        max_cameras=5,
        storage_limit_gb=sub.storage_limit_gb,
        storage_limit_days=sub.storage_limit_days,
        price_monthly=0.00,
        price_yearly=0.00,
        features=sub.features or {}, 
    )

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return subscription
