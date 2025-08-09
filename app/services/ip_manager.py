import ipaddress
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models import WireGuardConfig
from ..config.settings import settings

class IPManager:
    def __init__(self):
        self.subnet = ipaddress.IPv4Network(settings.wg_subnet)
        self.server_ip = ipaddress.IPv4Address(settings.wg_server_ip)
        self.client_start_ip = ipaddress.IPv4Address(settings.wg_client_start_ip)
    
    def get_allocated_ips(self, db: Session) -> List[str]:
        """Get all currently allocated IP addresses from database."""
        configs = db.query(WireGuardConfig).filter(
            WireGuardConfig.status == "active"
        ).all()
        return [config.allocated_ip for config in configs]
    
    def get_next_available_ip(self, db: Session) -> Optional[str]:
        """
        Get the next available IP address in sequential order.
        Reuses gaps in the sequence (e.g., if 10.0.0.3 is deleted, next user gets 10.0.0.3).
        """
        allocated_ips = set(self.get_allocated_ips(db))
        
        # Convert allocated IPs to IPv4Address objects for comparison
        allocated_ip_objects = {ipaddress.IPv4Address(ip.split('/')[0]) for ip in allocated_ips}
        
        # Start from client_start_ip and find first available
        current_ip = self.client_start_ip
        
        # Check each IP in sequence
        for ip in self.subnet.hosts():
            # Skip server IP
            if ip == self.server_ip:
                continue
                
            # Only consider IPs from client_start_ip onwards
            if ip < self.client_start_ip:
                continue
                
            # If this IP is not allocated, use it
            if ip not in allocated_ip_objects:
                return f"{ip}/24"
        
        # No available IP found
        return None
    
    def is_ip_in_subnet(self, ip: str) -> bool:
        """Check if an IP address is within the configured subnet."""
        try:
            ip_addr = ipaddress.IPv4Address(ip.split('/')[0])
            return ip_addr in self.subnet
        except Exception:
            return False
    
    def get_available_ip_count(self, db: Session) -> int:
        """Get count of available IP addresses."""
        allocated_count = len(self.get_allocated_ips(db))
        total_hosts = len(list(self.subnet.hosts()))
        # Subtract 1 for server IP and allocated IPs
        available = total_hosts - 1 - allocated_count
        return max(0, available)
