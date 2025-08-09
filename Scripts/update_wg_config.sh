#!/bin/bash
# WireGuard configuration update script
# Usage: update_wg_config.sh {add|remove} {temp_file|public_key}

WG_CONFIG_FILE="/etc/wireguard/wg0.conf"
BACKUP_DIR="/etc/wireguard/backup"
LOG_FILE="/var/log/wireguard_updates.log"

# Logging function
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Ensure log file exists
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
        
        # Append peer configuration from temp file
        if cat "$TEMP_FILE" >> "$WG_CONFIG_FILE"; then
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
        
        # Verify WireGuard config file exists
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
        
        # Create temporary file for filtered config
        TEMP_CONFIG="/tmp/wg0_temp_$(date +%Y%m%d_%H%M%S).conf"
        
        # Process the config file and exclude the peer with matching public key
        if awk -v pubkey="$PUBLIC_KEY" '
        BEGIN { skip = 0 }
        /^\[Peer\]/ { 
            peer_start = NR
            getline line
            if (line ~ "^PublicKey = " pubkey "$") {
                skip = 1
                next
            } else {
                print "[Peer]"
                print line
                skip = 0
            }
        }
        /^\[Interface\]/ { skip = 0; print; next }
        /^\[Peer\]/ && skip == 0 { print; next }
        skip == 0 { print }
        /^$/ && skip == 1 { skip = 0 }
        ' "$WG_CONFIG_FILE" > "$TEMP_CONFIG"; then
            
            # Replace original with filtered version
            if mv "$TEMP_CONFIG" "$WG_CONFIG_FILE"; then
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
                exit 1
            fi
        else
            log_message "ERROR: Failed to process config file"
            echo "Error: Failed to process config file"
            rm -f "$TEMP_CONFIG"
            exit 1
        fi
        ;;
        
    *)
        echo "Usage: $0 {add|remove} {temp_file|public_key}"
        log_message "ERROR: Invalid usage - $*"
        exit 1
        ;;
esac
