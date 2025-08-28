from pydantic_settings import BaseSettings
from typing import Optional
from urllib.parse import quote_plus

class Settings(BaseSettings):
    # Database
    db_host: str
    db_port: str 
    db_name: str
    db_user: str
    db_password: str
    
    # JWT Configuration
    secret_key: str
    algorithm: str
    access_token_expire_days: int
    access_token_expire_minutes: int
    
    # Email Configuration
    email_username: str
    email_password: str
    smtp_server: str
    smtp_port: int
    
    # WireGuard Server Constants
    wg_server_public_key: str
    wg_server_ip: str
    wg_server_port: str
    wg_server_allowed_ips: str
    wg_persistent_keepalive: int
    
    # Network Configuration
    wg_subnet: str
    wg_server_ip_internal: str
    wg_client_start_ip: str
    
    # System Configuration
    wg_config_file: str
    wg_update_script_path: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def database_url(self) -> str:
        """Generate the database URL with properly encoded password."""
        encoded_password = quote_plus(self.db_password)
        return f"postgresql+psycopg://{self.db_user}:{encoded_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def wg_server_endpoint(self) -> str:
        """Generate the WireGuard server endpoint from IP and port."""
        return f"{self.wg_server_ip}:{self.wg_server_port}"

settings = Settings()
