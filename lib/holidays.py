"""
Zimbabwe Public Holidays checker using Nager.Date API.
"""

import requests
from datetime import date
from typing import List
from lib.db import RatesDatabase

NAGER_API_URL = "https://date.nager.at/api/v3/publicholidays/{year}/ZW"


class ZimbabweHolidays:
    """Zimbabwe public holidays with caching."""
    
    def __init__(self, db: RatesDatabase = None):
        self.db = db or RatesDatabase()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "RBZ-Rates-Scraper/1.0"})
    
    def _fetch_holidays_from_api(self, year: int) -> List[dict]:
        try:
            url = NAGER_API_URL.format(year=year)
            print(f"Fetching holidays from: {url}")
            response = self._session.get(url, timeout=10)
            if response.status_code == 200:
                holidays = response.json()
                print(f"Fetched {len(holidays)} holidays for {year}")
                return holidays
            return []
        except Exception as e:
            print(f"Error fetching holidays: {e}")
            return []
    
    def _ensure_holidays_cached(self, year: int):
        if not self.db.has_holidays_for_year(year):
            holidays = self._fetch_holidays_from_api(year)
            if holidays:
                self.db.cache_holidays(year, holidays)
    
    def is_public_holiday(self, check_date: date) -> bool:
        self._ensure_holidays_cached(check_date.year)
        holiday_dates = self.db.get_cached_holidays(check_date.year)
        is_holiday = check_date.isoformat() in holiday_dates
        if is_holiday:
            print(f"{check_date.strftime('%d %B %Y')} is a public holiday")
        return is_holiday
    
    def is_business_day(self, check_date: date) -> bool:
        if check_date.weekday() >= 5:
            print(f"{check_date.strftime('%d %B %Y')} is a weekend")
            return False
        return not self.is_public_holiday(check_date)
