from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from pydantic import EmailStr
from ..database import get_db
from ..schemas import UserLogin, UserCreate, Token, SuccessResponse, UserResponse, ManageAlertSchema
from ..auth import authenticate_user, get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_DAYS, pwd_context
from .. import models

import random

from ..utils.otp_utils import send_email_otp_for_verification, send_email_otp, otp_storage
from ..utils.token_utils import get_client_ip

ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter(prefix="/alerts", tags=["Alerts Management"])

@router.post('/')
async def admin_add_alert(
    payload: ManageAlertSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only Admin and Manager can add alert
    if current_user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin and Manager can add alert"
        )

    # ✅ Check for duplicate rule_name + camera_name
    existing_alert = (
        db.query(models.Manage_Alert)
        .filter(models.Manage_Alert.rule_name == payload.rule_name)
        .filter(models.Manage_Alert.apply_to_camera == payload.camera_name)
        .first()
    )
    if existing_alert:
        raise HTTPException(
            status_code=400,
            detail="This Rule Name is already in use for this camera"
        )

    # ✅ Add new alert
    new_alert = models.Manage_Alert(
        rule_name=payload.rule_name,
        user_id=payload.user_id,
        description=payload.description,
        alert_type=payload.alert_type,
        apply_to_camera=payload.camera_name,
        servity_level=payload.servity_level,
        notification_method=payload.notification_method,  # store as JSON in DB
        status=payload.status,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)

    return {
        "msg": "Alert added successfully.",
        "alert_id": new_alert.id,
        "alert_name": new_alert.rule_name
    }

@router.get('/')
async def admin_get_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only Admin and Manager and viewer can see alerts
    if current_user.role.name not in ["Admin", "Manager","Viewer"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin and Manager and Viewer can view alerts"
        )

    alerts = db.query(models.Manage_Alert).all()

    return {
        "count": len(alerts),
        "data": [
            {
                "id": alert.id,
                "user_id": alert.user_id,
                "rule_name": alert.rule_name,
                "description": alert.description,
                "alert_type": alert.alert_type,
                "apply_to_camera": alert.apply_to_camera,
                "servity_level": alert.servity_level,
                "notification_method": alert.notification_method,
                "status": alert.status,
                "created_at": alert.created_at,
                "updated_at": alert.updated_at
            }
            for alert in alerts
        ]
    }    

@router.put('/{alert_id}')
async def admin_update_alert(
    alert_id: int,
    payload: ManageAlertSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(status_code=403, detail="Only Admin and Manager can update alerts")

    alert = db.query(models.Manage_Alert).filter(models.Manage_Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Update fields
    alert.rule_name = payload.rule_name
    alert.user_id = payload.user_id
    alert.description = payload.description
    alert.alert_type = payload.alert_type
    alert.apply_to_camera = payload.camera_name
    alert.servity_level = payload.servity_level
    alert.notification_method = payload.notification_method
    alert.status = payload.status
    db.commit()
    db.refresh(alert)

    return {"msg": "Alert updated successfully", "alert_id": alert.id}

@router.put('/{alert_id}/status')
async def admin_update_alert(
    alert_id: int,
    payload: models.AlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(status_code=403, detail="Only Admin and Manager can update alert's status")

    alert = db.query(models.Manage_Alert).filter(models.Manage_Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Update fields
    alert.status = payload.status
    alert.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)

    return {"msg": "Alert's status updated successfully", "alert_id": alert.id,"alert_status":alert.status}    

@router.delete('/{alert_id}')
async def admin_delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(status_code=403, detail="Only Admin and Manager can delete alerts")

    alert = db.query(models.Manage_Alert).filter(models.Manage_Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    db.delete(alert)
    db.commit()

    return {"msg": "Alert deleted successfully"}
