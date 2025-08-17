from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..schemas import (
    WireGuardConfigResponse, 
    WireGuardClientConfig, 
    SuccessResponse,
    WireGuardServerStatus
)
from ..services.wireguard_service import WireGuardService
from ..services.ip_manager import IPManager
from ..utils.system_utils import (
    append_peer_to_wg_config, 
    remove_peer_from_wg_config,
    get_wg_config_status
)
from ..dependencies import get_current_user
from .. import models

router = APIRouter(prefix="/wireguard", tags=["WireGuard Management"])

# Initialize services
wg_service = WireGuardService()
ip_manager = IPManager()

@router.post("/generate-config", response_model=WireGuardClientConfig)
def generate_wireguard_config(
    username: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate WireGuard configuration for the current user or specified username."""
    
    # Determine target user
    if username:
        # Admin functionality - get config for specified user
        target_user = db.query(models.User).filter(models.User.username == username).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found"
            )
    else:
        # Generate config for current user
        target_user = current_user
    
    # Check if user already has active config
    existing_config = wg_service.get_user_config(db, target_user)
    if existing_config:
        config_content = wg_service.generate_client_config_content(existing_config)
        return WireGuardClientConfig(
            config_content=config_content,
            allocated_ip=existing_config.allocated_ip,
            public_key=existing_config.public_key,
            expires_at=existing_config.expires_at
        )
    
    # Check available IPs
    if ip_manager.get_available_ip_count(db) <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No available IP addresses in the subnet"
        )
    
    # Create new config
    wg_config = wg_service.create_config(db, target_user)
    if not wg_config:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to allocate IP address"
        )
    
    # Add peer to server config
    peer_config = wg_service.generate_server_peer_config(wg_config)
    if not append_peer_to_wg_config(peer_config):
        # Rollback database changes
        db.delete(wg_config)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update server WireGuard configuration"
        )
    
    # Generate client config
    config_content = wg_service.generate_client_config_content(wg_config)
    
    return WireGuardClientConfig(
        config_content=config_content,
        allocated_ip=wg_config.allocated_ip,
        public_key=wg_config.public_key,
        expires_at=wg_config.expires_at
    )

@router.get("/config", response_model=WireGuardConfigResponse)
def get_user_wireguard_config(
    username: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get WireGuard configuration details for current user or specified username."""
    
    if username:
        config = wg_service.get_config_by_username(db, username)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No WireGuard config found for user '{username}'"
            )
        username_display = username
    else:
        config = wg_service.get_user_config(db, current_user)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No WireGuard configuration found for user"
            )
        username_display = current_user.username
    
    return WireGuardConfigResponse(
        id=config.id,
        user_id=config.user_id,
        username=username_display,
        public_key=config.public_key,
        allocated_ip=config.allocated_ip,
        status=config.status,
        created_at=config.created_at,
        expires_at=config.expires_at
    )

@router.delete("/config", response_model=SuccessResponse)
def revoke_wireguard_config(
    username: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke (delete) WireGuard configuration for current user or specified username."""
    
    # Determine target user
    if username:
        target_user = db.query(models.User).filter(models.User.username == username).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found"
            )
    else:
        target_user = current_user
    
    # Get existing config
    config = wg_service.get_user_config(db, target_user)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active WireGuard configuration found"
        )
    
    # Remove peer from server config
    if not remove_peer_from_wg_config(config.public_key):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove peer from server WireGuard configuration"
        )
    
    # Remove from database
    success = wg_service.revoke_config(db, target_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke WireGuard configuration"
        )
    
    return SuccessResponse(
        message=f"WireGuard configuration revoked successfully for user '{target_user.username}'",
        data={"freed_ip": config.allocated_ip}
    )

@router.get("/server-status", response_model=WireGuardServerStatus)
def get_wireguard_server_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get WireGuard server status and statistics."""
    
    # Get system status
    wg_status = get_wg_config_status()
    
    # Get database statistics
    active_configs = db.query(models.WireGuardConfig).filter(
        models.WireGuardConfig.status == "active"
    ).count()
    
    available_ips = ip_manager.get_available_ip_count(db)
    
    return WireGuardServerStatus(
        interface_up=wg_status.get("interface_up", False),
        active_peers=active_configs,
        available_ips=available_ips,
        total_configs=active_configs
    )
