# RBZ Rates Scraper

An advanced, stealthy web scraper for the **Reserve Bank of Zimbabwe (RBZ)**. It extracts daily **Exchange Rates** and **Gold Coin Prices**, utilizing a webpage-first strategy with a robust PDF fallback.

## 🚀 Features

- **Webpage-First Strategy**: Scrapes rates directly from the RBZ homepage (fastest method).
- **PDF Fallback**: Automatically downloads and parses the daily PDF if webpage scraping fails.
- **Bot Evasion**: Uses `playwright-stealth` and human-like interactions to avoid detection.
- **MongoDB Integration**: Connects to the `fx-rates` database and intelligently updates records:
    - Mapps data to `ZiG_Bid`, `ZiG_Ask`, `ZiG_Mid`, and `Gold`.
    - Handles currency re-evaluation dates automatically (Midnight ISO).
- **Email Notifications**: Sends an SMTP email summary **only** upon successful database updates.
- **Secure Credentials**: Credentials (MongoDB, SMTP) are stored locally in an encrypted SQLite database, not in plain text files.
- **Systemd Integration**: Built-in support for running as a background service on Linux servers.

## 📂 Project Structure

```
rates-scrapper/
├── main.py             # CLI entry point
├── lib/
│   ├── scraper.py      # Core scraping logic
│   ├── mongo.py        # MongoDB client (fx-rates integration)
│   ├── db.py           # SQLite manager (credentials & history)
│   ├── email_notify.py # SMTP notification system
│   └── holidays.py     # Zimbabwe holiday checker
├── scripts/
│   ├── install.sh      # Robust setup script (local & server)
│   ├── run.sh          # Cron-friendly runner
│   ├── set_user.sh     # Configuration wizard
│   └── deploy.sh       # Deployment automation
└── requirements.txt
```

## 🛠 Installation

### Server (Ubuntu 22.04/24.04)

1.  **Clone or Copy** the repository.
2.  **Run Install Script**:
    ```bash
    ./install.sh
    ```
    This will:
    - Install system dependencies (Python, Playwright, Tesseract).
    - Create a virtual environment (`venv`).
    - Setup a **Systemd Timer** to run every 10 minutes (Mon-Fri, 08:00-17:00).

### Local Development

1.  **Run Install Script**:
    ```bash
    ./install.sh
    ```
2.  **Activate Environment**:
    ```bash
    source venv/bin/activate
    ```

## ⚙️ Configuration

Use the interactive script to configure credentials. It stores them safely in the local SQLite database (`rates.db`).

```bash
./set_user.sh
```

You can configure:
- **Profile Name**: A label for this configuration (e.g., "Prod Server").
- **MongoDB**: URI, Username, Password.
- **Email (Optional)**: SMTP details for success notifications.

## 🚀 Usage

### Manual Run

To run the scraper once (e.g., for testing):

```bash
./run.sh
```

**Force Mode:** To scrape even if rates for today have already been collected:

```bash
./run.sh --force
```

### CLI Commands (`main.py`)

For more granular control, use the Python CLI:

```bash
source venv/bin/activate

# Run scraper
python main.py run [--force]

# Test MongoDB Connection
python main.py test-mongo

# Set Credentials Manually
python main.py set-mongo-uri "mongodb+srv://..."
python main.py set-mongo-user "user"
python main.py set-mongo-pass  # Secure prompt
```

## 📦 Deployment

To deploy to the production server (`51.195.252.90`):

1.  Open `deploy.sh` and verify the `SERVER` variable.
2.  Run:
    ```bash
    ./deploy.sh
    ```
    This script will:
    - Package the application (excluding local state/venv).
    - SSH into the server.
    - Backup existing `rates.db` (to preserve history/credentials).
    - **Clean the directory** and upload the new package.
    - Restore `rates.db` and run `./install.sh` on the server.

## 🔍 Logic & Data Flow

1.  **Check Date**: Is it a weekend or holiday? If yes, skip.
2.  **Check History**: Have we already scraped today? (Checks SQLite).
3.  **Scrape Webpage**:
    - Extracts "Exchange Rates" and date.
    - Clicks "Gold Coin Price" tab and extracts gold rates.
4.  **Fallback (if needed)**:
    - If gold rates missing, searches for "Gold Coin Price" PDF on RBZ Documents page.
    - Downloads and parses PDF text.
5.  **MongoDB Update**:
    - Connects to `fx-rates` collection.
    - Checks if a record exists for the **Exchange Rate Date**.
    - **If New**: Creates a record with `ZiG` fields.
    - **Gold Logic**: If Gold Rate Date == Exchange Rate Date, calculates `Gold = ZWG / USD` (4 decimals) and saves.
6.  **Notification**:
    - Sends email **only** if a new record was inserted into MongoDB.

## 📝 Logs

- **Server Logs**: Managed by systemd.
  ```bash
  sudo journalctl -u rbz-scraper -f
  ```
- **Log File**: `/var/log/rbz-scraper.log`
