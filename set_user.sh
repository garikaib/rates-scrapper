#!/bin/bash
# Script to configure MongoDB and SMTP credentials
# Press Enter to keep existing values unchanged

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate

# Helper function to get current value
get_current() {
    python -c "from lib.db import RatesDatabase; db=RatesDatabase(); v=db.get_credential('$1'); print(v if v else '')" 2>/dev/null
}

# Helper function to prompt with current value
prompt_with_default() {
    local prompt_text="$1"
    local key="$2"
    local current=$(get_current "$key")
    
    if [ -n "$current" ]; then
        # Mask password-like fields
        if [[ "$key" == *"pass"* ]]; then
            current_display="****"
        else
            current_display="$current"
        fi
        read -p "$prompt_text [$current_display]: " value
    else
        read -p "$prompt_text: " value
    fi
    
    # Return the value (or empty to keep current)
    echo "$value"
}

# Set credential only if not empty
set_if_not_empty() {
    local key="$1"
    local value="$2"
    if [ -n "$value" ]; then
        python -c "from lib.db import RatesDatabase; RatesDatabase().set_credential('$key', '''$value''')"
        echo "  ✓ Updated $key"
    fi
}

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║       RBZ Rates Scraper - Configuration                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Press Enter to keep existing values unchanged."
echo ""

# Profile Name
echo "─── Profile ───────────────────────────────────────────────"
profile=$(prompt_with_default "Profile name (for your reference)" "profile_name")
set_if_not_empty "profile_name" "$profile"

# MongoDB Section
echo ""
echo "─── MongoDB ───────────────────────────────────────────────"
mongo_uri=$(prompt_with_default "MongoDB URI" "mongo_uri")
set_if_not_empty "mongo_uri" "$mongo_uri"

mongo_user=$(prompt_with_default "MongoDB username" "mongo_user")
set_if_not_empty "mongo_user" "$mongo_user"

mongo_pass=$(prompt_with_default "MongoDB password" "mongo_pass")
set_if_not_empty "mongo_pass" "$mongo_pass"

# SMTP Section (Optional)
echo ""
echo "─── Email Notifications (Optional) ────────────────────────"
current_smtp_enabled=$(get_current "smtp_enabled")

read -p "Enable email notifications? (y/n) [$current_smtp_enabled]: " smtp_enabled_input
if [ -n "$smtp_enabled_input" ]; then
    if [[ "$smtp_enabled_input" == "y" || "$smtp_enabled_input" == "Y" ]]; then
        set_if_not_empty "smtp_enabled" "true"
    else
        set_if_not_empty "smtp_enabled" "false"
    fi
fi

# Only prompt for SMTP details if enabled
current_enabled=$(get_current "smtp_enabled")
if [[ "$current_enabled" == "true" ]]; then
    echo ""
    smtp_host=$(prompt_with_default "SMTP host" "smtp_host")
    set_if_not_empty "smtp_host" "$smtp_host"
    
    smtp_port=$(prompt_with_default "SMTP port (default: 587)" "smtp_port")
    if [ -n "$smtp_port" ]; then
        set_if_not_empty "smtp_port" "$smtp_port"
    fi
    
    smtp_user=$(prompt_with_default "SMTP username" "smtp_user")
    set_if_not_empty "smtp_user" "$smtp_user"
    
    smtp_pass=$(prompt_with_default "SMTP password" "smtp_pass")
    set_if_not_empty "smtp_pass" "$smtp_pass"
    
    smtp_from=$(prompt_with_default "From email address" "smtp_from")
    set_if_not_empty "smtp_from" "$smtp_from"
    
    smtp_to=$(prompt_with_default "To email address" "smtp_to")
    set_if_not_empty "smtp_to" "$smtp_to"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  ✓ Configuration saved!                                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"

# Show current profile
current_profile=$(get_current "profile_name")
if [ -n "$current_profile" ]; then
    echo ""
    echo "Current profile: $current_profile"
fi

echo ""
