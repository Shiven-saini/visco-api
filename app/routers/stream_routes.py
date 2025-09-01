"""
KVS Stream Management Router
Provides endpoints for managing Amazon Kinesis Video Streams
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from ..database import get_db
from ..auth import get_current_user
from ..models import User, KVSStream
from ..schemas import (
    StreamStartRequest, StreamStartResponse, 
    StreamStopRequest, StreamStopResponse,
    StreamStatusResponse, UserStreamsSummary,
    StreamBulkOperationResponse, StreamHealthCheck
)
from ..services.kvs_stream_service import KVSStreamService

router = APIRouter(prefix="/stream", tags=["KVS Stream Management"])
kvs_service = KVSStreamService()

@router.get("/status", response_model=List[StreamStatusResponse])
async def get_all_streams_status(
    include_stopped: bool = Query(False, description="Include stopped streams in response"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get status of all streams for the current user.
    
    This endpoint returns comprehensive information about all streams
    associated with the current user's organization.
    """
    try:
        streams = kvs_service.get_user_streams(current_user, db)
        
        if not include_stopped:
            streams = [s for s in streams if s.status not in ["stopped"]]
        
        response_streams = []
        for stream in streams:
            # Calculate uptime if stream is running
            uptime_seconds = None
            if stream.status == "running" and stream.start_time:
                uptime_seconds = int((datetime.now(timezone.utc) - stream.start_time).total_seconds())
            
            response_streams.append(StreamStatusResponse(
                stream_id=stream.id,
                stream_name=stream.stream_name,
                kvs_stream_name=stream.kvs_stream_name,
                user_id=stream.user_id,
                username=stream.user.name if stream.user else "Unknown",
                camera_id=stream.camera_id,
                camera_name=stream.camera.name if stream.camera else "Unknown",
                rtsp_url=stream.rtsp_url,
                status=stream.status,
                process_id=stream.process_id,
                process_status=stream.process_status,
                error_message=stream.error_message,
                start_time=stream.start_time,
                stop_time=stream.stop_time,
                last_health_check=stream.last_health_check,
                restart_count=stream.restart_count,
                uptime_seconds=uptime_seconds,
                created_at=stream.created_at,
                updated_at=stream.updated_at
            ))
        
        return response_streams
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get streams status: {str(e)}"
        )

@router.get("/user/{user_id}/status", response_model=UserStreamsSummary)
async def get_user_streams_summary(
    user_id: int = Path(..., description="User ID to get streams for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get comprehensive streams summary for a specific user.
    
    Only admins can view other users' streams, regular users can only view their own.
    """
    # Permission check
    if current_user.id != user_id and current_user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own streams unless you're an admin or manager"
        )
    
    try:
        # Get target user
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # If current user is not admin/manager, ensure they're in same org
        if (current_user.role.name not in ["Admin", "Manager"] and 
            current_user.org_id != target_user.org_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view streams from users in your organization"
            )
        
        streams = kvs_service.get_user_streams(target_user, db)
        
        # Calculate summary statistics
        total_streams = len(streams)
        active_streams = len([s for s in streams if s.status == "running"])
        stopped_streams = len([s for s in streams if s.status == "stopped"])
        error_streams = len([s for s in streams if s.status == "error"])
        
        # Build detailed stream responses
        stream_responses = []
        for stream in streams:
            uptime_seconds = None
            if stream.status == "running" and stream.start_time:
                uptime_seconds = int((datetime.now(timezone.utc) - stream.start_time).total_seconds())
            
            stream_responses.append(StreamStatusResponse(
                stream_id=stream.id,
                stream_name=stream.stream_name,
                kvs_stream_name=stream.kvs_stream_name,
                user_id=stream.user_id,
                username=stream.user.name if stream.user else "Unknown",
                camera_id=stream.camera_id,
                camera_name=stream.camera.name if stream.camera else "Unknown",
                rtsp_url=stream.rtsp_url,
                status=stream.status,
                process_id=stream.process_id,
                process_status=stream.process_status,
                error_message=stream.error_message,
                start_time=stream.start_time,
                stop_time=stream.stop_time,
                last_health_check=stream.last_health_check,
                restart_count=stream.restart_count,
                uptime_seconds=uptime_seconds,
                created_at=stream.created_at,
                updated_at=stream.updated_at
            ))
        
        return UserStreamsSummary(
            user_id=target_user.id,
            username=target_user.name,
            organization_name=target_user.org.name if target_user.org else "Unknown",
            total_streams=total_streams,
            active_streams=active_streams,
            stopped_streams=stopped_streams,
            error_streams=error_streams,
            streams=stream_responses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user streams summary: {str(e)}"
        )

@router.post("/start", response_model=StreamStartResponse)
async def start_camera_stream(
    request: StreamStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start KVS streaming for a specific camera.
    
    This endpoint will:
    1. Validate camera access and VPN configuration
    2. Generate a unique stream name
    3. Start the KVS streaming process
    4. Return stream details and status
    """
    try:
        success, message, stream = kvs_service.start_stream(
            request.camera_id, 
            current_user, 
            db, 
            request.custom_stream_name
        )
        
        if success and stream:
            return StreamStartResponse(
                stream_id=stream.id,
                stream_name=stream.stream_name,
                kvs_stream_name=stream.kvs_stream_name,
                camera_name=stream.camera.name if stream.camera else "Unknown",
                rtsp_url=stream.rtsp_url,
                status=stream.status,
                message=message
            )
        else:
            # If we have a stream object but failed, still return it for context
            if stream:
                return StreamStartResponse(
                    stream_id=stream.id,
                    stream_name=stream.stream_name,
                    kvs_stream_name=stream.kvs_stream_name,
                    camera_name=stream.camera.name if stream.camera else "Unknown",
                    rtsp_url=stream.rtsp_url,
                    status=stream.status,
                    message=message
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start stream: {str(e)}"
        )

@router.post("/stop/{stream_id}", response_model=StreamStopResponse)
async def stop_stream(
    stream_id: int = Path(..., description="Stream ID to stop"),
    request: StreamStopRequest = StreamStopRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stop a specific stream.
    
    This endpoint will gracefully stop the KVS streaming process.
    Use force=true to forcefully kill the process if it's not responding.
    """
    try:
        # Get current stream status before stopping
        stream = kvs_service.get_stream_status(stream_id, current_user, db)
        if not stream:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stream with ID {stream_id} not found or not accessible"
            )
        
        previous_status = stream.status
        
        success, message = kvs_service.stop_stream(stream_id, current_user, db, request.force)
        
        if success:
            # Get updated stream status
            updated_stream = kvs_service.get_stream_status(stream_id, current_user, db)
            current_status = updated_stream.status if updated_stream else "unknown"
            
            return StreamStopResponse(
                stream_id=stream_id,
                stream_name=stream.stream_name,
                previous_status=previous_status,
                current_status=current_status,
                message=message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop stream: {str(e)}"
        )

@router.post("/user/{user_id}/start-all", response_model=StreamBulkOperationResponse)
async def start_all_user_streams(
    user_id: int = Path(..., description="User ID to start all streams for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start streaming for all cameras belonging to a user.
    
    Only admins can start streams for other users, or users can start their own.
    """
    # Permission check
    if current_user.id != user_id and current_user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only start your own streams unless you're an admin or manager"
        )
    
    try:
        # Get target user
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        results = kvs_service.start_all_user_streams(target_user, db)
        
        return StreamBulkOperationResponse(
            user_id=user_id,
            operation="start_all",
            total_cameras=results["total_cameras"],
            successful_operations=results["successful_starts"],
            failed_operations=results["failed_starts"],
            results=results["results"],
            errors=results["errors"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start all user streams: {str(e)}"
        )

@router.post("/user/{user_id}/stop-all", response_model=StreamBulkOperationResponse)
async def stop_all_user_streams(
    user_id: int = Path(..., description="User ID to stop all streams for"),
    force: bool = Query(False, description="Force stop all streams"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stop all streams for a user.
    
    Only admins can stop streams for other users, or users can stop their own.
    """
    # Permission check
    if current_user.id != user_id and current_user.role.name not in ["Admin", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only stop your own streams unless you're an admin or manager"
        )
    
    try:
        # Get target user
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        results = kvs_service.stop_all_user_streams(target_user, db, force)
        
        return StreamBulkOperationResponse(
            user_id=user_id,
            operation="stop_all",
            total_cameras=results["total_streams"],
            successful_operations=results["successful_stops"],
            failed_operations=results["failed_stops"],
            results=results["results"],
            errors=results["errors"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop all user streams: {str(e)}"
        )

@router.get("/{stream_id}/status", response_model=StreamStatusResponse)
async def get_stream_status(
    stream_id: int = Path(..., description="Stream ID to get status for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed status of a specific stream.
    
    This endpoint provides comprehensive information about a single stream
    including process status, health checks, and performance metrics.
    """
    try:
        stream = kvs_service.get_stream_status(stream_id, current_user, db)
        
        if not stream:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stream with ID {stream_id} not found or not accessible"
            )
        
        # Calculate uptime
        uptime_seconds = None
        if stream.status == "running" and stream.start_time:
            uptime_seconds = int((datetime.now(timezone.utc) - stream.start_time).total_seconds())
        
        return StreamStatusResponse(
            stream_id=stream.id,
            stream_name=stream.stream_name,
            kvs_stream_name=stream.kvs_stream_name,
            user_id=stream.user_id,
            username=stream.user.name if stream.user else "Unknown",
            camera_id=stream.camera_id,
            camera_name=stream.camera.name if stream.camera else "Unknown",
            rtsp_url=stream.rtsp_url,
            status=stream.status,
            process_id=stream.process_id,
            process_status=stream.process_status,
            error_message=stream.error_message,
            start_time=stream.start_time,
            stop_time=stream.stop_time,
            last_health_check=stream.last_health_check,
            restart_count=stream.restart_count,
            uptime_seconds=uptime_seconds,
            created_at=stream.created_at,
            updated_at=stream.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stream status: {str(e)}"
        )

@router.get("/{stream_id}/health", response_model=StreamHealthCheck)
async def get_stream_health(
    stream_id: int = Path(..., description="Stream ID to check health for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get health check information for a specific stream.
    
    This endpoint provides detailed health diagnostics including:
    - Process status
    - Common issues detection
    - Recommendations for troubleshooting
    """
    try:
        stream = kvs_service.get_stream_status(stream_id, current_user, db)
        
        if not stream:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stream with ID {stream_id} not found or not accessible"
            )
        
        # Perform health checks
        is_healthy = stream.status == "running" and stream.process_id is not None
        process_running = stream.process_id is not None and stream.process_status == "running"
        
        issues = []
        recommendations = []
        
        # Check for common issues
        if stream.status == "error":
            issues.append("Stream is in error state")
            if stream.error_message:
                issues.append(f"Error: {stream.error_message}")
            recommendations.append("Check stream logs and restart if needed")
        
        if stream.status == "running" and not process_running:
            issues.append("Stream marked as running but process is not active")
            recommendations.append("Restart the stream to recover process")
        
        if stream.restart_count > 0:
            issues.append(f"Stream has been restarted {stream.restart_count} times")
            recommendations.append("Investigate underlying cause of restarts")
        
        if not stream.last_health_check or (datetime.now(timezone.utc) - stream.last_health_check).total_seconds() > 300:
            issues.append("Health check is outdated")
            recommendations.append("Health monitoring may need attention")
        
        # Add general recommendations
        if not issues and is_healthy:
            recommendations.append("Stream is healthy and functioning normally")
        
        return StreamHealthCheck(
            stream_id=stream.id,
            stream_name=stream.stream_name,
            is_healthy=is_healthy,
            process_running=process_running,
            last_check=stream.last_health_check or datetime.now(timezone.utc),
            issues=issues,
            recommendations=recommendations
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stream health: {str(e)}"
        )

@router.post("/cleanup-orphaned")
async def cleanup_orphaned_streams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Clean up orphaned streams (streams marked as running but process doesn't exist).
    
    Only admins can perform cleanup operations.
    """
    if current_user.role.name not in ["Admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform cleanup operations"
        )
    
    try:
        kvs_service.cleanup_orphaned_streams(db)
        
        return {
            "message": "Orphaned streams cleanup completed successfully",
            "timestamp": datetime.now(timezone.utc)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup orphaned streams: {str(e)}"
        )
