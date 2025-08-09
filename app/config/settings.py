from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    db_host: str = "127.0.0.1"
    db_port: str = "5432"
    db_name: str = "visco"
    db_user: str = "shiven"
    db_password: str = "Shiven@123"
    
    # WireGuard Server Constants
    wg_server_public_key: str
    wg_server_endpoint: str
    wg_server_allowed_ips: str = "10.0.0.1/24"
    wg_persistent_keepalive: int = 15
    
    # Network Configuration
    wg_subnet: str = "10.0.0.0/24"
    wg_server_ip: str = "10.0.0.1"
    wg_client_start_ip: str = "10.0.0.2"
    
    # System Configuration
    wg_config_file: str = "/etc/wireguard/wg0.conf"
    wg_update_script_path: str = "/usr/local/bin/update_wg_config.sh"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
