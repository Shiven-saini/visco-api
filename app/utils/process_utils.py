"""
Process Management Utilities for KVS Streams
Provides utilities for managing background processes and system monitoring
"""

import os
import signal
import subprocess
import psutil
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class ProcessManager:
    """Utility class for managing system processes"""
    
    @staticmethod
    def is_process_running(pid: int) -> bool:
        """Check if a process is running by PID"""
        try:
            return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    @staticmethod
    def get_process_info(pid: int) -> Optional[Dict]:
        """Get detailed information about a process"""
        try:
            if not psutil.pid_exists(pid):
                return None
            
            process = psutil.Process(pid)
            return {
                "pid": pid,
                "name": process.name(),
                "status": process.status(),
                "cpu_percent": process.cpu_percent(),
                "memory_info": process.memory_info()._asdict(),
                "create_time": datetime.fromtimestamp(process.create_time()),
                "cmdline": process.cmdline() if hasattr(process, 'cmdline') else [],
                "cwd": process.cwd() if hasattr(process, 'cwd') else None
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"Error getting process info for PID {pid}: {e}")
            return None
    
    @staticmethod
    def terminate_process(pid: int, timeout: int = 10) -> Tuple[bool, str]:
        """Terminate a process gracefully with timeout"""
        try:
            if not psutil.pid_exists(pid):
                return True, "Process not found (already terminated)"
            
            process = psutil.Process(pid)
            
            # Try graceful termination first
            process.terminate()
            
            try:
                process.wait(timeout=timeout)
                return True, "Process terminated gracefully"
            except psutil.TimeoutExpired:
                # Force kill if timeout
                process.kill()
                return True, "Process killed after timeout"
                
        except psutil.NoSuchProcess:
            return True, "Process not found"
        except Exception as e:
            logger.error(f"Error terminating process {pid}: {e}")
            return False, f"Failed to terminate: {str(e)}"
    
    @staticmethod
    def kill_process(pid: int) -> Tuple[bool, str]:
        """Force kill a process immediately"""
        try:
            if not psutil.pid_exists(pid):
                return True, "Process not found (already terminated)"
            
            process = psutil.Process(pid)
            process.kill()
            return True, "Process killed"
            
        except psutil.NoSuchProcess:
            return True, "Process not found"
        except Exception as e:
            logger.error(f"Error killing process {pid}: {e}")
            return False, f"Failed to kill: {str(e)}"
    
    @staticmethod
    def find_processes_by_name(name: str) -> List[Dict]:
        """Find all processes matching a name pattern"""
        matching_processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
                try:
                    if name.lower() in proc.info['name'].lower():
                        matching_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': proc.info['cmdline'],
                            'status': proc.info['status']
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"Error finding processes by name '{name}': {e}")
        
        return matching_processes
    
    @staticmethod
    def get_system_stats() -> Dict:
        """Get system resource statistics"""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": psutil.virtual_memory()._asdict(),
                "disk": psutil.disk_usage('/')._asdict(),
                "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None,
                "boot_time": datetime.fromtimestamp(psutil.boot_time()),
                "process_count": len(psutil.pids())
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}

class KVSProcessValidator:
    """Validator for KVS-specific processes"""
    
    def __init__(self, kvs_binary_path: str):
        self.kvs_binary_path = kvs_binary_path
        self.binary_name = os.path.basename(kvs_binary_path)
    
    def validate_kvs_binary(self) -> Tuple[bool, str]:
        """Validate that KVS binary exists and is executable"""
        try:
            if not os.path.exists(self.kvs_binary_path):
                return False, f"KVS binary not found at: {self.kvs_binary_path}"
            
            if not os.access(self.kvs_binary_path, os.X_OK):
                return False, f"KVS binary is not executable: {self.kvs_binary_path}"
            
            # Get binary info
            stat_info = os.stat(self.kvs_binary_path)
            binary_size = stat_info.st_size
            modified_time = datetime.fromtimestamp(stat_info.st_mtime)
            
            return True, f"KVS binary is valid (size: {binary_size} bytes, modified: {modified_time})"
            
        except Exception as e:
            return False, f"Error validating KVS binary: {str(e)}"
    
    def find_kvs_processes(self) -> List[Dict]:
        """Find all running KVS processes"""
        return ProcessManager.find_processes_by_name(self.binary_name)
    
    def validate_stream_command(self, stream_name: str, rtsp_url: str) -> Tuple[bool, str]:
        """Validate stream command parameters"""
        errors = []
        
        # Validate stream name
        if not stream_name or not isinstance(stream_name, str):
            errors.append("Stream name is required and must be a string")
        elif not stream_name.replace('_', '').replace('-', '').isalnum():
            errors.append("Stream name must contain only alphanumeric characters, hyphens, and underscores")
        
        # Validate RTSP URL
        if not rtsp_url or not isinstance(rtsp_url, str):
            errors.append("RTSP URL is required and must be a string")
        elif not rtsp_url.startswith('rtsp://'):
            errors.append("RTSP URL must start with 'rtsp://'")
        
        if errors:
            return False, "; ".join(errors)
        
        return True, "Command parameters are valid"
    
    def test_kvs_command(self, stream_name: str, rtsp_url: str, timeout: int = 30) -> Tuple[bool, str]:
        """Test KVS command execution (dry run)"""
        try:
            binary_valid, binary_msg = self.validate_kvs_binary()
            if not binary_valid:
                return False, binary_msg
            
            cmd_valid, cmd_msg = self.validate_stream_command(stream_name, rtsp_url)
            if not cmd_valid:
                return False, cmd_msg
            
            # Test command construction
            binary_dir = os.path.dirname(self.kvs_binary_path)
            binary_name = os.path.basename(self.kvs_binary_path)
            cmd = [f"./{binary_name}", stream_name, rtsp_url]
            
            return True, f"Command test successful: {' '.join(cmd)} (cwd: {binary_dir})"
            
        except Exception as e:
            return False, f"Command test failed: {str(e)}"

def cleanup_zombie_processes():
    """Clean up any zombie processes"""
    try:
        zombie_count = 0
        for proc in psutil.process_iter(['pid', 'status']):
            try:
                if proc.info['status'] == psutil.STATUS_ZOMBIE:
                    zombie_count += 1
                    logger.info(f"Found zombie process: PID {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if zombie_count > 0:
            logger.info(f"Found {zombie_count} zombie processes")
            # On Unix systems, zombie processes are cleaned up by their parent
            # We don't directly kill them, just report
        else:
            logger.info("No zombie processes found")
            
        return zombie_count
        
    except Exception as e:
        logger.error(f"Error checking for zombie processes: {e}")
        return 0

def get_kvs_environment_info() -> Dict:
    """Get environment information relevant to KVS"""
    try:
        info = {
            "python_version": f"{os.sys.version}",
            "platform": os.name,
            "cwd": os.getcwd(),
            "user": os.getenv('USER') or os.getenv('USERNAME', 'unknown'),
            "home": os.path.expanduser('~'),
            "path": os.environ.get('PATH', '').split(os.pathsep)[:5]  # First 5 PATH entries
        }
        
        # Add AWS-related environment variables
        aws_vars = ['AWS_REGION', 'AWS_DEFAULT_REGION', 'AWS_ACCESS_KEY_ID', 'AWS_PROFILE']
        aws_env = {}
        for var in aws_vars:
            value = os.getenv(var)
            if value:
                # Mask sensitive information
                if 'KEY' in var:
                    aws_env[var] = f"{value[:8]}***" if len(value) > 8 else "***"
                else:
                    aws_env[var] = value
        
        if aws_env:
            info["aws_environment"] = aws_env
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting environment info: {e}")
        return {"error": str(e)}
