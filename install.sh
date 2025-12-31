#!/bin/bash
# RBZ Rates Scraper - Install/Setup Script
#
# Robust installation handling environments where some packages might be missing.
# Handles running as sudo vs normal user.
# Ubuntu 24.04 compatible.

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Config
SERVICE_NAME="rbz-scraper"
USER_NAME=${SUDO_USER:-$USER}
# Fallback if SUDO_USER is not set (e.g. running as direct root login?)
if [ -z "$USER_NAME" ]; then
    USER_NAME=$(whoami)
fi

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║       RBZ Rates Scraper - Installation                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Running as: $USER (Target user: $USER_NAME)"
echo "Directory:  $SCRIPT_DIR"
echo ""

# Ensure we have sudo rights if not root
if [ "$EUID" -ne 0 ]; then
    if ! command -v sudo >/dev/null; then
        echo "Error: sudo is required to install system dependencies."
        exit 1
    fi
    SUDO="sudo"
else
    SUDO=""
    echo "⚠ Running with root privileges."
fi

# Detect Server Environment
if [[ "$SCRIPT_DIR" == *"/html/official-rates"* ]]; then
    IS_SERVER=true
    echo "Environment: Server Detected"
else
    IS_SERVER=false
    echo "Environment: Local/Dev"
fi

# 1. System Tools (requires root/sudo)
echo ""
echo "─── System Tools ───────────────────────────────────────────"

# Helper to check if a package is installed
is_installed() {
    dpkg -l "$1" &> /dev/null
}

PACKAGES_NEEDED=("python3" "python3-venv" "python3-pip" "python3-full" "tesseract-ocr")
MISSING_PACKAGES=()

for pkg in "${PACKAGES_NEEDED[@]}"; do
    if ! is_installed "$pkg"; then
        MISSING_PACKAGES+=("$pkg")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "Updating apt (missing: ${MISSING_PACKAGES[*]} )..."
    $SUDO apt-get update -qq
    
    echo "Installing missing system packages..."
    $SUDO apt-get install -y "${MISSING_PACKAGES[@]}"
else
    echo "System packages already installed (Skipping apt update/install)."
fi

# 2. Python Virtual Environment
echo ""
echo "─── Virtual Environment ────────────────────────────────────"

# If venv is broken or partial, remove it
if [ -d "venv" ]; then
    if [ ! -f "venv/bin/activate" ]; then
        echo "Found broken venv. Recreating..."
        rm -rf venv
    elif [ ! -x "venv/bin/python" ]; then
        echo "Found broken venv (no python binary). Recreating..."
        rm -rf venv
    fi
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    
    # Check if we can run as the target user to create venv
    if [ "$EUID" -eq 0 ] && [ "$USER_NAME" != "root" ]; then
        echo "Creating venv as user $USER_NAME..."
        su - "$USER_NAME" -c "cd $SCRIPT_DIR && python3 -m venv venv"
    else
        python3 -m venv venv
    fi
    
    if [ ! -f "venv/bin/activate" ]; then
        echo "ERROR: Failed to create virtual environment."
        exit 1
    fi
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment exists"
fi

# Ensure permissions if run as root
if [ "$EUID" -eq 0 ] && [ "$USER_NAME" != "root" ]; then
    echo "Fixing permissions for $USER_NAME..."
    chown -R "$USER_NAME:$USER_NAME" "$SCRIPT_DIR"
fi

# 3. Python Packages
echo ""
echo "─── Python Packages ────────────────────────────────────────"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "ERROR: venv/bin/activate not found!"
    exit 1
fi

echo "Upgrading pip..."
pip install --upgrade pip --quiet

echo "Installing requirements..."
pip install -r requirements.txt --quiet
echo "  ✓ Dependencies installed"

echo ""
echo "─── Playwright Dependencies ────────────────────────────────"
echo "Installing Playwright browsers..."
playwright install chromium

echo "Installing Playwright system dependencies (using sudo)..."
# Smart check: only try installing deps if we are not in 'quick' mode or if we suspect they are missing.
# Since checking for every lib is hard, we will rely on a SKIP_DEPS flag or argument.

if [[ "$1" == "--quick" ]]; then
    echo "Skipping Playwright system deps (Quick mode enabled)"
else
    # Use playwright install-deps which handles OS-specific packages
    if [ -n "$SUDO" ]; then
        $SUDO venv/bin/playwright install-deps chromium
    else
        venv/bin/playwright install-deps chromium
    fi
fi
echo "  ✓ Playwright dependencies checked"


# 4. Systemd Service (Server Only)
if [ "$IS_SERVER" = true ]; then
    echo ""
    echo "─── Systemd Service ────────────────────────────────────────"
    
    SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
    TIMER_FILE="/etc/systemd/system/$SERVICE_NAME.timer"
    
    # Configure service to run as USER_NAME
    echo "Configuring service to run as user: $USER_NAME"
    
    $SUDO tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=RBZ Rates Scraper
After=network.target

[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python main.py run
StandardOutput=append:/var/log/rbz-scraper.log
StandardError=append:/var/log/rbz-scraper.log

[Install]
WantedBy=multi-user.target
EOF

    # Timer: 10 minutes, Mon-Fri 08:00-17:00
    $SUDO tee "$TIMER_FILE" > /dev/null << EOF
[Unit]
Description=Run RBZ Rates Scraper every 10 minutes during business hours

[Timer]
OnCalendar=Mon-Fri 06:00..19:00/10
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Logs setup
    $SUDO touch /var/log/rbz-scraper.log
    if [ "$USER_NAME" != "root" ]; then
        $SUDO chown "$USER_NAME:$USER_NAME" /var/log/rbz-scraper.log
    fi

    # Reload
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable "$SERVICE_NAME.timer"
    
    # Restart timer to apply changes
    $SUDO systemctl restart "$SERVICE_NAME.timer"
    
    # Verify
    echo "  ✓ Systemd service installed & timer running"
    # Show status but don't fail script if systemctl returns non-zero (e.g. if inactive)
    systemctl status "$SERVICE_NAME.timer" --no-pager || true
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  ✓ Installation complete!                                 ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
