#!/bin/bash
# RBZ Rates Scraper - Deploy to Server
#
# Usage: ./deploy.sh

set -e

# Configuration
SERVER="ubuntu@51.195.252.90"
REMOTE_BASE="/home/ubuntu/html"
REMOTE_DIR="official-rates"
REMOTE_PATH="$REMOTE_BASE/$REMOTE_DIR"
PACKAGE_NAME="rbz-scraper.tar.gz"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║       RBZ Rates Scraper - Deploy to Server                ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Files to include in package
FILES=(
    "main.py"
    "requirements.txt"
    "README.md"
    "install.sh"
    "run.sh"
    "set_user.sh"
    "lib/"
)

# Create package
echo "Creating package..."
# Remove old package if exists locally
rm -f "$PACKAGE_NAME"

tar --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='venv' \
    --exclude='rates.db' \
    --exclude='rates.json' \
    --exclude='.git' \
    -czvf "$PACKAGE_NAME" "${FILES[@]}"

echo ""
echo "Package created: $PACKAGE_NAME"

# Clean remote directory and Upload
echo ""
echo "Preparing remote server ($SERVER)..."
ssh "$SERVER" << EOF
    # Create directory if it doesn't exist
    mkdir -p $REMOTE_PATH
    
    # Backup existing config/db if needed, or just clean everything except data
    # For now, per instructions: "empty it and replace"
    # We'll preserve .db and .json files if they exist to keep state/history
    
    cd $REMOTE_PATH
    
    # Move sensitive/state files to /tmp/rbz_backup if they exist
    mkdir -p /tmp/rbz_backup
    [ -f rates.db ] && cp rates.db /tmp/rbz_backup/
    [ -f rates.json ] && cp rates.json /tmp/rbz_backup/
    
    # Wipe directory contents
    echo "Cleaning $REMOTE_PATH..."
    rm -rf *
    
    # Restore state files
    [ -f /tmp/rbz_backup/rates.db ] && mv /tmp/rbz_backup/rates.db .
    [ -f /tmp/rbz_backup/rates.json ] && mv /tmp/rbz_backup/rates.json .
    rm -rf /tmp/rbz_backup
EOF

echo "Uploading package..."
scp "$PACKAGE_NAME" "$SERVER:$REMOTE_PATH/"

# Extract and install on server
echo ""
echo "Installing on server..."
ssh "$SERVER" -t << EOF
    cd $REMOTE_PATH
    tar -xzvf $PACKAGE_NAME
    rm $PACKAGE_NAME
    chmod +x install.sh run.sh set_user.sh
    
    # Run install script (it handles sudo internally or can be run with sudo)
    # We run it as the current user (ubuntu). It will prompt for sudo where needed.
    # Run install script with --quick to skip heavy dependency checks if they are already there
    # The install script now does smart checking, but --quick explicitly skips Playwright deps
    ./install.sh --quick
EOF

# Cleanup local package
rm "$PACKAGE_NAME"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  ✓ Deployment complete!                                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
