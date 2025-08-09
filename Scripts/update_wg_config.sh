#!/bin/bash
# WireGuard configuration update script
# Usage: update_wg_config.sh {add|remove} {temp_file|public_key}

WG_CONFIG_FILE="/etc/wireguard/wg0.conf"
BACKUP_DIR="/etc/wireguard/backup"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

case "$1" in
    "add")
        if [ -z "$2" ]; then
            echo "Error: Temporary file path required for add operation"
            exit 1
        fi
        
        # Append peer configuration from temp file
        cat "$2" >> "$WG_CONFIG_FILE"
        echo "Peer added to WireGuard configuration"
        exit 0
        ;;
        
    "remove")
        if [ -z "$2" ]; then
            echo "Error: Public key required for remove operation"
            exit 1
        fi
        
        # Create temporary file without the specified peer
        PUBLIC_KEY="$2"
        TEMP_CONFIG="/tmp/wg0_temp.conf"
        
        # Process the config file and exclude the peer with matching public key
        awk -v pubkey="$PUBLIC_KEY" '
        BEGIN { skip = 0 }
        /^\[Peer\]/ { 
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
        ' "$WG_CONFIG_FILE" > "$TEMP_CONFIG"
        
        # Replace original with filtered version
        mv "$TEMP_CONFIG" "$WG_CONFIG_FILE"
        echo "Peer removed from WireGuard configuration"
        exit 0
        ;;
        
    *)
        echo "Usage: $0 {add|remove} {temp_file|public_key}"
        exit 1
        ;;
esac

