# Gmail Email Processor

A scalable email processing system that connects to Gmail accounts, retrieves emails from a configurable time period, and extracts structured information about meetings, key dates, and upcoming events.

## Features

- **OAuth 2.0 Authentication** - Secure connection to personal Gmail accounts
- **Queue-Based Architecture** - Redis-backed job queues for scalable processing
- **Configurable Date Range** - Fetch emails from the last N days (default: 30)
- **Event Extraction** - Automatically identifies meetings, key dates, and events
- **Full Traceability** - UUID-based tracking for all jobs and processed emails
- **Structured Storage** - JSON results stored in PostgreSQL with searchable metadata
- **Debug-Friendly Logging** - Correlation IDs for end-to-end debugging

## Quick Start

```bash
# Clone the repository
git clone <your-repo-url>
cd gmail

# Copy environment template
cp .env.example .env

# Edit .env with your Gmail OAuth credentials (see GMAIL_AUTH.md)

# Start services with Docker Compose
docker-compose up -d

# Run database migrations
docker-compose exec api python manage.py migrate

# Start the Gmail fetcher (one-time or scheduled)
docker-compose exec worker python -m src.workers.gmail_fetcher --days 30
```

## Architecture

The system consists of four main components:

1. **Gmail Fetcher Worker** - Searches Gmail for emails and enqueues them
2. **Email Processor Worker** - Processes individual emails and extracts events
3. **Redis Queue** - Message broker for job distribution
4. **PostgreSQL Database** - Stores processed results and metadata

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

## Documentation

- [SETUP.md](SETUP.md) - Detailed installation and configuration
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design and data flow
- [GMAIL_AUTH.md](GMAIL_AUTH.md) - Gmail OAuth 2.0 setup guide

## Project Structure

```
gmail/
├── src/
│   ├── workers/
│   │   ├── gmail_fetcher.py      # Fetches emails from Gmail API
│   │   └── email_processor.py    # Processes and extracts event data
│   ├── services/
│   │   ├── gmail_client.py       # Gmail API client wrapper
│   │   └── event_extractor.py    # Event extraction logic
│   ├── models/
│   │   └── database.py           # SQLAlchemy models
│   ├── auth/
│   │   └── oauth.py              # OAuth 2.0 flow handler
│   └── config.py                 # Configuration management
├── docker-compose.yml            # Service orchestration
├── Dockerfile                    # Application container
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment template
```

## Technology Stack

- **Python 3.11+** - Core language
- **Celery** - Distributed task queue
- **Redis** - Message broker and cache
- **PostgreSQL** - Relational database
- **SQLAlchemy** - ORM
- **Google Gmail API** - Email access
- **Docker & Docker Compose** - Containerization

## Environment Variables

Key configuration options (see `.env.example` for full list):

- `GMAIL_CLIENT_ID` - Google OAuth client ID
- `GMAIL_CLIENT_SECRET` - Google OAuth client secret
- `GMAIL_REDIRECT_URI` - OAuth redirect URI
- `DEFAULT_DAYS_LOOKBACK` - Default number of days to fetch (default: 30)
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string

## Development

```bash
# Install dependencies locally
pip install -r requirements.txt

# Run tests
pytest

# Run linter
flake8 src/

# Format code
black src/
```

## License

MIT
