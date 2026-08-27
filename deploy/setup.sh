#!/bin/bash
# ============================================
# AWS Health Check Tool - EC2 Deployment Script
# Instance: AWS_Audit_Manager (t3.micro)
# IP: 65.1.253.48
# ============================================

set -e

echo "========================================="
echo "  AWS Health Check - Deployment Setup"
echo "========================================="

# Update system
echo "[1/7] Updating system packages..."
sudo yum update -y

# Install Python 3.9+ and pip
echo "[2/7] Installing Python and dependencies..."
sudo yum install -y python3 python3-pip git nginx

# Create app directory
echo "[3/7] Setting up application directory..."
sudo mkdir -p /opt/aws-health-check
sudo chown ec2-user:ec2-user /opt/aws-health-check

# Copy app files (run this after SCP/git clone)
echo "[4/7] Installing Python dependencies..."
cd /opt/aws-health-check
pip3 install --user -r requirements.txt

# Create output directory
mkdir -p /opt/aws-health-check/output

# Setup systemd service
echo "[5/7] Creating systemd service..."
sudo tee /etc/systemd/system/aws-health-check.service > /dev/null << 'EOF'
[Unit]
Description=AWS Health Check Dashboard
After=network.target

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/aws-health-check
ExecStart=/usr/local/bin/uvicorn dashboard.app:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=HOME=/home/ec2-user

[Install]
WantedBy=multi-user.target
EOF

# Setup Nginx reverse proxy
echo "[6/7] Configuring Nginx..."
sudo tee /etc/nginx/conf.d/aws-health-check.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name 65.1.253.48;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
EOF

# Remove default nginx config if exists
sudo rm -f /etc/nginx/conf.d/default.conf

# Enable and start services
echo "[7/7] Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable aws-health-check
sudo systemctl start aws-health-check
sudo systemctl enable nginx
sudo systemctl restart nginx

echo ""
echo "========================================="
echo "  Deployment Complete!"
echo "========================================="
echo ""
echo "  Dashboard: http://65.1.253.48"
echo ""
echo "  Service commands:"
echo "    sudo systemctl status aws-health-check"
echo "    sudo systemctl restart aws-health-check"
echo "    sudo journalctl -u aws-health-check -f"
echo ""
echo "========================================="
