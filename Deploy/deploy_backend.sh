#!/bin/bash

# Visco API Backend Deployment Script
# This script deploys the FastAPI backend with systemd services and WireGuard integration
# Must be run with sudo privileges

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
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

# Function to get the actual username (not root when using sudo)
get_actual_username() {
    # Get the user who invoked sudo
    if [[ -n "$SUDO_USER" ]]; then
        echo "$SUDO_USER"
    else
        # Fallback methods
        local username=$(logname 2>/dev/null || echo "")
        if [[ -n "$username" && "$username" != "root" ]]; then
            echo "$username"
        else
            # Try to get from /home directory
            username=$(ls /home/ 2>/dev/null | head -1)
            if [[ -n "$username" ]]; then
                echo "$username"
            else
                # Final fallback - common usernames
                for user in ubuntu ec2-user admin; do
                    if id "$user" &>/dev/null; then
                        echo "$user"
                        return
                    fi
                done
                echo "root"
            fi
        fi
    fi
}

# Function to ask for user confirmation
ask_confirmation() {
    print_step "Pre-deployment Verification"
    echo
    print_warning "Before proceeding, please confirm the following prerequisites:"
    echo
    echo "  ✓ PostgreSQL database is installed and configured"
    echo "  ✓ Database user and visco database exist"
    echo "  ✓ WireGuard is installed and configured"
    echo "  ✓ Python environment and dependencies are ready"
    echo "  ✓ FastAPI application code is in the correct location"
    echo
    read -p "$(echo -e ${YELLOW}Have you completed all the above prerequisites? ${NC}[y/N]: )" -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Deployment cancelled by user"
        print_status "Please complete the prerequisites and run the script again"
        print_status "Suggestions:"
        print_status "  1. Run the database deployment script: sudo ./deploy_database.sh"
        print_status "  2. Install WireGuard: sudo apt install wireguard"
        print_status "  3. Set up Python environment and install dependencies"
        exit 1
    fi
    
    print_success "Prerequisites confirmed, proceeding with deployment..."
    echo
}

# Function to fetch server public IP
fetch_public_ip() {
    print_step "Step 1: Fetching server public IP address..."
    
    local public_ip=""
    local max_retries=3
    local retry_count=0
    
    while [[ $retry_count -lt $max_retries ]]; do
        print_status "Attempting to fetch public IP (attempt $((retry_count + 1))/$max_retries)..."
        
        if public_ip=$(curl -s --connect-timeout 10 http://checkip.amazonaws.com); then
            # Validate IP format
            if [[ $public_ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
                print_success "Server public IP: $public_ip"
                echo "$public_ip" > /tmp/server_public_ip.txt
                return 0
            else
                print_warning "Invalid IP format received: $public_ip"
            fi
        else
            print_warning "Failed to fetch IP address"
        fi
        
        ((retry_count++))
        if [[ $retry_count -lt $max_retries ]]; then
            print_status "Retrying in 3 seconds..."
            sleep 3
        fi
    done
    
    print_error "Failed to fetch server public IP address after $max_retries attempts"
    print_error "This could be due to:"
    print_error "  - No internet connectivity"
    print_error "  - checkip.amazonaws.com is unreachable"
    print_error "  - Network firewall blocking the request"
    print_error "Please check your network connection and try again"
    return 1
}

# Function to copy systemd files
copy_systemd_files() {
    print_step "Step 2: Installing systemd service files..."
    
    local systemd_dir="../Systemd"
    local target_dir="/etc/systemd/system"
    
    if [[ ! -d "$systemd_dir" ]]; then
        print_error "Systemd directory not found: $systemd_dir"
        return 1
    fi
    
    # List files to be copied
    local files_copied=0
    for file in "$systemd_dir"/*; do
        if [[ -f "$file" ]]; then
            local filename=$(basename "$file")
            print_status "Copying $filename to $target_dir/"
            
            if cp "$file" "$target_dir/"; then
                print_success "Copied: $filename"
                ((files_copied++))
            else
                print_error "Failed to copy: $filename"
                return 1
            fi
        fi
    done
    
    if [[ $files_copied -eq 0 ]]; then
        print_warning "No systemd files found in $systemd_dir"
    else
        print_success "Copied $files_copied systemd service files"
        
        # Reload systemd daemon to recognize new files
        print_status "Reloading systemd daemon..."
        if systemctl daemon-reload; then
            print_success "Systemd daemon reloaded"
        else
            print_error "Failed to reload systemd daemon"
            return 1
        fi
    fi
}

# Function to install WireGuard update script
install_wg_script() {
    print_step "Step 3: Installing WireGuard configuration script..."
    
    local source_script="../Scripts/update_wg_config.sh"
    local target_script="/usr/local/bin/update_wg_config.sh"
    
    if [[ ! -f "$source_script" ]]; then
        print_error "WireGuard update script not found: $source_script"
        return 1
    fi
    
    # Check if target file exists
    if [[ -f "$target_script" ]]; then
        print_warning "Existing WireGuard script found at $target_script"
        print_status "Backing up existing script..."
        
        local backup_file="${target_script}.backup.$(date +%Y%m%d_%H%M%S)"
        if cp "$target_script" "$backup_file"; then
            print_success "Backup created: $backup_file"
        else
            print_warning "Failed to create backup, proceeding anyway..."
        fi
        
        print_status "Replacing existing script with newer version..."
    fi
    
    # Copy the script
    print_status "Installing WireGuard configuration script..."
    if cp "$source_script" "$target_script"; then
        print_success "Script installed: $target_script"
    else
        print_error "Failed to install WireGuard script"
        return 1
    fi
    
    # Set proper permissions
    print_status "Setting script permissions..."
    if chmod +x "$target_script"; then
        print_success "Script made executable"
    else
        print_error "Failed to make script executable"
        return 1
    fi
    
    # Set ownership
    print_status "Setting script ownership..."
    if chown root:root "$target_script"; then
        print_success "Script ownership set to root:root"
    else
        print_error "Failed to set script ownership"
        return 1
    fi
    
    print_success "WireGuard configuration script installed successfully"
}

# Function to configure sudo privileges for WireGuard script
configure_sudo_privileges() {
    print_step "Step 4: Configuring sudo privileges for WireGuard script..."
    
    # Get the actual username
    local username=$(get_actual_username)
    print_status "Detected username: $username"
    
    local sudoers_file="/etc/sudoers.d/wireguard-visco"
    local sudo_line="$username ALL=(ALL) NOPASSWD: /usr/local/bin/update_wg_config.sh"
    
    # Create a dedicated sudoers file for this application
    print_status "Creating sudoers configuration..."
    
    # Check if the rule already exists
    if [[ -f "$sudoers_file" ]] && grep -q "$username.*update_wg_config.sh" "$sudoers_file"; then
        print_warning "Sudo rule already exists for $username"
        print_status "Updating existing rule..."
    fi
    
    # Create the sudoers file with proper permissions
    if echo "$sudo_line" > "$sudoers_file"; then
        print_success "Sudoers rule created: $sudoers_file"
    else
        print_error "Failed to create sudoers rule"
        return 1
    fi
    
    # Set proper permissions for sudoers file
    if chmod 440 "$sudoers_file"; then
        print_success "Sudoers file permissions set correctly"
    else
        print_error "Failed to set sudoers file permissions"
        return 1
    fi
    
    # Validate the sudoers syntax
    print_status "Validating sudoers syntax..."
    if visudo -c -f "$sudoers_file"; then
        print_success "Sudoers syntax validation passed"
    else
        print_error "Sudoers syntax validation failed"
        print_error "Removing invalid sudoers file..."
        rm -f "$sudoers_file"
        return 1
    fi
    
    print_success "Sudo privileges configured for user '$username'"
    print_status "User '$username' can now run: sudo /usr/local/bin/update_wg_config.sh"
}

# Function to start systemd services
start_services() {
    print_step "Step 5: Starting systemd services..."
    
    local services=("visco-api" "wg-watch.path" "wg-watch.service")
    local started_services=()
    local failed_services=()
    
    for service in "${services[@]}"; do
        print_status "Starting service: $service"
        
        # Check if service file exists
        if [[ ! -f "/etc/systemd/system/$service" ]]; then
            print_warning "Service file not found: $service (skipping)"
            continue
        fi
        
        # Enable the service
        if systemctl enable "$service"; then
            print_success "Enabled service: $service"
        else
            print_warning "Failed to enable service: $service"
        fi
        
        # Start the service
        if systemctl start "$service"; then
            print_success "Started service: $service"
            started_services+=("$service")
            
            # Brief pause to allow service to initialize
            sleep 2
            
            # Check service status
            if systemctl is-active --quiet "$service"; then
                print_success "Service $service is running"
            else
                print_warning "Service $service may not be running properly"
            fi
        else
            print_error "Failed to start service: $service"
            failed_services+=("$service")
        fi
        
        echo
    done
    
    # Summary
    if [[ ${#started_services[@]} -gt 0 ]]; then
        print_success "Successfully started services: ${started_services[*]}"
    fi
    
    if [[ ${#failed_services[@]} -gt 0 ]]; then
        print_error "Failed to start services: ${failed_services[*]}"
        print_status "Check service logs with: journalctl -u <service-name> -f"
        return 1
    fi
    
    print_success "All systemd services started successfully"
}

# Function to show deployment summary
show_deployment_summary() {
    local public_ip=""
    if [[ -f "/tmp/server_public_ip.txt" ]]; then
        public_ip=$(cat /tmp/server_public_ip.txt)
    fi
    
    echo
    print_success "🎉 Backend deployment completed successfully!"
    echo
    print_status "=== Deployment Summary ==="
    
    if [[ -n "$public_ip" ]]; then
        print_status "Server Public IP: $public_ip"
    fi
    
    print_status "Systemd services installed and started:"
    print_status "  ✓ visco-api (FastAPI backend)"
    print_status "  ✓ wg-watch.path (WireGuard config watcher)"
    print_status "  ✓ wg-watch.service (WireGuard config updater)"
    
    local username=$(get_actual_username)
    print_status "WireGuard script configured for user: $username"
    print_status "Script location: /usr/local/bin/update_wg_config.sh"
    
    echo
    print_status "=== Next Steps ==="
    print_status "1. Verify services are running:"
    print_status "   sudo systemctl status visco-api"
    print_status "   sudo systemctl status wg-watch.path"
    print_status "   sudo systemctl status wg-watch.service"
    
    print_status "2. Check application logs:"
    print_status "   sudo journalctl -u visco-api -f"
    
    if [[ -n "$public_ip" ]]; then
        print_status "3. Test API endpoint (adjust port as needed):"
        print_status "   curl http://$public_ip:8000/"
    fi
    
    print_status "4. Monitor WireGuard configuration updates:"
    print_status "   sudo journalctl -u wg-watch -f"
    
    echo
    print_success "Deployment completed! Your Visco API backend is now running."
}

# Main function
main() {
    echo "================================================"
    echo "🚀 Visco API Backend Deployment Script"
    echo "================================================"
    echo
    
    # Execute all steps in sequence
    check_sudo || exit 1
    ask_confirmation || exit 1
    fetch_public_ip || exit 1
    copy_systemd_files || exit 1
    install_wg_script || exit 1
    configure_sudo_privileges || exit 1
    start_services || exit 1
    
    show_deployment_summary
    
    # Cleanup temporary files
    rm -f /tmp/server_public_ip.txt
    
    print_success "🎯 Backend deployment script completed successfully!"
}

# Trap to cleanup on exit
trap 'rm -f /tmp/server_public_ip.txt' EXIT

# Run main function
main "$@"
