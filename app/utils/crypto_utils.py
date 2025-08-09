import base64
from nacl.public import PrivateKey

def generate_wireguard_keypair():
    """
    Generate a Curve25519 (X25519) key pair for WireGuard.
    Returns base64-encoded private and public keys.
    """
    # Create a new private key (32 bytes) – PyNaCl uses X25519 (Curve25519)
    sk = PrivateKey.generate()

    # Extract raw 32-byte keys
    private_key_bytes = bytes(sk)            # Private (secret) key
    public_key_bytes = bytes(sk.public_key)  # Corresponding public key

    # Base64-encode each
    b64_private = base64.b64encode(private_key_bytes).decode("ascii")
    b64_public = base64.b64encode(public_key_bytes).decode("ascii")

    return b64_private, b64_public

def validate_wireguard_key(key: str) -> bool:
    """
    Validate if a string is a valid WireGuard key (base64, 44 chars).
    """
    try:
        decoded = base64.b64decode(key)
        return len(decoded) == 32 and len(key) == 44
    except Exception:
        return False
