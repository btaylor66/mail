# Commitment Tracking System

The commitment system provides a higher-level abstraction for tracking events, meetings, projects, and deadlines that span multiple emails and calendar events. It supports **progressive information refinement** where details become more specific over time.

## Overview

A **Commitment** is a single entity that can be linked to:
- Multiple emails (many-to-many)
- Multiple calendar events (many-to-many)
- Progressive date refinements (vague → specific)

### Key Features

✅ **UUID-based** - Every commitment has a unique identifier
✅ **AI + Manual linking** - AI auto-links with confidence scores, humans can override
✅ **Progressive dates** - Start with "December" and refine to "Dec 15 at 2pm EST"
✅ **Date history** - Track how date information evolved over time
✅ **Multi-source** - Link emails, calendar events, and more to one commitment
✅ **Flexible metadata** - JSONB fields for extensibility

## Use Case: Progressive Date Refinement

### Scenario
You receive three emails about a conference:

1. **Week 1**: "Annual Conference happening in December"
2. **Week 3**: "Conference is December 15-17 weekend"
3. **Week 5**: "Conference starts December 15 at 2pm EST"

### How It Works

#### Email 1: Create commitment with vague date

```python
from src.models.commitments import create_commitment, link_email_to_commitment
from datetime import datetime

# Create commitment with month-level certainty
commitment = create_commitment(
    session,
    title="Annual Conference",
    commitment_type="event",
    start_date=datetime(2025, 12, 1, 0, 0, 0),
    end_date=datetime(2025, 12, 31, 23, 59, 59),
    date_certainty="month",
    metadata={
        "date_history": [
            {
                "date": "December 2025",
                "source": "email-abc123",
                "updated_at": "2025-12-01T10:00:00Z"
            }
        ]
    }
)

# Link email to commitment
link_email_to_commitment(
    session,
    commitment_id=commitment.id,
    message_id="email-abc123",
    linked_by="ai",
    confidence_score=0.85,
    link_reason="First mention of annual conference"
)
```

#### Email 2: Refine to specific days

```python
from src.models.commitments import update_commitment_date

# AI recognizes same event, links second email
link_email_to_commitment(
    session,
    commitment_id=commitment.id,
    message_id="email-def456",
    linked_by="ai",
    confidence_score=0.92,
    link_reason="Same subject: 'Annual Conference', same organizer"
)

# Update date with more precision
update_commitment_date(
    session,
    commitment_id=commitment.id,
    start_date=datetime(2025, 12, 15, 0, 0, 0),
    end_date=datetime(2025, 12, 17, 23, 59, 59),
    date_certainty="day",
    source="email-def456"
)
```

#### Email 3: Refine to exact time

```python
# Link third email
link_email_to_commitment(
    session,
    commitment_id=commitment.id,
    message_id="email-ghi789",
    linked_by="ai",
    confidence_score=0.95,
    link_reason="Same subject + attendees, exact time provided"
)

# Update to exact time
update_commitment_date(
    session,
    commitment_id=commitment.id,
    start_date=datetime(2025, 12, 15, 14, 0, 0, tzinfo=timezone('America/New_York')),
    end_date=datetime(2025, 12, 15, 17, 0, 0, tzinfo=timezone('America/New_York')),
    date_certainty="exact",
    source="email-ghi789"
)

# Update timezone
commitment.timezone = "America/New_York"
session.commit()
```

#### Final Result

```python
print(commitment.to_dict())
```

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Annual Conference",
  "commitment_type": "event",
  "status": "active",
  "start_date": "2025-12-15T14:00:00-05:00",
  "end_date": "2025-12-15T17:00:00-05:00",
  "timezone": "America/New_York",
  "date_certainty": "exact",
  "metadata": {
    "date_history": [
      {
        "date": "December 2025",
        "source": "email-abc123",
        "updated_at": "2025-12-01T10:00:00Z"
      },
      {
        "date": "2025-12-15T00:00:00 to 2025-12-17T23:59:59",
        "source": "email-def456",
        "updated_at": "2025-12-08T14:00:00Z"
      },
      {
        "date": "2025-12-15T14:00:00-05:00 to 2025-12-15T17:00:00-05:00",
        "source": "email-ghi789",
        "updated_at": "2025-12-15T09:00:00Z"
      }
    ]
  },
  "email_count": 3,
  "calendar_event_count": 0
}
```

## Database Schema

### Tables

1. **`commitments`** - Core commitment data
2. **`commitment_emails`** - Links commitments ↔ emails (many-to-many)
3. **`commitment_calendar_events`** - Links commitments ↔ calendar events (many-to-many)

### Commitment Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier |
| `title` | VARCHAR(500) | Commitment title |
| `description` | TEXT | Detailed description |
| `commitment_type` | VARCHAR(100) | Type: 'meeting', 'event', 'project', 'trip', 'deadline' |
| `status` | VARCHAR(50) | Status: 'active', 'completed', 'cancelled' |
| `start_date` | TIMESTAMP | Start date/time (can be vague initially) |
| `end_date` | TIMESTAMP | End date/time |
| `timezone` | VARCHAR(100) | Timezone (e.g., 'America/New_York') |
| `date_certainty` | VARCHAR(50) | How specific is the date? See below |
| `participants` | JSONB | Array of participant objects |
| `organizer` | VARCHAR(500) | Organizer email/name |
| `location` | TEXT | Physical or virtual location |
| `meeting_links` | JSONB | Array of meeting URLs (Zoom, Teams, etc.) |
| `auto_linked` | BOOLEAN | Was this created by AI? |
| `confidence_score` | FLOAT | AI confidence (0.0 - 1.0) |
| `metadata` | JSONB | Flexible field for custom data |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

### Date Certainty Levels

| Level | Description | Example |
|-------|-------------|---------|
| `unknown` | No date information | "Event TBD" |
| `month` | Month known only | "December 2025" |
| `week` | Week known | "Week of Dec 15" |
| `day` | Day known, time unknown | "December 15-17" |
| `exact` | Day and time known | "Dec 15 at 2pm" |
| `time_confirmed` | Exact time with timezone | "Dec 15 at 2pm EST (confirmed)" |

## Common Operations

### Query all emails for a commitment

```python
commitment = session.query(Commitment).filter_by(id=commitment_id).first()

# Get all linked emails
for link in commitment.linked_emails:
    print(f"Email: {link.message_id}, Linked by: {link.linked_by}, Confidence: {link.confidence_score}")
```

### Find commitments in a date range

```python
from sqlalchemy import and_

# Find all meetings in December 2025
commitments = session.query(Commitment).filter(
    and_(
        Commitment.start_date >= datetime(2025, 12, 1),
        Commitment.start_date < datetime(2026, 1, 1),
        Commitment.commitment_type == 'meeting'
    )
).all()
```

### Find commitments by participant

```python
# Find all commitments with alice@company.com
commitments = session.query(Commitment).filter(
    Commitment.participants.op('@>')('[{"email": "alice@company.com"}]')
).all()
```

### Manual linking (override AI)

```python
# User manually links an email AI missed
link_email_to_commitment(
    session,
    commitment_id=commitment.id,
    message_id="email-xyz999",
    linked_by="manual",  # Human intervention
    confidence_score=1.0,
    link_reason="User manually linked related follow-up email"
)
```

### View date evolution

```python
commitment = session.query(Commitment).filter_by(id=commitment_id).first()

print("Date History:")
for entry in commitment.metadata.get('date_history', []):
    print(f"  {entry['updated_at']}: {entry['date']} (from {entry['source']})")
```

Output:
```
Date History:
  2025-12-01T10:00:00Z: December 2025 (from email-abc123)
  2025-12-08T14:00:00Z: 2025-12-15T00:00:00 to 2025-12-17T23:59:59 (from email-def456)
  2025-12-15T09:00:00Z: 2025-12-15T14:00:00-05:00 to 2025-12-15T17:00:00-05:00 (from email-ghi789)
```

## AI Linking Strategy

When processing emails, the AI should:

1. **Check for existing commitments** with similar:
   - Subject/title (fuzzy match)
   - Date range overlap
   - Participant overlap
   - Thread ID (if same conversation)

2. **Create new commitment if**:
   - No similar commitment found
   - Confidence score < 0.70

3. **Link to existing commitment if**:
   - Confidence score ≥ 0.70
   - Update dates if more specific information provided
   - Add to date_history

4. **Calculate confidence score based on**:
   - Subject similarity (0.0 - 0.4)
   - Date overlap (0.0 - 0.3)
   - Participant match (0.0 - 0.3)

   Total: 0.0 - 1.0

## Example: Complete Workflow

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.commitments import Base, create_commitment, link_email_to_commitment
from datetime import datetime

# Setup database
engine = create_engine('postgresql://user:pass@localhost/gmail_processor')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Create commitment
commitment = create_commitment(
    session,
    title="Team Standup - Q4 Planning",
    commitment_type="meeting",
    description="Quarterly planning discussion with leadership",
    start_date=datetime(2025, 12, 20, 10, 0, 0),
    end_date=datetime(2025, 12, 20, 11, 0, 0),
    date_certainty="exact",
    timezone="America/New_York",
    participants=[
        {"email": "alice@company.com", "name": "Alice", "role": "attendee"},
        {"email": "bob@company.com", "name": "Bob", "role": "organizer"}
    ],
    organizer="bob@company.com",
    location="Conference Room B",
    meeting_links=["https://zoom.us/j/123456789"],
    auto_linked=True,
    confidence_score=0.95,
    metadata={
        "project": "Q4 Planning",
        "department": "Engineering"
    }
)

# Link emails
link_email_to_commitment(session, commitment.id, "email-001", "ai", 0.95, "Calendar invite")
link_email_to_commitment(session, commitment.id, "email-002", "ai", 0.88, "Follow-up discussion")
link_email_to_commitment(session, commitment.id, "email-003", "manual", 1.0, "User added related context")

# View summary
print(commitment.to_dict())
```

## Migration

Run the migration to create tables:

```bash
# Using psql
psql -U postgres -d gmail_processor -f src/migrations/001_create_commitments.sql

# Or using Python migration tool (if using Alembic)
alembic upgrade head
```

## Next Steps

1. **Implement AI linking logic** in email processor worker
2. **Add API endpoints** for viewing/managing commitments
3. **Build UI** for manual review and correction
4. **Add search** by title, participants, date range
5. **Notifications** for upcoming commitments
