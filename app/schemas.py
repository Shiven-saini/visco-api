from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
from enum import Enum

# User registration schema
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str

# User login schema
class UserLogin(BaseModel):
    username: str
    password: str

# User update schema
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None

# User response schema
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Token schema
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

# Session schemas
class SessionResponse(BaseModel):
    session_id: str
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    
    class Config:
        from_attributes = True

class ActiveSessionsResponse(BaseModel):
    active_sessions_count: int
    sessions: List[SessionResponse]

class LoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str
    session_id: str
    user: dict
    ip_address: Optional[str] = None
    last_login: Optional[datetime] = None

class LogoutResponse(BaseModel):
    message: str

# Standard API response schemas
class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[dict] = None

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None

# WireGuard Schemas
class WireGuardConfigCreate(BaseModel):
    username: Optional[str] = None  # For admin use

class WireGuardConfigResponse(BaseModel):
    id: int
    user_id: int
    username: str
    public_key: str
    allocated_ip: str
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class WireGuardClientConfig(BaseModel):
    config_content: str
    allocated_ip: str
    public_key: str
    expires_at: Optional[datetime] = None

class WireGuardServerStatus(BaseModel):
    interface_up: bool
    active_peers: int
    available_ips: int
    total_configs: int


class CameraConfigSchema(BaseModel):
    name: str
    # Local camera details (for reference)
    camera_ip: str  # Local camera IP (e.g., 192.168.1.100)
    camera_port: int  # Local camera RTSP port (e.g., 554)
    
    # WireGuard and external access details (for KVS streaming)
    wireguard_ip: str  # WireGuard IP of the device
    external_port: int  # External port for forwarding (e.g., 8551)
    
    status: str
    stream_url: str  # RTSP URL using WireGuard IP and external port
    username: str
    password: str

    # Backward compatibility fields
    c_ip: Optional[str] = None  # Will map to camera_ip
    port: Optional[int] = None  # Will map to external_port

# New schema for camera stream response
class CameraStreamResponse(BaseModel):
    id: int
    name: str
    camera_ip: str
    port: Optional[str] = None  # External port for VPN access
    stream_url: str
    vpn_stream_url: str  # The transformed URL with WireGuard IP
    status: str
    location: Optional[str] = None
    resolution: Optional[str] = None
    features: Optional[str] = None
    last_active: Optional[str] = None

    class Config:
        from_attributes = True

# Enhanced VPN status information
class VPNStatus(BaseModel):
    has_config: bool
    is_active: bool
    is_expired: bool
    allocated_ip: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    status_message: str
    next_action: Optional[str] = None  # What user should do next

# Enhanced camera stream response with VPN support and edge cases
class EnhancedCameraStreamResponse(BaseModel):
    id: int
    name: str
    camera_ip: str
    port: Optional[int] = None  # External port for VPN access
    stream_url: str
    vpn_stream_url: Optional[str] = None  # The transformed URL with WireGuard IP
    local_stream_url: Optional[str] = None  # Fallback local network URL
    status: str
    location: Optional[str] = None
    resolution: Optional[str] = None
    features: Optional[str] = None
    last_active: Optional[str] = None
    
    # VPN-specific information
    vpn_status: str  # "available", "unavailable", "inactive", "expired", "not_configured"
    vpn_connectivity: Optional[str] = None  # "connected", "disconnected", "unknown"
    error_message: Optional[str] = None
    troubleshooting_info: Optional[dict] = None

    class Config:
        from_attributes = True

# Comprehensive camera streams response with VPN status
class CameraStreamsWithVPNResponse(BaseModel):
    vpn_status: VPNStatus
    cameras_count: int
    cameras: List[EnhancedCameraStreamResponse]
    available_actions: List[str]  # Available actions user can take

class ManageAlertSchema(BaseModel):
    user_id : int
    rule_name : str
    description : str
    alert_type : str
    camera_name : str
    servity_level : str
    notification_method : list[str]
    status : str

class AlertStatusUpdate(BaseModel):
    status: str

class SubscriptionCreate(BaseModel):
    duration_days: int
    user_id: int
    user_email: str
    organization_id: int
    plan: str
    status: str
    start_date: datetime
    end_date: datetime
    max_users: int
    max_cameras: int
    storage_limit_gb: int
    storage_limit_days: int
    price_monthly: Optional[float]
    features: Optional[Dict] = None
    price_yearly: Optional[float]
    active: bool

# KVS Stream Management Schemas
class StreamStartRequest(BaseModel):
    camera_id: int
    custom_stream_name: Optional[str] = None  # Optional custom name, will auto-generate if not provided

class StreamStartResponse(BaseModel):
    stream_id: int
    stream_name: str
    kvs_stream_name: str
    camera_name: str
    rtsp_url: str
    status: str
    message: str
    
    class Config:
        from_attributes = True

class StreamStopRequest(BaseModel):
    force: bool = False  # Force stop even if process is not responding

class StreamStopResponse(BaseModel):
    stream_id: int
    stream_name: str
    previous_status: str
    current_status: str
    message: str
    
    class Config:
        from_attributes = True

class StreamStatusResponse(BaseModel):
    stream_id: int
    stream_name: str
    kvs_stream_name: str
    user_id: int
    username: str
    camera_id: int
    camera_name: str
    rtsp_url: str
    status: str
    process_id: Optional[int] = None
    process_status: Optional[str] = None
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    stop_time: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    restart_count: int = 0
    uptime_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserStreamsSummary(BaseModel):
    user_id: int
    username: str
    organization_name: str
    total_streams: int
    active_streams: int
    stopped_streams: int
    error_streams: int
    streams: List[StreamStatusResponse]

class StreamBulkOperationResponse(BaseModel):
    user_id: int
    operation: str  # start_all, stop_all
    total_cameras: int
    successful_operations: int
    failed_operations: int
    results: List[dict]  # List of individual operation results
    errors: List[str]

class StreamHealthCheck(BaseModel):
    stream_id: int
    stream_name: str
    is_healthy: bool
    process_running: bool
    last_check: datetime
    issues: List[str] = []
    recommendations: List[str] = []
