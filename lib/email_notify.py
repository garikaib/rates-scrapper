"""
Email notifications for RBZ Rates Scraper.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, Dict
from lib.db import RatesDatabase


class EmailNotifier:
    """SMTP email notifier."""
    
    def __init__(self, db: RatesDatabase = None):
        self.db = db or RatesDatabase()
    
    def _get_config(self) -> Dict:
        """Get SMTP configuration from database."""
        return {
            "host": self.db.get_credential("smtp_host"),
            "port": int(self.db.get_credential("smtp_port") or "587"),
            "user": self.db.get_credential("smtp_user"),
            "pass": self.db.get_credential("smtp_pass"),
            "from": self.db.get_credential("smtp_from"),
            "to": self.db.get_credential("smtp_to"),
            "enabled": self.db.get_credential("smtp_enabled") == "true",
        }
    
    def is_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        config = self._get_config()
        return config["enabled"] and config["host"] and config["user"]
    
    def send_success_notification(self, exchange_rates: Dict = None, gold_rates: Dict = None) -> bool:
        """Send success notification email."""
        if not self.is_enabled():
            return False
        
        config = self._get_config()
        
        try:
            # Build email content
            subject = f"RBZ Rates Updated - {datetime.now().strftime('%Y-%m-%d')}"
            
            body_parts = ["RBZ Rates have been successfully scraped and stored.\n"]
            
            if exchange_rates:
                body_parts.append("Exchange Rates:")
                body_parts.append(f"  Date: {exchange_rates.get('rate_date', 'N/A')}")
                body_parts.append(f"  USD/ZWG Bid: {exchange_rates.get('bid', 'N/A')}")
                body_parts.append(f"  USD/ZWG Ask: {exchange_rates.get('ask', 'N/A')}")
                body_parts.append(f"  USD/ZWG Avg: {exchange_rates.get('avg', 'N/A')}")
                body_parts.append("")
            
            if gold_rates:
                body_parts.append("Gold Coin Prices (1oz):")
                body_parts.append(f"  Date: {gold_rates.get('rate_date', 'N/A')}")
                if gold_rates.get('usd'):
                    body_parts.append(f"  USD: ${gold_rates['usd']:,.2f}")
                if gold_rates.get('zwg'):
                    body_parts.append(f"  ZWG: {gold_rates['zwg']:,.2f}")
                if gold_rates.get('zar'):
                    body_parts.append(f"  ZAR: R{gold_rates['zar']:,.2f}")
                body_parts.append("")
            
            body_parts.append(f"\nScraped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            body = "\n".join(body_parts)
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = config['from'] or config['user']
            msg['To'] = config['to'] or config['user']
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            # Send via SMTP with TLS
            with smtplib.SMTP(config['host'], config['port']) as server:
                server.starttls()
                server.login(config['user'], config['pass'])
                server.send_message(msg)
            
            print(f"Email notification sent to {msg['To']}")
            return True
            
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False


def set_smtp_credential(key: str, value: str):
    """Set an SMTP credential."""
    db = RatesDatabase()
    db.set_credential(f"smtp_{key}", value)
    print(f"SMTP {key} updated")
