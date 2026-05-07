# Deployment Guide

Complete guide for deploying the Prophet Portfolio Optimization system to production.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Hostinger VPS Deployment](#hostinger-vps-deployment)
4. [Supabase Configuration](#supabase-configuration)
5. [Environment Variables](#environment-variables)
6. [Monitoring & Logs](#monitoring--logs)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended) or macOS
- **Python**: 3.11+
- **Memory**: 2GB minimum
- **Storage**: 1GB minimum
- **Internet**: Stable connection for API calls

### External Services
- **Supabase Account**: https://supabase.com (free tier suitable)
- **GitHub Account**: For code repository
- **Domain Name** (optional): For public deployment

---

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/nyxkings/prophet-stock-forecast.git
cd prophet-stock-forecast
```

### 2. Create Python Environment

**Using Poetry (Recommended):**
```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Create virtual environment and install dependencies
poetry install

# Activate environment
poetry shell
```

**Alternative - Using venv:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Environment Variables

Create `.env` file in project root:
```bash
cat > .env << EOF
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
EOF
```

### 4. Run Locally

**Single Optimization Run:**
```bash
python -c "from src.main import run_optimisation; print(run_optimisation(['AAPL', 'MSFT'], '2024-01-01', '2024-05-06'))"
```

**Start Dashboard:**
```bash
streamlit run src/streamlit_app.py
```

### 5. Run Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific test file
pytest tests/test_model.py -v
```

---

## Hostinger VPS Deployment

### 1. VPS Setup

**At Hostinger Dashboard:**
1. Create Ubuntu 20.04 LTS VPS (2GB RAM recommended)
2. Enable SSH access
3. Get root credentials

### 2. Initial Server Configuration

```bash
# SSH into server
ssh root@your_vps_ip

# Update system
apt update && apt upgrade -y

# Install Python and system dependencies
apt install -y python3.11 python3.11-venv python3.11-dev
apt install -y pip git curl wget
apt install -y build-essential libssl-dev libffi-dev
```

### 3. Clone Repository

```bash
# Create app directory
mkdir -p /var/www/portfolio-app
cd /var/www/portfolio-app

# Clone repository
git clone https://github.com/nyxkings/prophet-stock-forecast.git .
```

### 4. Setup Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure Environment Variables

```bash
# Create .env file
nano .env
```

**Contents:**
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
PYTHONUNBUFFERED=1
```

Save with `Ctrl+X`, then `Y`, then `Enter`.

### 6. Setup Systemd Service

Create systemd service for daily execution:

```bash
sudo nano /etc/systemd/system/portfolio-optimization.service
```

**Contents:**
```ini
[Unit]
Description=Prophet Portfolio Optimization
After=network.target

[Service]
Type=oneshot
User=www-data
Group=www-data
WorkingDirectory=/var/www/portfolio-app
Environment="PATH=/var/www/portfolio-app/venv/bin"
ExecStart=/var/www/portfolio-app/venv/bin/python -c "from src.main import run_optimisation; run_optimisation(['AAPL','MSFT','GOOGL','AMZN','TSLA','NVDA','META','NVIDIA','BERKB','JPM','JNJ','V'], '2024-01-01', '2024-05-07')"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 7. Setup Cron Job for Daily Execution

```bash
# Edit crontab
sudo crontab -e

# Add this line (runs every day at 9:00 AM UTC)
0 9 * * * cd /var/www/portfolio-app && source venv/bin/activate && python -c "from src.main import run_optimisation; run_optimisation(['AAPL','MSFT','GOOGL','AMZN','TSLA','NVDA','META','NVIDIA','BERKB','JPM','JNJ','V'], '2024-01-01', '2024-05-07')" >> /var/log/portfolio-optimization.log 2>&1
```

### 8. Deploy Streamlit Dashboard

**Install Nginx as Reverse Proxy:**
```bash
sudo apt install -y nginx

# Create Nginx config
sudo nano /etc/nginx/sites-available/portfolio
```

**Contents:**
```nginx
upstream streamlit {
    server localhost:8501;
}

server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://streamlit;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable config:
```bash
sudo ln -s /etc/nginx/sites-available/portfolio /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Create Systemd Service for Streamlit:**

```bash
sudo nano /etc/systemd/system/streamlit-portfolio.service
```

**Contents:**
```ini
[Unit]
Description=Streamlit Portfolio Dashboard
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/portfolio-app
Environment="PATH=/var/www/portfolio-app/venv/bin"
ExecStart=/var/www/portfolio-app/venv/bin/streamlit run src/streamlit_app.py --server.port 8501 --server.address 127.0.0.1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable streamlit-portfolio
sudo systemctl start streamlit-portfolio
```

### 9. SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Generate certificate (replace with your domain)
sudo certbot certonly --nginx -d your_domain.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

Update Nginx config to use HTTPS and redirect HTTP to HTTPS.

---

## Supabase Configuration

### 1. Create Project

1. Visit https://supabase.com
2. Sign up or log in
3. Create new project
4. Wait for project initialization (~5 minutes)

### 2. Create Database Table

**SQL Editor:**
```sql
-- Table for storing optimization results
CREATE TABLE stock_optimisation_store (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    date DATE NOT NULL,
    ticker TEXT NOT NULL,
    predicted_price FLOAT NOT NULL,
    predicted_return FLOAT NOT NULL,
    weight FLOAT NOT NULL,
    actual_prices_last_month JSONB,
    metadata JSONB DEFAULT NULL,
    UNIQUE(date, ticker)
);

-- Index for faster queries
CREATE INDEX idx_date ON stock_optimisation_store(date);
CREATE INDEX idx_ticker ON stock_optimisation_store(ticker);
```

### 3. Get API Keys

**In Supabase Dashboard:**
1. Navigate to "Settings" → "API"
2. Copy: `Project URL` → `SUPABASE_URL`
3. Copy: `anon public` key → `SUPABASE_KEY`

### 4. Row Level Security (RLS)

For public read access:
```sql
ALTER TABLE stock_optimisation_store ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read"
    ON stock_optimisation_store FOR SELECT
    USING (true);

CREATE POLICY "Allow service role insert"
    ON stock_optimisation_store FOR INSERT
    WITH CHECK (true);
```

---

## Environment Variables

Required environment variables for all deployments:

```bash
# Required: Supabase credentials
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Optional: Python settings
PYTHONUNBUFFERED=1      # Immediate output (useful for logging)
PYTHONDONTWRITEBYTECODE=1  # Don't create __pycache__

# Optional: Application settings
PORTFOLIO_TICKERS=AAPL,MSFT,GOOGL,AMZN  # Comma-separated
RISK_AVERSION=5.0
MIN_ALLOCATION=0.05
MAX_ALLOCATION=1.0
```

### Setting Variables

**On VPS:**
```bash
# Add to /etc/environment
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

**In Cron Job:**
Include in crontab (as shown in Cron Job section)

**For Systemd Service:**
Use `Environment=KEY=VALUE` in service file

---

## Monitoring & Logs

### View Logs

**Systemd Service:**
```bash
# Real-time logs
sudo journalctl -u portfolio-optimization.service -f

# Last 50 lines
sudo journalctl -u portfolio-optimization.service -n 50
```

**Cron Logs:**
```bash
# View cron log
tail -f /var/log/portfolio-optimization.log
```

**Application Logs:**
```bash
# Check VPS server logs
tail -f /var/log/syslog
```

### Monitoring Dashboard

Visit deployed Streamlit app to see:
- Latest optimization results
- Historical predictions vs actual prices
- Portfolio weight evolution
- Performance metrics

### Health Checks

Create health check script:
```bash
#!/bin/bash
# /var/www/portfolio-app/health_check.sh

cd /var/www/portfolio-app
source venv/bin/activate

# Test imports
python -c "from src.main import run_optimisation; print('OK')" || exit 1

# Check Supabase connection
python -c "from src.database import get_supabase_client; get_supabase_client(); print('OK')" || exit 1

echo "Health check passed"
```

Run periodically:
```bash
# Add to crontab (check every hour)
0 * * * * /var/www/portfolio-app/health_check.sh >> /var/log/health-check.log 2>&1
```

---

## Troubleshooting

### Common Issues

#### 1. **ModuleNotFoundError: No module named 'prophet'**

**Cause:** Dependencies not installed

**Solution:**
```bash
source venv/bin/activate
pip install prophet
```

#### 2. **Connection refused when accessing dashboard**

**Cause:** Streamlit service not running

**Solution:**
```bash
sudo systemctl status streamlit-portfolio
sudo systemctl start streamlit-portfolio
```

#### 3. **Supabase connection errors**

**Cause:** Missing or incorrect credentials

**Solution:**
```bash
# Verify environment variables
echo $SUPABASE_URL
echo $SUPABASE_KEY

# Test connection
python -c "from src.database import get_supabase_client; get_supabase_client()"
```

#### 4. **yfinance data not fetching**

**Cause:** Network issue or API rate limit

**Solution:**
```bash
# Test yfinance
python -c "import yfinance as yf; print(yf.Ticker('AAPL').history(period='1y').head())"

# Add delay between requests
time.sleep(1)  # in code
```

#### 5. **Out of memory errors**

**Cause:** Large portfolio or insufficient RAM

**Solution:**
- Reduce portfolio size
- Upgrade VPS RAM (Hostinger allows easy upgrades)
- Optimize Prophet model (reduce seasonality)

### Debug Mode

Enable debug logging:
```python
# Add to main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Rollback Procedure

If deployment fails:
```bash
# Revert to previous git commit
cd /var/www/portfolio-app
git log --oneline  # Find commit hash
git checkout <commit-hash>

# Restart services
sudo systemctl restart streamlit-portfolio
sudo systemctl restart portfolio-optimization
```

---

## Performance Tuning

### For Large Portfolios (50+ tickers)

1. **Parallel Prophet Training:**
   - Use multiprocessing in model.py
   - Reduces training time from O(n) to O(n/cores)

2. **Cache Historical Data:**
   - Store data locally
   - Update incrementally instead of full fetch

3. **Optimize Supabase:**
   - Use batch inserts
   - Add database indexes

### Memory Optimization

```python
# In extractor.py - process tickers one-by-one
# Instead of loading all into memory at once
```

### Network Optimization

- Use local DNS resolution
- Cache DNS lookups
- Use connection pooling for API calls

---

## Backup & Recovery

### Database Backups

Supabase provides automatic daily backups. Access via:
1. Supabase Dashboard → Backups
2. Select backup date
3. Download or restore

### Code Backups

Repository is version controlled on GitHub. Restore with:
```bash
git clone https://github.com/nyxkings/prophet-stock-forecast.git
```

### Configuration Backups

Store `.env` file in secure location (not in git):
```bash
# Backup locally
scp root@vps_ip:/var/www/portfolio-app/.env ./backup/.env
```

---

## Cost Estimation

### VPS (Hostinger)
- Small VPS: $3.99/month
- 2GB RAM, 50GB SSD
- Sufficient for 12+ ticker portfolio

### Supabase
- Free tier: Suitable for development
- Pro tier: $25/month for production
- Includes 500GB database storage

### Domain (optional)
- .com domain: $10-15/year

### Total
- **Minimal Setup**: ~$10/month (VPS + free Supabase)
- **Production Setup**: ~$40-50/month

---

## Scaling Considerations

### Current Limits
- Up to 50 tickers per optimization
- Completes in 30-60 seconds
- Supabase free tier: 100,000 rows/month

### For Higher Scale
- Use serverless functions (AWS Lambda, Google Cloud Functions)
- Implement caching layer (Redis)
- Use dedicated ML inference service (SageMaker)

---

## See Also

- [API Documentation](API.md)
- [Architecture Documentation](ARCHITECTURE.md)
- [Testing Guide](TESTING.md)
- [User Guide](USER_GUIDE.md)

---

**Last Updated**: May 7, 2024
**Tested With**: Ubuntu 20.04 LTS, Python 3.11, Supabase
