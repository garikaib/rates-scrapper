"""
Database manager for RBZ Rates Scraper.

SQLite for:
- Scrape run history
- Gold and exchange rates
- Public holidays cache
- MongoDB credentials (secure storage)
"""

import sqlite3
from datetime import datetime, date
from typing import Optional, List, Dict
from pathlib import Path

# Database file location
DB_PATH = Path(__file__).parent.parent / "rates.db"


class RatesDatabase:
    """SQLite database manager."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Scrape runs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrape_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date DATE NOT NULL,
                run_time TIMESTAMP NOT NULL,
                gold_success BOOLEAN DEFAULT 0,
                exchange_success BOOLEAN DEFAULT 0,
                gold_source TEXT,
                exchange_source TEXT,
                notes TEXT
            )
        """)
        
        # Gold rates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gold_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rate_date DATE UNIQUE NOT NULL,
                usd REAL, zwg REAL, zar REAL, gbp REAL, eur REAL, bwp REAL, aud REAL,
                pm_fix REAL,
                source TEXT,
                source_url TEXT,
                scraped_at TIMESTAMP NOT NULL
            )
        """)
        
        # Exchange rates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rate_date DATE UNIQUE NOT NULL,
                currency_pair TEXT DEFAULT 'USD/ZWG',
                bid REAL, ask REAL, avg REAL,
                source TEXT,
                scraped_at TIMESTAMP NOT NULL
            )
        """)
        
        # Public holidays cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public_holidays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                holiday_date DATE NOT NULL,
                year INTEGER NOT NULL,
                name TEXT,
                local_name TEXT,
                fetched_at TIMESTAMP NOT NULL,
                UNIQUE(holiday_date, year)
            )
        """)
        
        # Credentials (for MongoDB etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
    
    # --- Credentials ---
    
    def set_credential(self, key: str, value: str):
        """Store a credential."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO credentials (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
        """, (key, value, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_credential(self, key: str) -> Optional[str]:
        """Get a credential."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM credentials WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row["value"] if row else None
    
    def delete_credential(self, key: str):
        """Delete a credential."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM credentials WHERE key = ?", (key,))
        conn.commit()
        conn.close()
    
    # --- Scrape Runs ---
    
    def log_scrape_run(self, run_date: date, gold_success: bool = False,
                       exchange_success: bool = False, gold_source: str = None,
                       exchange_source: str = None, notes: str = None) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scrape_runs 
            (run_date, run_time, gold_success, exchange_success, gold_source, exchange_source, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (run_date.isoformat(), datetime.now().isoformat(),
              gold_success, exchange_success, gold_source, exchange_source, notes))
        run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return run_id
    
    def has_successful_gold_scrape(self, target_date: date) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM gold_rates WHERE rate_date = ?", (target_date.isoformat(),))
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    def has_successful_exchange_scrape(self, target_date: date) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM exchange_rates WHERE rate_date = ?", (target_date.isoformat(),))
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    # --- Gold Rates ---
    
    def save_gold_rates(self, rate_date: date, usd: float = None, zwg: float = None,
                        zar: float = None, gbp: float = None, eur: float = None,
                        bwp: float = None, aud: float = None, pm_fix: float = None,
                        digital_token_usd: float = None, digital_token_zwg: float = None,
                        source: str = None, source_url: str = None):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if new columns exist, if not add them (migration)
        try:
            cursor.execute("SELECT digital_token_usd FROM gold_rates LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE gold_rates ADD COLUMN digital_token_usd REAL")
            cursor.execute("ALTER TABLE gold_rates ADD COLUMN digital_token_zwg REAL")
            conn.commit()
            
        cursor.execute("""
            INSERT INTO gold_rates 
            (rate_date, usd, zwg, zar, gbp, eur, bwp, aud, pm_fix, digital_token_usd, digital_token_zwg, source, source_url, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rate_date) DO UPDATE SET
                usd=excluded.usd, zwg=excluded.zwg, zar=excluded.zar,
                gbp=excluded.gbp, eur=excluded.eur, bwp=excluded.bwp,
                aud=excluded.aud, pm_fix=excluded.pm_fix,
                digital_token_usd=excluded.digital_token_usd,
                digital_token_zwg=excluded.digital_token_zwg,
                source=excluded.source, source_url=excluded.source_url,
                scraped_at=excluded.scraped_at
        """, (rate_date.isoformat(), usd, zwg, zar, gbp, eur, bwp, aud, pm_fix,
              digital_token_usd, digital_token_zwg,
              source, source_url, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_gold_rates(self, rate_date: date) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gold_rates WHERE rate_date = ?", (rate_date.isoformat(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    # --- Exchange Rates ---
    
    def save_exchange_rates(self, rate_date: date, bid: float, ask: float, avg: float, source: str = None):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exchange_rates 
            (rate_date, currency_pair, bid, ask, avg, source, scraped_at)
            VALUES (?, 'USD/ZWG', ?, ?, ?, ?, ?)
            ON CONFLICT(rate_date) DO UPDATE SET
                bid=excluded.bid, ask=excluded.ask, avg=excluded.avg,
                source=excluded.source, scraped_at=excluded.scraped_at
        """, (rate_date.isoformat(), bid, ask, avg, source, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_exchange_rates(self, rate_date: date) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exchange_rates WHERE rate_date = ?", (rate_date.isoformat(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    # --- Holidays ---
    
    def cache_holidays(self, year: int, holidays: List[Dict]):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Clear existing holidays for this year to avoid duplicates if re-fetching
        cursor.execute("DELETE FROM public_holidays WHERE year = ?", (year,))
        
        for h in holidays:
            cursor.execute("""
                INSERT INTO public_holidays 
                (holiday_date, year, name, local_name, fetched_at)
                VALUES (?, ?, ?, ?, ?)
            """, (h['date'], year, h.get('name'), h.get('localName'), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_cached_holidays(self, year: int) -> List[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT holiday_date FROM public_holidays WHERE year = ?", (year,))
        rows = cursor.fetchall()
        conn.close()
        return [row['holiday_date'] for row in rows]
    
    def has_valid_holidays_cache(self, year: int) -> bool:
        """Check if we have holidays cached for this year and they are less than 7 days old."""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Check if we have any holidays for this year
        cursor.execute("SELECT fetched_at FROM public_holidays WHERE year = ? LIMIT 1", (year,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False
            
        # Check freshness
        fetched_at_str = row['fetched_at']
        try:
            fetched_at = datetime.fromisoformat(fetched_at_str)
            age = datetime.now() - fetched_at
            return age.days < 7
        except ValueError:
            return False
