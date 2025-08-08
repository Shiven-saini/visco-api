# Visco Backend API

A **FastAPI backend** with JWT authentication, PostgreSQL database integration, and comprehensive user management endpoints.

## Features

- **JWT Authentication** (30-day token validity)
- **User Management** (Register, Login, Profile, Update, Delete)
- **PostgreSQL Integration** with SQLAlchemy
- **Interactive API Documentation** (Swagger UI)
- **Modern FastAPI** with latest packages

## Prerequisites

- **Python 3.9+**
- **PostgreSQL** (running service)
- **Database:** `visco` (must exist)
- **PostgreSQL Credentials:** username=`shiven`, password=`Shiven@123`

***

## Setup Instructions

### **Option 1: Using Virtual Environment (venv)**

```bash
# 1. Clone/navigate to project directory
cd visco-api

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the application
python run.py
```

### **Option 2: Using UV Package Manager**

```bash
# 1. Navigate to project directory
cd visco-api

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

***

## Quick Usage Guide

### **1. Register a New User**
```bash
curl -X POST "http://localhost:8086/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com", 
    "password": "mypassword",
    "first_name": "Test",
    "last_name": "User"
  }'
```

### **2. Login and Get JWT Token**
```bash
curl -X POST "http://localhost:8086/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "mypassword"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 2592000
}
```

### **3. Access Protected Endpoints**
```bash
curl -X GET "http://localhost:8086/users/profile" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE"
```

***

## Testing with Swagger UI

1. **Open** `http://localhost:8086/docs`
2. **Register** a new user using `/auth/register`
3. **Login** using `/auth/login` to get your JWT token
4. **Click** the **Authorize** button in Swagger UI
5. **Enter:** `Bearer YOUR_JWT_TOKEN_HERE`
6. **Test** all protected endpoints!

***

## Integration with Visco Connect C++ Qt Application

For your **C++17 & Qt 6.5.3** Windows app:

1. **Make HTTP POST** to `/auth/login` with credentials
2. **Store the JWT token** from response
3. **Include header** in all authenticated requests:
   ```
   Authorization: Bearer YOUR_JWT_TOKEN_HERE
   ```
4. **Token expires** in 30 days

***

## Troubleshooting

**Database Connection Issues:**
- Ensure PostgreSQL service is running
- Verify database "visco" exists
- Check credentials in `app/database.py`

**Port Already in Use:**
- Change port in `run.py`: `uvicorn.run(..., port=8001)`

**Import Errors:**
- Ensure you're in the correct directory
- Virtual environment is activated

***

## Project Structure
```
visco_auth_api/
├── app/
│   ├── main.py           # FastAPI app
│   ├── database.py       # DB configuration  
│   ├── models.py         # SQLAlchemy models
│   ├── schemas.py        # Pydantic schemas
│   ├── auth.py          # JWT utilities
│   ├── dependencies.py  # Auth dependencies
│   └── routers/         # API route handlers
├── requirements.txt     # Dependencies
└── run.py              # App entry point
```

**Contact Me**<br>
Author : Shiven Saini<br>
Email: [shiven.career@proton.me](mailto:shiven.career@proton.me)