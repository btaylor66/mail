# Design Decisions

This document explains the key architectural and technology choices for the Gmail Email Processor, and the reasoning behind them.

## Technology Choices

### Python 3.11+

**Decision:** Use Python as the primary language

**Rationale:**
- **Gmail API Support:** Excellent official Google API client library
- **NLP Libraries:** Best-in-class libraries (spaCy, NLTK) for event extraction
- **Async Support:** Native async/await for concurrent processing
- **Ecosystem:** Rich ecosystem for email processing, date parsing, and data extraction
- **Rapid Development:** Fast prototyping and iteration

**Alternatives Considered:**
- **Node.js:** Good Gmail API support, but weaker NLP ecosystem
- **Go:** Excellent performance, but limited NLP libraries
- **Java:** Robust, but heavier weight and slower development

### OAuth 2.0 (Not Service Accounts)

**Decision:** Use OAuth 2.0 for personal Gmail access

**Rationale:**
- **Personal Gmail Requirement:** Service accounts only work with Google Workspace domain-wide delegation
- **User Consent:** Users explicitly authorize access to their email
- **Security:** Limited scope permissions (read-only)
- **Standard Practice:** Industry standard for third-party app access

**When to Use Service Accounts:**
- Google Workspace organizations only
- Requires domain admin privileges
- Not applicable for personal Gmail accounts

**Reference:** See [GMAIL_AUTH.md](GMAIL_AUTH.md) for detailed comparison

### Celery + Redis for Task Queuing

**Decision:** Use Celery with Redis as the message broker

**Rationale:**
- **Proven Technology:** Battle-tested in production at scale
- **Python Native:** First-class Python support with excellent documentation
- **Rich Features:** Retry logic, scheduling, monitoring, prioritization
- **Horizontal Scaling:** Easy to add more workers
- **Monitoring:** Flower dashboard for real-time visibility
- **Async Task Support:** Native async/await support

**Alternatives Considered:**
- **RabbitMQ:** More complex setup, overkill for single-user case
- **AWS SQS:** Cloud-specific, vendor lock-in, not cloud-agnostic requirement
- **Google Pub/Sub:** Same vendor lock-in concerns
- **RQ (Redis Queue):** Simpler but less feature-rich than Celery

**Trade-offs:**
- Celery can be complex to configure initially
- Redis requires memory for queue persistence
- Benefits outweigh complexity for this use case

### PostgreSQL for Data Storage

**Decision:** Use PostgreSQL for relational data storage

**Rationale:**
- **JSONB Support:** Native JSON storage with indexing for `extracted_data` field
- **Relational Integrity:** Foreign keys for `fetch_job_id` → `message_id` relationships
- **Query Performance:** Excellent indexing for correlation ID lookups
- **Robust:** ACID compliance for data integrity
- **Full-Text Search:** Built-in text search capabilities
- **Mature Ecosystem:** Well-supported, excellent ORMs (SQLAlchemy)

**Alternatives Considered:**
- **MongoDB:** Good for JSON storage, but lose relational integrity
- **DynamoDB:** NoSQL, harder to query by correlation IDs
- **MySQL:** Less robust JSON support than PostgreSQL

**Schema Design:**
- Normalized tables with foreign keys for traceability
- JSONB for flexible event data structure
- Indexes on correlation IDs for fast log lookups

### Docker + Docker Compose

**Decision:** Use Docker for containerization and Docker Compose for orchestration

**Rationale:**
- **Cloud-Agnostic:** Runs anywhere (local, AWS, GCP, Azure)
- **Consistent Environments:** Dev/staging/prod parity
- **Easy Setup:** Single `docker-compose up` command
- **Isolation:** Each service in its own container
- **Portable:** Easy to share and deploy

**Deployment Path:**
- Local development: Docker Compose
- Production: Kubernetes, ECS, or Cloud Run (future)

### UUID for Correlation IDs

**Decision:** Use UUIDs (v4) for all correlation IDs

**Rationale:**
- **Uniqueness:** Globally unique without coordination
- **Distributed-Safe:** No ID collisions across multiple workers
- **Debugging-Friendly:** Copy-paste IDs from logs to database queries
- **No Sequential Info Leak:** Random IDs don't expose processing order or volume

**ID Hierarchy:**
```
fetch_job_id (UUID)
  └─> message_id (Gmail message ID)
       └─> processing_job_id (UUID)
            └─> result_id (UUID)
```

**Alternative Considered:**
- **Auto-incrementing IDs:** Simpler but less suitable for distributed systems
- **Snowflake IDs:** More complex, unnecessary for this scale

## Architectural Decisions

### Queue-Based Processing

**Decision:** Two-stage queue processing (fetch → process)

**Rationale:**
- **Scalability:** Independent scaling of fetch and process workers
- **Fault Tolerance:** Failed processing doesn't affect fetching
- **Rate Limiting:** Control Gmail API call rate at fetch stage
- **Flexibility:** Easy to add more processing stages (e.g., ML enrichment)

**Flow:**
```
Gmail API → Fetch Worker → Redis Queue → Process Workers → PostgreSQL
```

**Benefits:**
- Decouple Gmail API calls from processing logic
- Retry individual email processing without re-fetching
- Backpressure handling via queue depth

### Two Queue Design

**Decision:** Separate queues for fetching and processing

**Rationale:**
- **Fetch Queue:** High priority, fewer tasks, Gmail API rate limiting
- **Process Queue:** Lower priority, many tasks, CPU-intensive

**Configuration:**
```python
CELERY_ROUTES = {
    'fetch_gmail_emails': {'queue': 'gmail_fetch_queue', 'priority': 10},
    'process_email': {'queue': 'email_processing_queue', 'priority': 5}
}
```

**Alternative Considered:**
- **Single Queue:** Simpler but less control over priorities and scaling

### Event Extraction Strategy

**Decision:** Rule-based + NLP hybrid approach

**Rationale:**
- **Structured Data:** Parse .ics attachments for calendar invites (rule-based)
- **Unstructured Text:** Use spaCy NLP for text extraction (ML-based)
- **Date Parsing:** dateparser library for flexible date recognition
- **Accuracy:** Combine precision of rules with flexibility of NLP

**Extraction Layers:**
1. **ICS Attachments:** Parse calendar invite files (highest confidence)
2. **Email Headers:** Extract meeting invites from headers
3. **HTML/Text Body:** NLP extraction for meeting mentions
4. **Link Detection:** Zoom/Teams/Meet links (meeting indicators)

**Confidence Scoring:**
- ICS attachment: 0.95+
- Structured headers: 0.85+
- NLP extraction: 0.60-0.80
- Threshold: 0.70 minimum to store

### Encryption for OAuth Tokens

**Decision:** Encrypt OAuth tokens at rest using Fernet (symmetric encryption)

**Rationale:**
- **Security:** Protect refresh tokens in database
- **Compliance:** Best practice for sensitive credentials
- **Simple:** Symmetric encryption is simpler than asymmetric for this use case
- **Performance:** Fast encryption/decryption

**Implementation:**
```python
from cryptography.fernet import Fernet

key = os.getenv('TOKEN_ENCRYPTION_KEY')
cipher = Fernet(key)
encrypted = cipher.encrypt(token.encode())
```

**Alternatives Considered:**
- **No Encryption:** Unacceptable security risk
- **Asymmetric Encryption (RSA):** Overkill, slower, more complex

### Structured Logging with Correlation IDs

**Decision:** Log all events with correlation IDs in structured JSON format

**Rationale:**
- **Traceability:** Follow email processing end-to-end
- **Debugging:** Query logs by correlation ID
- **Aggregation:** Easy to parse and aggregate in log management tools
- **Filtering:** Filter logs by job, email, or result

**Log Format:**
```json
{
  "timestamp": "2025-12-17T10:30:00Z",
  "level": "INFO",
  "correlation_id": "fetch-job-uuid-123",
  "message": "Found 150 emails",
  "metadata": {"days_lookback": 30, "user_id": "user@gmail.com"}
}
```

**Benefits:**
- Searchable in Elasticsearch, Datadog, etc.
- Human-readable and machine-parseable
- Consistent format across all services

### Database Schema Design

**Decision:** Normalized relational schema with JSONB for flexibility

**Rationale:**
- **Fixed Metadata:** `fetch_jobs`, `email_metadata` are structured tables
- **Flexible Results:** `extracted_data` JSONB column for varying event schemas
- **Query Performance:** Indexes on foreign keys and correlation IDs
- **Data Integrity:** Foreign key constraints ensure referential integrity

**Schema Pattern:**
```
fetch_jobs (structured) ─1:N─> email_metadata (structured)
                                      │
                                      └─1:N─> processed_results (JSONB)
```

**GIN Index on JSONB:**
```sql
CREATE INDEX idx_extracted_data_gin ON processed_results USING gin(extracted_data);
```

Enables fast queries like:
```sql
SELECT * FROM processed_results
WHERE extracted_data @> '{"result_type": "meeting"}';
```

## Scalability Considerations

### Current Design (Single User)

**Capacity:**
- 1 Fetch Worker: ~10,000 emails/hour
- 4 Process Workers: ~2,000 emails/hour (bottleneck)
- PostgreSQL: Handles millions of records
- Redis: Handles 100,000+ queue items

**Bottleneck:** Email processing (NLP is CPU-intensive)

### Future Scaling (Multi-User)

**Horizontal Scaling:**
- Add more Celery workers (process queue)
- Partition queues by user: `user_123_queue`
- Database sharding by `user_id`

**Vertical Scaling:**
- Larger worker instances (more CPU for NLP)
- Increase database connection pool

**Cloud Deployment:**
- Use managed services (RDS, ElastiCache, Cloud Run)
- Auto-scaling worker pools
- Load balancing for API

## Security Decisions

### Read-Only Gmail Scope

**Decision:** Use `gmail.readonly` scope only

**Rationale:**
- **Principle of Least Privilege:** Only request needed permissions
- **User Trust:** Reassures users app won't send/delete emails
- **Reduced Risk:** Compromised tokens can't modify user data

### API Key Not Required (Initially)

**Decision:** No API key authentication for single-user deployment

**Rationale:**
- **Simplicity:** Lower barrier to setup
- **Local Deployment:** Running on localhost doesn't need API auth
- **Future:** Easy to add API keys when multi-user support is added

### No Rate Limiting (Initially)

**Decision:** No application-level rate limiting for single user

**Rationale:**
- **Gmail API Limits:** Gmail API has built-in quotas (250,000/day)
- **Single User:** One user unlikely to hit limits
- **Exponential Backoff:** Handle 429 errors with retry logic

**Future:** Add rate limiting for multi-tenant deployments

## Testing Strategy

**Decision:** Unit tests + Integration tests + Manual testing

**Test Coverage:**
- **Unit Tests:** Gmail client, event extraction, database models
- **Integration Tests:** End-to-end fetch → process → store
- **Fixtures:** Mock Gmail API responses, sample email data
- **CI/CD:** GitHub Actions for automated testing

**Manual Testing:**
- Real Gmail account with test emails
- Variety of email formats (calendar invites, plain text, HTML)
- Different event types (meetings, deadlines, conferences)

## Future Enhancements

### Machine Learning

- Train custom NER model for event extraction
- Improve confidence scores
- Multi-language support

### Multi-User Support

- User management and authentication
- Per-user job tracking
- Rate limiting per user
- User dashboard

### Advanced Features

- Email categorization (work, personal, promotions)
- Smart summaries (daily digest)
- Calendar integration (auto-add events)
- Notification system (upcoming events)

### Monitoring

- Prometheus metrics
- Grafana dashboards
- Alerting (queue depth, worker health, errors)
- Sentry for error tracking

## Lessons Learned

### OAuth Complexity

**Learning:** OAuth setup is the hardest part for users

**Solution:** Detailed [GMAIL_AUTH.md](GMAIL_AUTH.md) with screenshots and troubleshooting

### Queue Depth Monitoring

**Learning:** Important to monitor queue depth to detect bottlenecks

**Solution:** Flower dashboard + Celery inspect commands

### Email Format Variability

**Learning:** Emails vary wildly in format (plain text, HTML, multipart)

**Solution:** Robust parsing with BeautifulSoup, fallback strategies

### Date Parsing Challenges

**Learning:** Date formats are inconsistent ("Dec 20", "12/20/2025", "next Friday")

**Solution:** Use dateparser library with timezone awareness

## References

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Celery Documentation](https://docs.celeryproject.org/)
- [PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)
- [OAuth 2.0 RFC](https://datatracker.ietf.org/doc/html/rfc6749)
- [spaCy NLP](https://spacy.io/)
