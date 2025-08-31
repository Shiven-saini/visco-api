from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, Path, Query
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from pydantic import EmailStr
from typing import List
import re
from ..database import get_db
from ..schemas import UserLogin, UserCreate, Token, SuccessResponse, UserResponse, CameraConfigSchema, CameraStreamResponse
from ..auth import get_current_user, create_access_token, pwd_context
from ..config.settings import settings
from ..services.wireguard_service import WireGuardService
from .. import models

import random

from ..utils.otp_utils import send_email_otp_for_verification, send_email_otp, otp_storage
from ..utils.token_utils import get_client_ip

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

@router.get("/get-added-cameras")
async def get_admin_added_cameras(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    
    if current_user.role.name not in ["Admin", "Manager", "Viewer"]:
       raise HTTPException(status_code=403, detail="Only Admins, Managers, or Viewers can view cameras")

    # ✅ Fetch cameras created by the Admin in their organization
    cameras = db.query(models.Camera_details).filter(
        models.Camera_details.organization_id == current_user.org_id
    ).all()

    # ✅ If no cameras found
    if not cameras:
        return {"message": "No cameras configured yet."}

    # ✅ Return camera data
    return {
        "cameras": [
            {
                "camera_id": cam.id,
                "name": cam.name,
                "camera_ip": cam.camera_ip,
                "status": cam.status,
                "port": cam.port,
                "stream_url": cam.stream_url,
                "username": cam.username
            }
            for cam in cameras
        ]
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
    include_local_fallback: bool = Query(False, description="Include local network URLs when VPN is unavailable"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get all available cameras with RTSP URLs transformed for VPN access.
    
    This endpoint returns camera streaming URLs with the user's WireGuard VPN IP 
    and external ports instead of local network IPs and ports.
    
    Edge Cases Handled:
    - User hasn't joined WireGuard VPN: Returns helpful error message with guidance
    - VPN configuration exists but is inactive: Returns error with activation guidance  
    - VPN configuration is expired: Returns error with renewal guidance
    - include_local_fallback=true: Returns local network URLs as fallback
    
    Example transformation:
    - Original: rtsp://admin:industry4@192.168.88.200:554/cam/realmonitor?channel=1&subtype=0
    - VPN: rtsp://admin:industry4@10.0.0.4:8551/cam/realmonitor?channel=1&subtype=0
    """
    
    # Get user's WireGuard configuration
    wg_config = wg_service.get_user_config(db, current_user)
    
    # Handle case where user hasn't joined VPN yet
    if not wg_config:
        if include_local_fallback:
            # Provide local network URLs as fallback
            cameras = db.query(models.Camera_details).filter(
                models.Camera_details.organization_id == current_user.org_id
            ).all()
            
            if not cameras:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No cameras found for your organization."
                )
            
            # Return cameras with local network URLs and guidance
            camera_streams = []
            for camera in cameras:
                # Build local network RTSP URL
                external_port = camera.port if camera.port else "554"
                credentials = ""
                if camera.username and camera.password_hash:
                    credentials = f"{camera.username}:{camera.password_hash}@"
                
                path = camera.stream_url if camera.stream_url else "/cam/realmonitor?channel=1&subtype=0"
                if not path.startswith('/'):
                    path = f"/{path}"
                
                local_stream_url = f"rtsp://{credentials}{camera.camera_ip}:{external_port}{path}"
                
                camera_streams.append(CameraStreamResponse(
                    id=camera.id,
                    name=camera.name,
                    camera_ip=camera.camera_ip,
                    port=camera.port,
                    stream_url=camera.stream_url,
                    vpn_stream_url="VPN_NOT_CONFIGURED - Generate VPN config first: POST /wireguard/generate-config",
                    status=camera.status,
                    location=camera.location,
                    resolution=camera.resolution,
                    features=camera.features,
                    last_active=camera.last_active
                ))
            
            return camera_streams
        else:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail={
                    "error": "No WireGuard VPN configuration found",
                    "message": "You need to generate a VPN configuration before accessing camera streams remotely.",
                    "next_steps": [
                        "1. Generate VPN configuration: POST /wireguard/generate-config",
                        "2. Download and install the VPN configuration file on your device",
                        "3. Connect to the VPN", 
                        "4. Access this endpoint again to get VPN-enabled camera streams"
                    ],
                    "alternative": "Use include_local_fallback=true to get local network URLs for testing"
                }
            )
    
    # Handle case where VPN config exists but is inactive
    if wg_config.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "WireGuard VPN configuration is inactive",
                "message": "Your VPN configuration exists but is currently inactive.",
                "vpn_config_status": wg_config.status,
                "created_at": wg_config.created_at.isoformat() if wg_config.created_at else None,
                "next_steps": [
                    "1. Contact your administrator to reactivate your VPN configuration",
                    "2. Check if there are any organization-level restrictions",
                    "3. Try regenerating your VPN configuration if permitted"
                ],
                "alternative": "Use include_local_fallback=true to get local network URLs if you're on the same network"
            }
        )
    
    # Handle case where VPN config is expired
    if wg_config.expires_at and wg_config.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error": "WireGuard VPN configuration has expired", 
                "message": "Your VPN configuration expired and needs to be renewed.",
                "expired_at": wg_config.expires_at.isoformat(),
                "allocated_ip": wg_config.allocated_ip,
                "next_steps": [
                    "1. Generate a new VPN configuration: POST /wireguard/generate-config",
                    "2. Remove the old configuration from your VPN client",
                    "3. Install the new configuration file",
                    "4. Connect to the VPN with the new configuration"
                ],
                "alternative": "Use include_local_fallback=true to get local network URLs if you're on the same network"
            }
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
            detail={
                "error": "No active cameras found",
                "message": "No active cameras found for your organization.",
                "vpn_status": "ready",
                "vpn_ip": vpn_ip,
                "next_steps": [
                    "1. Add cameras to your organization: POST /cameras/",
                    "2. Ensure cameras are set to 'active' status",
                    "3. Contact administrator if cameras should be available"
                ]
            }
        )
    
    camera_streams = []
    processing_errors = []
    
    for camera in cameras:
        try:
            # Validate camera configuration
            if not camera.camera_ip:
                processing_errors.append(f"Camera '{camera.name}' (ID: {camera.id}) missing IP address")
                continue
            
            # Use the port field as the external port for VPN access
            external_port = camera.port if camera.port else "554"
            
            # Construct the VPN-accessible RTSP URL
            vpn_stream_url = ""
            local_stream_url = None
            
            if camera.stream_url and camera.username and camera.password_hash:
                if camera.stream_url.startswith('rtsp://'):
                    # Full RTSP URL provided - transform it to use VPN IP and external port
                    vpn_stream_url = transform_rtsp_url_for_vpn(
                        camera.stream_url, 
                        camera.camera_ip, 
                        str(camera.port) if camera.port else "554",
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
            
            # Include local stream URL if requested
            if include_local_fallback:
                credentials = ""
                if camera.username and camera.password_hash:
                    credentials = f"{camera.username}:{camera.password_hash}@"
                path = camera.stream_url if camera.stream_url else "/cam/realmonitor?channel=1&subtype=0"
                if not path.startswith('/'):
                    path = f"/{path}"
                local_stream_url = f"rtsp://{credentials}{camera.camera_ip}:{external_port}{path}"
            
            # Validate required fields and add warnings
            issues = []
            if not camera.username:
                issues.append("Missing camera username - authentication may fail")
            if not camera.password_hash:
                issues.append("Missing camera password - authentication may fail")  
            if not camera.stream_url:
                issues.append("Missing stream URL - using default path")
                
            # Add issues to vpn_stream_url as comments if any
            if issues:
                vpn_stream_url += f" # Issues: {'; '.join(issues)}"
            
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
            processing_errors.append(f"Error processing camera '{camera.name}' (ID: {camera.id}): {str(e)}")
            continue
    
    if not camera_streams:
        error_detail = {
            "error": "Failed to process camera streams",
            "message": "No cameras could be processed successfully.",
            "processing_errors": processing_errors,
            "troubleshooting": [
                "1. Check camera configurations (IP, port, credentials)",
                "2. Ensure cameras are accessible on the network",
                "3. Verify stream URLs are correct",
                "4. Contact administrator for assistance"
            ]
        }
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )
    
    # Include processing errors in response headers or logs if any
    if processing_errors:
        print("Camera processing warnings:", processing_errors)
    
    return camera_streams


@router.get('/vpn-streams/{camera_id}', response_model=CameraStreamResponse)
async def get_single_camera_stream_for_vpn(
    camera_id: int = Path(..., description="Camera ID to get VPN stream URL for"),
    include_local_fallback: bool = Query(False, description="Include local network URL when VPN is unavailable"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get a specific camera's RTSP URL transformed for VPN access.
    
    This endpoint returns a single camera's streaming URL with the user's WireGuard VPN IP 
    and external port instead of local network IP and port.
    
    Edge Cases Handled:
    - User hasn't joined WireGuard VPN: Returns helpful error message with guidance
    - VPN configuration exists but is inactive: Returns error with activation guidance  
    - VPN configuration is expired: Returns error with renewal guidance
    - Camera not found or no permission: Returns appropriate error
    - Camera configuration issues: Returns warnings with the stream URL
    - include_local_fallback=true: Returns local network URL when VPN unavailable
    """
    
    # Get the specific camera first
    camera = db.query(models.Camera_details).filter(
        models.Camera_details.id == camera_id,
        models.Camera_details.organization_id == current_user.org_id
    ).first()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Camera not found",
                "message": f"Camera with ID {camera_id} not found or you don't have permission to access it.",
                "camera_id": camera_id,
                "organization_id": current_user.org_id,
                "troubleshooting": [
                    "1. Verify the camera ID is correct",
                    "2. Check if the camera belongs to your organization",
                    "3. Ensure you have permission to access this camera",
                    "4. Contact administrator if camera should be available"
                ]
            }
        )
    
    # Get user's WireGuard configuration
    wg_config = wg_service.get_user_config(db, current_user)
    
    # Handle case where user hasn't joined VPN yet
    if not wg_config:
        if include_local_fallback:
            # Provide local network URL as fallback
            external_port = camera.port if camera.port else "554"
            credentials = ""
            if camera.username and camera.password_hash:
                credentials = f"{camera.username}:{camera.password_hash}@"
            
            path = camera.stream_url if camera.stream_url else "/cam/realmonitor?channel=1&subtype=0"
            if not path.startswith('/'):
                path = f"/{path}"
            
            local_stream_url = f"rtsp://{credentials}{camera.camera_ip}:{external_port}{path}"
            
            return CameraStreamResponse(
                id=camera.id,
                name=camera.name,
                camera_ip=camera.camera_ip,
                port=camera.port,
                stream_url=camera.stream_url,
                vpn_stream_url="VPN_NOT_CONFIGURED - Generate VPN config first: POST /wireguard/generate-config",
                status=camera.status,
                location=camera.location,
                resolution=camera.resolution,
                features=camera.features,
                last_active=camera.last_active
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY,
                detail={
                    "error": "No WireGuard VPN configuration found",
                    "message": "You need to generate a VPN configuration before accessing camera streams remotely.",
                    "camera_name": camera.name,
                    "camera_id": camera.id,
                    "next_steps": [
                        "1. Generate VPN configuration: POST /wireguard/generate-config",
                        "2. Download and install the VPN configuration file on your device",
                        "3. Connect to the VPN", 
                        "4. Access this endpoint again to get VPN-enabled camera stream"
                    ],
                    "alternative": f"Use include_local_fallback=true to get local network URL for testing: GET /cameras/vpn-streams/{camera_id}?include_local_fallback=true"
                }
            )
    
    # Handle case where VPN config exists but is inactive
    if wg_config.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "WireGuard VPN configuration is inactive",
                "message": "Your VPN configuration exists but is currently inactive.",
                "camera_name": camera.name,
                "camera_id": camera.id,
                "vpn_config_status": wg_config.status,
                "created_at": wg_config.created_at.isoformat() if wg_config.created_at else None,
                "next_steps": [
                    "1. Contact your administrator to reactivate your VPN configuration",
                    "2. Check if there are any organization-level restrictions",
                    "3. Try regenerating your VPN configuration if permitted"
                ],
                "alternative": f"Use include_local_fallback=true to get local network URL if you're on the same network: GET /cameras/vpn-streams/{camera_id}?include_local_fallback=true"
            }
        )
    
    # Handle case where VPN config is expired
    if wg_config.expires_at and wg_config.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error": "WireGuard VPN configuration has expired", 
                "message": "Your VPN configuration expired and needs to be renewed.",
                "camera_name": camera.name,
                "camera_id": camera.id,
                "expired_at": wg_config.expires_at.isoformat(),
                "allocated_ip": wg_config.allocated_ip,
                "next_steps": [
                    "1. Generate a new VPN configuration: POST /wireguard/generate-config",
                    "2. Remove the old configuration from your VPN client",
                    "3. Install the new configuration file",
                    "4. Connect to the VPN with the new configuration"
                ],
                "alternative": f"Use include_local_fallback=true to get local network URL if you're on the same network: GET /cameras/vpn-streams/{camera_id}?include_local_fallback=true"
            }
        )
    
    # Get user's WireGuard IP (remove subnet mask if present)
    vpn_ip = wg_config.allocated_ip.split('/')[0]
    
    # Use the port field as the external port for VPN access
    external_port = camera.port if camera.port else "554"
    
    # Construct the VPN-accessible RTSP URL
    vpn_stream_url = ""
    
    try:
        if camera.stream_url and camera.username and camera.password_hash:
            if camera.stream_url.startswith('rtsp://'):
                # Full RTSP URL provided - transform it to use VPN IP and external port
                vpn_stream_url = transform_rtsp_url_for_vpn(
                    camera.stream_url, 
                    camera.camera_ip, 
                    str(camera.port) if camera.port else "554",  # local port (not used in transformation)
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
        
        # Validate required fields and add warnings
        issues = []
        if not camera.username:
            issues.append("Missing camera username - authentication may fail")
        if not camera.password_hash:
            issues.append("Missing camera password - authentication may fail")  
        if not camera.stream_url:
            issues.append("Missing stream URL - using default path")
        if not camera.camera_ip:
            issues.append("Missing camera IP address - this will cause connection issues")
            
        # Add issues to vpn_stream_url as comments if any
        if issues:
            vpn_stream_url += f" # Configuration Issues: {'; '.join(issues)}"
        
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
            detail={
                "error": "Failed to process camera stream",
                "message": f"Failed to generate VPN stream URL for camera '{camera.name}'",
                "camera_id": camera.id,
                "technical_error": str(e),
                "troubleshooting": [
                    "1. Check camera configuration (IP, port, credentials, stream URL)",
                    "2. Verify camera is accessible on the network",
                    "3. Ensure stream URL format is correct",
                    "4. Try accessing with include_local_fallback=true for local testing",
                    "5. Contact administrator for technical support"
                ]
            }
        )

@router.get("/get-queue-details/{camera_name}")
async def get_single_camera_queue_monitoring(
    camera_name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # ✅ Check role permissions
    if current_user.role.name not in ["Admin", "Manager", "Viewer"]:
        raise HTTPException(
            status_code=403,
            detail="Only Admins, Managers, or Viewers can view queue details"
        )

    # ✅ Fetch camera details
    camera = db.query(models.Camera_details).filter(
        models.Camera_details.organization_id == current_user.org_id,
        models.Camera_details.name == camera_name
    ).first()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # ✅ Fetch **last 800** queue monitoring records
    queue_data_list = (
        db.query(models.QueueMonitoring)
        .filter(models.QueueMonitoring.camera_id == str(camera.name))
        .order_by(models.QueueMonitoring.created_at.desc())
        .limit(800)
        .all()
    )

    # ✅ If no data found
    if not queue_data_list:
        return {
            "camera_id": camera.id,
            "name": camera.name,
            "camera_ip": camera.camera_ip,
            "status": camera.status,
            "port": camera.port,
            "stream_url": camera.stream_url,
            "username": camera.username,
            "queue_details": []
        }

    # ✅ Format the data in a list
    queue_details = [
        {
            "frame_id": q.frame_id,
            "time_stamp": q.time_stamp,
            "queue_count": q.queue_count,
            "queue_name": q.queue_name,
            "queue_length": q.queue_length,
            "front_person_wt": q.front_person_wt,
            "average_wt_time": q.average_wt_time,
            "status": q.status,
            "total_people_detected": q.total_people_detected,
            "people_ids": q.people_ids,
            "queue_assignment": q.queue_assignment,
            "entry_time": q.entry_time,
            "people_wt_time": q.people_wt_time,
            "processing_status": q.processing_status,
            "created_at": q.created_at,
        }
        for q in queue_data_list
    ]

    # ✅ Return camera + last 800 queue monitoring records
    return {
        "camera_id": camera.id,
        "name": camera.name,
        "camera_ip": camera.camera_ip,
        "status": camera.status,
        "port": camera.port,
        "stream_url": camera.stream_url,
        "username": camera.username,
        "queue_details": queue_details
    }
       
