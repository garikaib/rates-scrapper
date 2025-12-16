#!/bin/bash
# Script to sync local credentials to remote server
# Usage: ./configure_remote.sh [SERVER_ADDRESS]

SERVER="${1:-ubuntu@51.195.252.90}"

# Run the python sync script
python3 sync_remote.py "$SERVER"
