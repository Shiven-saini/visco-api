import subprocess
import os
from typing import Optional
from ..config.settings import settings

def append_peer_to_wg_config(peer_config: str) -> bool:
    """
    Append a peer configuration to the WireGuard server config file.
    Returns True if successful, False otherwise.
    """
    try:
        # Use the separate script to handle root permissions
        script_path = settings.wg_update_script_path
        
        # Write peer config to a temporary file
        temp_file = "/tmp/wg_peer_add.conf"
        with open(temp_file, "w") as f:
            f.write(peer_config)
        
        # Call the update script
        result = subprocess.run([
            "sudo", script_path, "add", temp_file
        ], capture_output=True, text=True, timeout=30)
        
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error updating WireGuard config: {e}")
        return False

def remove_peer_from_wg_config(public_key: str) -> bool:
    """
    Remove a peer from the WireGuard server config file.
    Returns True if successful, False otherwise.
    """
    try:
        script_path = settings.wg_update_script_path
        
        # Call the update script to remove peer
        result = subprocess.run([
            "sudo", script_path, "remove", public_key
        ], capture_output=True, text=True, timeout=30)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error removing peer from WireGuard config: {e}")
        return False

def get_wg_config_status() -> dict:
    """Get the current status of WireGuard server."""
    try:
        # Check if WireGuard interface is up
        result = subprocess.run([
            "sudo", "wg", "show", "wg0"
        ], capture_output=True, text=True, timeout=10)
        
        return {
            "interface_up": result.returncode == 0,
            "output": result.stdout if result.returncode == 0 else result.stderr
        }
    except Exception as e:
        return {
            "interface_up": False,
            "error": str(e)
        }
