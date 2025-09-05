from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func, DECIMAL, JSON,Numeric,Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB,ARRAY

from datetime import datetime
from .database import Base

# class User(Base):
#     __tablename__ = "users"

#     id = Column(Integer, primary_key=True, index=True)
#     username = Column(String, unique=True, index=True, nullable=False)
#     email = Column(String, unique=True, index=True, nullable=False)
#     password = Column(String, nullable=False)  # Plain text will change to hashed in production: Shiven Saini
#     first_name = Column(String, nullable=False)
#     last_name = Column(String, nullable=False)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())

#     # Relationship to WireGuard config
#     wireguard_config = relationship("WireGuardConfig", back_populates="user", uselist=False)


# Visco User SQL Table Object Relational Mapping
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"))
    org_id = Column(Integer, ForeignKey("organizations.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("Role")
    org = relationship("Organization", foreign_keys=[org_id])
    wireguard_config = relationship("WireGuardConfig", back_populates="user", uselist=False)

class Super_admin(Base):
    __tablename__ = 'super_admin'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    org_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    role = Column(String, nullable=False)


# Role User object relational Mapping
class Role(Base):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

class Organization(Base):
    __tablename__ = 'organizations'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", foreign_keys=[created_by])

class Verify_otp(Base):
    __tablename__ = "verify_account_otp"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    otp = Column(Integer, nullable=False)
    email = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)    


class IPAddress(Base):
    __tablename__ = 'ip_address'

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Optional FK
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Send Otp Model
class ResetOtp(Base):
    __tablename__ = "otp_reset_password"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    otp = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    role = Column(String, default="null")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Camera_details(Base):
    __tablename__ = 'camera_details'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Optional FK
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)  # Optional FK
    
    # Local camera details (for reference only)
    camera_ip = Column(String, nullable=True)  # Local camera IP (e.g., 192.168.1.100)
    camera_port = Column(String, nullable=True)  # Local camera RTSP port (e.g., 554)
    
    # WireGuard and external access details (for KVS streaming)
    wireguard_ip = Column(String, nullable=True)  # WireGuard IP of the device
    external_port = Column(String, nullable=True)  # External port for forwarding (e.g., 8551)
    
    mac_address = Column(String, nullable=True)
    location = Column(String, nullable=True)
    status = Column(String, nullable=True)
    port = Column(String, nullable=True)  # Keep for backward compatibility, will store external_port
    username = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    stream_url = Column(String, nullable=True)  # RTSP URL using WireGuard IP and external port
    resolution = Column(String, nullable=True)
    features = Column(String, nullable=True)
    last_active = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 


class Manage_Alert(Base):
    __tablename__ = 'manage_alert'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  
    rule_name = Column(String)
    description = Column(String, nullable=True)
    alert_type = Column(String, nullable=True)
    apply_to_camera = Column(String, nullable=True)
    servity_level = Column(String, nullable=True)
    notification_method = Column(JSONB)
    status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    plan = Column(String, nullable=False, default="trial")   # trial/basic/pro/enterprise
    status = Column(String, nullable=False, default="active") # active/cancelled/past_due/expired
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True))
    trial_end_date = Column(DateTime(timezone=True))
    max_users = Column(Integer, default=5)
    max_cameras = Column(Integer, default=10)
    storage_limit_gb = Column(Integer, default=50)
    storage_limit_days = Column(Integer,nullable=True)
    price_monthly = Column(DECIMAL(10, 2))
    price_yearly = Column(DECIMAL(10, 2))
    stripe_customer_id = Column(String, index=True)
    stripe_subscription_id = Column(String, index=True)
    stripe_payment_method_id = Column(String, index=True)
    stripe_price_id = Column(String, index=True)
    features = Column(JSON, nullable=False, default={})
    description = Column(String)
    active = Column(Boolean, default=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) 


class QueueMonitoring(Base):
    __tablename__ = "queue_monitoring"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String(50), nullable=False)
    frame_id = Column(String(100), unique=True, nullable=False)
    time_stamp = Column(String(25), nullable=True)
    queue_count = Column(Integer, nullable=True)
    queue_name = Column(ARRAY(Text), nullable=True)
    queue_length = Column(ARRAY(Integer), nullable=True)
    front_person_wt = Column(ARRAY(Integer), nullable=True)
    average_wt_time = Column(ARRAY(Integer), nullable=True)
    status = Column(ARRAY(Text), nullable=True)
    total_people_detected = Column(Integer, nullable=True)
    people_ids = Column(ARRAY(Integer), nullable=True)
    queue_assignment = Column(ARRAY(Integer), nullable=True)
    entry_time = Column(ARRAY(Text), nullable=True)
    people_wt_time = Column(ARRAY(Integer), nullable=True)
    processing_status = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_info = Column(String, nullable=True)  # User agent, device name, etc.
    ip_address = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationship to user
    user = relationship("User", foreign_keys=[user_id])

class WireGuardConfig(Base):
    __tablename__ = "wireguard_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    private_key = Column(String, nullable=False)
    public_key = Column(String, nullable=False)
    allocated_ip = Column(String, nullable=False, unique=True)
    status = Column(String, default="active")  # active, inactive, revoked
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship back to user
    user = relationship("User", back_populates="wireguard_config")

class KVSStream(Base):
    __tablename__ = "kvs_streams"

    id = Column(Integer, primary_key=True, index=True)
    stream_name = Column(String, nullable=False, unique=True, index=True)  # e.g., "shiven_1", "john_2"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    camera_id = Column(Integer, ForeignKey("camera_details.id"), nullable=False)
    rtsp_url = Column(String, nullable=False)  # VPN-accessible RTSP URL
    kvs_stream_name = Column(String, nullable=False)  # AWS KVS stream name
    status = Column(String, default="stopped")  # stopped, starting, running, error, stopping
    process_id = Column(Integer, nullable=True)  # System process ID
    process_status = Column(String, nullable=True)  # Process status details
    error_message = Column(String, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    stop_time = Column(DateTime(timezone=True), nullable=True)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    restart_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    camera = relationship("Camera_details", foreign_keys=[camera_id])