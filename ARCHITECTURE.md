# System Architecture

## Overview

The Gmail Email Processor is a queue-based system designed for scalable email retrieval and event extraction. It uses a multi-stage pipeline with full traceability via UUID-based correlation IDs.

## Architecture Diagram

```
┌─────────────────┐
│   User Gmail    │
│    Account      │
└────────┬────────┘
         │ OAuth 2.0
         │
┌────────▼────────────────────────────────────────────────────┐
│                   Gmail Fetcher Worker                      │
│  - Authenticates via OAuth 2.0                              │
│  - Searches for emails (last N days)                        │
│  - Creates fetch_job_id (UUID)                              │
│  - Enqueues email metadata to Redis                         │
└────────┬────────────────────────────────────────────────────┘
         │
         │ Enqueue: {email_id, fetch_job_id, message_id}
         │
┌────────▼────────────────────────────────────────────────────┐
│                     Redis Queue                             │
│  Queue: "email_processing_queue"                            │
│  - Persistent job storage                                   │
│  - At-least-once delivery                                   │
└────────┬────────────────────────────────────────────────────┘
         │
         │ Dequeue job
         │
┌────────▼────────────────────────────────────────────────────┐
│                 Email Processor Worker                      │
│  - Receives email metadata from queue                       │
│  - Creates processing_job_id (UUID)                         │
│  - Downloads full email content via Gmail API               │
│  - Extracts events, meetings, dates                         │
│  - Creates result_id (UUID) for each finding                │
│  - Stores JSON results in PostgreSQL                        │
└────────┬────────────────────────────────────────────────────┘
         │
         │ Store results
         │
┌────────▼────────────────────────────────────────────────────┐
│                  PostgreSQL Database                        │
│  Tables:                                                    │
│  - fetch_jobs: Fetch job metadata and status                │
│  - email_metadata: Email headers and correlation IDs        │
│  - processed_results: Extracted events as JSON              │
│  - processing_logs: Timestamped logs with correlation IDs   │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Gmail Fetching Stage

**Input:** User trigger (manual, scheduled, or API call)

**Process:**
1. Gmail Fetcher Worker starts with `fetch_job_id = uuid4()`
2. Authenticates to Gmail API using stored OAuth tokens
3. Searches for emails with query: `after:YYYY/MM/DD` (N days ago)
4. For each email found:
   - Extract metadata: `message_id`, `subject`, `from`, `date`, `thread_id`
   - Create job payload: `{email_id, fetch_job_id, message_id, subject, from, date}`
   - Push to Redis queue: `email_processing_queue`
5. Log fetch summary with `fetch_job_id` for traceability

**Output:** Jobs enqueued to `email_processing_queue`

**Database Records:**
```sql
INSERT INTO fetch_jobs (id, user_id, days_lookback, status, started_at, emails_found)
VALUES (fetch_job_id, user_id, 30, 'completed', NOW(), 150);
```

### 2. Email Processing Stage

**Input:** Job from `email_processing_queue`

**Process:**
1. Email Processor Worker dequeues job
2. Creates `processing_job_id = uuid4()`
3. Downloads full email content via Gmail API (MIME message)
4. Parses email:
   - Plain text and HTML bodies
   - Attachments (ICS files for calendar invites)
   - Headers
5. Extracts structured information:
   - **Meetings:** Calendar invites, Zoom links, meeting times
   - **Key Dates:** Deadlines, expiration dates, important dates
   - **Events:** Conferences, webinars, appointments
6. For each finding:
   - Create `result_id = uuid4()`
   - Store as JSON in `processed_results` table
7. Log processing with all correlation IDs

**Output:** Structured events stored in database

**Database Records:**
```sql
INSERT INTO email_metadata (message_id, fetch_job_id, subject, from_address, received_at)
VALUES (message_id, fetch_job_id, 'Team Standup', 'boss@company.com', '2025-12-15 09:00:00');

INSERT INTO processed_results (id, message_id, processing_job_id, result_type, extracted_data, created_at)
VALUES (
  result_id,
  message_id,
  processing_job_id,
  'meeting',
  '{"title": "Team Standup", "date": "2025-12-20", "time": "10:00 AM", "location": "Zoom", "attendees": [...]}',
  NOW()
);
```

## Database Schema

### `fetch_jobs` Table
Tracks each Gmail fetch operation.

```sql
CREATE TABLE fetch_jobs (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    days_lookback INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,  -- 'running', 'completed', 'failed'
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    emails_found INTEGER DEFAULT 0,
    error_message TEXT
);
```

### `email_metadata` Table
Stores email headers and correlation IDs.

```sql
CREATE TABLE email_metadata (
    message_id VARCHAR(255) PRIMARY KEY,
    fetch_job_id UUID REFERENCES fetch_jobs(id),
    thread_id VARCHAR(255),
    subject TEXT,
    from_address VARCHAR(500),
    to_addresses TEXT,
    received_at TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fetch_job ON email_metadata(fetch_job_id);
CREATE INDEX idx_received_at ON email_metadata(received_at);
```

### `processed_results` Table
Stores extracted events as JSON.

```sql
CREATE TABLE processed_results (
    id UUID PRIMARY KEY,
    message_id VARCHAR(255) REFERENCES email_metadata(message_id),
    processing_job_id UUID NOT NULL,
    result_type VARCHAR(100) NOT NULL,  -- 'meeting', 'key_date', 'event'
    extracted_data JSONB NOT NULL,
    confidence_score FLOAT,  -- Optional: ML confidence score
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_message_id ON processed_results(message_id);
CREATE INDEX idx_processing_job ON processed_results(processing_job_id);
CREATE INDEX idx_result_type ON processed_results(result_type);
CREATE INDEX idx_extracted_data_gin ON processed_results USING gin(extracted_data);
```

### `processing_logs` Table
Centralized logging with correlation IDs.

```sql
CREATE TABLE processing_logs (
    id BIGSERIAL PRIMARY KEY,
    correlation_id UUID NOT NULL,  -- fetch_job_id OR processing_job_id
    log_level VARCHAR(20) NOT NULL,  -- 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    message TEXT NOT NULL,
    metadata JSONB,  -- Additional context
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_correlation_id ON processing_logs(correlation_id);
CREATE INDEX idx_created_at ON processing_logs(created_at);
```

## Traceability & Debugging

### Correlation ID Hierarchy

1. **`fetch_job_id`** - Traces an entire Gmail fetch operation
   - Created when Gmail Fetcher Worker starts
   - Associated with all emails found in that fetch
   - Logged in: `fetch_jobs` table, `email_metadata` table, `processing_logs`

2. **`processing_job_id`** - Traces processing of a single email
   - Created when Email Processor Worker picks up a job
   - Associated with all extracted results from that email
   - Logged in: `processed_results` table, `processing_logs`

3. **`result_id`** - Unique ID for each extracted event/meeting/date
   - Created for each finding in an email
   - Primary key in `processed_results` table

### Example Debugging Flow

**Scenario:** User reports a missing meeting from an email.

**Debug Steps:**

1. **Find the email:**
   ```sql
   SELECT message_id, fetch_job_id
   FROM email_metadata
   WHERE subject LIKE '%Team Meeting%';
   ```
   Result: `message_id = abc123`, `fetch_job_id = uuid-111`

2. **Check fetch job status:**
   ```sql
   SELECT * FROM fetch_jobs WHERE id = 'uuid-111';
   ```
   Verify the fetch completed successfully.

3. **Check processing logs:**
   ```sql
   SELECT * FROM processing_logs
   WHERE correlation_id IN (
     SELECT processing_job_id
     FROM processed_results
     WHERE message_id = 'abc123'
   )
   ORDER BY created_at;
   ```
   Review logs to see parsing errors or extraction issues.

4. **Check extracted results:**
   ```sql
   SELECT * FROM processed_results WHERE message_id = 'abc123';
   ```
   See what was actually extracted.

## Queue Configuration

### Celery Task Definitions

**Task 1: `fetch_gmail_emails`**
- Priority: High
- Retry: 3 attempts with exponential backoff
- Timeout: 5 minutes
- Queue: `gmail_fetch_queue`

**Task 2: `process_email`**
- Priority: Normal
- Retry: 5 attempts with exponential backoff
- Timeout: 2 minutes per email
- Queue: `email_processing_queue`

### Queue Monitoring

- Use Celery Flower for real-time monitoring: `http://localhost:5555`
- Monitor queue depth, worker health, and failed tasks
- Set alerts for queue depth > 1000 or worker failures

## Error Handling

### Gmail API Errors
- **Rate Limits (429):** Exponential backoff with jitter
- **Auth Errors (401):** Trigger OAuth refresh token flow
- **Temporary Failures (5xx):** Retry up to 3 times

### Processing Errors
- **Malformed Email:** Log error, skip email, continue processing
- **Extraction Failure:** Store partial results, mark as low confidence
- **Database Errors:** Retry transaction, dead-letter queue if persistent

### Dead Letter Queue
Failed jobs after max retries go to `failed_jobs_queue` for manual inspection.

## Scalability Considerations

### Current Design (Single User)
- 1 Gmail Fetcher Worker (runs periodically)
- 2-4 Email Processor Workers (parallel processing)
- Single Redis instance
- Single PostgreSQL instance

### Future Scale (Multi-Tenant)
- **Horizontal Scaling:** Add more Email Processor Workers
- **User Isolation:** Separate queues per user or tenant
- **Database Sharding:** Partition by `user_id` for large datasets
- **Caching:** Use Redis for frequently accessed results
- **Rate Limiting:** Per-user Gmail API quotas

## Security

- **OAuth Tokens:** Encrypted at rest in database
- **API Keys:** Stored in environment variables, never in code
- **Database Access:** Use connection pooling, parameterized queries
- **Email Content:** Consider PII sensitivity, implement data retention policies

## Performance Metrics

- **Gmail Fetch Time:** Track time to fetch N emails
- **Processing Throughput:** Emails processed per minute
- **Extraction Accuracy:** Manual validation of sample results
- **Queue Depth:** Monitor for bottlenecks
- **Database Query Performance:** Index optimization

## Example JSON Result Schema

```json
{
  "result_id": "uuid-result-456",
  "result_type": "meeting",
  "title": "Q4 Planning Meeting",
  "date": "2025-12-20",
  "time": "14:00:00",
  "timezone": "America/New_York",
  "location": "Conference Room B / Zoom",
  "attendees": ["alice@company.com", "bob@company.com"],
  "organizer": "boss@company.com",
  "description": "Quarterly planning and budget review",
  "meeting_link": "https://zoom.us/j/123456789",
  "calendar_invite_attached": true,
  "extracted_from": {
    "email_subject": "Q4 Planning - Dec 20",
    "email_from": "boss@company.com",
    "extraction_method": "ics_attachment"
  },
  "confidence_score": 0.98
}
```
