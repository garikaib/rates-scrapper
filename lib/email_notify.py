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
        
    def _generate_html_body(self, exchange_rates: Dict = None, gold_rates: Dict = None) -> str:
        """Generate HTML email body."""
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
                h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
                .section { margin-bottom: 30px; }
                .rate-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
                .rate-table th, .rate-table td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
                .rate-table th { background-color: #f8f9fa; color: #2c3e50; }
                .highlight { font-weight: bold; color: #27ae60; }
                .footer { margin-top: 30px; font-size: 12px; color: #7f8c8d; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>RBZ Rates Update</h2>
        """
        
        if exchange_rates:
            html += f"""
                <div class="section">
                    <h3>💱 Exchange Rates ({exchange_rates.get('rate_date', 'N/A')})</h3>
                    <table class="rate-table">
                        <tr>
                            <th>Pair</th>
                            <th>Bid</th>
                            <th>Ask</th>
                            <th>Mid-Rate</th>
                        </tr>
                        <tr>
                            <td>USD/ZWG</td>
                            <td class="highlight">{exchange_rates.get('bid', 'N/A'):,.4f}</td>
                            <td class="highlight">{exchange_rates.get('ask', 'N/A'):,.4f}</td>
                            <td class="highlight">{exchange_rates.get('avg', 'N/A'):,.4f}</td>
                        </tr>
                    </table>
                </div>
            """
            
        if gold_rates:
            html += f"""
                <div class="section">
                    <h3>🏆 Gold Coin Prices ({gold_rates.get('rate_date', 'N/A')})</h3>
                    <p><em>Price per 1oz</em></p>
                    <table class="rate-table">
                        <tr>
                            <th>Currency</th>
                            <th>Price</th>
                        </tr>
            """
            if gold_rates.get('usd'):
                html += f"<tr><td>USD</td><td class='highlight'>${gold_rates['usd']:,.2f}</td></tr>"
            if gold_rates.get('zwg'):
                html += f"<tr><td>ZWG</td><td class='highlight'>{gold_rates['zwg']:,.2f}</td></tr>"
            if gold_rates.get('zar'):
                html += f"<tr><td>ZAR</td><td>R{gold_rates['zar']:,.2f}</td></tr>"
                
            html += """
                    </table>
                </div>
            """
            
        html += f"""
                <div class="footer">
                    <p>Scraped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>RBZ Scraper Bot</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def send_success_notification(self, exchange_rates: Dict = None, gold_rates: Dict = None) -> bool:
        """Send success notification email."""
        if not self.is_enabled():
            return False
        
        config = self._get_config()
        
        try:
            subject = f"RBZ Rates Update - {datetime.now().strftime('%d %b %Y')}"
            html_body = self._generate_html_body(exchange_rates, gold_rates)
            
            # Create message
            msg = MIMEMultipart('alternative')
            sender_email = config['from'] or config['user']
            msg['From'] = f"Rates Updater <{sender_email}>"
            msg['To'] = config['to'] or config['user']
            msg['Subject'] = subject
            
            # Attach HTML version
            msg.attach(MIMEText(html_body, 'html'))
            
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

    def send_test_email(self) -> bool:
        """Send a test email with the latest available data."""
        if not self.is_enabled():
            print("Email notifications are not enabled. Check configuration.")
            return False
            
        print("Fetching latest rates for test email...")
        exchange = self.db.get_latest_exchange_rates()
        gold = self.db.get_latest_gold_rates()
        
        if not exchange and not gold:
            print("No data found in database to send test email.")
            return False
            
        print(f"Found data: Exchange={bool(exchange)}, Gold={bool(gold)}")
        print("Sending test email...")
        return self.send_success_notification(exchange, gold)


def set_smtp_credential(key: str, value: str):
    """Set an SMTP credential."""
    db = RatesDatabase()
    db.set_credential(f"smtp_{key}", value)
    print(f"SMTP {key} updated")
