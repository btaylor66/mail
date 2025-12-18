# Setup Guide

Complete installation and configuration instructions for the Gmail Email Processor.

## Prerequisites

- **Docker** and **Docker Compose** (recommended) OR
- **Python 3.11+** for local development
- **Google Cloud Project** with Gmail API enabled (see [GMAIL_AUTH.md](GMAIL_AUTH.md))
- **Gmail Account** for testing

## Installation

### Option 1: Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd gmail
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure Gmail OAuth credentials**

   Follow the [GMAIL_AUTH.md](GMAIL_AUTH.md) guide to:
   - Create a Google Cloud Project
   - Enable Gmail API
   - Create OAuth 2.0 credentials
   - Download credentials and update `.env`

4. **Edit `.env` file**
   ```bash
   nano .env  # or use your preferred editor
   ```

   Required variables:
   ```bash
   GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GMAIL_CLIENT_SECRET=your-client-secret
   GMAIL_REDIRECT_URI=http://localhost:8000/auth/callback
   DEFAULT_DAYS_LOOKBACK=30
   ```

5. **Start services**
   ```bash
   docker-compose up -d
   ```

6. **Initialize database**
   ```bash
   docker-compose exec api python -m src.db.init_db
   ```

7. **Verify services are running**
   ```bash
   docker-compose ps
   ```

   You should see:
   - `gmail_api` - API server (port 8000)
   - `gmail_worker` - Celery worker
   - `gmail_redis` - Redis (port 6379)
   - `gmail_postgres` - PostgreSQL (port 5432)
   - `gmail_flower` - Celery monitoring (port 5555)

### Option 2: Local Development (Without Docker)

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd gmail
   ```

2. **Create virtual environment**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install and start PostgreSQL**
   ```bash
   # macOS
   brew install postgresql@15
   brew services start postgresql@15

   # Ubuntu/Debian
   sudo apt install postgresql postgresql-contrib
   sudo systemctl start postgresql

   # Create database
   createdb gmail_processor
   ```

5. **Install and start Redis**
   ```bash
   # macOS
   brew install redis
   brew services start redis

   # Ubuntu/Debian
   sudo apt install redis-server
   sudo systemctl start redis
   ```

6. **Create environment file**
   ```bash
   cp .env.example .env
   ```

7. **Edit `.env` with local configuration**
   ```bash
   DATABASE_URL=postgresql://localhost:5432/gmail_processor
   REDIS_URL=redis://localhost:6379/0
   GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GMAIL_CLIENT_SECRET=your-client-secret
   GMAIL_REDIRECT_URI=http://localhost:8000/auth/callback
   DEFAULT_DAYS_LOOKBACK=30
   ```

8. **Initialize database**
   ```bash
   python -m src.db.init_db
   ```

## OAuth Authentication Setup

### First-Time User Authorization

1. **Start the API server** (if not already running)
   ```bash
   # Docker
   docker-compose up -d api

   # Local
   python -m src.api.main
   ```

2. **Initiate OAuth flow**

   Visit: `http://localhost:8000/auth/login`

   This will redirect you to Google's OAuth consent screen.

3. **Grant permissions**

   - Sign in with your Gmail account
   - Review permissions (read-only access to Gmail)
   - Click "Allow"

4. **Callback and token storage**

   - You'll be redirected to `http://localhost:8000/auth/callback`
   - OAuth tokens will be encrypted and stored in the database
   - You should see: `✅ Authorization successful!`

5. **Verify authentication**
   ```bash
   # Docker
   docker-compose exec api python -m src.auth.verify_token

   # Local
   python -m src.auth.verify_token
   ```

### Token Refresh

OAuth tokens expire after 1 hour, but refresh tokens are long-lived. The system automatically refreshes tokens when needed.

## Running the Gmail Fetcher

### Manual One-Time Fetch

Fetch emails from the last 30 days:

```bash
# Docker
docker-compose exec worker python -m src.workers.gmail_fetcher --days 30

# Local
python -m src.workers.gmail_fetcher --days 30
```

Fetch from a specific date range:

```bash
docker-compose exec worker python -m src.workers.gmail_fetcher --days 7
```

### Scheduled Fetching

Set up a cron job or use Celery Beat for periodic fetching.

**Using Celery Beat (Recommended):**

1. **Enable beat scheduler in `docker-compose.yml`**

   Uncomment the `celery-beat` service:
   ```yaml
   celery-beat:
     <<: *app-service
     command: celery -A src.workers.celery_app beat --loglevel=info
     depends_on:
       - redis
   ```

2. **Configure schedule in `src/workers/celery_app.py`**
   ```python
   from celery.schedules import crontab

   app.conf.beat_schedule = {
       'fetch-emails-daily': {
           'task': 'src.workers.gmail_fetcher.fetch_emails',
           'schedule': crontab(hour=6, minute=0),  # 6 AM daily
           'args': (30,)  # Last 30 days
       },
   }
   ```

3. **Restart services**
   ```bash
   docker-compose restart celery-beat
   ```

**Using System Cron:**

```bash
# Edit crontab
crontab -e

# Add daily fetch at 6 AM
0 6 * * * cd /path/to/gmail && docker-compose exec -T worker python -m src.workers.gmail_fetcher --days 30
```

## Monitoring

### Celery Flower Dashboard

Real-time monitoring of workers and tasks:

```bash
# Access Flower UI
open http://localhost:5555
```

Features:
- Active tasks
- Worker status
- Task history
- Queue depth
- Success/failure rates

### Logs

**View all logs:**
```bash
docker-compose logs -f
```

**View specific service logs:**
```bash
docker-compose logs -f worker
docker-compose logs -f api
```

**Search logs by correlation ID:**
```bash
# Docker
docker-compose exec postgres psql -U postgres -d gmail_processor -c \
  "SELECT * FROM processing_logs WHERE correlation_id = 'your-uuid-here' ORDER BY created_at;"

# Local
psql -d gmail_processor -c \
  "SELECT * FROM processing_logs WHERE correlation_id = 'your-uuid-here' ORDER BY created_at;"
```

### Database Queries

**Check fetch job status:**
```sql
SELECT id, status, started_at, emails_found
FROM fetch_jobs
ORDER BY started_at DESC
LIMIT 10;
```

**View recent processed emails:**
```sql
SELECT m.subject, m.from_address, m.received_at, m.processed
FROM email_metadata m
ORDER BY m.received_at DESC
LIMIT 20;
```

**Find extracted meetings:**
```sql
SELECT
  r.id,
  r.extracted_data->>'title' AS title,
  r.extracted_data->>'date' AS meeting_date,
  m.subject AS email_subject
FROM processed_results r
JOIN email_metadata m ON r.message_id = m.message_id
WHERE r.result_type = 'meeting'
ORDER BY r.created_at DESC
LIMIT 10;
```

**Debug a specific email:**
```sql
-- Find email
SELECT message_id, fetch_job_id, subject
FROM email_metadata
WHERE subject LIKE '%important meeting%';

-- Get processing logs
SELECT pl.log_level, pl.message, pl.created_at
FROM processing_logs pl
JOIN processed_results pr ON pl.correlation_id = pr.processing_job_id
WHERE pr.message_id = 'your-message-id'
ORDER BY pl.created_at;

-- Get extracted results
SELECT result_type, extracted_data
FROM processed_results
WHERE message_id = 'your-message-id';
```

## Configuration

### Environment Variables

Full list of configuration options:

```bash
# Gmail OAuth
GMAIL_CLIENT_ID=                    # OAuth client ID
GMAIL_CLIENT_SECRET=                # OAuth client secret
GMAIL_REDIRECT_URI=                 # OAuth redirect URI

# Database
DATABASE_URL=                       # PostgreSQL connection string
DATABASE_POOL_SIZE=10               # Connection pool size
DATABASE_MAX_OVERFLOW=20            # Max overflow connections

# Redis
REDIS_URL=                          # Redis connection string
REDIS_MAX_CONNECTIONS=50            # Max Redis connections

# Queue Configuration
CELERY_BROKER_URL=                  # Same as REDIS_URL
CELERY_RESULT_BACKEND=              # Same as REDIS_URL
CELERY_TASK_SERIALIZER=json         # Task serialization format
CELERY_RESULT_SERIALIZER=json       # Result serialization format

# Application
DEFAULT_DAYS_LOOKBACK=30            # Default email fetch range
LOG_LEVEL=INFO                      # Logging level
ENVIRONMENT=development             # Environment (development/production)

# Security
SECRET_KEY=                         # Flask secret key for encryption
TOKEN_ENCRYPTION_KEY=               # Fernet key for OAuth token encryption

# API
API_HOST=0.0.0.0                    # API server host
API_PORT=8000                       # API server port
```

### Generating Encryption Keys

For `TOKEN_ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Testing

### Run Tests

```bash
# Docker
docker-compose exec api pytest

# Local
pytest
```

### Test Coverage

```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Manual Testing

1. **Test OAuth flow**
   ```bash
   curl http://localhost:8000/auth/login
   ```

2. **Test Gmail fetch (requires auth)**
   ```bash
   docker-compose exec worker python -m src.workers.gmail_fetcher --days 1
   ```

3. **Check queue status**
   ```bash
   docker-compose exec worker celery -A src.workers.celery_app inspect active
   ```

## Troubleshooting

### OAuth Errors

**Problem:** `invalid_grant` error

**Solution:**
- Tokens may have expired
- Re-authorize: visit `http://localhost:8000/auth/login`

**Problem:** `redirect_uri_mismatch`

**Solution:**
- Ensure `.env` `GMAIL_REDIRECT_URI` matches Google Cloud Console settings
- Must be exactly: `http://localhost:8000/auth/callback`

### Gmail API Errors

**Problem:** `Quota exceeded` (HTTP 429)

**Solution:**
- Gmail API has quotas: 1 billion quota units/day
- Each API call costs ~5-10 units
- For large fetches, implement rate limiting or backoff

**Problem:** `Invalid credentials` (HTTP 401)

**Solution:**
- Refresh OAuth token: `python -m src.auth.refresh_token`
- Re-authenticate if refresh fails

### Database Connection Errors

**Problem:** `connection refused` to PostgreSQL

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Restart PostgreSQL
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### Redis Connection Errors

**Problem:** `Error connecting to Redis`

**Solution:**
```bash
# Check if Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
# Should return: PONG

# Restart Redis
docker-compose restart redis
```

### Worker Not Processing Jobs

**Problem:** Jobs stuck in queue

**Solution:**
```bash
# Check worker status
docker-compose logs worker

# Restart worker
docker-compose restart worker

# Check Celery inspect
docker-compose exec worker celery -A src.workers.celery_app inspect active
docker-compose exec worker celery -A src.workers.celery_app inspect stats
```

## Upgrading

### Update Dependencies

```bash
# Pull latest code
git pull origin main

# Rebuild containers
docker-compose build

# Restart services
docker-compose down
docker-compose up -d

# Run migrations (if any)
docker-compose exec api python -m src.db.migrate
```

## Backup and Restore

### Backup Database

```bash
# Backup
docker-compose exec postgres pg_dump -U postgres gmail_processor > backup.sql

# Restore
docker-compose exec -T postgres psql -U postgres gmail_processor < backup.sql
```

### Export OAuth Tokens

```bash
# Export encrypted tokens (for migration)
docker-compose exec api python -m src.auth.export_tokens > tokens_backup.json
```

## Production Deployment

For production deployment considerations:

- Use managed PostgreSQL (AWS RDS, Google Cloud SQL)
- Use managed Redis (AWS ElastiCache, Google Memorystore)
- Enable SSL/TLS for all connections
- Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- Set up monitoring and alerts (Prometheus, Grafana, Sentry)
- Implement log aggregation (ELK stack, Datadog)
- Use HTTPS for OAuth redirects
- Configure proper firewall rules
- Regular database backups
- Set up CI/CD pipeline

## Support

For issues or questions:
- Check existing [GitHub Issues](https://github.com/your-repo/issues)
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Review [GMAIL_AUTH.md](GMAIL_AUTH.md) for OAuth setup
