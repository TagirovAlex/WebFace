#!/bin/bash

# WebFace - Production Setup Script
# This script configures the application for production deployment

set -e

echo "========================================"
echo "   WebFace Production Setup"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PYTHON_CMD="python3"
if ! $PYTHON_CMD --version &> /dev/null; then
   PYTHON_CMD="python"
fi

# Check if running as root
if [ "$EUID" -ne 0 ] && [ "$(whoami)" != "root" ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

# Check if application is installed
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: Application not installed. Run install.sh first.${NC}"
    exit 1
fi

echo -e "${GREEN}Python version:$($PYTHON_CMD --version)${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Error: Virtual environment not found. Run install.sh first.${NC}"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Create systemd service file
echo -e "${GREEN}Creating systemd service...${NC}"
cat > /etc/systemd/system/webface.service << EOF
[Unit]
Description=WebFace - ComfyUI Web Interface
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/webface
Environment="PATH=/opt/webface/venv/bin"
EnvironmentFile=/opt/webface/.env
ExecStart=/opt/webface/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}Created systemd service${NC}"
echo ""

# Create production-ready .env
echo -e "${GREEN}Updating .env for production...${NC}"

# Check if FLASK_ENV is already set to production
if ! grep -q "^FLASK_ENV=production" .env; then
    sed -i "s/^FLASK_ENV=.*/FLASK_ENV=production/" .env
    echo "  - Set FLASK_ENV=production"
fi

# Enable secure session cookies
if ! grep -q "^SESSION_COOKIE_SECURE=True" .env; then
    sed -i "s/^SESSION_COOKIE_SECURE=.*/SESSION_COOKIE_SECURE=True/" .env
    echo "  - Set SESSION_COOKIE_SECURE=True"
fi

# Enable CSRF SSL strict
if ! grep -q "^WTF_CSRF_SSL_STRICT=True" .env; then
    sed -i "s/^WTF_CSRF_SSL_STRICT=.*/WTF_CSRF_SSL_STRICT=True/" .env
    echo "  - Set WTF_CSRF_SSL_STRICT=True"
fi

echo ""
echo -e "${YELLOW}Next, configure Nginx:${NC}"
echo ""
echo "Create /etc/nginx/sites-available/webface:"
echo ""
echo "server {"
echo "    listen 80;"
echo "    server_name your-domain.com;"
echo ""
echo "    location / {"
echo "        proxy_pass http://127.0.0.1:5000;"
echo "        proxy_set_header Host \$host;"
echo "        proxy_set_header X-Real-IP \$remote_addr;"
echo "        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;"
echo "        proxy_set_header X-Scheme \$scheme;"
echo "        proxy_set_header X-Forwarded-Proto \$scheme;"
echo "    }"
echo ""
echo "    # Rate limiting"
echo "    limit_req zone=one burst=20 nodelay;"
echo "}"
echo ""

echo -e "${YELLOW}Recommended Nginx configuration (save as /etc/nginx/sites-available/webface):${NC}"
echo ""
cat << 'NGINX'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 16M;
    }

    # Rate limiting
    limit_req zone=one burst=20 nodelay;
}

# Optional: Rate limiting zone
limit_req_zone $binary_remote_addr zone=one:10m rate=10r/s;
NGINX

echo ""
echo -e "${GREEN}To complete setup:${NC}"
echo "1. Edit Nginx config: sudo nano /etc/nginx/sites-available/webface"
echo "2. Enable site: sudo ln -s /etc/nginx/sites-available/webface /etc/nginx/sites-enabled/"
echo "3. Test config: sudo nginx -t"
echo "4. Restart Nginx: sudo systemctl restart nginx"
echo ""
echo -e "${GREEN}To enable WebFace service:${NC}"
echo "1. Move project to /opt/webface: sudo cp -r . /opt/webface/"
echo "2. Change ownership: sudo chown -R www-data:www-data /opt/webface"
echo "3. Reload systemd: sudo systemctl daemon-reload"
echo "4. Start service: sudo systemctl start webface"
echo "5. Enable auto-start: sudo systemctl enable webface"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Production Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""