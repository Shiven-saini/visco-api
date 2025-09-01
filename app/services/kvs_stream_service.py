"""
KVS Stream Service for managing Amazon Kinesis Video Streams
Handles starting, stopping, and monitoring KVS streaming processes using kvs_gstreamer_sample
"""

import os
import subprocess
import psutil
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models import KVSStream, Camera_details, User
from ..database import get_db
from ..services.wireguard_service import WireGuardService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KVSStreamService:
    def __init__(self):
        self.kvs_binary_path = "/home/ubuntu/kvs/kvs-producer-sdk-cpp/build/kvs_gstreamer_sample"
        self.wg_service = WireGuardService()
        
        # Verify binary exists
        if not os.path.exists(self.kvs_binary_path):
            logger.error(f"KVS binary not found at: {self.kvs_binary_path}")
            raise FileNotFoundError(f"KVS binary not found at: {self.kvs_binary_path}")
    
    def generate_stream_name(self, user: User, camera: Camera_details, db: Session) -> str:
        """Generate unique stream name in format username_N"""
        # Get user's existing streams count
        existing_streams = db.query(KVSStream).filter(
            and_(
                KVSStream.user_id == user.id,
                KVSStream.status.in_(["running", "starting", "stopping"])
            )
        ).count()
        
        # Clean username for stream name (replace special chars)
        clean_username = "".join(c for c in user.name.lower() if c.isalnum())
        if not clean_username:
            clean_username = f"user{user.id}"
        
        # Generate stream name
        stream_number = existing_streams + 1
        return f"{clean_username}_{stream_number}"
    
    def get_vpn_rtsp_url(self, camera: Camera_details, user: User, db: Session) -> Optional[str]:
        """Get VPN-accessible RTSP URL for camera"""
        try:
            # Get user's WireGuard config
            wg_config = self.wg_service.get_user_config(db, user)
            if not wg_config or wg_config.status != "active":
                logger.error(f"No active VPN config for user {user.id}")
                return None
            
            # Check if config is expired
            if wg_config.expires_at and wg_config.expires_at < datetime.utcnow():
                logger.error(f"VPN config expired for user {user.id}")
                return None
            
            # Get VPN IP
            vpn_ip = wg_config.allocated_ip.split('/')[0]
            
            # Build RTSP URL
            external_port = camera.port if camera.port else "554"
            credentials = ""
            if camera.username and camera.password_hash:
                credentials = f"{camera.username}:{camera.password_hash}@"
            
            path = camera.stream_url if camera.stream_url else "/cam/realmonitor?channel=1&subtype=0"
            if not path.startswith('/'):
                path = f"/{path}"
            
            return f"rtsp://{credentials}{vpn_ip}:{external_port}{path}"
            
        except Exception as e:
            logger.error(f"Error building VPN RTSP URL: {e}")
            return None
    
    def start_stream(self, camera_id: int, user: User, db: Session, custom_stream_name: Optional[str] = None) -> Tuple[bool, str, Optional[KVSStream]]:
        """Start KVS streaming for a camera"""
        try:
            # Get camera
            camera = db.query(Camera_details).filter(
                and_(
                    Camera_details.id == camera_id,
                    Camera_details.organization_id == user.org_id,
                    Camera_details.status == "active"
                )
            ).first()
            
            if not camera:
                return False, "Camera not found or not accessible", None
            
            # Check if stream already exists for this camera
            existing_stream = db.query(KVSStream).filter(
                and_(
                    KVSStream.camera_id == camera_id,
                    KVSStream.user_id == user.id,
                    KVSStream.status.in_(["running", "starting"])
                )
            ).first()
            
            if existing_stream:
                return False, f"Stream already running for camera {camera.name}", existing_stream
            
            # Get VPN RTSP URL
            rtsp_url = self.get_vpn_rtsp_url(camera, user, db)
            if not rtsp_url:
                return False, "Unable to generate VPN RTSP URL. Check VPN configuration.", None
            
            # Generate stream name
            if custom_stream_name:
                stream_name = custom_stream_name
                # Check if custom name is already used
                existing_custom = db.query(KVSStream).filter(
                    and_(
                        KVSStream.stream_name == stream_name,
                        KVSStream.status.in_(["running", "starting"])
                    )
                ).first()
                if existing_custom:
                    return False, f"Stream name '{stream_name}' already in use", None
            else:
                stream_name = self.generate_stream_name(user, camera, db)
            
            # Create KVS stream name (for AWS)
            kvs_stream_name = stream_name.replace("_", "-")  # AWS KVS stream naming
            
            # Create database record
            stream_record = KVSStream(
                stream_name=stream_name,
                user_id=user.id,
                organization_id=user.org_id,
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                kvs_stream_name=kvs_stream_name,
                status="starting"
            )
            
            db.add(stream_record)
            db.commit()
            db.refresh(stream_record)
            
            # Start KVS process
            success, message, process_id = self._start_kvs_process(kvs_stream_name, rtsp_url)
            
            if success:
                # Update stream record
                stream_record.status = "running"
                stream_record.process_id = process_id
                stream_record.start_time = datetime.now(timezone.utc)
                stream_record.process_status = "running"
                stream_record.error_message = None
                
                db.commit()
                db.refresh(stream_record)
                
                logger.info(f"Started KVS stream {stream_name} for camera {camera.name}")
                return True, f"Stream started successfully: {stream_name}", stream_record
            else:
                # Update stream record with error
                stream_record.status = "error"
                stream_record.error_message = message
                
                db.commit()
                
                logger.error(f"Failed to start KVS stream {stream_name}: {message}")
                return False, message, stream_record
                
        except Exception as e:
            logger.error(f"Error starting stream: {e}")
            return False, f"Internal error: {str(e)}", None
    
    def _start_kvs_process(self, kvs_stream_name: str, rtsp_url: str) -> Tuple[bool, str, Optional[int]]:
        """Start the actual KVS process"""
        try:
            # Change to the binary directory
            binary_dir = os.path.dirname(self.kvs_binary_path)
            binary_name = os.path.basename(self.kvs_binary_path)
            
            # Command to execute
            cmd = [f"./{binary_name}", kvs_stream_name, rtsp_url]
            
            logger.info(f"Starting KVS process: {' '.join(cmd)} in directory {binary_dir}")
            
            # Start process
            process = subprocess.Popen(
                cmd,
                cwd=binary_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True  # Create new session to prevent inheriting signals
            )
            
            # Give process a moment to start
            import time
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                logger.info(f"KVS process started successfully with PID: {process.pid}")
                return True, "Process started successfully", process.pid
            else:
                # Process terminated quickly, get error
                _, stderr = process.communicate()
                error_msg = stderr.decode('utf-8') if stderr else "Process terminated unexpectedly"
                logger.error(f"KVS process failed to start: {error_msg}")
                return False, f"Process failed to start: {error_msg}", None
                
        except Exception as e:
            logger.error(f"Error starting KVS process: {e}")
            return False, f"Failed to start process: {str(e)}", None
    
    def stop_stream(self, stream_id: int, user: User, db: Session, force: bool = False) -> Tuple[bool, str]:
        """Stop KVS streaming"""
        try:
            # Get stream record
            stream = db.query(KVSStream).filter(
                and_(
                    KVSStream.id == stream_id,
                    KVSStream.user_id == user.id
                )
            ).first()
            
            if not stream:
                return False, "Stream not found or not accessible"
            
            if stream.status in ["stopped", "error"]:
                return True, f"Stream already stopped (status: {stream.status})"
            
            previous_status = stream.status
            stream.status = "stopping"
            db.commit()
            
            # Stop the process
            success, message = self._stop_kvs_process(stream.process_id, force)
            
            # Update stream record
            if success:
                stream.status = "stopped"
                stream.stop_time = datetime.now(timezone.utc)
                stream.process_id = None
                stream.process_status = "stopped"
                stream.error_message = None
            else:
                stream.status = "error"
                stream.error_message = message
            
            db.commit()
            
            logger.info(f"Stopped stream {stream.stream_name}: {message}")
            return success, message
            
        except Exception as e:
            logger.error(f"Error stopping stream: {e}")
            return False, f"Internal error: {str(e)}"
    
    def _stop_kvs_process(self, process_id: Optional[int], force: bool = False) -> Tuple[bool, str]:
        """Stop the actual KVS process"""
        if not process_id:
            return True, "No process ID to stop"
        
        try:
            # Check if process exists
            if not psutil.pid_exists(process_id):
                return True, "Process already terminated"
            
            process = psutil.Process(process_id)
            
            if force:
                # Force kill
                process.kill()
                logger.info(f"Force killed process {process_id}")
                return True, "Process force killed"
            else:
                # Graceful termination
                process.terminate()
                
                # Wait for process to terminate (max 10 seconds)
                try:
                    process.wait(timeout=10)
                    logger.info(f"Process {process_id} terminated gracefully")
                    return True, "Process terminated gracefully"
                except psutil.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    process.kill()
                    logger.info(f"Process {process_id} killed after timeout")
                    return True, "Process killed after timeout"
                    
        except psutil.NoSuchProcess:
            return True, "Process not found (already terminated)"
        except Exception as e:
            logger.error(f"Error stopping process {process_id}: {e}")
            return False, f"Failed to stop process: {str(e)}"
    
    def get_stream_status(self, stream_id: int, user: User, db: Session) -> Optional[KVSStream]:
        """Get status of a specific stream"""
        try:
            stream = db.query(KVSStream).filter(
                and_(
                    KVSStream.id == stream_id,
                    KVSStream.user_id == user.id
                )
            ).first()
            
            if stream:
                # Update process status
                self._update_stream_health(stream, db)
            
            return stream
            
        except Exception as e:
            logger.error(f"Error getting stream status: {e}")
            return None
    
    def get_user_streams(self, user: User, db: Session) -> List[KVSStream]:
        """Get all streams for a user"""
        try:
            streams = db.query(KVSStream).filter(
                KVSStream.user_id == user.id
            ).all()
            
            # Update health for all streams
            for stream in streams:
                self._update_stream_health(stream, db)
            
            return streams
            
        except Exception as e:
            logger.error(f"Error getting user streams: {e}")
            return []
    
    def start_all_user_streams(self, user: User, db: Session) -> Dict:
        """Start streaming for all user's cameras"""
        try:
            # Get all active cameras for user
            cameras = db.query(Camera_details).filter(
                and_(
                    Camera_details.organization_id == user.org_id,
                    Camera_details.status == "active"
                )
            ).all()
            
            results = {
                "total_cameras": len(cameras),
                "successful_starts": 0,
                "failed_starts": 0,
                "results": [],
                "errors": []
            }
            
            for camera in cameras:
                success, message, stream = self.start_stream(camera.id, user, db)
                
                result = {
                    "camera_id": camera.id,
                    "camera_name": camera.name,
                    "success": success,
                    "message": message,
                    "stream_id": stream.id if stream else None,
                    "stream_name": stream.stream_name if stream else None
                }
                
                results["results"].append(result)
                
                if success:
                    results["successful_starts"] += 1
                else:
                    results["failed_starts"] += 1
                    results["errors"].append(f"Camera {camera.name}: {message}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error starting all user streams: {e}")
            return {
                "total_cameras": 0,
                "successful_starts": 0,
                "failed_starts": 0,
                "results": [],
                "errors": [f"Internal error: {str(e)}"]
            }
    
    def stop_all_user_streams(self, user: User, db: Session, force: bool = False) -> Dict:
        """Stop all streams for a user"""
        try:
            # Get all active streams for user
            streams = db.query(KVSStream).filter(
                and_(
                    KVSStream.user_id == user.id,
                    KVSStream.status.in_(["running", "starting"])
                )
            ).all()
            
            results = {
                "total_streams": len(streams),
                "successful_stops": 0,
                "failed_stops": 0,
                "results": [],
                "errors": []
            }
            
            for stream in streams:
                success, message = self.stop_stream(stream.id, user, db, force)
                
                result = {
                    "stream_id": stream.id,
                    "stream_name": stream.stream_name,
                    "camera_name": stream.camera.name if stream.camera else "Unknown",
                    "success": success,
                    "message": message
                }
                
                results["results"].append(result)
                
                if success:
                    results["successful_stops"] += 1
                else:
                    results["failed_stops"] += 1
                    results["errors"].append(f"Stream {stream.stream_name}: {message}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error stopping all user streams: {e}")
            return {
                "total_streams": 0,
                "successful_stops": 0,
                "failed_stops": 0,
                "results": [],
                "errors": [f"Internal error: {str(e)}"]
            }
    
    def _update_stream_health(self, stream: KVSStream, db: Session):
        """Update stream health based on process status"""
        try:
            if not stream.process_id:
                if stream.status == "running":
                    stream.status = "stopped"
                    stream.process_status = "no_pid"
                return
            
            # Check if process is running
            if psutil.pid_exists(stream.process_id):
                try:
                    process = psutil.Process(stream.process_id)
                    if process.is_running():
                        stream.process_status = "running"
                        stream.last_health_check = datetime.now(timezone.utc)
                    else:
                        stream.status = "stopped"
                        stream.process_status = "terminated"
                        stream.process_id = None
                except psutil.NoSuchProcess:
                    stream.status = "stopped"
                    stream.process_status = "not_found"
                    stream.process_id = None
            else:
                stream.status = "stopped"
                stream.process_status = "not_running"
                stream.process_id = None
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating stream health: {e}")
            stream.error_message = f"Health check error: {str(e)}"
            db.commit()
    
    def cleanup_orphaned_streams(self, db: Session):
        """Clean up streams that have lost their processes"""
        try:
            # Get all streams marked as running
            running_streams = db.query(KVSStream).filter(
                KVSStream.status == "running"
            ).all()
            
            for stream in running_streams:
                if stream.process_id and not psutil.pid_exists(stream.process_id):
                    logger.info(f"Cleaning up orphaned stream: {stream.stream_name}")
                    stream.status = "stopped"
                    stream.process_status = "orphaned"
                    stream.process_id = None
                    stream.stop_time = datetime.now(timezone.utc)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error cleaning up orphaned streams: {e}")
