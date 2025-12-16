#!/bin/bash
# RBZ Rates Scraper - Cron-friendly run script
# 
# Usage:
#   ./run.sh           # Normal run
#   ./run.sh --force   # Force scraping even if already done today
#
# Cron example:
#   0 10 * * 1-5 /path/to/rates-scrapper/run.sh >> /var/log/rbz-scraper.log 2>&1

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Logging helper
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting RBZ Rates Scraper..."

# Check for virtual environment
if [ ! -d "venv" ]; then
    log "ERROR: Virtual environment not found."
    log "Please run: ./install.sh"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if requirements are installed
log "Checking dependencies..."
if ! python -c "import playwright; import pymongo; import pymupdf" 2>/dev/null; then
    log "Some dependencies are missing. Running install..."
    ./install.sh
fi

# Run the scraper
log "Running..."
python main.py "$@"

log "Scraper finished."
