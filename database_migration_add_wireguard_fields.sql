-- Migration to add WireGuard IP and external port fields to camera_details table
-- This migration adds the new fields needed for proper KVS streaming with WireGuard VPN

-- Add new columns to camera_details table
ALTER TABLE camera_details 
ADD COLUMN camera_port VARCHAR DEFAULT '554',
ADD COLUMN wireguard_ip VARCHAR,
ADD COLUMN external_port VARCHAR DEFAULT '8551';

-- Update existing data: 
-- 1. Set camera_port to '554' (default RTSP port) for existing cameras
-- 2. Move current port values to external_port (these should be the forwarding ports)
UPDATE camera_details 
SET camera_port = '554',
    external_port = COALESCE(port, '8551')
WHERE camera_port IS NULL;

-- Add comments to document the field purposes
COMMENT ON COLUMN camera_details.camera_ip IS 'Local camera IP address (e.g., 192.168.1.100)';
COMMENT ON COLUMN camera_details.camera_port IS 'Local camera RTSP port (typically 554)';
COMMENT ON COLUMN camera_details.wireguard_ip IS 'WireGuard VPN IP address of the device';
COMMENT ON COLUMN camera_details.external_port IS 'External port for port forwarding (e.g., 8551, 8552, etc.)';
COMMENT ON COLUMN camera_details.port IS 'Legacy port field - now stores external_port for backward compatibility';

-- Create index for performance on WireGuard IP lookups
CREATE INDEX IF NOT EXISTS idx_camera_details_wireguard_ip ON camera_details(wireguard_ip);
CREATE INDEX IF NOT EXISTS idx_camera_details_external_port ON camera_details(external_port);

-- Show the migration results
SELECT 
    id,
    name,
    camera_ip,
    camera_port,
    wireguard_ip,
    external_port,
    port as legacy_port,
    status
FROM camera_details 
ORDER BY id;
