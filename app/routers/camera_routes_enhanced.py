"""
Enhanced camera routes with comprehensive VPN support and edge case handling
This file provides improved camera stream endpoints that handle:
- Users without VPN configuration
- Inactive/expired VPN configurations
- Fallback to local network URLs
- Detailed error messages and troubleshooting
- Network connectivity validation
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
import re
import ipaddress
from urllib.parse import urlparse

from ..database import get_db
from ..schemas import (
    EnhancedCameraStreamResponse, 
    CameraStreamsWithVPNResponse,
    VPNStatus
)
from ..auth import get_current_user
from ..services.wireguard_service import WireGuardService
from .. import models

router = APIRouter(prefix="/cameras-enhanced", tags=["Enhanced Camera Management with VPN"])
wg_service = WireGuardService()

def get_vpn_status(db: Session, user: models.User) -> VPNStatus:
    """Get comprehensive VPN status for user"""
    wg_config = wg_service.get_user_config(db, user)
    
    if not wg_config:
        return VPNStatus(
            has_config=False,
            is_active=False,
            is_expired=False,
            status_message="No VPN configuration found. Generate a VPN configuration to access cameras remotely.",
            next_action="Generate VPN configuration from /wireguard/generate-config endpoint"
        )
    
    is_expired = wg_config.expires_at and wg_config.expires_at < datetime.utcnow()
    
    if wg_config.status != "active":
        return VPNStatus(
            has_config=True,
            is_active=False,
            is_expired=is_expired,
            allocated_ip=wg_config.allocated_ip,
            expires_at=wg_config.expires_at,
            created_at=wg_config.created_at,
            status_message="VPN configuration exists but is inactive. Contact administrator to reactivate.",
            next_action="Contact administrator to reactivate VPN configuration"
        )
    
    if is_expired:
        return VPNStatus(
            has_config=True,
            is_active=False,
            is_expired=True,
            allocated_ip=wg_config.allocated_ip,
            expires_at=wg_config.expires_at,
            created_at=wg_config.created_at,
            status_message="VPN configuration has expired. Generate a new configuration.",
            next_action="Generate new VPN configuration from /wireguard/generate-config endpoint"
        )
    
    return VPNStatus(
        has_config=True,
        is_active=True,
        is_expired=False,
        allocated_ip=wg_config.allocated_ip,
        expires_at=wg_config.expires_at,
        created_at=wg_config.created_at,
        status_message="VPN configuration is active and ready for use.",
        next_action=None
    )

def build_rtsp_url(camera: models.Camera_details, target_ip: str, target_port: int, use_credentials: bool = True) -> str:
    """Build RTSP URL for camera with proper error handling"""
    try:
        # Get credentials
        credentials = ""
        if use_credentials and camera.username:
            # Note: We're using password_hash field but it should ideally be plain password
            # In a real implementation, you'd want a separate password field or decrypt this
            password = camera.password_hash or ""
            credentials = f"{camera.username}:{password}@"
        
        # Get stream path
        stream_path = camera.stream_url or "/cam/realmonitor?channel=1&subtype=0"
        if not stream_path.startswith('/'):
            stream_path = f"/{stream_path}"
        
        # Handle case where stream_url is already a full RTSP URL
        if camera.stream_url and camera.stream_url.startswith('rtsp://'):
            # Extract path from full URL
            parsed = urlparse(camera.stream_url)
            stream_path = parsed.path
            if parsed.query:
                stream_path += f"?{parsed.query}"
        
        return f"rtsp://{credentials}{target_ip}:{target_port}{stream_path}"
        
    except Exception as e:
        # Return a basic URL if construction fails
        return f"rtsp://{target_ip}:{target_port}/stream"

def validate_camera_config(camera: models.Camera_details) -> dict:
    """Validate camera configuration and return issues"""
    issues = []
    
    if not camera.camera_ip:
        issues.append("Camera IP address is missing")
    else:
        try:
            ipaddress.ip_address(camera.camera_ip)
        except ValueError:
            issues.append("Camera IP address is invalid")
    
    if not camera.port:
        issues.append("Camera port is missing - using default 554")
    
    if not camera.username:
        issues.append("Camera username is missing - authentication may fail")
    
    if not camera.password_hash:
        issues.append("Camera password is missing - authentication may fail")
    
    if not camera.stream_url:
        issues.append("Stream URL is missing - using default path")
    
    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "severity": "high" if any("missing" in issue for issue in issues) else "low"
    }

@router.get('/streams', response_model=CameraStreamsWithVPNResponse)
async def get_enhanced_camera_streams(
    include_local: bool = Query(False, description="Include local network URLs as fallback"),
    validate_config: bool = Query(True, description="Validate camera configurations"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get camera streams with comprehensive VPN support and edge case handling.
    
    This endpoint provides:
    - VPN-ready RTSP URLs when VPN is available
    - Local network URLs as fallback when requested
    - Detailed VPN status information
    - Configuration validation and troubleshooting
    - Clear error messages and next steps for users
    """
    
    # Get VPN status
    vpn_status = get_vpn_status(db, current_user)
    
    # Get cameras for user's organization
    cameras = db.query(models.Camera_details).filter(
        models.Camera_details.organization_id == current_user.org_id
    ).all()
    
    if not cameras:
        return CameraStreamsWithVPNResponse(
            vpn_status=vpn_status,
            cameras_count=0,
            cameras=[],
            available_actions=[
                "Add cameras using POST /cameras/",
                "Contact administrator to add cameras to your organization"
            ]
        )
    
    camera_responses = []
    available_actions = []
    
    # Determine available actions based on VPN status
    if not vpn_status.has_config:
        available_actions.extend([
            "Generate VPN configuration: POST /wireguard/generate-config",
            "View cameras with local network URLs by setting include_local=true"
        ])
    elif not vpn_status.is_active or vpn_status.is_expired:
        available_actions.extend([
            "Regenerate VPN configuration: POST /wireguard/generate-config",
            "Contact administrator for VPN access"
        ])
    else:
        available_actions.extend([
            "Connect to VPN to access camera streams",
            "Download VPN configuration file",
            "Test VPN connectivity"
        ])
    
    # Process each camera
    for camera in cameras:
        # Validate camera configuration
        config_validation = validate_camera_config(camera) if validate_config else {"is_valid": True, "issues": []}
        
        # Determine ports
        default_rtsp_port = 554
        external_port = camera.port if camera.port else str(default_rtsp_port)
        try:
            external_port_int = int(external_port)
        except (ValueError, TypeError):
            external_port_int = default_rtsp_port
        
        # Initialize response object
        camera_response = EnhancedCameraStreamResponse(
            id=camera.id,
            name=camera.name,
            camera_ip=camera.camera_ip,
            port=external_port_int,
            stream_url=camera.stream_url,
            status=camera.status,
            location=camera.location,
            resolution=camera.resolution,
            features=camera.features,
            last_active=camera.last_active,
            vpn_status="not_configured",
            vpn_connectivity="unknown"
        )
        
        # Build local network URL if requested or as fallback
        if include_local or not vpn_status.is_active:
            try:
                local_url = build_rtsp_url(camera, camera.camera_ip, external_port_int)
                camera_response.local_stream_url = local_url
            except Exception as e:
                camera_response.local_stream_url = None
                camera_response.error_message = f"Failed to build local URL: {str(e)}"
        
        # Build VPN URL if VPN is available
        if vpn_status.is_active and not vpn_status.is_expired:
            try:
                vpn_ip = vpn_status.allocated_ip.split('/')[0] if vpn_status.allocated_ip else None
                if vpn_ip:
                    vpn_url = build_rtsp_url(camera, vpn_ip, external_port_int)
                    camera_response.vpn_stream_url = vpn_url
                    camera_response.vpn_status = "available"
                    camera_response.vpn_connectivity = "ready"
                else:
                    camera_response.vpn_status = "unavailable"
                    camera_response.error_message = "VPN IP address not available"
            except Exception as e:
                camera_response.vpn_status = "unavailable"
                camera_response.error_message = f"Failed to build VPN URL: {str(e)}"
        elif vpn_status.is_expired:
            camera_response.vpn_status = "expired"
            camera_response.error_message = "VPN configuration has expired"
        elif vpn_status.has_config and not vpn_status.is_active:
            camera_response.vpn_status = "inactive"
            camera_response.error_message = "VPN configuration is inactive"
        else:
            camera_response.vpn_status = "not_configured"
            camera_response.error_message = "No VPN configuration found"
        
        # Add troubleshooting information
        troubleshooting = {}
        
        if not config_validation["is_valid"]:
            troubleshooting["configuration_issues"] = config_validation["issues"]
        
        if camera_response.vpn_status != "available":
            troubleshooting["vpn_issues"] = [
                f"VPN Status: {vpn_status.status_message}",
                f"Next Action: {vpn_status.next_action}" if vpn_status.next_action else "No action required"
            ]
        
        if not camera.camera_ip:
            troubleshooting["network_issues"] = ["Camera IP address is not configured"]
        
        if troubleshooting:
            camera_response.troubleshooting_info = troubleshooting
        
        camera_responses.append(camera_response)
    
    return CameraStreamsWithVPNResponse(
        vpn_status=vpn_status,
        cameras_count=len(camera_responses),
        cameras=camera_responses,
        available_actions=available_actions
    )

@router.get('/streams/{camera_id}', response_model=EnhancedCameraStreamResponse)
async def get_enhanced_single_camera_stream(
    camera_id: int = Path(..., description="Camera ID to get stream URLs for"),
    include_local: bool = Query(False, description="Include local network URL as fallback"),
    validate_config: bool = Query(True, description="Validate camera configuration"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get a specific camera's stream URLs with comprehensive VPN support.
    
    Provides detailed information about VPN status, configuration issues,
    and troubleshooting guidance for a single camera.
    """
    
    # Get VPN status
    vpn_status = get_vpn_status(db, current_user)
    
    # Get the specific camera
    camera = db.query(models.Camera_details).filter(
        models.Camera_details.id == camera_id,
        models.Camera_details.organization_id == current_user.org_id
    ).first()
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found or you don't have permission to access it."
        )
    
    # Validate camera configuration
    config_validation = validate_camera_config(camera) if validate_config else {"is_valid": True, "issues": []}
    
    # Determine ports
    default_rtsp_port = 554
    external_port = camera.port if camera.port else str(default_rtsp_port)
    try:
        external_port_int = int(external_port)
    except (ValueError, TypeError):
        external_port_int = default_rtsp_port
    
    # Initialize response
    camera_response = EnhancedCameraStreamResponse(
        id=camera.id,
        name=camera.name,
        camera_ip=camera.camera_ip,
        port=external_port_int,
        stream_url=camera.stream_url,
        status=camera.status,
        location=camera.location,
        resolution=camera.resolution,
        features=camera.features,
        last_active=camera.last_active,
        vpn_status="not_configured",
        vpn_connectivity="unknown"
    )
    
    # Build local network URL if requested
    if include_local:
        try:
            local_url = build_rtsp_url(camera, camera.camera_ip, external_port_int)
            camera_response.local_stream_url = local_url
        except Exception as e:
            camera_response.error_message = f"Failed to build local URL: {str(e)}"
    
    # Build VPN URL if available
    if vpn_status.is_active and not vpn_status.is_expired:
        try:
            vpn_ip = vpn_status.allocated_ip.split('/')[0] if vpn_status.allocated_ip else None
            if vpn_ip:
                vpn_url = build_rtsp_url(camera, vpn_ip, external_port_int)
                camera_response.vpn_stream_url = vpn_url
                camera_response.vpn_status = "available"
                camera_response.vpn_connectivity = "ready"
            else:
                camera_response.vpn_status = "unavailable"
                camera_response.error_message = "VPN IP address not available"
        except Exception as e:
            camera_response.vpn_status = "unavailable"
            camera_response.error_message = f"Failed to build VPN URL: {str(e)}"
    elif vpn_status.is_expired:
        camera_response.vpn_status = "expired"
        camera_response.error_message = "VPN configuration has expired"
    elif vpn_status.has_config and not vpn_status.is_active:
        camera_response.vpn_status = "inactive"
        camera_response.error_message = "VPN configuration is inactive"
    else:
        camera_response.vpn_status = "not_configured"
        camera_response.error_message = "No VPN configuration found"
    
    # Add troubleshooting information
    troubleshooting = {}
    
    if not config_validation["is_valid"]:
        troubleshooting["configuration_issues"] = config_validation["issues"]
        troubleshooting["configuration_severity"] = config_validation["severity"]
    
    if camera_response.vpn_status != "available":
        troubleshooting["vpn_status"] = vpn_status.status_message
        if vpn_status.next_action:
            troubleshooting["recommended_action"] = vpn_status.next_action
    
    # Network diagnostics
    network_info = {}
    if camera.camera_ip:
        network_info["camera_ip"] = camera.camera_ip
        network_info["external_port"] = external_port_int
        network_info["local_rtsp_url"] = f"rtsp://{camera.camera_ip}:{external_port_int}"
    
    if vpn_status.allocated_ip:
        vpn_ip = vpn_status.allocated_ip.split('/')[0]
        network_info["vpn_ip"] = vpn_ip
        network_info["vpn_rtsp_url"] = f"rtsp://{vpn_ip}:{external_port_int}"
    
    troubleshooting["network_information"] = network_info
    
    camera_response.troubleshooting_info = troubleshooting
    
    return camera_response

@router.get('/vpn-status')
async def get_vpn_status_for_cameras(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get detailed VPN status information for camera access.
    
    This endpoint helps users understand their VPN configuration status
    and what actions they need to take to access cameras remotely.
    """
    
    vpn_status = get_vpn_status(db, current_user)
    
    # Additional information for troubleshooting
    additional_info = {
        "total_cameras": db.query(models.Camera_details).filter(
            models.Camera_details.organization_id == current_user.org_id
        ).count(),
        "active_cameras": db.query(models.Camera_details).filter(
            models.Camera_details.organization_id == current_user.org_id,
            models.Camera_details.status == "active"
        ).count(),
        "vpn_endpoints": {
            "generate_config": "/wireguard/generate-config",
            "get_config": "/wireguard/config",
            "revoke_config": "/wireguard/config"
        },
        "camera_endpoints": {
            "enhanced_streams": "/cameras-enhanced/streams",
            "single_stream": "/cameras-enhanced/streams/{camera_id}",
            "with_local_fallback": "/cameras-enhanced/streams?include_local=true"
        }
    }
    
    return {
        "vpn_status": vpn_status,
        "additional_info": additional_info,
        "recommendations": _get_recommendations_based_on_status(vpn_status)
    }

def _get_recommendations_based_on_status(vpn_status: VPNStatus) -> List[str]:
    """Get recommendations based on VPN status"""
    recommendations = []
    
    if not vpn_status.has_config:
        recommendations.extend([
            "1. Generate a VPN configuration using POST /wireguard/generate-config",
            "2. Download and install the VPN configuration file",
            "3. Connect to the VPN to access cameras remotely",
            "4. Use include_local=true parameter to view local network URLs as fallback"
        ])
    elif vpn_status.is_expired:
        recommendations.extend([
            "1. Your VPN configuration has expired",
            "2. Generate a new configuration using POST /wireguard/generate-config",
            "3. Remove the old configuration from your VPN client",
            "4. Install and connect with the new configuration"
        ])
    elif not vpn_status.is_active:
        recommendations.extend([
            "1. Your VPN configuration exists but is inactive",
            "2. Contact your administrator to reactivate the configuration",
            "3. Check if there are any organization-level VPN restrictions"
        ])
    else:
        recommendations.extend([
            "1. Your VPN configuration is active and ready",
            "2. Connect to the VPN to access cameras remotely",
            "3. Use the enhanced camera streams endpoint for best experience",
            "4. Monitor VPN connectivity status in the camera responses"
        ])
    
    return recommendations
