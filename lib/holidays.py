"""
Zimbabwe Public Holidays checker using Nager.Date API.
"""

import requests
from datetime import date, datetime
from typing import List
from lib.db import RatesDatabase

NAGER_API_URL = "https://date.nager.at/api/v3/publicholidays/{year}/ZW"
# Free API key limited to 1 request per second
ABSTRACT_API_KEY = "44489895a21648109915d73e9d4ff0e0"
ABSTRACT_API_URL = "https://holidays.abstractapi.com/v1/"


class ZimbabweHolidays:
    """Zimbabwe public holidays with caching."""
    
    def __init__(self, db: RatesDatabase = None):
        self.db = db or RatesDatabase()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "RBZ-Rates-Scraper/1.0"})
    
    def _fetch_holiday_for_date(self, target_date: date) -> List[dict]:
        """Fetch holidays for a specific date using AbstractAPI."""
        try:
            params = {
                "api_key": ABSTRACT_API_KEY,
                "country": "ZW",
                "year": target_date.year,
                "month": target_date.month,
                "day": target_date.day
            }
            print(f"Fetching holidays for {target_date} from AbstractAPI...")
            response = self._session.get(ABSTRACT_API_URL, params=params, timeout=10)
            
            if response.status_code == 200:
                holidays = response.json()
                # Empty list means no holiday. Non-empty means holiday(s).
                if holidays:
                    print(f"Found holiday: {holidays[0].get('name')}")
                else:
                    print("No holiday found for this date.")
                return holidays
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"Error fetching holidays: {e}")
            return []
    
    def is_public_holiday(self, check_date: date) -> bool:
        # 1. Check if we have already queried API for this date
        if self.db.was_holiday_checked(check_date):
            # We already checked this date. If it was a holiday, it would be in public_holidays table.
            # If it's not in public_holidays, then it's not a holiday.
            holiday_dates = self.db.get_cached_holidays(check_date.year)
            is_holiday = check_date.isoformat() in holiday_dates
            if is_holiday:
                print(f"{check_date.strftime('%d %B %Y')} is a registered public holiday")
            return is_holiday
            
        # 2. If not checked, query the API
        holidays = self._fetch_holiday_for_date(check_date)
        
        # 3. Mark as checked regardless of result
        self.db.mark_holiday_checked(check_date)
        
        # 4. If it is a holiday, store it
        if holidays:
             # Adapt AbstractAPI response format to our DB schema if needed
             # AbstractAPI: {"name", "name_local", "date": "MM/DD/YYYY", ...}
             # Our DB expects: {"date": "YYYY-MM-DD", "name", "localName"}
             formatted_holidays = []
             for h in holidays:
                 # Ensure date format is YYYY-MM-DD
                 # The API returns "date": "12/25/2025" or similar?
                 # Example response says "date": "12/22/2025"
                 try:
                     raw_date = h.get("date")
                     # Parse MM/DD/YYYY
                     d_obj = datetime.strptime(raw_date, "%m/%d/%Y").date()
                     formatted_date = d_obj.isoformat()
                 except:
                     formatted_date = check_date.isoformat() # Fallback
                     
                 formatted_holidays.append({
                     "date": formatted_date,
                     "name": h.get("name"),
                     "localName": h.get("name_local")
                 })
             
             self.db.cache_holidays(check_date.year, formatted_holidays)
             return True
             
        return False
    
    def is_business_day(self, check_date: date) -> bool:
        if check_date.weekday() >= 5:
            print(f"{check_date.strftime('%d %B %Y')} is a weekend")
            return False
        return not self.is_public_holiday(check_date)
