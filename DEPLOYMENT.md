# Deployment Guide

Complete instructions for deploying the Prophet Portfolio Optimization application to production.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Hostinger VPS Deployment](#hostinger-vps-deployment)
4. [Supabase Setup](#supabase-setup)
5. [Environment Configuration](#environment-configuration)
6. [Running the Application](#running-the-application)
7. [Scheduled Jobs](#scheduled-jobs)
8. [Monitoring & Maintenance](#monitoring--maintenance)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended) or macOS
- **Python**: 3.11+
- **RAM**: 2GB minimum (4GB recommended for Prophet model)
- **Disk Space**: 500MB+ for application and dependencies
- **Internet**: Stable connection for yfinance and Supabase access

### Required Accounts
1. **Supabase Account** (Free tier available)
   - For database storage
   - Sign up at https://supabase.com

2. **GitHub Account** (optional but recommended)
   - For version control
   - Repository: https://github.com/nyxkings/prophet-stock-forecast

3. **Hostinger Account** (optional)
   - For VPS hosting
   - Recommended for scheduled jobs

---

## Local Development Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/nyxkings/prophet-stock-forecast.git
cd prophet-stock-forecast
```

### Step 2: Install Python Dependencies

Using Poetry (recommended):
```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

Or using pip:
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Create `.env` file in project root:
```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Optional: Portfolio Configuration
PORTFOLIO_TICKERS=AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,JPM,JNJ,V,WMT,XOM
RISK_AVERSION=5
MINIMUM_ALLOCATION=0.05
MAXIMUM_ALLOCATION=1.0
START_DATE=2024-01-01
END_DATE=2024-12-31
```

### Step 4: Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=html

# Run specific test file
pytest tests/test_model.py -v
```

### Step 5: Run Application

```bash
# One-time optimization run
python -c "
from src.main import run_optimisation
from src.database import save_results_to_supabase

result = run_optimisation(['AAPL', 'MSFT', 'GOOGL'], '2024-01-01', '2024-12-31')
if result:
    save_results_to_supabase(result)
    print('Optimization complete!')
"

# Run Streamlit dashboard
streamlit run src/streamlit_app.py
```

---

## Hostinger VPS Deployment

### Step 1: VPS Setup on Hostinger

1. **Create VPS Instance**
   - Log in to Hostinger Control Panel
   - Click "VPS Hosting" → "Create VPS"
   - Choose: Ubuntu 20.04 LTS, 2GB RAM, 50GB SSD
   - Note the IP address and root password

2. **Connect via SSH**
   ```bash
   ssh root@YOUR_VPS_IP
   # Enter password when prompted
   ```

3. **Initial System Setup**
   ```bash
   # Update system
   apt update && apt upgrade -y
   
   # Install essential tools
   apt install -y python3.11 python3.11-venv python3-pip git curl
   
   # Create non-root user
   useradd -m -s /bin/bash prophet
   usermod -aG sudo prophet
   su - prophet
   ```

### Step 2: Application Deployment

1. **Clone Repository**
   ```bash
   cd ~
   git clone https://github.com/nyxkings/prophet-stock-forecast.git
   cd prophet-stock-forecast
   ```

2. **Setup Virtual Environment**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Create Environment File**
   ```bash
   nano .env
   ```
   
   Add configuration:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   ```
   
   Save with Ctrl+O, Enter, Ctrl+X

### Step 3: Systemd Service Setup

Create service file:
```bash
sudo tee /etc/systemd/system/prophet-optimization.service > /dev/null <<EOF
[Unit]
Description=Prophet Portfolio Optimization
After=network.target

[Service]
User=prophet
WorkingDirectory=/home/prophet/prophet-stock-forecast
Environment="PATH=/home/prophet/prophet-stock-forecast/venv/bin"
ExecStart=/home/prophet/prophet-stock-forecast/venv/bin/python -m src.main
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF
```

Enable service:
```bash
sudo systemctl enable prophet-optimization
sudo systemctl start prophet-optimization
```

### Step 4: Scheduled Daily Runs

Install and configure cron:

```bash
# Edit crontab
crontab -e

# Add daily run at 9am UTC
0 9 * * * cd /home/prophet/prophet-stock-forecast && source venv/bin/activate && python -m src.main >> /tmp/prophet.log 2>&1
```

Or use systemd timer:

```bash
sudo tee /etc/systemd/system/prophet-optimization.timer > /dev/null <<EOF
[Unit]
Description=Prophet Portfolio Optimization Daily Timer
Requires=prophet-optimization.service

[Timer]
OnCalendar=*-*-* 09:00:00
Unit=prophet-optimization.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl enable prophet-optimization.timer
sudo systemctl start prophet-optimization.timer
```

### Step 5: Setup Streamlit Dashboard (Optional)

Install additional dependencies:
```bash
pip install streamlit
```

Create systemd service for dashboard:
```bash
sudo tee /etc/systemd/system/prophet-dashboard.service > /dev/null <<EOF
[Unit]
Description=Prophet Dashboard
After=network.target

[Service]
User=prophet
WorkingDirectory=/home/prophet/prophet-stock-forecast
Environment="PATH=/home/prophet/prophet-stock-forecast/venv/bin"
ExecStart=/home/prophet/prophet-stock-forecast/venv/bin/streamlit run src/streamlit_app.py --server.port=8501
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable prophet-dashboard
sudo systemctl start prophet-dashboard
```

Access dashboard:
```
http://YOUR_VPS_IP:8501
```

---

## Supabase Setup

### Step 1: Create Supabase Account

1. Visit https://supabase.com
2. Sign up with email or GitHub account
3. Create a new organization and project

### Step 2: Get API Credentials

1. Go to Project Settings → API
2. Copy:
   - Project URL → `SUPABASE_URL`
   - Anon Key → `SUPABASE_KEY`

### Step 3: Create Database Table

In Supabase SQL Editor, run:

```sql
-- Create table for storing optimization results
-- Column names must match src/database.py save_results_to_supabase()
CREATE TABLE IF NOT EXISTS stock_optimisation_store (
  id UUID PRIMARY KEY,
  created_at TIMESTAMPTZ,
  as_of_date DATE,
  ticker TEXT NOT NULL,
  predicted_price DOUBLE PRECISION NOT NULL,
  predicted_return DOUBLE PRECISION NOT NULL,
  actual_prices_last_month JSONB,
  portfolio_weight DOUBLE PRECISION NOT NULL
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_as_of_date ON stock_optimisation_store(as_of_date DESC);
CREATE INDEX IF NOT EXISTS idx_ticker ON stock_optimisation_store(ticker);

-- Enable Row Level Security
ALTER TABLE stock_optimisation_store ENABLE ROW LEVEL SECURITY;

-- Create policy for public read access
CREATE POLICY "Enable read access for all users"
  ON stock_optimisation_store
  FOR SELECT
  USING (true);

-- Create policy for insert access (for our app)
CREATE POLICY "Enable insert access for service role"
  ON stock_optimisation_store
  FOR INSERT
  WITH CHECK (true);
```

### Step 4: Verify Connection

Test from local machine:
```python
from src.database import get_supabase_client

client = get_supabase_client()
if client:
    result = client.table('stock_optimisation_store').select('*').limit(1).execute()
    print("✅ Connected to Supabase!")
    print(f"Found {len(result.data)} records")
else:
    print("❌ Failed to connect - check credentials")
```

---

## Environment Configuration

### Environment Variables

Create `.env` file:

```bash
# Required: Supabase credentials
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Optional: Portfolio configuration
# Default: AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, JPM, JNJ, V, WMT, XOM
PORTFOLIO_TICKERS=AAPL,MSFT,GOOGL

# Optional: Optimization parameters
RISK_AVERSION=5              # Risk aversion coefficient (1-10)
MINIMUM_ALLOCATION=0.05      # 5% minimum per asset
MAXIMUM_ALLOCATION=1.0       # 100% maximum per asset

# Optional: Date range for analysis
START_DATE=2024-01-01
END_DATE=2024-12-31
```

### Loading Environment Variables

Application automatically loads from `.env` file using `python-dotenv`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
```

---

## Running the Application

### Standalone Script

```bash
# Activate virtual environment
source venv/bin/activate

# Run optimization
python -m src.main

# With custom parameters
python -c "
from src.main import run_optimisation
result = run_optimisation(
    ['AAPL', 'MSFT'],
    '2024-01-01',
    '2024-12-31'
)
print(result)
"
```

### With Docker (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy application
COPY . /app

# Install Python dependencies
RUN pip install -r requirements.txt

# Run application
CMD ["python", "-m", "src.main"]
```

Build and run:
```bash
# Build image
docker build -t prophet-optimization .

# Run container
docker run -e SUPABASE_URL="..." -e SUPABASE_KEY="..." prophet-optimization

# Or with env file
docker run --env-file .env prophet-optimization
```

---

## Scheduled Jobs

### Daily Optimization Cron

Run optimization every day at 9am UTC:

```bash
# Edit crontab
crontab -e

# Add this line
0 9 * * * cd /path/to/prophet-stock-forecast && source venv/bin/activate && python -m src.main >> /tmp/prophet.log 2>&1
```

### Monitoring Cron Execution

```bash
# View cron logs
sudo tail -f /var/log/syslog | grep CRON

# View application logs
tail -f /tmp/prophet.log
```

### Advanced Scheduling with APScheduler

Create `scheduler.py`:
```python
from apscheduler.schedulers.blocking import BlockingScheduler
from src.main import run_optimisation
from src.database import save_results_to_supabase

scheduler = BlockingScheduler()

@scheduler.scheduled_job('cron', hour=9, minute=0)
def daily_optimization():
    print("Starting daily optimization...")
    result = run_optimisation(
        ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META'],
        '2024-01-01',
        '2024-12-31'
    )
    if result:
        save_results_to_supabase(result)
        print("✅ Optimization completed and saved")
    else:
        print("❌ Optimization failed")

if __name__ == '__main__':
    scheduler.start()
```

Run:
```bash
python scheduler.py
```

---

## Monitoring & Maintenance

### Health Checks

Create `health_check.py`:
```python
import sys
from src.database import get_supabase_client

def check_database():
    """Verify database connectivity"""
    try:
        client = get_supabase_client()
        if not client:
            return False, "Credentials not configured"
        
        result = client.table('stock_optimisation_store').select('count').eq('count', 'exact').execute()
        return True, "Database connected"
    except Exception as e:
        return False, str(e)

def check_recent_results():
    """Check if recent optimization results exist"""
    try:
        client = get_supabase_client()
        if not client:
            return False, "Cannot connect to database"
        
        result = client.table('stock_optimisation_store').select('as_of_date').order('as_of_date', desc=True).limit(1).execute()
        
        if result.data:
            last_run = result.data[0]['as_of_date']
            return True, f"Last run: {last_run}"
        else:
            return False, "No results found in database"
    except Exception as e:
        return False, str(e)

if __name__ == '__main__':
    db_ok, db_msg = check_database()
    results_ok, results_msg = check_recent_results()
    
    print(f"🗄️  Database: {'✅' if db_ok else '❌'} {db_msg}")
    print(f"📊 Results: {'✅' if results_ok else '❌'} {results_msg}")
    
    sys.exit(0 if (db_ok and results_ok) else 1)
```

Run health check:
```bash
python health_check.py
```

### Log Monitoring

View application logs:
```bash
# Recent logs
tail -100 /tmp/prophet.log

# Follow live logs
tail -f /tmp/prophet.log

# Search for errors
grep ERROR /tmp/prophet.log

# Get statistics
wc -l /tmp/prophet.log  # Total lines
grep "completed" /tmp/prophet.log | wc -l  # Successful runs
```

### Database Backup

Export data:
```bash
# From Supabase dashboard
1. Go to "Backups" tab
2. Create manual backup
3. Or use Supabase CLI:

supabase db pull  # Pull database schema
```

### Performance Optimization

1. **Prophet Model Tuning**
   - Adjust `changepoint_prior_scale` for sensitivity
   - Modify `seasonality_mode` (additive/multiplicative)
   - See `src/settings.py`

2. **Optimization Tuning**
   - Adjust `risk_aversion` parameter (1-10)
   - Modify allocation constraints
   - See `src/settings.py`

3. **Memory Management**
   - Prophet can use significant RAM for large datasets
   - Monitor with `top` or `htop`
   - Reduce date range if needed

---

## Troubleshooting

### Common Issues

#### Issue: "No module named 'prophet'"

**Solution:**
```bash
# Activate venv
source venv/bin/activate

# Reinstall
pip install prophet --no-cache-dir
```

#### Issue: "SUPABASE_URL or SUPABASE_KEY not found"

**Solution:**
```bash
# Check .env file exists
ls -la .env

# Add missing variables
echo "SUPABASE_URL=your_url" >> .env
echo "SUPABASE_KEY=your_key" >> .env

# Verify environment
python -c "import os; print(os.getenv('SUPABASE_URL'))"
```

#### Issue: "Connection timeout to yfinance"

**Solution:**
```bash
# Test connectivity
python -c "import yfinance as yf; print(yf.Ticker('AAPL').history(period='1d'))"

# Use retry logic
pip install retry

# Check network
ping google.com
curl -I https://query1.finance.yahoo.com
```

#### Issue: "Permission denied" when starting service

**Solution:**
```bash
# Fix file ownership
sudo chown -R prophet:prophet /home/prophet/prophet-stock-forecast

# Set correct permissions
sudo chmod -R 755 /home/prophet/prophet-stock-forecast
```

#### Issue: "OutOfMemory" during Prophet fitting

**Solution:**
```bash
# Check available memory
free -h

# Reduce date range in config
START_DATE=2024-06-01  # Shorter period

# Or reduce number of tickers
PORTFOLIO_TICKERS=AAPL,MSFT,GOOGL
```

### Debug Mode

Enable verbose logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Debug information...")
```

Or set environment variable:
```bash
export PYTHONUNBUFFERED=1
export LOG_LEVEL=DEBUG

python -m src.main
```

### Getting Help

1. **Check logs first**
   ```bash
   grep -i error /tmp/prophet.log
   ```

2. **Review test cases**
   ```bash
   pytest tests/ -v -k "test_name"
   ```

3. **Check documentation**
   - `API_DOCUMENTATION.md` - Function reference
   - `TESTING.md` - Testing guide
   - `README.md` - Quick start

4. **Report issues**
   - GitHub Issues: https://github.com/nyxkings/prophet-stock-forecast/issues
   - Include: Error message, logs, system info, reproduction steps

---

## Version Information

- **Application**: Prophet Stock Forecasting v0.1.0
- **Python**: 3.11+
- **Last Updated**: May 2026

