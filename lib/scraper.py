"""
RBZ Rates Scraper - Main scraper class.
"""

import os
import re
import json
import time
import random
import requests
import pymupdf
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Tuple
import pytz

from lib.db import RatesDatabase
from lib.holidays import ZimbabweHolidays
from lib.mongo import MongoStorage
from lib.email_notify import EmailNotifier
from lib.cache import RedisCache

RBZ_HOMEPAGE_URL = "https://www.rbz.co.zw/"
RBZ_PDF_BASE_URL = "https://www.rbz.co.zw/documents"
HARARE_TZ = pytz.timezone("Africa/Harare")


class RBZRateScraper:
    """Scraper for RBZ exchange rates and gold prices."""
    
    def __init__(self):
        self.db = RatesDatabase()
        self.holidays = ZimbabweHolidays(self.db)
        self.mongo = MongoStorage(self.db)
        self.email = EmailNotifier(self.db)
        self.cache = RedisCache(self.db)
        self.session = requests.Session()
        self._playwright = None
        self._browser = None
    
    def _get_current_time(self) -> datetime:
        return datetime.now(HARARE_TZ)
    
    def _get_today(self) -> date:
        return self._get_current_time().date()
    
    def _is_business_day(self, check_date: date = None) -> bool:
        return self.holidays.is_business_day(check_date or self._get_today())
    
    def _already_have_gold_rates(self, target_date: date) -> bool:
        return self.db.has_successful_gold_scrape(target_date)
    
    def _already_have_exchange_rates(self, target_date: date) -> bool:
        return self.db.has_successful_exchange_scrape(target_date)
    
    # === Browser Utilities ===
    
    def _start_browser(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
    
    def _stop_browser(self):
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
    
    def _random_delay(self, min_s=0.5, max_s=2.0):
        time.sleep(random.uniform(min_s, max_s))
    
    def _human_like_click(self, page, element):
        box = element.bounding_box()
        if box:
            try:
                page.mouse.move(int(box["x"] + box["width"]/2), int(box["y"] + box["height"]/2))
                self._random_delay(0.2, 0.5)
            except Exception:
                pass
        element.click()
        self._random_delay(1.5, 3.0)
    
    def _create_context(self):
        return self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-ZW", timezone_id="Africa/Harare"
        )
    
    # === Date Extraction ===
    
    def _parse_dd_mm_yyyy(self, text: str) -> Optional[date]:
        match = re.search(r'(\d{2})[-/](\d{2})[-/](\d{4})', text)
        if match:
            try:
                return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
            except ValueError:
                pass
        return None
    
    # === Webpage Scraping ===
    
    def _extract_exchange_rates_dom(self, page) -> Optional[Dict]:
        print("Extracting exchange rates...")
        data = {}
        
        # Try to get date from header
        try:
            content = page.content()
            date_match = re.search(r'EXCHANGE\s+RATES?\s*(\d{2}[-/]\d{2}[-/]\d{4})', content, re.I)
            if date_match:
                data["rate_date"] = self._parse_dd_mm_yyyy(date_match.group(1)).isoformat()
                print(f"  Date found in header: {data['rate_date']}")
        except:
            pass
        
        for row in page.locator("tr").all():
            try:
                cells = row.locator("td").all_inner_texts()
                if len(cells) >= 4 and "USD" in cells[0] and "ZWG" in cells[0]:
                    data["currency_pair"] = "USD/ZWG"
                    data["bid"] = float(cells[1].replace(',', ''))
                    data["ask"] = float(cells[2].replace(',', ''))
                    data["avg"] = float(cells[3].replace(',', ''))
                    print(f"  USD/ZWG: Bid={data['bid']}, Ask={data['ask']}, Avg={data['avg']}")
                    break
            except (ValueError, Exception):
                continue
        
        return data if "bid" in data else None
    
    def _extract_gold_rates_dom(self, page) -> Optional[Dict]:
        print("Extracting gold rates...")
        data = {}
        currencies = {"USD": "usd", "ZAR": "zar", "ZWG": "zwg", "GBP": "gbp", "EUR": "eur"}
        
        # Try to get date from header
        try:
            content = page.content()
            date_match = re.search(r'GOLD\s+COIN\s+PRICE.*?(\d{2}[-/]\d{2}[-/]\d{4})', content, re.I)
            if date_match:
                data["rate_date"] = self._parse_dd_mm_yyyy(date_match.group(1)).isoformat()
                print(f"  Date found in header: {data['rate_date']}")
        except:
            pass
        
        # Locate rows
        rows = page.locator("tr").all()
        for row in rows:
            try:
                cells = row.locator("td").all_inner_texts()
                if not cells:
                    continue
                    
                # Standard currencies
                if len(cells) >= 2:
                    label = cells[0].strip()
                    
                    # Check for Digital Token
                    if "DIGITAL TOKEN PRICE" in label.upper():
                        # Expecting format like "USD0.1279" "ZiG3.34" in subsequent cells
                        # Cells could be [Label, Val1, Val2] or [Label, Val1, empty, Val2] etc.
                        # We'll search through all remaining cells for USD and ZiG/ZWG values
                        print("  Found Digital Token row")
                        for cell in cells[1:]:
                            cell_clean = cell.strip().upper()
                            if "USD" in cell_clean:
                                val_str = re.sub(r'[^\d.]', '', cell_clean)
                                if val_str:
                                    data["digital_token_usd"] = float(val_str)
                                    print(f"    Digital Token USD: {data['digital_token_usd']}")
                            elif "ZIG" in cell_clean or "ZWG" in cell_clean:
                                val_str = re.sub(r'[^\d.]', '', cell_clean)
                                if val_str:
                                    data["digital_token_zwg"] = float(val_str)
                                    print(f"    Digital Token ZiG: {data['digital_token_zwg']}")
                        continue

                    currency = label
                    # Check if price is in 2nd or 3rd column depending on table structure
                    price_text = cells[2].strip() if len(cells) >= 3 else cells[1].strip()
                    
                    if currency in currencies and currencies[currency] not in data:
                        # Clean price text
                        price_text = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
                        if price_text:
                            data[currencies[currency]] = float(price_text)
                            print(f"  {currency}: {data[currencies[currency]]:,.2f}")
            except (ValueError, Exception):
                pass
        
        return data if data else None
    
    def _scrape_from_webpage(self) -> Tuple[Optional[Dict], Optional[Dict]]:
        print("\n[Webpage] Scraping...")
        try:
            self._start_browser()
            context = self._create_context()
            page = context.new_page()
            
            try:
                from playwright_stealth import Stealth
                Stealth().apply_stealth_sync(page)
            except ImportError:
                pass
            
            self._random_delay(1.0, 2.0)
            print(f"Navigating to {RBZ_HOMEPAGE_URL}")
            page.goto(RBZ_HOMEPAGE_URL, timeout=60000, wait_until="domcontentloaded")
            self._random_delay(3.0, 5.0)
            
            # Exchange rates (default tab)
            exchange = self._extract_exchange_rates_dom(page)
            
            # Click gold tab
            self._random_delay(1.0, 2.0)
            tab = page.get_by_text("Mosi Oa Tunya Gold Coin Price", exact=False)
            if tab.count() > 0:
                self._human_like_click(page, tab.first)
                print("Clicked Gold tab")
                self._random_delay(2.0, 3.0) # Wait for tab switch
            else:
                print("Gold tab not found")
                context.close()
                return exchange, None
            
            # Gold rates
            gold = self._extract_gold_rates_dom(page)
            
            context.close()
            
            if exchange: exchange["source"] = "webpage"
            if gold: gold["source"] = "webpage"
            
            return exchange, gold
        except Exception as e:
            print(f"Webpage error: {e}")
            return None, None
        finally:
            self._stop_browser()
    
    # === PDF Fallback ===
    
    def _build_gold_pdf_url(self, d: date) -> str:
        # Url format: .../2025/December/MOSI_OA_TUNYA_PRICES_9_DECEMBER_2025.pdf
        return f"{RBZ_PDF_BASE_URL}/Mosi-Rates/{d.year}/{d.strftime('%B')}/MOSI_OA_TUNYA_PRICES_{d.day}_{d.strftime('%B').upper()}_{d.year}.pdf"
    
    def _scrape_gold_from_pdf(self, target_date: date) -> Optional[Dict]:
        print(f"\n[PDF Fallback] {target_date}...")
        url = self._build_gold_pdf_url(target_date)
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200 or resp.content[:4] != b"%PDF":
                return None
            
            doc = pymupdf.open(stream=resp.content, filetype="pdf")
            text = doc[0].get_text()
            doc.close()
            
            data = {"source": "pdf", "source_url": url}
            currencies = {"USD": "usd", "ZAR": "zar", "ZWG": "zwg"}
            
            # Extract date from PDF content
            date_match = re.search(r'(\d{1,2})\s+(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})', text, re.I)
            if date_match:
                 try:
                    month_map = {"JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6, 
                                 "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12}
                    extracted_date = date(int(date_match.group(3)), month_map[date_match.group(2).upper()], int(date_match.group(1)))
                    data["rate_date"] = extracted_date.isoformat()
                 except: pass

            lines = text.split("\n")
            # PDF fallback does not support digital tokens for now as per instructions
            for i, line in enumerate(lines):
                if line.strip() in currencies:
                    for j in range(1, 5):
                        if i + j < len(lines):
                            try:
                                val = float(lines[i+j].replace(',', ''))
                                data[currencies[line.strip()]] = val
                                break
                            except ValueError:
                                continue
            
            return data if len(data) > 2 else None
        except Exception as e:
            print(f"PDF error: {e}")
            return None
    
    # === Main Logic ===
    
    def scrape_rates(self) -> Dict:
        today = self._get_today()
        scraped_at = self._get_current_time().isoformat()
        result = {"scrape_date": today.isoformat(), "scraped_at": scraped_at}
        
        exchange, gold = self._scrape_from_webpage()
        
        if exchange:
            result["exchange_rates"] = exchange
            rate_date_str = exchange.get("rate_date", today.isoformat())
            self.db.save_exchange_rates(date.fromisoformat(rate_date_str), exchange["bid"], exchange["ask"], exchange["avg"], "webpage")
        
        if gold:
            result["gold_rates"] = gold
            rate_date_str = gold.get("rate_date", today.isoformat())
            self.db.save_gold_rates(date.fromisoformat(rate_date_str), 
                                    usd=gold.get("usd"), zwg=gold.get("zwg"), zar=gold.get("zar"),
                                    gbp=gold.get("gbp"), eur=gold.get("eur"), source="webpage",
                                    digital_token_usd=gold.get("digital_token_usd"),
                                    digital_token_zwg=gold.get("digital_token_zwg"))
        
        if not gold:
            gold = self._scrape_gold_from_pdf(today)
            if gold:
                result["gold_rates"] = gold
                rate_date_str = gold.get("rate_date", today.isoformat())
                self.db.save_gold_rates(date.fromisoformat(rate_date_str), usd=gold.get("usd"), zwg=gold.get("zwg"), zar=gold.get("zar"), source="pdf")
        
        # MongoDB - update fx-rates collection
        if "exchange_rates" in result:
            mongo_success = self.mongo.update_fx_rates(
                exchange_rates=result.get("exchange_rates"),
                gold_rates=result.get("gold_rates")
            )
            
            # Only send email notification if MongoDB update was successful
            if mongo_success:
                self.email.send_success_notification(
                    exchange_rates=result.get("exchange_rates"),
                    gold_rates=result.get("gold_rates")
                )
                
                # Invalidate cache
                print("Invalidating relevant Redis cache keys...")
                self.cache.invalidate_for_date(today)
        
        self.db.log_scrape_run(today, "gold_rates" in result, "exchange_rates" in result)
        result["status"] = "completed"
        return result
    
    def run(self, force: bool = False) -> Dict:
        print("=" * 60)
        print(f"RBZ Rates Scraper - {self._get_current_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print("=" * 60)
        
        if force:
            print("⚠ Force mode enabled - will scrape regardless of existing data")
        
        today = self._get_today()
        
        if not self._is_business_day(today):
            print("\n⏸ Not a business day.")
            return {"status": "skipped"}
        
        if not force and self._already_have_gold_rates(today) and self._already_have_exchange_rates(today):
            print("\n✓ Already have today's rates.")
            return {"status": "already_scraped"}
        
        result = self.scrape_rates()
        
        print("\n" + "=" * 60)
        if "exchange_rates" in result:
            er = result["exchange_rates"]
            print(f"Exchange ({er.get('rate_date', 'N/A')}): Bid={er.get('bid')}, Ask={er.get('ask')}, Avg={er.get('avg')}")
        if "gold_rates" in result:
            gr = result["gold_rates"]
            print(f"Gold ({gr.get('rate_date', 'N/A')}): USD=${gr.get('usd',0):,.2f}, ZWG={gr.get('zwg',0):,.2f}")
        
        return result
