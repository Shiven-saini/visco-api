from pydantic import BaseModel, EmailStr
from typing import List,Optional,Dict
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
    # user_id: int
    # org_id: int
    c_ip: str
    status: str
    port: int
    stream_url: str
    username: str
    password: str

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
       