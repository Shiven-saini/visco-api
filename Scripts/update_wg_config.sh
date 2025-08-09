#!/bin/bash
# WireGuard configuration update script
# Usage: update_wg_config.sh {add|remove} {temp_file|public_key} [temp_dir]

WG_CONFIG_FILE="/etc/wireguard/wg0.conf"
BACKUP_DIR="/etc/wireguard/backup"
LOG_FILE="/var/log/wireguard_updates.log"

# Function to get best temp directory
get_temp_dir() {
    local preferred_temp="$1"
    local temp_dirs=("$preferred_temp" "/var/tmp" "/tmp" "/home/ec2-user/tmp")
    
    for temp_dir in "${temp_dirs[@]}"; do
        if [ -z "$temp_dir" ]; then
            continue
        fi
        
        # Create directory if it doesn't exist
        mkdir -p "$temp_dir" 2>/dev/null
        
        # Check if directory is writable and has space
        if [ -w "$temp_dir" ]; then
            # Simple space check - try to create a small test file
            if echo "test" > "$temp_dir/wg_space_test" 2>/dev/null; then
                rm -f "$temp_dir/wg_space_test"
                echo "$temp_dir"
                return 0
            fi
        fi
    done
    
    # Fallback
    echo "/tmp"
    return 1
}

# Function to clean up excess blank lines in config
cleanup_config() {
    local config_file="$1"
    local temp_file="$2"
    
    # Remove excessive blank lines while preserving single blank lines between sections
    awk '
    BEGIN { blank_count = 0 }
    /^$/ { 
        blank_count++
        if (blank_count <= 1) {
            blank_lines[blank_count] = $0
        }
        next
    }
    /./ {
        # Print accumulated blank lines (max 1)
        if (blank_count > 0) {
            if (blank_count == 1) {
                print ""
            }
            blank_count = 0
        }
        print
    }
    END {
        # Don'\''t add trailing blank lines
    }
    ' "$config_file" > "$temp_file"
}

# Logging function
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"
touch "$LOG_FILE"

case "$1" in
    "add")
        if [ -z "$2" ]; then
            log_message "ERROR: Temporary file path required for add operation"
            echo "Error: Temporary file path required for add operation"
            exit 1
        fi
        
        TEMP_FILE="$2"
        
        # Verify temporary file exists and is readable
        if [ ! -f "$TEMP_FILE" ]; then
            log_message "ERROR: Temporary file '$TEMP_FILE' does not exist"
            echo "Error: Temporary file '$TEMP_FILE' does not exist"
            exit 1
        fi
        
        if [ ! -r "$TEMP_FILE" ]; then
            log_message "ERROR: Cannot read temporary file '$TEMP_FILE'"
            echo "Error: Cannot read temporary file '$TEMP_FILE'"
            exit 1
        fi
        
        # Verify WireGuard config file exists
        if [ ! -f "$WG_CONFIG_FILE" ]; then
            log_message "ERROR: WireGuard config file '$WG_CONFIG_FILE' does not exist"
            echo "Error: WireGuard config file '$WG_CONFIG_FILE' does not exist"
            exit 1
        fi
        
        # Check if config file is writable
        if [ ! -w "$WG_CONFIG_FILE" ]; then
            log_message "ERROR: Cannot write to WireGuard config file '$WG_CONFIG_FILE'"
            echo "Error: Cannot write to WireGuard config file '$WG_CONFIG_FILE'"
            exit 1
        fi
        
        # Get temp directory for cleanup
        TEMP_DIR=$(get_temp_dir "$3")
        CLEANUP_TEMP="$TEMP_DIR/wg_cleanup_$(date +%Y%m%d_%H%M%S).conf"
        
        # Append peer configuration from temp file
        if cat "$TEMP_FILE" >> "$WG_CONFIG_FILE"; then
            # Clean up excess blank lines after addition
            cleanup_config "$WG_CONFIG_FILE" "$CLEANUP_TEMP"
            mv "$CLEANUP_TEMP" "$WG_CONFIG_FILE"
            
            log_message "SUCCESS: Peer added to WireGuard configuration from '$TEMP_FILE'"
            echo "Peer added to WireGuard configuration"
            exit 0
        else
            log_message "ERROR: Failed to append peer configuration to '$WG_CONFIG_FILE'"
            echo "Error: Failed to append peer configuration"
            exit 1
        fi
        ;;
        
    "remove")
        if [ -z "$2" ]; then
            log_message "ERROR: Public key required for remove operation"
            echo "Error: Public key required for remove operation"
            exit 1
        fi
        
        PUBLIC_KEY="$2"
        PREFERRED_TEMP_DIR="$3"  # Third argument is preferred temp directory
        
        # Get the best temp directory
        TEMP_DIR=$(get_temp_dir "$PREFERRED_TEMP_DIR")
        log_message "INFO: Using temp directory: $TEMP_DIR"
        
        if [ ! -f "$WG_CONFIG_FILE" ]; then
            log_message "ERROR: WireGuard config file '$WG_CONFIG_FILE' does not exist"
            echo "Error: WireGuard config file '$WG_CONFIG_FILE' does not exist"
            exit 1
        fi
        
        # Create backup before modification
        BACKUP_FILE="$BACKUP_DIR/wg0_backup_$(date +%Y%m%d_%H%M%S).conf"
        if ! cp "$WG_CONFIG_FILE" "$BACKUP_FILE"; then
            log_message "WARNING: Failed to create backup file '$BACKUP_FILE'"
        else
            log_message "INFO: Backup created at '$BACKUP_FILE'"
        fi
        
        # Create temporary file for filtered config using dynamic temp directory
        TEMP_CONFIG="$TEMP_DIR/wg0_temp_$(date +%Y%m%d_%H%M%S).conf"
        CLEANUP_TEMP="$TEMP_DIR/wg_cleanup_$(date +%Y%m%d_%H%M%S).conf"
        log_message "INFO: Creating temporary config file: $TEMP_CONFIG"
        
        # Improved awk logic that properly handles peer blocks and removes excess whitespace
        if awk -v target_pubkey="$PUBLIC_KEY" '
        BEGIN { 
            in_peer_block = 0
            current_peer_pubkey = ""
            skip_current_peer = 0
            peer_lines = ""
        }
        
        # Start of Interface section
        /^\[Interface\]/ {
            # Output any pending peer block
            if (in_peer_block && !skip_current_peer && peer_lines != "") {
                print peer_lines
            }
            in_peer_block = 0
            skip_current_peer = 0
            print
            next
        }
        
        # Start of Peer section
        /^\[Peer\]/ {
            # If we were in a previous peer block, output it if not skipping
            if (in_peer_block && !skip_current_peer && peer_lines != "") {
                print peer_lines
            }
            
            # Reset for new peer block
            in_peer_block = 1
            current_peer_pubkey = ""
            skip_current_peer = 0
            peer_lines = "[Peer]"
            next
        }
        
        # Inside a peer block
        in_peer_block == 1 {
            # Skip empty lines within peer blocks for cleaner output
            if (/^$/) {
                next
            }
            
            # Look for PublicKey line
            if (/^PublicKey = /) {
                current_peer_pubkey = $3  # Extract the public key
                if (current_peer_pubkey == target_pubkey) {
                    skip_current_peer = 1
                }
            }
            
            # Add line to current peer block (unless we are skipping)
            if (!skip_current_peer) {
                peer_lines = peer_lines "\n" $0
            }
            next
        }
        
        # Lines outside peer blocks (like in Interface section)
        in_peer_block == 0 {
            # Skip excessive blank lines
            if (/^$/) {
                next
            }
            print
            next
        }
        
        # End of file - output last peer if not skipping
        END {
            if (in_peer_block && !skip_current_peer && peer_lines != "") {
                print peer_lines
            }
        }
        ' "$WG_CONFIG_FILE" > "$TEMP_CONFIG"; then
            
            # Clean up excess blank lines in the filtered config
            cleanup_config "$TEMP_CONFIG" "$CLEANUP_TEMP"
            
            # Replace original with cleaned version
            if mv "$CLEANUP_TEMP" "$WG_CONFIG_FILE"; then
                # Clean up temp files
                rm -f "$TEMP_CONFIG"
                
                log_message "SUCCESS: Peer with public key '$PUBLIC_KEY' removed from WireGuard configuration"
                echo "Peer removed from WireGuard configuration"
                exit 0
            else
                log_message "ERROR: Failed to replace config file"
                echo "Error: Failed to replace config file"
                # Restore from backup if available
                if [ -f "$BACKUP_FILE" ]; then
                    cp "$BACKUP_FILE" "$WG_CONFIG_FILE"
                    log_message "INFO: Config file restored from backup"
                fi
                rm -f "$TEMP_CONFIG" "$CLEANUP_TEMP"
                exit 1
            fi
        else
            log_message "ERROR: Failed to process config file - awk command failed"
            echo "Error: Failed to process config file"
            rm -f "$TEMP_CONFIG" "$CLEANUP_TEMP"
            exit 1
        fi
        ;;
        
    *)
        echo "Usage: $0 {add|remove} {temp_file|public_key} [temp_dir]"
        log_message "ERROR: Invalid usage - $*"
        exit 1
        ;;
esac
