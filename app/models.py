from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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

class IPAddress(Base):
    __tablename__ = 'ip_address'

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Optional FK
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Camera_details(Base):
    __tablename__ = 'camera_details'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Optional FK
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)  # Optional FK
    camera_ip = Column(String, nullable=True)
    mac_address = Column(String, nullable=True)
    location = Column(String, nullable=True)
    status = Column(String, nullable=True)
    port = Column(String, nullable=True)
    username = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    stream_url = Column(String, nullable=True)
    resolution = Column(String, nullable=True)
    features = Column(String, nullable=True)
    last_active = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 


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