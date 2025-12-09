#!/usr/bin/env python3
"""
RBZ Rates Scraper CLI
"""

import sys
import argparse
import getpass
from lib.scraper import RBZRateScraper
from lib.mongo import set_mongo_credential, test_mongo_connection
from lib.db import RatesDatabase


def verify_setup():
    """Verify essential setup."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception as e:
        print(f"Playwright check failed: {e}")
        print("Please run: playwright install chromium")
        sys.exit(1)


def run_scraper(force: bool = False):
    """Run the scraper."""
    verify_setup()
    scraper = RBZRateScraper()
    scraper.run(force=force)


def main():
    parser = argparse.ArgumentParser(description="RBZ Rates Scraper CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Run command with --force flag
    run_parser = subparsers.add_parser("run", help="Run the scraper")
    run_parser.add_argument("--force", "-f", action="store_true", 
                            help="Force scraping even if already scraped today")
    
    # Mongo commands
    subparsers.add_parser("test-mongo", help="Test MongoDB connection")
    
    mongo_uri_parser = subparsers.add_parser("set-mongo-uri", help="Set MongoDB URI")
    mongo_uri_parser.add_argument("uri", help="MongoDB URI connection string")
    
    mongo_user_parser = subparsers.add_parser("set-mongo-user", help="Set MongoDB username")
    mongo_user_parser.add_argument("username", help="MongoDB username")
    
    subparsers.add_parser("set-mongo-pass", help="Set MongoDB password (interactive)")
    
    args = parser.parse_args()
    
    if args.command == "run":
        run_scraper(force=args.force)
    
    elif args.command == "test-mongo":
        if test_mongo_connection():
            print("Connection successful!")
        else:
            print("Connection failed.")
            sys.exit(1)
            
    elif args.command == "set-mongo-uri":
        set_mongo_credential("uri", args.uri)
        
    elif args.command == "set-mongo-user":
        set_mongo_credential("user", args.username)
        
    elif args.command == "set-mongo-pass":
        try:
            if not sys.stdin.isatty():
                password = sys.stdin.read().strip()
            else:
                password = getpass.getpass("Enter MongoDB password: ")
            
            if password:
                set_mongo_credential("pass", password)
            else:
                print("Aborted.")
        except KeyboardInterrupt:
            print("\nAborted.")
            
    else:
        run_scraper()  # Default behavior


if __name__ == "__main__":
    main()
