"""
Redis Cache Manager for RBZ Rates Scraper.
Handles smart invalidation of cache keys based on date logic.
"""

import os
import re
try:
    import redis
except ImportError:
    redis = None

from urllib.parse import urlparse, parse_qs
from datetime import date, datetime
from typing import Optional, List
from lib.db import RatesDatabase

# Redis settings
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

class RedisCache:
    """Redis cache manager with smart invalidation."""
    
    def __init__(self, db: RatesDatabase = None):
        self.sqlite_db = db or RatesDatabase()
        self._client = None
    
    def _get_cache_pattern(self) -> Optional[str]:
        """Get cache pattern for keys to invalidate."""
        # Check env first
        pattern = os.environ.get("CACHE_PATTERN")
        if pattern:
            return pattern
            
        # Check SQLite
        pattern = self.sqlite_db.get_credential("cache_pattern")
        
        # Default pattern if not set
        if not pattern:
            return "*/api/rates/fx-rates"
            
        return pattern
    
    def connect(self) -> bool:
        """Connect to Redis."""
        if redis is None:
            # print("Redis module not installed. Cache disabled.") # Optional: suppress noise
            return False

        try:
            # Allow env overrides
            host = os.environ.get("REDIS_HOST", REDIS_HOST)
            port = int(os.environ.get("REDIS_PORT", REDIS_PORT))
            
            self._client = redis.Redis(
                host=host,
                port=port,
                db=REDIS_DB,
                decode_responses=True # Get strings back
            )
            self._client.ping()
            return True
        except Exception as e:
            # print(f"Redis connection failed: {e}") # Safe to ignore if optional
            return False
            
    def _is_date_relevant(self, url: str, target_date: date) -> bool:
        """
        Check if the cached URL is relevant to the target date.
        
        Logic:
        1. No query params -> RELEVANT (assumes default is 'today')
        2. 'day' param -> RELEVANT if matches target_date
        3. 'from'/'to' params -> RELEVANT if target_date in range [from, to]
        """
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            # Case 1: No relevant date params
            if not any(k in params for k in ['day', 'from', 'to']):
                return True
                
            # Case 2: Specific day
            if 'day' in params:
                day_str = params['day'][0]
                try:
                    cached_date = date.fromisoformat(day_str)
                    if cached_date == target_date:
                        return True
                except ValueError:
                    pass # Invalid date format, ignore or treat as not match
            
            # Case 3: Date range
            if 'from' in params and 'to' in params:
                try:
                    from_date = date.fromisoformat(params['from'][0])
                    to_date = date.fromisoformat(params['to'][0])
                    if from_date <= target_date <= to_date:
                        return True
                except ValueError:
                    pass

            return False
            
        except Exception:
            return False

    def invalidate_for_date(self, target_date: date) -> int:
        """
        Invalidate cache keys relevant to the target date.
        Returns number of keys cleared.
        """
        pattern = self._get_cache_pattern()
        if not pattern:
            print("No cache pattern configured. Skipping cache invalidation.")
            return 0
            
        if not self._client:
            if not self.connect():
                return 0
        
        print(f"Scanning Redis for pattern: {pattern}")
        
        # We need to scan for the pattern + wildcard to find actual keys
        # The user provides e.g. "*/api/rates/fx-rates"
        # We search for "*/api/rates/fx-rates*" to catch query params
        search_pattern = pattern if pattern.endswith('*') else f"{pattern}*"
        
        keys_to_delete = []
        count = 0
        
        try:
            # Use scan_iter for efficiency
            for key in self._client.scan_iter(match=search_pattern):
                if self._is_date_relevant(key, target_date):
                    keys_to_delete.append(key)
                    count += 1
            
            if keys_to_delete:
                # Delete in batches if necessary, but UNLINK handles multiple
                self._client.unlink(*keys_to_delete)
                print(f"Invalidated {count} Redis keys for {target_date}")
            else:
                print(f"No relevant cache keys found for {target_date}")
                
            return count
            
        except Exception as e:
            print(f"Error during cache invalidation: {e}")
            return 0

    def clear_all_matching(self) -> int:
        """Manual clear of all keys matching pattern (CLI usage)."""
        pattern = self._get_cache_pattern()
        if not pattern:
            print("No cache pattern configured.")
            return 0
            
        if not self._client:
            if not self.connect():
                return 0
                
        search_pattern = pattern if pattern.endswith('*') else f"{pattern}*"
        
        try:
            keys = list(self._client.scan_iter(match=search_pattern))
            if keys:
                self._client.unlink(*keys)
                print(f"Cleared all {len(keys)} keys matching {search_pattern}")
                return len(keys)
            else:
                print("No keys found.")
                return 0
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return 0
