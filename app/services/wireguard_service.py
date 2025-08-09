from typing import Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import User, WireGuardConfig
from ..utils.crypto_utils import generate_wireguard_keypair
from .ip_manager import IPManager
from ..config.settings import settings

class WireGuardService:
    def __init__(self):
        self.ip_manager = IPManager()
    
    def create_config(self, db: Session, user: User) -> Optional[WireGuardConfig]:
        """
        Create a new WireGuard configuration for a user.
        Returns None if IP allocation fails.
        """
        # Check if user already has an active config
        existing_config = db.query(WireGuardConfig).filter(
            WireGuardConfig.user_id == user.id,
            WireGuardConfig.status == "active"
        ).first()
        
        if existing_config:
            return existing_config
        
        # Generate new keypair
        private_key, public_key = generate_wireguard_keypair()
        
        # Allocate IP address
        allocated_ip = self.ip_manager.get_next_available_ip(db)
        if not allocated_ip:
            return None  # No available IPs
        
        # Create new config
        wg_config = WireGuardConfig(
            user_id=user.id,
            private_key=private_key,
            public_key=public_key,
            allocated_ip=allocated_ip,
            status="active",
            expires_at=datetime.utcnow() + timedelta(days=365)  # 1 year expiry
        )
        
        db.add(wg_config)
        db.commit()
        db.refresh(wg_config)
        
        return wg_config
    
    def get_user_config(self, db: Session, user: User) -> Optional[WireGuardConfig]:
        """Get active WireGuard config for a user."""
        return db.query(WireGuardConfig).filter(
            WireGuardConfig.user_id == user.id,
            WireGuardConfig.status == "active"
        ).first()
    
    def get_config_by_username(self, db: Session, username: str) -> Optional[WireGuardConfig]:
        """Get active WireGuard config by username."""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        return self.get_user_config(db, user)
    
    def revoke_config(self, db: Session, user: User) -> bool:
        """Revoke (delete) a user's WireGuard configuration."""
        config = self.get_user_config(db, user)
        if not config:
            return False
        
        # Delete the config (this frees up the IP)
        db.delete(config)
        db.commit()
        return True
    
    def generate_client_config_content(self, wg_config: WireGuardConfig) -> str:
        """Generate the WireGuard client configuration file content."""
        config_content = f"""[Interface]
PrivateKey = {wg_config.private_key}
Address = {wg_config.allocated_ip}

[Peer]
PublicKey = {settings.wg_server_public_key}
Endpoint = {settings.wg_server_endpoint}
AllowedIPs = {settings.wg_server_allowed_ips}
PersistentKeepalive = {settings.wg_persistent_keepalive}
"""
        
        return config_content
    
    def generate_server_peer_config(self, wg_config: WireGuardConfig) -> str:
        """Generate the server-side peer configuration for wg0.conf."""
        peer_config = f"\n[Peer]\nPublicKey = {wg_config.public_key}\nAllowedIPs = {wg_config.allocated_ip}\n"
        
        return peer_config
