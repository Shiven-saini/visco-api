#!/usr/bin/env python3
"""
WireGuard Keypair Generator

This script generates WireGuard-compatible private/public keypairs using Curve25519
and stores them in base64 encoded format. The keys are compatible with WireGuard
and use the same format as the `wg genkey` and `wg pubkey` commands.

Dependencies:
    - pynacl: For Curve25519 cryptographic operations
    
Usage:
    python generate_wireguard_keys.py
"""

import base64
import os
from datetime import datetime
from nacl.public import PrivateKey
from nacl.encoding import Base64Encoder

def generate_wireguard_keypair():
    """
    Generate a WireGuard-compatible private/public keypair.
    
    WireGuard uses Curve25519 for key exchange. The private key is a random
    32-byte value, and the public key is derived from it.
    
    Returns:
        tuple: (private_key_b64, public_key_b64) - Base64 encoded strings
    """
    # Generate a random private key (32 bytes for Curve25519)
    private_key = PrivateKey.generate()
    
    # Get the public key
    public_key = private_key.public_key
    
    # Encode keys in base64 format (WireGuard standard)
    private_key_b64 = base64.b64encode(private_key.encode()).decode('ascii')
    public_key_b64 = base64.b64encode(public_key.encode()).decode('ascii')
    
    return private_key_b64, public_key_b64

def save_keys_to_file(private_key, public_key, filename="secrets_wireguard.txt"):
    """
    Save the generated keypair to a file.
    
    Args:
        private_key (str): Base64 encoded private key
        public_key (str): Base64 encoded public key  
        filename (str): Output filename
    """
    content = f"""PRIVATE_KEY={private_key}
PUBLIC_KEY={public_key}
"""
    
    with open(filename, 'w') as f:
        f.write(content)
    
    # Set restrictive permissions on the file (Unix-like systems)
    if os.name == 'posix':
        os.chmod(filename, 0o600)  # Read/write for owner only

def validate_keys(private_key_b64, public_key_b64):
    """
    Validate that the generated keys are properly formatted and compatible.
    
    Args:
        private_key_b64 (str): Base64 encoded private key
        public_key_b64 (str): Base64 encoded public key
        
    Returns:
        bool: True if keys are valid
    """
    try:
        # Decode and check length
        private_key_bytes = base64.b64decode(private_key_b64)
        public_key_bytes = base64.b64decode(public_key_b64)
        
        # WireGuard keys should be exactly 32 bytes
        if len(private_key_bytes) != 32:
            print(f"Invalid private key length: {len(private_key_bytes)} (expected 32)")
            return False
            
        if len(public_key_bytes) != 32:
            print(f"Invalid public key length: {len(public_key_bytes)} (expected 32)")
            return False
            
        # Verify the public key can be derived from private key
        private_key_obj = PrivateKey(private_key_bytes)
        derived_public_key = private_key_obj.public_key.encode()
        
        if derived_public_key != public_key_bytes:
            print("Public key doesn't match derived public key from private key")
            return False
            
        return True
        
    except Exception as e:
        print(f"Key validation failed: {e}")
        return False

def main():
    """Main function to generate and save WireGuard keypair."""
    
    try:
        # Generate keypair
        private_key, public_key = generate_wireguard_keypair()
        
        # Validate keys
        if not validate_keys(private_key, public_key):
            print("Key generation failed validation!")
            return 1
        
        # Display keys
        print(f"PRIVATE_KEY={private_key}")
        print(f"PUBLIC_KEY={public_key}")
        
        # Save to file
        filename = "secrets_wireguard.txt"
        save_keys_to_file(private_key, public_key, filename)
        
        # Return the keypair for programmatic use
        return {
            'private_key': private_key,
            'public_key': public_key,
            'file_path': os.path.abspath(filename)
        }
        
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please install: pip install pynacl")
        return 1
        
    except Exception as e:
        print(f"Error generating keypair: {e}")
        return 1

if __name__ == "__main__":
    result = main()
    if isinstance(result, dict):
        # Script succeeded, keys generated
        exit(0)
    else:
        # Script failed
        exit(result)
