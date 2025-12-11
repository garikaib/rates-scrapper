"""
MongoDB client for RBZ rates - integrates with fx-rates collection.
"""

import os
from datetime import datetime, date, time
from typing import Optional, Dict
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure
from lib.db import RatesDatabase

# MongoDB settings
MONGO_DATABASE = "fx-rates"
MONGO_COLLECTION = "fx-rates"


def date_to_midnight_iso(d: date) -> datetime:
    """Convert date to midnight datetime for MongoDB Date field."""
    return datetime.combine(d, time.min)


class MongoStorage:
    """MongoDB storage for RBZ rates - integrates with existing fx-rates collection."""
    
    def __init__(self, db: RatesDatabase = None):
        self.sqlite_db = db or RatesDatabase()
        self._client = None
        self._db = None
    
    def _get_mongo_uri(self) -> Optional[str]:
        """Get MongoDB URI from environment or SQLite credentials."""
        # First check environment variable
        uri = os.environ.get("MONGO_URI")
        if uri:
            return uri
        
        # Get from SQLite credentials
        base_uri = self.sqlite_db.get_credential("mongo_uri")
        user = self.sqlite_db.get_credential("mongo_user")
        password = self.sqlite_db.get_credential("mongo_pass")
        
        if base_uri:
            # If we have user/pass, inject them into the URI
            if user and password and "@" in base_uri:
                if "user:pwd@" in base_uri:
                    uri = base_uri.replace("user:pwd", f"{user}:{password}")
                else:
                    parts = base_uri.split("://", 1)
                    if len(parts) == 2:
                        # Remove existing credentials if any
                        host_part = parts[1].split("@")[-1] if "@" in parts[1] else parts[1]
                        uri = f"{parts[0]}://{user}:{password}@{host_part}"
                    else:
                        uri = base_uri
                return uri
            return base_uri
        
        return None
    
    def connect(self) -> bool:
        """Connect to MongoDB fx-rates database."""
        uri = self._get_mongo_uri()
        if not uri:
            print("MongoDB URI not configured")
            return False
        
        try:
            # Append database name if not already present
            if not uri.rstrip('/').endswith(MONGO_DATABASE):
                uri = uri.rstrip('/') + '/' + MONGO_DATABASE
            
            self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # Test connection
            self._client.admin.command('ping')
            self._db = self._client[MONGO_DATABASE]
            print(f"Connected to MongoDB: {MONGO_DATABASE}")
            return True
        except ConnectionFailure as e:
            print(f"MongoDB connection failed: {e}")
            return False
        except Exception as e:
            print(f"MongoDB error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MongoDB."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
    
    def _get_latest_record(self) -> Optional[Dict]:
        """Get the latest fx-rates record by Date field."""
        try:
            collection = self._db[MONGO_COLLECTION]
            record = collection.find_one(sort=[("Date", DESCENDING)])
            return record
        except Exception as e:
            print(f"Error fetching latest record: {e}")
            return None
    
    def update_fx_rates(self, exchange_rates: Dict = None, gold_rates: Dict = None) -> bool:
        """
        Update fx-rates collection with new RBZ rates.
        
        Logic:
        1. Get latest record by Date
        2. If latest Date == exchange_rates.rate_date → already updated, skip
        3. If latest Date < exchange_rates.rate_date → create new record
           - Copy latest record (keep other fields)
           - Set Date = exchange_rates.rate_date (midnight ISO)
           - Update ZiG_Bid, ZiG_Ask, ZiG_Mid
           - If gold_rates.rate_date == new Date → calculate Gold = zwg/usd
        4. Insert new record
        
        Returns True if update was successful, False otherwise.
        """
        if not exchange_rates:
            print("No exchange rates to update")
            return False
        
        if not self._db:
            if not self.connect():
                return False
        
        try:
            collection = self._db[MONGO_COLLECTION]
            
            # Parse exchange rates date
            exchange_date_str = exchange_rates.get("rate_date")
            if not exchange_date_str:
                print("No rate_date in exchange_rates")
                return False
            
            exchange_date = date.fromisoformat(exchange_date_str)
            exchange_datetime = date_to_midnight_iso(exchange_date)
            
            # Get latest record
            latest = self._get_latest_record()
            
            if latest:
                latest_date = latest.get("Date")
                if isinstance(latest_date, datetime):
                    latest_date_only = latest_date.date()
                else:
                    latest_date_only = latest_date
                
                # Check if already updated
                if latest_date_only == exchange_date:
                    print(f"Already have rates for {exchange_date}, skipping")
                    return False
                
                print(f"Latest record date: {latest_date_only}, Exchange date: {exchange_date}")
            
            # Create new record
            new_record = {}
            
            # Copy fields from latest record if exists (to preserve other values)
            if latest:
                # Copy all fields except _id
                for key, value in latest.items():
                    if key != "_id":
                        new_record[key] = value
            
            # Update Date to exchange rates date (midnight)
            new_record["Date"] = exchange_datetime
            
            # Update ZiG fields from exchange rates
            new_record["ZiG_Bid"] = exchange_rates.get("bid")
            new_record["ZiG_Ask"] = exchange_rates.get("ask")
            new_record["ZiG_Mid"] = exchange_rates.get("avg")
            
            print(f"Updated ZiG: Bid={new_record['ZiG_Bid']}, Ask={new_record['ZiG_Ask']}, Mid={new_record['ZiG_Mid']}")
            
            # Check if gold rates date matches
            if gold_rates:
                gold_date_str = gold_rates.get("rate_date")
                if gold_date_str:
                    gold_date = date.fromisoformat(gold_date_str)
                    
                    if gold_date == exchange_date:
                        # Calculate Gold = zwg / usd, rounded to 4 decimals
                        zwg = gold_rates.get("zwg")
                        usd = gold_rates.get("usd")
                        
                    if gold_date == exchange_date:
                        # Calculate Gold = zwg / usd (Physical Gold)
                        zwg = gold_rates.get("zwg")
                        usd = gold_rates.get("usd")
                        
                        if zwg and usd and usd > 0:
                            gold_value = round(zwg / usd, 4)
                            new_record["Gold"] = gold_value
                            print(f"Updated Gold: {gold_value} (ZWG {zwg} / USD {usd})")
                        else:
                            print("Could not calculate Gold: missing zwg or usd")
                            
                        # Calculate eGold = digital_token_zwg / digital_token_usd (Digital Token)
                        dt_zwg = gold_rates.get("digital_token_zwg")
                        dt_usd = gold_rates.get("digital_token_usd")
                        
                        if dt_zwg and dt_usd and dt_usd > 0:
                            egold_value = round(dt_zwg / dt_usd, 4)
                            new_record["eGold"] = egold_value
                            print(f"Updated eGold: {egold_value} (Digital ZiG {dt_zwg} / USD {dt_usd})")
                        else:
                            print("Could not calculate eGold: missing digital token prices")
                    else:
                        print(f"Gold date ({gold_date}) != Exchange date ({exchange_date}), keeping existing Gold/eGold")
            
            # Insert new record
            result = collection.insert_one(new_record)
            
            if result.inserted_id:
                print(f"Inserted new fx-rates record for {exchange_date}")
                return True
            else:
                print("Failed to insert record")
                return False
            
        except OperationFailure as e:
            print(f"MongoDB operation failed: {e}")
            return False
        except Exception as e:
            print(f"MongoDB update error: {e}")
            return False


# Convenience functions for CLI
def set_mongo_credential(key: str, value: str):
    """Set a MongoDB credential in SQLite."""
    db = RatesDatabase()
    db.set_credential(f"mongo_{key}", value)
    print(f"MongoDB {key} updated successfully")


def test_mongo_connection() -> bool:
    """Test MongoDB connection."""
    storage = MongoStorage()
    result = storage.connect()
    if result:
        # Also test fetching latest record
        latest = storage._get_latest_record()
        if latest:
            print(f"Latest record date: {latest.get('Date')}")
    storage.disconnect()
    return result
