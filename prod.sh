#!/bin/bash

# WebFace - Nginx & Systemd Setup Script (Production)
# This script automatically configures Nginx and Systemd for production deployment

set -e

echo "========================================"
echo "   WebFace Production Configuration"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -ne 0 ] && [ "$(whoami)" != "root" ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

# Get project path
PROJECT_PATH="${1:-$(pwd)}"
DOMAIN="${2:-localhost}"

echo -e "${GREEN}Project path: $PROJECT_PATH${NC}"
echo -e "${GREEN}Domain: $DOMAIN${NC}"
echo ""

# Check if application exists
if [ ! -f "$PROJECT_PATH/.env" ] || [ ! -d "$PROJECT_PATH/venv" ]; then
    echo -e "${RED}Error: Application not properly installed at $PROJECT_PATH${NC}"
    exit 1
fi

# Create systemd service
echo -e "${GREEN}Creating systemd service...${NC}"

cat > /etc/systemd/system/webface.service << EOF
[Unit]
Description=WebFace - ComfyUI Web Interface
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$PROJECT_PATH
Environment="PATH=$PROJECT_PATH/venv/bin"
EnvironmentFile=$PROJECT_PATH/.env
ExecStart=$PROJECT_PATH/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ Systemd service created${NC}"

# Create Nginx configuration
echo -e "${GREEN}Creating Nginx configuration...${NC}"

cat > /etc/nginx/sites-available/webface << EOF
server {
    listen 80;
    server_name $DOMAIN;

    # Max upload size
    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme \$scheme;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme \$scheme;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 16M;
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
    }
}
EOF

echo -e "${GREEN}✓ Nginx configuration created${NC}"

# Enable Nginx site
echo -e "${GREEN}Enabling Nginx site...${NC}"

if [ -f /etc/nginx/sites-enabled/default ]; then
    rm -f /etc/nginx/sites-enabled/default
    echo -e "${GREEN}✓ Removed default site${NC}"
fi

ln -sf /etc/nginx/sites-available/webface /etc/nginx/sites-enabled/webface
echo -e "${GREEN}✓ Nginx site enabled${NC}"

# Test Nginx configuration
echo -e "${GREEN}Testing Nginx configuration...${NC}"
if nginx -t 2>&1; then
    echo -e "${GREEN}✓ Nginx configuration valid${NC}"
else
    echo -e "${YELLOW}⚠ Nginx test failed. Please check configuration manually.${NC}"
fi

# Reload systemd and start services
echo -e "${GREEN}Reloading systemd...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"

echo -e "${GREEN}Enabling and starting WebFace service...${NC}"
systemctl enable webface
systemctl restart webface

if systemctl is-active --quiet webface; then
    echo -e "${GREEN}✓ WebFace service started${NC}"
else
    echo -e "${YELLOW}⚠ WebFace service failed to start. Check: sudo journalctl -u webface -n 50${NC}"
fi

echo -e "${GREEN}Enabling and starting Nginx...${NC}"
systemctl enable nginx
systemctl restart nginx

if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx service started${NC}"
else
    echo -e "${YELLOW}⚠ Nginx service failed to start. Check: sudo journalctl -u nginx -n 50${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Production Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Access your application at:${NC} http://$DOMAIN"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  Status:  sudo systemctl status webface"
echo "  Logs:    sudo journalctl -u webface -f"
echo "  Stop:    sudo systemctl stop webface"
echo "  Restart: sudo systemctl restart webface"
echo ""
