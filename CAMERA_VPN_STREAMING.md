# VPN Camera Streaming Feature

This document describes the new VPN camera streaming functionality that allows users to access camera RTSP streams through their WireGuard VPN connection.

## Overview

The VPN camera streaming feature transforms local camera RTSP URLs to use the user's WireGuard VPN IP address and external ports, enabling secure remote access to camera streams.

### Key Features

- **Secure Access**: Camera streams accessible only through user's WireGuard VPN
- **IP Transformation**: Automatically replaces local camera IPs with user's VPN IP
- **Port Mapping**: Uses external ports for VPN access instead of local camera ports
- **Multi-Camera Support**: Handles multiple cameras per organization
- **Error Handling**: Robust error handling for various camera configurations

## API Endpoints

### 1. Get All VPN Camera Streams

```http
GET /cameras/vpn-streams
Authorization: Bearer <access_token>
```

**Description**: Returns all active cameras for the user's organization with VPN-accessible RTSP URLs.

**Response Example**:
```json
[
    {
        "id": 1,
        "name": "Front Door Camera",
        "camera_ip": "192.168.88.200",
        "external_port": "8551",
        "stream_url": "/cam/realmonitor?channel=1&subtype=0",
        "vpn_stream_url": "rtsp://admin:industry4@10.0.0.4:8551/cam/realmonitor?channel=1&subtype=0",
        "status": "active",
        "location": "Main Entrance",
        "resolution": "1080p",
        "features": "night_vision,motion_detect",
        "last_active": "2025-08-26T10:30:00"
    }
]
```

### 2. Get Single Camera VPN Stream

```http
GET /cameras/vpn-streams/{camera_id}
Authorization: Bearer <access_token>
```

**Description**: Returns a specific camera's VPN-accessible RTSP URL.

**Parameters**:
- `camera_id` (path): ID of the camera

## URL Transformation Logic

### Input Examples
- **Local RTSP**: `rtsp://admin:industry4@192.168.88.200:554/cam/realmonitor?channel=1&subtype=0`
- **User's VPN IP**: `10.0.0.4`
- **External Port**: `8551`

### Output
- **VPN RTSP**: `rtsp://admin:industry4@10.0.0.4:8551/cam/realmonitor?channel=1&subtype=0`

## Database Changes

### New Column: `external_port`

Added to `camera_details` table:
```sql
ALTER TABLE camera_details ADD COLUMN external_port VARCHAR;
```

### Updated Camera Configuration Schema

```python
class CameraConfigSchema(BaseModel):
    name: str
    c_ip: str
    status: str
    port: int
    external_port: Optional[int] = None  # New field
    stream_url: str
    username: str
    password: str
```

## Prerequisites

### 1. WireGuard Configuration
Users must have an active WireGuard configuration to access VPN camera streams:

```http
POST /wireguard/generate-config
Authorization: Bearer <access_token>
```

### 2. Camera Configuration
Cameras should be configured with external ports for optimal functionality:

```http
POST /cameras/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "name": "Front Door Camera",
    "c_ip": "192.168.88.200",
    "status": "active",
    "port": 554,
    "external_port": 8551,
    "stream_url": "/cam/realmonitor?channel=1&subtype=0",
    "username": "admin",
    "password": "industry4"
}
```

## Error Handling

### Common Error Scenarios

1. **No WireGuard Configuration**
   ```json
   {
       "detail": "No WireGuard configuration found for user. Please generate a VPN configuration first."
   }
   ```

2. **Inactive WireGuard Configuration**
   ```json
   {
       "detail": "WireGuard configuration is not active. Please contact administrator."
   }
   ```

3. **No Active Cameras**
   ```json
   {
       "detail": "No active cameras found for your organization."
   }
   ```

4. **Camera Not Found**
   ```json
   {
       "detail": "Camera not found or you don't have permission to access it."
   }
   ```

## Installation & Migration

### 1. Update Database Schema
Run the migration script to add the `external_port` column:

```bash
python migration_add_external_port.py
```

### 2. Restart Application
After running the migration, restart your FastAPI application.

## Configuration

### Default External Port
If no external port is specified for a camera, the system defaults to `8551`.

### Port Assignment Strategy
- **Sequential Assignment**: Assign ports incrementally (8551, 8552, 8553, etc.)
- **Fixed Assignment**: Use the same external port for all cameras
- **Custom Assignment**: Allow administrators to specify custom external ports

## Security Considerations

1. **VPN-Only Access**: Camera streams are only accessible through WireGuard VPN
2. **User Isolation**: Users can only access cameras from their organization
3. **Active Configuration Check**: Ensures WireGuard configuration is active
4. **Credential Protection**: Camera credentials are securely handled

## Usage Examples

### Python Client Example
```python
import requests

# Get access token first
auth_response = requests.post("http://api.example.com/auth/login", {
    "username": "user@example.com",
    "password": "password"
})
token = auth_response.json()["access_token"]

# Get VPN camera streams
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://api.example.com/cameras/vpn-streams",
    headers=headers
)

cameras = response.json()
for camera in cameras:
    print(f"Camera: {camera['name']}")
    print(f"VPN Stream URL: {camera['vpn_stream_url']}")
    print("---")
```

### VLC Media Player
Use the VPN stream URL directly in VLC:
```
rtsp://admin:industry4@10.0.0.4:8551/cam/realmonitor?channel=1&subtype=0
```

### FFmpeg
```bash
ffmpeg -i "rtsp://admin:industry4@10.0.0.4:8551/cam/realmonitor?channel=1&subtype=0" -c copy output.mp4
```

## Troubleshooting

### 1. Stream URL Not Working
- Check if WireGuard VPN is connected
- Verify camera is active and accessible
- Ensure external port is correctly configured

### 2. Permission Denied
- Verify user has access to the organization's cameras
- Check if WireGuard configuration is active

### 3. Network Issues
- Ensure port forwarding is configured on the network
- Check firewall rules for external ports
- Verify WireGuard tunnel is established

## Future Enhancements

1. **Dynamic Port Allocation**: Automatically assign available external ports
2. **Load Balancing**: Distribute camera load across multiple external ports
3. **Stream Health Monitoring**: Check camera stream availability
4. **Bandwidth Optimization**: Adaptive streaming based on connection quality
5. **Multi-Stream Support**: Support for multiple stream qualities per camera
