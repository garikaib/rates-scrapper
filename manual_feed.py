#!/usr/bin/env python3
"""
Manual feed script to update database from screenshots.
Target Dates: 29 Dec 2025, 30 Dec 2025
"""

import sys
from datetime import date
from lib.db import RatesDatabase
from lib.cache import RedisCache

from lib.mongo import MongoStorage

def update_data():
    db = RatesDatabase()
    mongo = MongoStorage(db)
    
    # --- 29 December 2025 ---
    date_29 = date(2025, 12, 29)
    print(f"Updating {date_29}...")
    
    # Exchange Rates
    # USD: Bid 25.3605, Ask 26.6611, Avg 26.0108
    er_29 = {
        "rate_date": date_29.isoformat(),
        "bid": 25.3605,
        "ask": 26.6611,
        "avg": 26.0108,
        "source": "Manual/RBZ Image"
    }
    db.save_exchange_rates(date_29, er_29["bid"], er_29["ask"], er_29["avg"], er_29["source"])
    
    # Gold Rates
    # 1oz USD: 4,671.87
    # 1oz ZWG: 121,519.17
    # eGold (0.01oz) approximated
    # 0.10oz USD = 467.19 -> 0.01oz = 46.72
    # 0.10oz ZWG = 12,151.92 -> 0.01oz = 1215.19
    gr_29 = {
        "rate_date": date_29.isoformat(),
        "usd": 4671.87,
        "zwg": 121519.17,
        "digital_token_usd": 46.72,
        "digital_token_zwg": 1215.19,
        "source": "Manual/RBZ Image",
        "source_url": "https://www.rbz.co.zw" 
    }
    # Create a copy for unpacking that doesn't have rate_date (since we pass it positionally)
    gr_29_args = gr_29.copy()
    gr_29_args.pop("rate_date")
    db.save_gold_rates(date_29, **gr_29_args)

    # Sync to Mongo
    print("Syncing 29 Dec into MongoDB...")
    mongo.update_fx_rates(exchange_rates=er_29, gold_rates=gr_29)
    
    # --- 30 December 2025 ---
    date_30 = date(2025, 12, 30)
    print(f"Updating {date_30}...")
    
    # Exchange Rates
    er_30 = {
        "rate_date": date_30.isoformat(),
        "bid": 25.3378,
        "ask": 26.6372,
        "avg": 25.9875,
        "source": "Manual/RBZ Image"
    }
    db.save_exchange_rates(date_30, er_30["bid"], er_30["ask"], er_30["avg"], er_30["source"])
    
    # Gold Rates
    # 1oz USD: 4,553.90
    # 1oz ZWG: 118,344.54
    # eGold (0.01oz)
    # 0.10oz USD = 455.39 -> 0.01oz = 45.54
    # 0.10oz ZWG = 11,834.45 -> 0.01oz = 1183.45
    gr_30 = {
        "rate_date": date_30.isoformat(),
        "usd": 4553.90,
        "zwg": 118344.54,
        "digital_token_usd": 45.54,
        "digital_token_zwg": 1183.45,
        "source": "Manual/RBZ Image",
        "source_url": "https://www.rbz.co.zw"
    }
    gr_30_args = gr_30.copy()
    gr_30_args.pop("rate_date")
    db.save_gold_rates(date_30, **gr_30_args)

    # Sync to Mongo
    print("Syncing 30 Dec into MongoDB...")
    mongo.update_fx_rates(exchange_rates=er_30, gold_rates=gr_30)
    
    print("Database updated.")

def clear_cache():
    print("Clearing Redis cache...")
    try:
        cache = RedisCache()
        cache.clear_all_matching()
        print("Cache cleared.")
    except Exception as e:
        print(f"Failed to clear cache: {e}")

if __name__ == "__main__":
    update_data()
    clear_cache()
