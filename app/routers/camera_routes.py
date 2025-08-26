from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, Path
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from pydantic import EmailStr
from ..database import get_db
from ..schemas import UserLogin, UserCreate, Token, SuccessResponse, UserResponse, CameraConfigSchema
from ..auth import get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_DAYS, pwd_context
from .. import models

import random

from ..utils.otp_utils import send_email_otp_for_verification, send_email_otp, otp_storage
from ..utils.token_utils import get_client_ip

ACCESS_TOKEN_EXPIRE_MINUTES = 720

router = APIRouter(prefix="/cameras", tags=["Camera Management"])

@router.post('/')
async def admin_configure_camera(
    payload: CameraConfigSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only Admin can add/configure cameras
    if current_user.role.name != "Admin":
        raise HTTPException(status_code=403, detail="Only Admin can configure a camera")
    
    # Check for duplicate camera IP
    existing_camera = db.query(models.Camera_details).filter(models.Camera_details.camera_ip == payload.c_ip).first()
    if existing_camera:
        raise HTTPException(status_code=400, detail="This camera IP is already in use")

    # Add new camera
    new_camera = models.Camera_details(
        name=payload.name,
        # user_id=payload.user_id,
        # organization_id=payload.org_id,
        user_id=current_user.id,
        organization_id=current_user.org_id,
        camera_ip=payload.c_ip,
        status=payload.status,
        port=payload.port,
        stream_url=payload.stream_url,
        username=payload.username,
        password_hash=payload.password, 
    )
    db.add(new_camera)
    db.commit()
    db.refresh(new_camera)

    return {
        "msg": "Camera configured successfully.",
        "camera_id": new_camera.id,
        "camera_ip": new_camera.camera_ip
    }

@router.put('/{camera_id}')
async def admin_update_camera(
    payload: CameraConfigSchema,  # moved above
    camera_id: int = Path(..., description="Camera ID to update"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role.name != "Admin":
        raise HTTPException(status_code=403, detail="Only Admin can update a camera")

    camera = db.query(models.Camera_details).filter(models.Camera_details.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    if camera.organization_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Unauthorized to modify this camera")

    if payload.c_ip != camera.camera_ip:
        ip_conflict = db.query(models.Camera_details).filter(models.Camera_details.camera_ip == payload.c_ip).first()
        if ip_conflict:
            raise HTTPException(status_code=400, detail="This camera IP is already in use")

    camera.name = payload.name
    camera.camera_ip = payload.c_ip
    camera.status = payload.status
    camera.port = payload.port
    camera.stream_url = payload.stream_url
    camera.username = payload.username
    camera.password_hash = payload.password

    db.commit()
    db.refresh(camera)

    return {
        "message": "Camera updated successfully.",
        "camera": {
            "id": camera.id,
            "ip": camera.camera_ip,
            "name": camera.name,
            "status": camera.status
        }
    }

@router.delete('/{camera_id}')
async def admin_delete_camera(
    camera_id: int = Path(..., description="Camera ID to delete"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only Admin can delete cameras
    if current_user.role.name != "Admin":
        raise HTTPException(status_code=403, detail="Only Admin can delete a camera")

    # Fetch camera
    camera = db.query(models.Camera_details).filter(models.Camera_details.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Optional: Validate ownership/org
    if camera.organization_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Unauthorized to delete this camera")

    # Delete the camera
    db.delete(camera)
    db.commit()

    return {"message": "Camera deleted successfully."}
