#!/usr/bin/env python3
"""
Sync local credentials to remote server.
"""

import sys
import sqlite3
import subprocess
import shlex
from pathlib import Path

# Configuration
LOCAL_DB_PATH = Path(__file__).parent / "rates.db"
REMOTE_DIR = "/home/ubuntu/html/official-rates"
DEFAULT_SERVER = "ubuntu@51.195.252.90"

def get_local_credentials():
    """Read all credentials from local SQLite DB."""
    if not LOCAL_DB_PATH.exists():
        print(f"Error: Local database not found at {LOCAL_DB_PATH}")
        sys.exit(1)
        
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM credentials")
        rows = cursor.fetchall()
        conn.close()
        return {row["key"]: row["value"] for row in rows}
    except Exception as e:
        print(f"Error reading local database: {e}")
        sys.exit(1)

def chunk_string(string, length):
    return (string[0+i:length+i] for i in range(0, len(string), length))

def set_remote_credential(server, key, value):
    """Set a single credential on the remote server via SSH."""
    print(f"Syncing {key}...")
    
    # Escape value for safe transport
    # We use triple quotes in the python command to handle most content
    # But we also need to be careful about the shell command itself.
    
    # The command we want to run on remote is:
    # ./venv/bin/python -c "from lib.db import RatesDatabase; RatesDatabase().set_credential('key', '''value''')"
    
    # We need to escape ' in key (unlikely) and ''' in value
    safe_value = value.replace("'''", "\\'\\'\\'")
    
    python_code = f"from lib.db import RatesDatabase; RatesDatabase().set_credential('{key}', '''{safe_value}''')"
    
    # Construct SSH command
    # We use ssh server "command"
    remote_cmd = f"cd {REMOTE_DIR} && ./venv/bin/python -c \"{python_code}\""
    
    try:
        cmd = ["ssh", server, remote_cmd]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"  ❌ Failed: {result.stderr.strip()}")
            return False
        else:
            print(f"  ✓ Synced")
            return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    server = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER
    
    print("=" * 60)
    print(f"Syncing credentials to {server}")
    print("=" * 60)
    
    creds = get_local_credentials()
    
    if not creds:
        print("No credentials found in local database.")
        sys.exit(0)
        
    print(f"Found {len(creds)} credentials locally.")
    
    success_count = 0
    for key, value in creds.items():
        if set_remote_credential(server, key, value):
            success_count += 1
            
    print("-" * 60)
    print(f"Sync complete: {success_count}/{len(creds)} credentials synced.")
    print("=" * 60)

    # Trigger a test
    print("\nTesting remote MongoDB connection...")
    subprocess.run(["ssh", server, f"cd {REMOTE_DIR} && ./venv/bin/python main.py test-mongo"])

if __name__ == "__main__":
    main()
