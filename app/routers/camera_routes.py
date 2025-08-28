from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, Path
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from pydantic import EmailStr
from typing import List
import re
from ..database import get_db
from ..schemas import UserLogin, UserCreate, Token, SuccessResponse, UserResponse, CameraConfigSchema, CameraStreamResponse
from ..auth import get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_DAYS, pwd_context
from ..services.wireguard_service import WireGuardService
from .. import models

import random

from ..utils.otp_utils import send_email_otp_for_verification, send_email_otp, otp_storage
from ..utils.token_utils import get_client_ip

ACCESS_TOKEN_EXPIRE_MINUTES = 720

router = APIRouter(prefix="/cameras", tags=["Camera Management"])
wg_service = WireGuardService()

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


def transform_rtsp_url_for_vpn(stream_url: str, camera_ip: str, local_port: str, vpn_ip: str, external_port: str) -> str:
    """
    Transform local RTSP URL to use VPN IP and external port.
    
    Args:
        stream_url: Original stream URL (e.g., /cam/realmonitor?channel=1&subtype=0)
        camera_ip: Original camera IP (e.g., 192.168.88.200)  
        local_port: Original camera port (e.g., 554) - not used in transformation
        vpn_ip: User's WireGuard IP (e.g., 10.0.0.4)
        external_port: External port for VPN access (e.g., 8551)
    
    Returns:
        Transformed RTSP URL with VPN IP and external port
    """
    try:
        # Handle cases where stream_url might be a complete RTSP URL
        if stream_url.startswith('rtsp://'):
            # Extract credentials and path from full URL
            rtsp_pattern = r'rtsp://([^@]+)@([^:]+):(\d+)(.*)'
            match = re.match(rtsp_pattern, stream_url)
            if match:
                credentials, _, _, path = match.groups()
                return f"rtsp://{credentials}@{vpn_ip}:{external_port}{path}"
            else:
                # Fallback: replace IP and port in the URL
                # Replace any IP:PORT pattern with VPN_IP:EXTERNAL_PORT
                ip_port_pattern = r'@([^:]+):(\d+)'
                return re.sub(ip_port_pattern, f'@{vpn_ip}:{external_port}', stream_url)
        else:
            # stream_url is just the path part, we need to construct full URL
            # This will be handled in the endpoint
            return stream_url
            
    except Exception as e:
        # If transformation fails, return original URL
        return stream_url


@router.get('/vpn-streams', response_model=List[CameraStreamResponse])
async def get_camera_streams_for_vpn(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get all available cameras with RTSP URLs transformed for VPN access.
    
    This endpoint returns camera streaming URLs with the user's WireGuard VPN IP 
    and external ports instead of local network IPs and ports.
    
    Example transformation:
    - Original: rtsp://admin:industry4@192.168.88.200:554/cam/realmonitor?channel=1&subtype=0
    - VPN: rtsp://admin:industry4@10.0.0.4:8551/cam/realmonitor?channel=1&subtype=0
    """
    
    # Get user's WireGuard configuration
    wg_config = wg_service.get_user_config(db, current_user)
    if not wg_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No WireGuard configuration found for user. Please generate a VPN configuration first."
        )
    
    if wg_config.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WireGuard configuration is not active. Please contact administrator."
        )
    
    # Get user's WireGuard IP (remove subnet mask if present)
    vpn_ip = wg_config.allocated_ip.split('/')[0]
    
    # Get all cameras for the user's organization
    cameras = db.query(models.Camera_details).filter(
        models.Camera_details.organization_id == current_user.org_id,
        models.Camera_details.status == "active"  # Only return active cameras
    ).all()
    
    if not cameras:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active cameras found for your organization."
        )
    
    camera_streams = []
    for camera in cameras:
        try:
            # Use the port field as the external port for VPN access
            external_port = camera.port if camera.port else "8551"
            
            # Construct the VPN-accessible RTSP URL
            vpn_stream_url = ""
            
            if camera.stream_url and camera.username and camera.password_hash:
                if camera.stream_url.startswith('rtsp://'):
                    # Full RTSP URL provided - transform it to use VPN IP and external port
                    vpn_stream_url = transform_rtsp_url_for_vpn(
                        camera.stream_url, 
                        camera.camera_ip, 
                        str(camera.port),  # local port (not used in transformation)
                        vpn_ip, 
                        str(external_port)
                    )
                else:
                    # Stream URL is just the path, construct full RTSP URL
                    vpn_stream_url = f"rtsp://{camera.username}:{camera.password_hash}@{vpn_ip}:{external_port}{camera.stream_url}"
            else:
                # Construct basic RTSP URL if stream_url is not complete
                credentials = ""
                if camera.username and camera.password_hash:
                    credentials = f"{camera.username}:{camera.password_hash}@"
                
                # Default path if stream_url is empty
                path = camera.stream_url if camera.stream_url else "/cam/realmonitor?channel=1&subtype=0"
                if not path.startswith('/'):
                    path = f"/{path}"
                    
                vpn_stream_url = f"rtsp://{credentials}{vpn_ip}:{external_port}{path}"
            
            camera_stream = CameraStreamResponse(
                id=camera.id,
                name=camera.name,
                camera_ip=camera.camera_ip,
                port=camera.port,
                stream_url=camera.stream_url,
                vpn_stream_url=vpn_stream_url,
                status=camera.status,
                location=camera.location,
                resolution=camera.resolution,
                features=camera.features,
                last_active=camera.last_active
            )
            
            camera_streams.append(camera_stream)
            
        except Exception as e:
            # Log error but continue with other cameras
            print(f"Error processing camera {camera.id}: {str(e)}")
            continue
    
    if not camera_streams:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process camera streams. Please check camera configurations."
        )
    
    return camera_streams


@router.get('/vpn-streams/{camera_id}', response_model=CameraStreamResponse)
async def get_single_camera_stream_for_vpn(
    camera_id: int = Path(..., description="Camera ID to get VPN stream URL for"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get a specific camera's RTSP URL transformed for VPN access.
    
    This endpoint returns a single camera's streaming URL with the user's WireGuard VPN IP 
    and external port instead of local network IP and port.
    """
    
    # Get user's WireGuard configuration
    wg_config = wg_service.get_user_config(db, current_user)
    if not wg_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No WireGuard configuration found for user. Please generate a VPN configuration first."
        )
    
    if wg_config.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WireGuard configuration is not active. Please contact administrator."
        )
    
    # Get the specific camera
    camera = db.query(models.Camera_details).filter(
        models.Camera_details.id == camera_id,
        models.Camera_details.organization_id == current_user.org_id
    ).first()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found or you don't have permission to access it."
        )
    
    # Get user's WireGuard IP (remove subnet mask if present)
    vpn_ip = wg_config.allocated_ip.split('/')[0]
    
    # Use the port field as the external port for VPN access
    external_port = camera.port if camera.port else "8551"
    
    # Construct the VPN-accessible RTSP URL
    vpn_stream_url = ""
    
    try:
        if camera.stream_url and camera.username and camera.password_hash:
            if camera.stream_url.startswith('rtsp://'):
                # Full RTSP URL provided - transform it to use VPN IP and external port
                vpn_stream_url = transform_rtsp_url_for_vpn(
                    camera.stream_url, 
                    camera.camera_ip, 
                    str(camera.port),  # local port (not used in transformation)
                    vpn_ip, 
                    str(external_port)
                )
            else:
                # Stream URL is just the path, construct full RTSP URL
                vpn_stream_url = f"rtsp://{camera.username}:{camera.password_hash}@{vpn_ip}:{external_port}{camera.stream_url}"
        else:
            # Construct basic RTSP URL if stream_url is not complete
            credentials = ""
            if camera.username and camera.password_hash:
                credentials = f"{camera.username}:{camera.password_hash}@"
            
            # Default path if stream_url is empty
            path = camera.stream_url if camera.stream_url else "/cam/realmonitor?channel=1&subtype=0"
            if not path.startswith('/'):
                path = f"/{path}"
                
            vpn_stream_url = f"rtsp://{credentials}{vpn_ip}:{external_port}{path}"
        
        camera_stream = CameraStreamResponse(
            id=camera.id,
            name=camera.name,
            camera_ip=camera.camera_ip,
            port=camera.port,
            stream_url=camera.stream_url,
            vpn_stream_url=vpn_stream_url,
            status=camera.status,
            location=camera.location,
            resolution=camera.resolution,
            features=camera.features,
            last_active=camera.last_active
        )
        
        return camera_stream
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process camera stream: {str(e)}"
        )
