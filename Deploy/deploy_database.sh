#!/bin/bash

# PostgreSQL 17 Database Deployment Script
# This script sets up PostgreSQL 17 with the configuration from .env file
# Must be run with sudo privileges

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if running as root/sudo
check_sudo() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run with sudo privileges!"
        print_error "Usage: sudo $0"
        exit 1
    fi
    print_success "Running with sudo privileges"
}

# Function to load environment variables from .env file
load_env_config() {
    local env_file="../.env"
    
    if [[ ! -f "$env_file" ]]; then
        print_error ".env file not found at $env_file"
        exit 1
    fi
    
    print_status "Loading database configuration from .env file..."
    
    # Source the .env file and extract database configuration
    DB_NAME=$(grep "^DB_NAME=" "$env_file" | cut -d'=' -f2)
    DB_USER=$(grep "^DB_USER=" "$env_file" | cut -d'=' -f2)
    DB_PASSWORD=$(grep "^DB_PASSWORD=" "$env_file" | cut -d'=' -f2)
    DB_HOST=$(grep "^DB_HOST=" "$env_file" | cut -d'=' -f2)
    DB_PORT=$(grep "^DB_PORT=" "$env_file" | cut -d'=' -f2)
    
    # Validate that all required variables are loaded
    if [[ -z "$DB_NAME" || -z "$DB_USER" || -z "$DB_PASSWORD" ]]; then
        print_error "Failed to load database configuration from .env file"
        print_error "Required: DB_NAME, DB_USER, DB_PASSWORD"
        exit 1
    fi
    
    print_success "Database configuration loaded:"
    print_status "  Database Name: $DB_NAME"
    print_status "  Database User: $DB_USER"
    print_status "  Database Host: ${DB_HOST:-localhost}"
    print_status "  Database Port: ${DB_PORT:-5432}"
}

# Function to install PostgreSQL 17
install_postgresql() {
    print_status "Step 1: Installing PostgreSQL 17..."
    
    # Check if PostgreSQL 17 is already installed
    if command -v psql >/dev/null 2>&1; then
        local pg_version=$(psql --version | grep -oP '\d+\.\d+' | head -1)
        if [[ "$pg_version" == "17."* ]]; then
            print_warning "PostgreSQL 17 is already installed"
            return 0
        fi
    fi
    
    print_status "Adding PostgreSQL 17 official repository..."
    
    # Add PostgreSQL APT repository
    if ! sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'; then
        print_error "Failed to add PostgreSQL repository"
        return 1
    fi
    
    # Import repository signing key
    print_status "Importing PostgreSQL signing key..."
    if ! wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | tee /etc/apt/trusted.gpg.d/pgdg.asc &>/dev/null; then
        print_error "Failed to import PostgreSQL signing key"
        return 1
    fi
    
    # Update package list
    print_status "Updating package list..."
    if ! apt update; then
        print_error "Failed to update package list"
        return 1
    fi
    
    # Install PostgreSQL 17
    print_status "Installing PostgreSQL 17 server and client..."
    if ! apt install -y postgresql-17 postgresql-client-17; then
        print_error "Failed to install PostgreSQL 17"
        return 1
    fi
    
    print_success "PostgreSQL 17 installed successfully"
}

# Function to configure PostgreSQL authentication
configure_authentication() {
    print_status "Step 2: Configuring PostgreSQL authentication..."
    
    local pg_version="17"
    local pg_config_dir="/etc/postgresql/$pg_version/main"
    local pg_hba_file="$pg_config_dir/pg_hba.conf"
    local pg_conf_file="$pg_config_dir/postgresql.conf"
    
    if [[ ! -f "$pg_hba_file" ]]; then
        print_error "PostgreSQL configuration file not found: $pg_hba_file"
        return 1
    fi
    
    # Backup original pg_hba.conf
    print_status "Backing up pg_hba.conf..."
    if ! cp "$pg_hba_file" "$pg_hba_file.backup.$(date +%Y%m%d_%H%M%S)"; then
        print_error "Failed to backup pg_hba.conf"
        return 1
    fi
    
    # Configure authentication to use md5 instead of peer
    print_status "Configuring password authentication..."
    
    # Update local connections to use md5 authentication
    sed -i 's/^local\s\+all\s\+postgres\s\+peer$/local   all             postgres                                md5/' "$pg_hba_file"
    sed -i 's/^local\s\+all\s\+all\s\+peer$/local   all             all                                     md5/' "$pg_hba_file"
    
    # Ensure host connections use md5
    sed -i 's/^host\s\+all\s\+all\s\+127\.0\.0\.1\/32\s\+ident$/host    all             all             127.0.0.1\/32            md5/' "$pg_hba_file"
    sed -i 's/^host\s\+all\s\+all\s\+::1\/128\s\+ident$/host    all             all             ::1\/128                 md5/' "$pg_hba_file"
    
    # Add custom configuration for the application user
    if ! grep -q "# Custom visco-api configuration" "$pg_hba_file"; then
        cat >> "$pg_hba_file" << EOF

# Custom visco-api configuration
host    all             $DB_USER        127.0.0.1/32            md5
host    all             $DB_USER        ::1/128                 md5
local   all             $DB_USER                                md5
EOF
    fi
    
    print_success "Authentication configured successfully"
}

# Function to set PostgreSQL root password
set_root_password() {
    print_status "Step 3: Setting PostgreSQL root (postgres) password..."
    
    # Start PostgreSQL service if not running
    if ! systemctl is-active --quiet postgresql; then
        print_status "Starting PostgreSQL service..."
        if ! systemctl start postgresql; then
            print_error "Failed to start PostgreSQL service"
            return 1
        fi
    fi
    
    # Set postgres user password
    print_status "Setting postgres user password to 'Admin@123'..."
    if ! sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'Admin@123';"; then
        print_error "Failed to set postgres user password"
        return 1
    fi
    
    print_success "PostgreSQL root password set successfully"
}

# Function to create application user and database
create_user_and_database() {
    print_status "Step 4: Creating application user and database..."
    
    # Create the application user with required privileges
    print_status "Creating user '$DB_USER' with required privileges..."
    
    # Check if user already exists
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER';" | grep -q 1; then
        print_warning "User '$DB_USER' already exists"
        
        # Update password for existing user
        if ! sudo -u postgres psql -c "ALTER USER $DB_USER PASSWORD '$DB_PASSWORD';"; then
            print_error "Failed to update password for user '$DB_USER'"
            return 1
        fi
        
        # Update privileges for existing user
        if ! sudo -u postgres psql -c "ALTER USER $DB_USER SUPERUSER CREATEDB CREATEROLE REPLICATION BYPASSRLS;"; then
            print_error "Failed to update privileges for user '$DB_USER'"
            return 1
        fi
        
        print_success "Updated existing user '$DB_USER'"
    else
        # Create new user with all required privileges
        if ! sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD' SUPERUSER CREATEDB CREATEROLE REPLICATION BYPASSRLS;"; then
            print_error "Failed to create user '$DB_USER'"
            return 1
        fi
        print_success "User '$DB_USER' created successfully"
    fi
    
    # Create the database
    print_status "Creating database '$DB_NAME'..."
    
    # Check if database already exists
    if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        print_warning "Database '$DB_NAME' already exists"
    else
        # Create database owned by the application user
        if ! sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"; then
            print_error "Failed to create database '$DB_NAME'"
            return 1
        fi
        print_success "Database '$DB_NAME' created successfully"
    fi
    
    # Grant all privileges on database to user (redundant but explicit)
    if ! sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"; then
        print_warning "Could not grant privileges (user may already have them)"
    fi
    
    # Test connection with the new user
    print_status "Testing database connection..."
    if ! PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" >/dev/null 2>&1; then
        print_error "Failed to connect to database with user '$DB_USER'"
        return 1
    fi
    
    print_success "Database connection test successful"
}

# Function to restart PostgreSQL service
restart_postgresql() {
    print_status "Step 5: Restarting PostgreSQL service..."
    
    if ! systemctl restart postgresql; then
        print_error "Failed to restart PostgreSQL service"
        return 1
    fi
    
    # Wait a moment for service to fully start
    sleep 3
    
    # Verify service is running
    if ! systemctl is-active --quiet postgresql; then
        print_error "PostgreSQL service is not running after restart"
        return 1
    fi
    
    print_success "PostgreSQL service restarted successfully"
}

# Function to display final information
show_final_info() {
    print_success "PostgreSQL 17 deployment completed successfully!"
    echo
    print_status "Connection Details:"
    print_status "  Host: ${DB_HOST:-localhost}"
    print_status "  Port: ${DB_PORT:-5432}"
    print_status "  Database: $DB_NAME"
    print_status "  Username: $DB_USER"
    print_status "  Password: $DB_PASSWORD"
    echo
    print_status "Root PostgreSQL User:"
    print_status "  Username: postgres"
    print_status "  Password: Admin@123"
    echo
    print_status "Test connection with:"
    print_status "  psql -h ${DB_HOST:-localhost} -p ${DB_PORT:-5432} -U $DB_USER -d $DB_NAME"
    echo
    print_status "Service status:"
    systemctl status postgresql --no-pager -l
}

# Main function
main() {
    echo "=========================================="
    echo "PostgreSQL 17 Database Deployment Script"
    echo "=========================================="
    echo
    
    # Execute all steps in sequence
    check_sudo || exit 1
    load_env_config || exit 1
    install_postgresql || exit 1
    configure_authentication || exit 1
    set_root_password || exit 1
    create_user_and_database || exit 1
    restart_postgresql || exit 1
    
    echo
    show_final_info
    
    print_success "Database deployment completed successfully!"
}

# Run main function
main "$@"
