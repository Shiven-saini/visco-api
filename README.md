# Visco Backend API

A **FastAPI backend** with JWT authentication, PostgreSQL database integration, WireGuard VPN support, comprehensive user management, and **Amazon Kinesis Video Streams (KVS) integration** for camera streaming.

## Features

- **JWT Authentication** (30-day token validity)
- **User Management** (Register, Login, Profile, Update, Delete)
- **PostgreSQL Integration** with SQLAlchemy
- **Interactive API Documentation** (Swagger UI)
- **WireGuard VPN Integration** for secure camera access
- **Camera Management** with VPN-tunneled RTSP streaming
- **Amazon KVS Streaming** for real-time video processing
- **Process Management** for streaming services
- **Comprehensive Error Handling** and monitoring

## Prerequisites

- **Python 3.9+**
- **PostgreSQL** (running service)
- **Database:** `visco` (must exist)
- **PostgreSQL Credentials:** username=`shiven`, password=`Shiven@123`
- **WireGuard** (for VPN functionality)
- **Amazon KVS Producer SDK** (compiled binary required)
- **AWS Credentials** (for KVS streaming)

***

## Setup Instructions

### **Option 1: Quick Setup with Script**

```bash
# 1. Navigate to project directory
cd visco-api-2

# 2. Make setup script executable and run
chmod +x setup_kvs_streaming.sh
./setup_kvs_streaming.sh
```

### **Option 2: Manual Setup**

```bash
# 1. Clone/navigate to project directory
cd visco-api-2

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run database migration for KVS streams
python migrate_add_kvs_streams.py

# 6. Configure AWS credentials
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_REGION="us-west-2"

# 7. Set KVS binary path
export KVS_BINARY_PATH="/home/ubuntu/kvs/kvs-producer-sdk-cpp/build/kvs_gstreamer_sample"

# 8. Run the application
python run.py
```

### **Option 3: Using UV Package Manager**

```bash
# 1. Navigate to project directory
cd visco-api-2

# 2. Install dependencies and run
uv run run.py
```

***

## Access the API

Once running, the API will be available at:

- **API Base URL:** `http://localhost:8086`
- **Swagger Documentation:** `http://localhost:8086/docs`
- **ReDoc Documentation:** `http://localhost:8086/redoc`
- **Health Check:** `http://localhost:8086/health`

***

## API Endpoints

### **Authentication Endpoints**
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/auth/register` | Register new user | ❌ |
| `POST` | `/auth/login` | User login (returns JWT) | ❌ |
| `POST` | `/auth/logout` | Logout (client-side) | ❌ |

### **User Management Endpoints**
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/users/profile` | Get current user profile | ✅ |
| `PUT` | `/users/profile` | Update user profile | ✅ |
| `DELETE` | `/users/profile` | Delete user account | ✅ |
| `GET` | `/users/all` | List all users | ✅ |

### **Camera Management Endpoints**
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/cameras/vpn-streams` | Get VPN-accessible camera streams | ✅ |
| `GET` | `/cameras/vpn-streams/{camera_id}` | Get specific camera VPN stream | ✅ |
| `POST` | `/cameras/` | Add new camera (Admin only) | ✅ |
| `PUT` | `/cameras/{camera_id}` | Update camera (Admin only) | ✅ |
| `DELETE` | `/cameras/{camera_id}` | Delete camera (Admin only) | ✅ |

### **WireGuard VPN Endpoints**
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/wireguard/generate-config` | Generate VPN configuration | ✅ |
| `GET` | `/wireguard/config` | Download VPN config file | ✅ |
| `DELETE` | `/wireguard/config` | Revoke VPN configuration | ✅ |
| `GET` | `/wireguard/status` | Get VPN server status | ✅ |

### **KVS Stream Management Endpoints** 🆕
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/stream/status` | Get all user streams status | ✅ |
| `GET` | `/stream/user/{user_id}/status` | Get user stream summary | ✅ |
| `POST` | `/stream/start` | Start streaming for a camera | ✅ |
| `POST` | `/stream/stop/{stream_id}` | Stop specific stream | ✅ |
| `POST` | `/stream/user/{user_id}/start-all` | Start all user streams | ✅ |
| `POST` | `/stream/user/{user_id}/stop-all` | Stop all user streams | ✅ |
| `GET` | `/stream/{stream_id}/status` | Get specific stream status | ✅ |
| `GET` | `/stream/{stream_id}/health` | Get stream health check | ✅ |
| `POST` | `/stream/cleanup-orphaned` | Cleanup orphaned streams (Admin) | ✅ |

***

## KVS Streaming Usage Examples

### **Start Streaming for a Camera**
```bash
curl -X POST "http://localhost:8086/stream/start" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": 1,
    "custom_stream_name": "front_door_cam"
  }'
```

### **Get Stream Status**
```bash
curl -X GET "http://localhost:8086/stream/status" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### **Stop a Stream**
```bash
curl -X POST "http://localhost:8086/stream/stop/1" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
```

### **Start All Streams for User**
```bash
curl -X POST "http://localhost:8086/stream/user/123/start-all" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

***

## Testing the System

### **Run Comprehensive Tests**
```bash
# Configure test environment
export API_BASE_URL="http://localhost:8086"
export TEST_USERNAME="your_username"
export TEST_PASSWORD="your_password"

# Run the test suite
./run_kvs_tests.sh
```

### **Manual Testing Steps**
1. **Setup cameras** using `/cameras/` endpoints
2. **Generate VPN config** using `/wireguard/generate-config`
3. **Connect to VPN** using the downloaded configuration
4. **Start streaming** using `/stream/start`
5. **Monitor streams** using `/stream/status`
6. **View in AWS KVS** console

***

## Configuration

### **Environment Variables**
```bash
# KVS Configuration
export KVS_BINARY_PATH="/home/ubuntu/kvs/kvs-producer-sdk-cpp/build/kvs_gstreamer_sample"

# AWS Configuration  
export AWS_REGION="us-west-2"
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"

# Stream Limits
export MAX_STREAMS_PER_USER="10"
export STREAM_HEALTH_CHECK_INTERVAL="300"
```

### **KVS Binary Setup**
The system requires the compiled KVS Producer SDK binary:
```bash
# Example build location
/home/ubuntu/kvs/kvs-producer-sdk-cpp/build/kvs_gstreamer_sample
```

Make sure the binary is executable:
```bash
chmod +x /path/to/kvs_gstreamer_sample
```

***

## Architecture Overview

### **Stream Management Flow**
1. **User requests stream** via API
2. **System validates** VPN access and camera permissions  
3. **VPN RTSP URL** is constructed using WireGuard IP
4. **KVS process spawned** using kvs_gstreamer_sample binary
5. **Process monitored** and status tracked in database
6. **Health checks** ensure stream reliability

### **Security Model**
- **Organization-based isolation** - users only access their org's cameras
- **VPN-required access** - all camera streams require active VPN
- **JWT authentication** - all endpoints require valid tokens
- **Process isolation** - each stream runs in separate process

***

## Quick Usage Guide

### **1. Register and Get Token**
```bash
# Register
curl -X POST "http://localhost:8086/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com", 
    "password": "mypassword",
    "first_name": "Test",
    "last_name": "User"
  }'

# Login
curl -X POST "http://localhost:8086/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "mypassword"
  }'
```

### **2. Setup VPN and Camera**
```bash
# Generate VPN config
curl -X POST "http://localhost:8086/wireguard/generate-config" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Add a camera (Admin only)
curl -X POST "http://localhost:8086/cameras/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door",
    "c_ip": "192.168.1.100",
    "port": 554,
    "username": "admin",
    "password": "password123",
    "status": "active",
    "stream_url": "/cam/realmonitor"
  }'
```

### **3. Start KVS Streaming**
```bash
# Start streaming
curl -X POST "http://localhost:8086/stream/start" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"camera_id": 1}'

# Check status
curl -X GET "http://localhost:8086/stream/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

***

## Troubleshooting

**KVS Binary Issues:**
- Verify binary exists and is executable
- Check AWS credentials configuration
- Ensure proper permissions on binary directory

**Stream Startup Failures:**
- Check VPN configuration is active
- Verify camera RTSP URL accessibility
- Review AWS KVS service limits

**Database Issues:**
- Run migration: `python migrate_add_kvs_streams.py`
- Check PostgreSQL connection
- Verify table creation

**Process Management:**
- Use cleanup endpoint for orphaned streams
- Check system resources (CPU/Memory)
- Monitor process logs

***

## Documentation

- **Comprehensive Guide:** [KVS_STREAM_MANAGEMENT.md](KVS_STREAM_MANAGEMENT.md)
- **API Documentation:** `http://localhost:8086/docs`
- **VPN Setup Guide:** [CAMERA_VPN_STREAMING.md](CAMERA_VPN_STREAMING.md)

***

## Project Structure
```
visco-api-2/
├── app/
│   ├── main.py                    # FastAPI app
│   ├── models.py                  # SQLAlchemy models (includes KVSStream)
│   ├── schemas.py                 # Pydantic schemas
│   ├── routers/
│   │   ├── stream_routes.py       # KVS stream management endpoints
│   │   ├── camera_routes.py       # Camera management
│   │   └── wireguard_routes.py    # VPN management
│   ├── services/
│   │   ├── kvs_stream_service.py  # KVS stream management service
│   │   └── wireguard_service.py   # VPN service
│   └── utils/
│       └── process_utils.py       # Process management utilities
├── migrate_add_kvs_streams.py     # Database migration
├── setup_kvs_streaming.sh         # Setup script
├── test_kvs_streaming.py          # Comprehensive test suite
├── run_kvs_tests.sh              # Test runner
├── KVS_STREAM_MANAGEMENT.md      # Detailed documentation
├── requirements.txt              # Dependencies
└── run.py                        # App entry point
```

***

## Contact & Support

**Author:** Shiven Saini  
**Email:** [shiven.career@proton.me](mailto:shiven.career@proton.me)

For KVS streaming issues, check the comprehensive documentation in `KVS_STREAM_MANAGEMENT.md` or run the test suite with `./run_kvs_tests.sh` to diagnose problems.