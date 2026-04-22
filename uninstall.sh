#!/bin/bash

# WebFace - Uninstall Script
# This script removes the application installation

set -e

echo "========================================"
echo "   WebFace Uninstall Script"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Safety check
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found. Are you in the WebFace directory?${NC}"
    exit 1
fi

echo -e "${YELLOW}WARNING: This will delete:${NC}"
echo "  - Virtual environment (venv/)"
echo "  - Database files (webface.db, *.db)"
echo "  - Uploads and results folders"
echo "  - Installed Python packages"
echo ""
echo -n "Are you sure you want to continue? (yes/no): "
read -r confirm

if [ "$confirm" != "yes" ]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}Stopping any running processes...${NC}"
pkill -f "python.*app.py" 2>/dev/null || true

echo -e "${GREEN}Removing virtual environment...${NC}"
rm -rf venv/

echo -e "${GREEN}Removing database files...${NC}"
rm -f webface.db *.db 2>/dev/null || true

echo -e "${GREEN}Removing uploads and results...${NC}"
rm -rf uploads/ results/ 2>/dev/null || true

echo -e "${GREEN}Removing compiled Python files...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

echo -e "${GREEN}Removing .env file...${NC}"
rm -f .env

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Uninstall Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "All WebFace files have been removed."
echo "You can now delete the project directory."
echo ""
