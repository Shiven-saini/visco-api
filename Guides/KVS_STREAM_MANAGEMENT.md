# KVS Stream Management System

This documentation describes the comprehensive Amazon Kinesis Video Streams (KVS) integration that allows users to stream their VPN-tunneled RTSP camera feeds directly to AWS KVS using the kvs_gstreamer_sample binary.

## Overview

The KVS Stream Management System provides:

- **Automatic Stream Management**: Start/stop individual camera streams or all user streams
- **VPN Integration**: Uses existing WireGuard VPN infrastructure to access cameras
- **Process Monitoring**: Real-time monitoring of streaming processes
- **Health Checks**: Automatic detection of failed streams and recovery options
- **Multi-User Support**: Organization-based access control with user isolation
- **Robust Error Handling**: Comprehensive error handling and troubleshooting

## Architecture

### Components

1. **KVSStream Model**: Database model to track streaming processes
2. **KVSStreamService**: Core service for managing stream processes
3. **Stream Router**: REST API endpoints for stream management
4. **Process Utilities**: System utilities for process management
5. **Migration Script**: Database schema updates

### Process Flow

1. User requests to start streaming for a camera
2. System validates VPN access and camera permissions
3. VPN-accessible RTSP URL is constructed
4. KVS process is spawned using kvs_gstreamer_sample binary
5. Process is monitored and status is tracked in database
6. Users can monitor, stop, or manage streams through API

## API Endpoints

### Stream Status

#### Get All User Streams
```http
GET /stream/status?include_stopped=false
Authorization: Bearer <access_token>
```

**Response:**
```json
[
    {
        "stream_id": 1,
        "stream_name": "john_1",
        "kvs_stream_name": "john-1",
        "user_id": 123,
        "username": "john",
        "camera_id": 45,
        "camera_name": "Front Door Camera",
        "rtsp_url": "rtsp://admin:pass@10.0.0.4:8551/cam/realmonitor",
        "status": "running",
        "process_id": 12345,
        "process_status": "running",
        "start_time": "2025-01-01T10:00:00Z",
        "uptime_seconds": 3600,
        "restart_count": 0,
        "created_at": "2025-01-01T10:00:00Z"
    }
]
```

#### Get User Stream Summary
```http
GET /stream/user/{user_id}/status
Authorization: Bearer <access_token>
```

**Response:**
```json
{
    "user_id": 123,
    "username": "john",
    "organization_name": "ACME Corp",
    "total_streams": 3,
    "active_streams": 2,
    "stopped_streams": 1,
    "error_streams": 0,
    "streams": [...]
}
```

#### Get Specific Stream Status
```http
GET /stream/{stream_id}/status
Authorization: Bearer <access_token>
```

### Stream Control

#### Start Stream
```http
POST /stream/start
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "camera_id": 45,
    "custom_stream_name": "front_door_cam"  // Optional
}
```

**Response:**
```json
{
    "stream_id": 1,
    "stream_name": "john_1",
    "kvs_stream_name": "john-1",
    "camera_name": "Front Door Camera",
    "rtsp_url": "rtsp://admin:pass@10.0.0.4:8551/cam/realmonitor",
    "status": "running",
    "message": "Stream started successfully"
}
```

#### Stop Stream
```http
POST /stream/stop/{stream_id}?force=false
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "force": false
}
```

**Response:**
```json
{
    "stream_id": 1,
    "stream_name": "john_1",
    "previous_status": "running",
    "current_status": "stopped",
    "message": "Process terminated gracefully"
}
```

### Bulk Operations

#### Start All User Streams
```http
POST /stream/user/{user_id}/start-all
Authorization: Bearer <access_token>
```

**Response:**
```json
{
    "user_id": 123,
    "operation": "start_all",
    "total_cameras": 3,
    "successful_operations": 2,
    "failed_operations": 1,
    "results": [
        {
            "camera_id": 45,
            "camera_name": "Front Door",
            "success": true,
            "message": "Stream started successfully",
            "stream_id": 1,
            "stream_name": "john_1"
        }
    ],
    "errors": ["Camera Garage: VPN configuration not active"]
}
```

#### Stop All User Streams
```http
POST /stream/user/{user_id}/stop-all?force=false
Authorization: Bearer <access_token>
```

### Health & Monitoring

#### Stream Health Check
```http
GET /stream/{stream_id}/health
Authorization: Bearer <access_token>
```

**Response:**
```json
{
    "stream_id": 1,
    "stream_name": "john_1",
    "is_healthy": true,
    "process_running": true,
    "last_check": "2025-01-01T11:00:00Z",
    "issues": [],
    "recommendations": ["Stream is healthy and functioning normally"]
}
```

#### Cleanup Orphaned Streams (Admin Only)
```http
POST /stream/cleanup-orphaned
Authorization: Bearer <admin_access_token>
```

## Stream Naming Convention

Streams are automatically named using the format: `{username}_{number}`

- **username**: Sanitized username (alphanumeric only)
- **number**: Sequential number starting from 1

Examples:
- `john_1`, `john_2`, `john_3`
- `alice_1`, `alice_2`
- `user123_1` (for users with special characters)

Custom stream names can be provided but must:
- Be unique across all active streams
- Contain only alphanumeric characters, hyphens, and underscores
- Be converted to AWS KVS compatible format (hyphens replace underscores)

## Database Schema

### KVSStream Table
```sql
CREATE TABLE kvs_streams (
    id SERIAL PRIMARY KEY,
    stream_name VARCHAR UNIQUE NOT NULL,           -- e.g., "john_1"
    user_id INTEGER NOT NULL REFERENCES users(id),
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    camera_id INTEGER NOT NULL REFERENCES camera_details(id),
    rtsp_url VARCHAR NOT NULL,                     -- VPN-accessible RTSP URL
    kvs_stream_name VARCHAR NOT NULL,              -- AWS KVS stream name
    status VARCHAR DEFAULT 'stopped',             -- stopped, starting, running, error, stopping
    process_id INTEGER,                            -- System process ID
    process_status VARCHAR,                        -- Process status details
    error_message VARCHAR,                         -- Error message if any
    start_time TIMESTAMPTZ,                       -- When stream was started
    stop_time TIMESTAMPTZ,                        -- When stream was stopped
    last_health_check TIMESTAMPTZ,               -- Last health check time
    restart_count INTEGER DEFAULT 0,              -- Number of restarts
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Installation & Setup

### 1. Database Migration
```bash
python migrate_add_kvs_streams.py
```

### 2. Verify KVS Binary
Ensure the KVS binary is available at:
```
/home/ubuntu/kvs/kvs-producer-sdk-cpp/build/kvs_gstreamer_sample
```

### 3. AWS Configuration
Ensure AWS credentials are configured for KVS access:
```bash
# Set AWS environment variables or use AWS credentials file
export AWS_REGION=us-west-2
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

### 4. Restart Application
```bash
# Restart FastAPI application to load new routes
systemctl restart visco-api  # or your service name
```

## Process Management

### Automatic Process Monitoring
- Streams are monitored for process health
- Orphaned processes are automatically detected
- Health checks run periodically

### Process States
- **stopped**: Stream is not running
- **starting**: Stream is being started
- **running**: Stream is active and streaming
- **stopping**: Stream is being stopped
- **error**: Stream encountered an error

### Error Recovery
- Automatic detection of failed processes
- Manual restart capabilities
- Force stop for unresponsive processes
- Cleanup of orphaned database records

## Security & Permissions

### Access Control
- Users can only manage their own streams
- Admins and Managers can manage streams for users in their organization
- Super Admins have full access

### VPN Requirements
- Streams require active WireGuard VPN configuration
- RTSP URLs use VPN-allocated IP addresses
- Automatic validation of VPN status before streaming

### Data Protection
- Camera credentials are handled securely
- Process information is organization-isolated
- Stream URLs contain authentication tokens

## Monitoring & Troubleshooting

### Common Issues

1. **VPN Configuration Problems**
   - Error: "Unable to generate VPN RTSP URL"
   - Solution: Check VPN configuration is active and not expired

2. **Binary Not Found**
   - Error: "KVS binary not found"
   - Solution: Ensure kvs_gstreamer_sample is installed and executable

3. **Stream Startup Failures**
   - Error: "Process failed to start"
   - Solution: Check RTSP URL accessibility and AWS credentials

4. **Orphaned Processes**
   - Issue: Processes running but not tracked
   - Solution: Use cleanup endpoint or restart application

### Health Monitoring
- Regular process health checks
- Automatic status updates
- Performance metrics tracking
- Error alerting capabilities

### Logging
- Comprehensive logging of all stream operations
- Process start/stop events
- Error conditions and recovery actions
- Performance metrics

## Usage Examples

### Python Client
```python
import requests

# Authentication
auth_response = requests.post("http://api.example.com/auth/login", {
    "username": "user@example.com",
    "password": "password"
})
token = auth_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Start streaming for a camera
start_response = requests.post(
    "http://api.example.com/stream/start",
    json={"camera_id": 45},
    headers=headers
)
stream_info = start_response.json()
print(f"Started stream: {stream_info['stream_name']}")

# Check stream status
status_response = requests.get(
    f"http://api.example.com/stream/{stream_info['stream_id']}/status",
    headers=headers
)
status = status_response.json()
print(f"Stream status: {status['status']}")

# Stop stream
stop_response = requests.post(
    f"http://api.example.com/stream/stop/{stream_info['stream_id']}",
    headers=headers
)
print("Stream stopped")
```

### Bash Script
```bash
#!/bin/bash
API_BASE="http://api.example.com"
TOKEN="your_access_token"

# Start all streams for user
curl -X POST "$API_BASE/stream/user/123/start-all" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json"

# Get stream status
curl -X GET "$API_BASE/stream/status" \
     -H "Authorization: Bearer $TOKEN"

# Stop all streams
curl -X POST "$API_BASE/stream/user/123/stop-all" \
     -H "Authorization: Bearer $TOKEN"
```

## Performance Considerations

### Resource Usage
- Each stream consumes CPU and memory resources
- Monitor system resources when running multiple streams
- Consider stream quality settings for bandwidth optimization

### Scalability
- Database indexes optimize query performance
- Process monitoring scales with number of streams
- Consider implementing stream limits per user/organization

### AWS KVS Limits
- Be aware of AWS KVS service limits
- Monitor KVS usage and costs
- Implement stream lifecycle management

## Future Enhancements

1. **Stream Quality Management**
   - Dynamic quality adjustment based on bandwidth
   - Multiple quality levels per stream
   - Adaptive bitrate streaming

2. **Advanced Monitoring**
   - Stream performance metrics
   - Bandwidth usage tracking
   - Real-time alerts for stream failures

3. **Automated Recovery**
   - Automatic stream restart on failures
   - Intelligent retry mechanisms
   - Load balancing across multiple KVS streams

4. **Stream Recording**
   - Local recording capabilities
   - Scheduled recording
   - Cloud storage integration

5. **Analytics Integration**
   - Stream usage analytics
   - Performance dashboards
   - Usage reporting

## Support

For issues or questions regarding the KVS Stream Management System:

1. Check the troubleshooting section above
2. Review application logs for error details
3. Use the health check endpoints for diagnostics
4. Contact system administrator for AWS or infrastructure issues

## Configuration

### Environment Variables
```bash
# KVS Binary Location (default: /home/ubuntu/kvs/kvs-producer-sdk-cpp/build/kvs_gstreamer_sample)
KVS_BINARY_PATH=/path/to/kvs_gstreamer_sample

# AWS Configuration
AWS_REGION=us-west-2
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Stream Configuration
MAX_STREAMS_PER_USER=10
STREAM_HEALTH_CHECK_INTERVAL=300  # seconds
PROCESS_TIMEOUT=30  # seconds
```

This completes the comprehensive KVS Stream Management System implementation.
