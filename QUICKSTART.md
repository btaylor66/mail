# Quick Start Guide

Get the Gmail Email Processor up and running in 15 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Gmail account
- 15 minutes

## Step 1: Get Google OAuth Credentials (5 minutes)

1. Go to https://console.cloud.google.com/
2. Create new project: "gmail-processor"
3. Enable Gmail API:
   - APIs & Services → Library → Search "Gmail API" → Enable
4. Configure OAuth consent screen:
   - OAuth consent screen → External → Create
   - App name: "Gmail Email Processor"
   - Your email for support
   - Add test user: your Gmail address
   - Save
5. Create credentials:
   - Credentials → Create Credentials → OAuth client ID
   - Type: Web application
   - Name: "Gmail Client"
   - Redirect URI: `http://localhost:8000/auth/callback`
   - Create
6. **Copy Client ID and Client Secret** - you'll need these!

## Step 2: Clone and Configure (2 minutes)

```bash
# Clone or create project directory
mkdir gmail-processor
cd gmail-processor

# Create .env file
cat > .env << 'EOF'
GMAIL_CLIENT_ID=YOUR_CLIENT_ID_HERE
GMAIL_CLIENT_SECRET=YOUR_CLIENT_SECRET_HERE
GMAIL_REDIRECT_URI=http://localhost:8000/auth/callback
DEFAULT_DAYS_LOOKBACK=30

DATABASE_URL=postgresql://postgres:postgres@postgres:5432/gmail_processor
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
TOKEN_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

LOG_LEVEL=INFO
ENVIRONMENT=development
EOF

# Replace placeholders with your actual credentials
nano .env  # Or use your preferred editor
```

## Step 3: Start Services (2 minutes)

```bash
# Start all services
docker-compose up -d

# Check that all services are running
docker-compose ps

# You should see:
# - gmail_postgres (PostgreSQL)
# - gmail_redis (Redis)
# - gmail_api (API server)
# - gmail_worker (Celery worker)
# - gmail_flower (Monitoring)

# Initialize database
docker-compose exec api python -m src.db.init_db
```

## Step 4: Authorize Gmail Access (3 minutes)

1. **Open browser**: http://localhost:8000/auth/login

2. **Sign in** with your Gmail account

3. **Grant permissions**:
   - You'll see "Google hasn't verified this app"
   - Click "Advanced"
   - Click "Go to Gmail Email Processor (unsafe)" - it's your app, it's safe!
   - Click "Allow"

4. **Success**: You should see "✅ Authorization successful!"

## Step 5: Fetch and Process Emails (3 minutes)

```bash
# Fetch emails from last 30 days
docker-compose exec worker python -m src.workers.gmail_fetcher --days 30

# Watch the logs
docker-compose logs -f worker

# You should see:
# - "Starting Gmail fetch..."
# - "Found X emails"
# - "Enqueued X emails for processing"
# - "Processing email: [subject]"
# - "Extracted N events from email"
```

## Step 6: View Results

### Check Celery Dashboard
Open: http://localhost:5555

You'll see:
- Active tasks
- Completed tasks
- Worker status

### Query the Database

```bash
# Connect to database
docker-compose exec postgres psql -U postgres -d gmail_processor

# View recent fetch jobs
SELECT id, emails_found, status, started_at FROM fetch_jobs ORDER BY started_at DESC LIMIT 5;

# View processed emails
SELECT subject, from_address, received_at FROM email_metadata ORDER BY received_at DESC LIMIT 10;

# View extracted meetings
SELECT
  extracted_data->>'title' AS meeting,
  extracted_data->>'date' AS date,
  extracted_data->>'time' AS time
FROM processed_results
WHERE result_type = 'meeting'
ORDER BY created_at DESC
LIMIT 10;

# Exit psql
\q
```

## Common Issues

### "redirect_uri_mismatch"
- Ensure `.env` has exactly: `GMAIL_REDIRECT_URI=http://localhost:8000/auth/callback`
- Ensure Google Console has exactly: `http://localhost:8000/auth/callback`

### Services won't start
```bash
# Check logs
docker-compose logs

# Restart services
docker-compose restart

# Rebuild if needed
docker-compose down
docker-compose build
docker-compose up -d
```

### No emails found
- Check Gmail account has emails in the date range
- Try a smaller date range: `--days 7`
- Check OAuth token is valid: `docker-compose exec api python -m src.auth.verify_token`

## Next Steps

- **Schedule periodic fetching**: Uncomment `celery-beat` in `docker-compose.yml`
- **Customize event extraction**: Edit `src/services/event_extractor.py`
- **Add more Gmail accounts**: See [SETUP.md](SETUP.md) for multi-user setup
- **Deploy to production**: See [SETUP.md](SETUP.md) production section

## Full Documentation

- [README.md](README.md) - Project overview
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design and data flow
- [SETUP.md](SETUP.md) - Detailed installation guide
- [GMAIL_AUTH.md](GMAIL_AUTH.md) - OAuth setup details

## Getting Help

- Check logs: `docker-compose logs -f`
- Review [GMAIL_AUTH.md](GMAIL_AUTH.md) for OAuth issues
- Check GitHub issues: https://github.com/your-repo/issues
