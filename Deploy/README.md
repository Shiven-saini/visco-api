# Visco API Backend Deployment Guide

**Contact for any queries:** Shiven Saini - shiven.career@proton.me

This directory contains comprehensive deployment scripts and documentation for the Visco API FastAPI backend with WireGuard VPN integration.

## Files

- `deploy_database.sh` - PostgreSQL 17 deployment and configuration script
- `deploy_backend.sh` - FastAPI backend deployment with systemd services

## Step-by-Step Deployment Instructions

### Step 1: Setup UV Package Manager and Dependencies

First, install UV package manager and set up the Python environment:

```bash
# Install UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Reload your shell or source the profile
source ~/.bashrc

# Navigate to project directory
cd /path/to/visco-api

# Install dependencies using UV
uv sync

# Activate the virtual environment
source .venv/bin/activate

# Verify installation
uv pip list
```

Alternative installation methods for UV:

```bash
# Using pip
pip install uv

# Using homebrew (macOS)
brew install uv

# Using conda
conda install -c conda-forge uv
```

### Step 2: Generate WireGuard Key Pair

Generate WireGuard compatible private/public key pair using the provided script:

```bash
# Run the key generation script
python generate_wireguard_keys.py

# The script will create a keys/ directory with:
# - private_key.txt (keep this secure)
# - public_key.txt
# - keypair.txt (contains both keys)
```

**Important:** Store these keys in a secure location. The private key should never be shared or committed to version control.

### Step 3: Install and Configure WireGuard

Install WireGuard and create the server configuration:

```bash
# Install WireGuard
sudo apt update
sudo apt install wireguard

# Create WireGuard configuration directory
sudo mkdir -p /etc/wireguard

# Create the server configuration file
sudo nano /etc/wireguard/wg0.conf
```

Add the following content to `/etc/wireguard/wg0.conf`:

```ini
[Interface]
Address = 10.0.0.1/24
SaveConfig = false
ListenPort = 51820
PrivateKey = <YOUR GENERATED PRIVATE KEY>
```

Replace `<YOUR GENERATED PRIVATE KEY>` with the private key generated in Step 2.

Start the WireGuard systemd service:

```bash
# Enable and start WireGuard service
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0

# Verify service status
sudo systemctl status wg-quick@wg0

# Check WireGuard interface
sudo wg show
```

### Step 4: Configure Environment Variables

Update the `.env` file with your WireGuard public key and other configurations:

```bash
# Edit the .env file
nano .env
```

Add or update the following configuration in your `.env` file:

```properties
# Database Configuration
DB_NAME=visco
DB_USER=visco_cctv
DB_PASSWORD=Visco@0408
DB_HOST=127.0.0.1
DB_PORT=5432

# WireGuard Configuration
WG_SERVER_IP=YOUR_SERVER_PUBLIC_IP
WG_SERVER_PORT=51820
WG_SERVER_PUBLIC_KEY=YOUR_GENERATED_PUBLIC_KEY
WG_SERVER_PRIVATE_KEY=YOUR_GENERATED_PRIVATE_KEY

# JWT Configuration
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email Configuration (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
```

Replace the placeholder values with your actual configuration.

### Step 5: Deploy Database

Deploy PostgreSQL 17 database using the provided script:

```bash
# Make the database deployment script executable
chmod +x Deploy/deploy_database.sh

# Run the database deployment script with sudo privileges
sudo ./Deploy/deploy_database.sh
```

The script will:
- Install PostgreSQL 17
- Configure authentication
- Create the application user and database
- Verify the setup

### Step 6: Deploy Backend

Deploy the FastAPI backend with systemd services:

```bash
# Make the backend deployment script executable
chmod +x Deploy/deploy_backend.sh

# Run the backend deployment script with sudo privileges
sudo ./Deploy/deploy_backend.sh
```

The script will:
- Fetch server public IP
- Install systemd service files
- Configure WireGuard script with sudo privileges
- Start all required services (visco-api, wg-watch.path, wg-watch.service)

## Post-Deployment Verification

After completing all steps, verify your deployment:

### Check Service Status

```bash
# Check FastAPI backend service
sudo systemctl status visco-api

# Check WireGuard watcher services
sudo systemctl status wg-watch.path
sudo systemctl status wg-watch.service

# Check WireGuard interface
sudo systemctl status wg-quick@wg0
```

### View Service Logs

```bash
# View FastAPI backend logs
sudo journalctl -u visco-api -f

# View WireGuard watcher logs
sudo journalctl -u wg-watch -f

# View WireGuard service logs
sudo journalctl -u wg-quick@wg0 -f
```

### Test API Endpoints

```bash
# Test basic API endpoint (adjust IP and port as needed)
curl http://YOUR_SERVER_IP:8000/

# Test health check
curl http://YOUR_SERVER_IP:8000/health

# Test WireGuard-related endpoints
curl http://YOUR_SERVER_IP:8000/wireguard/status
```

## Troubleshooting

### Common Issues and Solutions

1. **Service fails to start:**
   - Check service logs: `sudo journalctl -u service-name -n 50`
   - Verify `.env` file configuration
   - Ensure all dependencies are installed

2. **Database connection issues:**
   - Verify PostgreSQL is running: `sudo systemctl status postgresql`
   - Test database connection: `psql -h localhost -U visco_cctv -d visco`
   - Check database configuration in `.env`

3. **WireGuard configuration issues:**
   - Verify WireGuard is installed: `wg version`
   - Check interface status: `sudo wg show`
   - Verify key pair generation and configuration

4. **Permission issues:**
   - Ensure scripts are executable: `chmod +x script_name.sh`
   - Run deployment scripts with sudo: `sudo ./script_name.sh`
   - Check file ownership and permissions

### Log Locations

- FastAPI application logs: `sudo journalctl -u visco-api`
- WireGuard service logs: `sudo journalctl -u wg-quick@wg0`
- PostgreSQL logs: `sudo journalctl -u postgresql`
- System logs: `/var/log/syslog`

## Security Considerations

1. **Keep private keys secure** - Never commit private keys to version control
2. **Use strong passwords** - Update default passwords in `.env` file
3. **Firewall configuration** - Configure UFW or iptables as needed
4. **Regular updates** - Keep system and dependencies updated
5. **Monitor logs** - Regularly check service logs for issues

## Support

For additional support or questions, contact:
- **Shiven Saini** - shiven.career@proton.me

Include the following information when reporting issues:
- Operating system and version
- Error messages and logs
- Steps to reproduce the issue
- Current configuration (without sensitive data)
