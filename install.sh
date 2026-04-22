#!/bin/bash

# WebFace - Installation Script
# This script sets up the application environment

set -e

echo "========================================"
echo "   WebFace Installation Script"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_CMD="python3"
if ! $PYTHON_CMD --version &> /dev/null; then
   PYTHON_CMD="python"
fi

echo -e "${GREEN}Python version:$($PYTHON_CMD --version)${NC}"
echo ""

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment 'venv' already exists${NC}"
    echo -n "Use existing venv? (y/n): "
    read -r use_existing
    if [ "$use_existing" != "y" ]; then
        echo "Aborted."
        exit 1
    fi
else
    echo -e "${GREEN}Creating virtual environment...${NC}"
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${GREEN}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${GREEN}Installing dependencies...${NC}"
pip install -r requirements.txt

# Copy .env.example if .env doesn't exist
if [ ! -f ".env" ]; then
    echo ""
    echo -e "${YELLOW}Creating .env file from .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}Created .env file${NC}"
    echo ""
    echo -e "${YELLOW}Please edit .env file with your configuration:${NC}"
    echo "  - SECRET_KEY (generate with: python -c \"import secrets; print(secrets.token_hex(32))\")"
    echo "  - COMFY_URL (ComfyUI API endpoint)"
    echo "  - DATABASE_URL (PostgreSQL for production)"
    echo ""
    echo -n "Do you want to configure these now? (y/n): "
    read -r configure_env
    if [ "$configure_env" = "y" ]; then
        echo ""
        
        # Generate SECRET_KEY
        SECRET_KEY=$($PYTHON_CMD -c "import secrets; print(secrets.token_hex(32))")
        echo -e "${GREEN}Generated SECRET_KEY${NC}"
        
        # Update .env
        sed -i "s/SECRET_KEY=your-secret-key-here-minimum-32-characters/SECRET_KEY=$SECRET_KEY/" .env
        
        echo ""
        echo -n "Enter COMFY_URL (default: http://127.0.0.1:8188): "
        read -r comfy_url
        if [ -z "$comfy_url" ]; then
            comfy_url="http://127.0.0.1:8188"
        fi
        sed -i "s|COMFY_URL=http://127.0.0.1:8188|COMFY_URL=$comfy_url|" .env
        
        echo ""
        echo -e "${GREEN}Updated .env file${NC}"
    fi
fi

# Initialize database
echo ""
echo -e "${GREEN}Initializing database...${NC}"
$PYTHON_CMD -c "from app import app, db; from models import *; app.app_context().push(); db.create_all(); print('Database initialized successfully')"

# Run migration if database exists
if [ -f "webface.db" ]; then
    echo -e "${YELLOW}Database file found. Running migration...${NC}"
    $PYTHON_CMD migrate_db.py --backup
fi

# Create admin user
echo ""
echo -e "${GREEN}Creating administrator account...${NC}"
$PYTHON_CMD create_admin.py

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Start the application: $PYTHON_CMD app.py"
echo "2. Access the web interface at http://localhost:5000"
echo "3. Log in with your admin credentials"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- Edit .env file to configure Telegram bot (BOT_TOKEN, TELEGRAM_CHAT_ID)"
echo "- For production, set FLASK_ENV=production and use HTTPS"
echo ""
