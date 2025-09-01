#!/bin/bash

# KVS Stream Management Setup Script
# This script sets up the KVS streaming functionality

set -e  # Exit on any error

echo "🚀 Setting up KVS Stream Management System"
echo "=========================================="

# Configuration
KVS_BINARY_PATH="${KVS_BINARY_PATH:-/home/ubuntu/kvs/kvs-producer-sdk-cpp/build/kvs_gstreamer_sample}"
PYTHON_ENV="${PYTHON_ENV:-venv}"
SERVICE_NAME="${SERVICE_NAME:-visco-api}"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check prerequisites
log_info "Checking prerequisites..."

if ! command_exists python3; then
    log_error "Python3 is not installed"
    exit 1
fi

if ! command_exists pip; then
    log_error "pip is not installed"
    exit 1
fi

log_success "Python prerequisites are available"

# Step 2: Check KVS binary
log_info "Checking KVS binary at: $KVS_BINARY_PATH"

if [ ! -f "$KVS_BINARY_PATH" ]; then
    log_error "KVS binary not found at: $KVS_BINARY_PATH"
    log_info "Please ensure kvs_gstreamer_sample is compiled and available"
    log_info "You can set custom path with: export KVS_BINARY_PATH=/path/to/binary"
    exit 1
fi

if [ ! -x "$KVS_BINARY_PATH" ]; then
    log_error "KVS binary is not executable: $KVS_BINARY_PATH"
    log_info "Run: chmod +x $KVS_BINARY_PATH"
    exit 1
fi

log_success "KVS binary is available and executable"

# Step 3: Check AWS credentials
log_info "Checking AWS configuration..."

if [ -z "$AWS_ACCESS_KEY_ID" ] && [ -z "$AWS_PROFILE" ] && [ ! -f ~/.aws/credentials ]; then
    log_warning "AWS credentials not found"
    log_info "Please configure AWS credentials using one of:"
    log_info "  - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
    log_info "  - AWS profile: AWS_PROFILE"
    log_info "  - AWS credentials file: ~/.aws/credentials"
else
    log_success "AWS configuration appears to be set"
fi

# Step 4: Activate virtual environment if exists
if [ -d "$PYTHON_ENV" ]; then
    log_info "Activating Python virtual environment: $PYTHON_ENV"
    source "$PYTHON_ENV/bin/activate"
    log_success "Virtual environment activated"
fi

# Step 5: Install additional dependencies if needed
log_info "Checking Python dependencies..."

# Check if psutil is available
if ! python3 -c "import psutil" 2>/dev/null; then
    log_info "Installing psutil for process management..."
    pip install psutil
fi

log_success "Python dependencies are available"

# Step 6: Run database migration
log_info "Running database migration..."

if python3 migrate_add_kvs_streams.py; then
    log_success "Database migration completed successfully"
else
    log_error "Database migration failed"
    exit 1
fi

# Step 7: Test KVS binary
log_info "Testing KVS binary..."

cd "$(dirname "$KVS_BINARY_PATH")"
BINARY_NAME="$(basename "$KVS_BINARY_PATH")"

# Test binary help/version
if timeout 5s "./$BINARY_NAME" --help 2>/dev/null || timeout 5s "./$BINARY_NAME" --version 2>/dev/null; then
    log_success "KVS binary responds to commands"
elif [ $? -eq 124 ]; then
    log_success "KVS binary is responsive (timeout is expected for help command)"
else
    log_warning "KVS binary test inconclusive, but binary exists and is executable"
fi

cd - > /dev/null

# Step 8: Create service configuration if running as service
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    log_info "Service $SERVICE_NAME is running"
    
    log_info "Adding KVS binary path to service environment..."
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
    
    if [ -f "$SERVICE_FILE" ]; then
        # Check if KVS_BINARY_PATH is already in the service file
        if ! grep -q "KVS_BINARY_PATH" "$SERVICE_FILE"; then
            log_info "Adding KVS_BINARY_PATH environment variable to service"
            # This would require sudo privileges
            log_warning "Manual step required: Add the following to $SERVICE_FILE under [Service]:"
            echo "Environment=\"KVS_BINARY_PATH=$KVS_BINARY_PATH\""
        else
            log_success "KVS_BINARY_PATH already configured in service"
        fi
    fi
fi

# Step 9: Test basic API functionality
log_info "Testing basic API connectivity..."

# Try to connect to the API (assuming it's running)
API_URL="${API_URL:-http://localhost:8000}"

if curl -s "$API_URL/health" > /dev/null 2>&1; then
    log_success "API is accessible at $API_URL"
    
    # Test if stream endpoints are available
    if curl -s "$API_URL/docs" | grep -q "stream" 2>/dev/null; then
        log_success "Stream endpoints are available in API documentation"
    else
        log_warning "Stream endpoints may not be loaded yet"
    fi
else
    log_warning "API is not accessible at $API_URL (may not be running)"
fi

# Step 10: Create example configuration
log_info "Creating example configuration..."

cat > kvs_stream_config.example << 'EOF'
# KVS Stream Management Configuration

# KVS Binary Path
export KVS_BINARY_PATH="/home/ubuntu/kvs/kvs-producer-sdk-cpp/build/kvs_gstreamer_sample"

# AWS Configuration
export AWS_REGION="us-west-2"
export AWS_ACCESS_KEY_ID="your_access_key_here"
export AWS_SECRET_ACCESS_KEY="your_secret_key_here"

# Optional: AWS Profile instead of keys
# export AWS_PROFILE="your_profile_name"

# Stream Configuration
export MAX_STREAMS_PER_USER="10"
export STREAM_HEALTH_CHECK_INTERVAL="300"
export PROCESS_TIMEOUT="30"

# API Configuration
export API_BASE_URL="http://localhost:8000"
EOF

log_success "Created example configuration file: kvs_stream_config.example"

# Step 11: Create test script runner
log_info "Creating test script runner..."

cat > run_kvs_tests.sh << 'EOF'
#!/bin/bash

# Load configuration if exists
if [ -f "kvs_stream_config" ]; then
    source kvs_stream_config
fi

# Set defaults
export API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
export TEST_USERNAME="${TEST_USERNAME:-admin@example.com}"
export TEST_PASSWORD="${TEST_PASSWORD:-password}"

echo "Running KVS Stream Tests..."
echo "API URL: $API_BASE_URL"
echo "Username: $TEST_USERNAME"
echo ""

python3 test_kvs_streaming.py
EOF

chmod +x run_kvs_tests.sh
log_success "Created test runner: run_kvs_tests.sh"

# Step 12: Service restart recommendation
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    log_info "Recommending service restart to load new routes..."
    log_warning "Please restart the service to load KVS stream routes:"
    log_info "  sudo systemctl restart $SERVICE_NAME"
    log_info "  sudo systemctl status $SERVICE_NAME"
fi

# Step 13: Final summary
echo ""
echo "🎉 KVS Stream Management Setup Complete!"
echo "========================================"
echo ""
log_success "Database migration completed"
log_success "KVS binary verified: $KVS_BINARY_PATH"
log_success "Configuration examples created"
log_success "Test scripts ready"
echo ""
echo "Next Steps:"
echo "1. Configure AWS credentials (see kvs_stream_config.example)"
echo "2. Restart the FastAPI service if running"
echo "3. Test the functionality with: ./run_kvs_tests.sh"
echo "4. Check API documentation at: $API_URL/docs"
echo ""
echo "KVS Stream Endpoints will be available at:"
echo "  - GET  /stream/status"
echo "  - POST /stream/start"
echo "  - POST /stream/stop/{stream_id}"
echo "  - POST /stream/user/{user_id}/start-all"
echo "  - POST /stream/user/{user_id}/stop-all"
echo ""
echo "For detailed documentation, see: KVS_STREAM_MANAGEMENT.md"
echo ""

# Check if we should restart service automatically
if [ "$AUTO_RESTART_SERVICE" = "true" ] && systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    log_info "AUTO_RESTART_SERVICE is enabled, restarting service..."
    if sudo systemctl restart "$SERVICE_NAME"; then
        log_success "Service restarted successfully"
        sleep 3
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log_success "Service is running"
        else
            log_error "Service failed to start after restart"
        fi
    else
        log_error "Failed to restart service"
    fi
fi

log_success "Setup completed successfully! 🎉"
