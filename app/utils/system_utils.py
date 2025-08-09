import subprocess
import os
import tempfile
from typing import Optional
from ..config.settings import settings

def get_temp_dir() -> str:
    """Get the best available temporary directory with space."""
    # Try directories in order of preference
    temp_dirs = ["/var/tmp", "/tmp", "/home/ec2-user/tmp"]
    
    for temp_dir in temp_dirs:
        try:
            # Ensure directory exists
            os.makedirs(temp_dir, mode=0o755, exist_ok=True)
            
            # Check if we have write permission and space
            statvfs = os.statvfs(temp_dir)
            available_mb = (statvfs.f_bavail * statvfs.f_frsize) / (1024 * 1024)
            
            if available_mb >= 10:  # At least 10MB available
                return temp_dir
        except (OSError, PermissionError):
            continue
    
    # Fallback to system temp
    return tempfile.gettempdir()

def check_disk_space(path: str = "/tmp", min_mb: int = 10) -> bool:
    """Check if there's enough disk space available."""
    try:
        statvfs = os.statvfs(path)
        available_mb = (statvfs.f_bavail * statvfs.f_frsize) / (1024 * 1024)
        return available_mb >= min_mb
    except Exception:
        return False

def append_peer_to_wg_config(peer_config: str) -> bool:
    """
    Append a peer configuration to the WireGuard server config file.
    Returns True if successful, False otherwise.
    """
    try:
        # Get the best temporary directory
        temp_dir = get_temp_dir()
        
        # Check disk space in chosen temp directory
        if not check_disk_space(temp_dir, 10):
            print(f"Error: Insufficient disk space in {temp_dir}")
            return False
        
        # Ensure WireGuard directory exists
        wg_dir = os.path.dirname(settings.wg_config_file)
        if not os.path.exists(wg_dir):
            os.makedirs(wg_dir, mode=0o700, exist_ok=True)
        
        script_path = settings.wg_update_script_path
        
        # Use the selected temp directory
        temp_file = os.path.join(temp_dir, "wg_peer_add.conf")
        
        try:
            with open(temp_file, "w") as f:
                f.write(peer_config)
            print(f"Temporary file created at: {temp_file}")
        except OSError as e:
            print(f"Error writing temporary file: {e}")
            return False
        
        # Call the update script
        result = subprocess.run([
            "sudo", script_path, "add", temp_file
        ], capture_output=True, text=True, timeout=30)
        
        # Clean up temp file
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        
        if result.returncode != 0:
            print(f"Script error: {result.stderr}")
            return False
        
        print("Peer successfully added to WireGuard configuration")
        return True
        
    except Exception as e:
        print(f"Error updating WireGuard config: {e}")
        return False

def remove_peer_from_wg_config(public_key: str) -> bool:
    """
    Remove a peer from the WireGuard server config file.
    Returns True if successful, False otherwise.
    """
    try:
        temp_dir = get_temp_dir()
        
        if not check_disk_space(temp_dir, 10):
            print(f"Error: Insufficient disk space in {temp_dir}")
            return False
        
        script_path = settings.wg_update_script_path
        
        result = subprocess.run([
            "sudo", script_path, "remove", public_key
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"Script error: {result.stderr}")
            return False
        
        return True
        
    except Exception as e:
        print(f"Error removing peer from WireGuard config: {e}")
        return False

def get_system_disk_usage() -> dict:
    """Get system disk usage information."""
    try:
        disk_info = {}
        
        for path in ["/", "/tmp", "/var/tmp", "/etc", "/var"]:
            try:
                if not os.path.exists(path):
                    disk_info[path] = {"error": "Path does not exist"}
                    continue
                    
                statvfs = os.statvfs(path)
                total_mb = (statvfs.f_blocks * statvfs.f_frsize) / (1024 * 1024)
                available_mb = (statvfs.f_bavail * statvfs.f_frsize) / (1024 * 1024)
                used_mb = total_mb - available_mb
                usage_percent = (used_mb / total_mb) * 100 if total_mb > 0 else 0
                
                disk_info[path] = {
                    "total_mb": round(total_mb, 2),
                    "available_mb": round(available_mb, 2),
                    "used_mb": round(used_mb, 2),
                    "usage_percent": round(usage_percent, 2)
                }
            except OSError:
                disk_info[path] = {"error": "Unable to access"}
        
        return disk_info
    except Exception as e:
        return {"error": str(e)}

def get_wg_config_status() -> dict:
    """Get the current status of WireGuard server."""
    try:
        result = subprocess.run([
            "sudo", "wg", "show", "wg0"
        ], capture_output=True, text=True, timeout=10)
        
        disk_usage = get_system_disk_usage()
        
        return {
            "interface_up": result.returncode == 0,
            "output": result.stdout if result.returncode == 0 else result.stderr,
            "disk_usage": disk_usage
        }
    except Exception as e:
        return {
            "interface_up": False,
            "error": str(e),
            "disk_usage": get_system_disk_usage()
        }
