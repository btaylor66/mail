"""
SQLAlchemy models for commitment tracking system.

Commitments link related emails and calendar events together,
supporting progressive information refinement over time.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import (
    Column, String, Text, Boolean, Float, TIMESTAMP,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class Commitment(Base):
    """
    Core commitment model representing events, meetings, projects, trips, etc.

    Supports progressive date refinement:
    - Email 1: "Event in December" → start_date = 2025-12-01, certainty = 'month'
    - Email 2: "December 15-17" → start_date = 2025-12-15, certainty = 'day'
    - Email 3: "Dec 15 at 2pm" → start_date = 2025-12-15 14:00, certainty = 'exact'
    """

    __tablename__ = 'commitments'

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Core metadata
    title = Column(String(500), nullable=False)
    description = Column(Text)
    commitment_type = Column(String(100))  # 'meeting', 'event', 'project', 'trip', 'deadline'
    status = Column(String(50), default='active')  # 'active', 'completed', 'cancelled'

    # Temporal data
    start_date = Column(TIMESTAMP(timezone=True))
    end_date = Column(TIMESTAMP(timezone=True))
    timezone = Column(String(100))
    date_certainty = Column(String(50), default='unknown')
    # Values: 'unknown', 'month', 'week', 'day', 'exact', 'time_confirmed'

    # Participants
    participants = Column(JSONB, default=list)  # [{"email": "...", "name": "...", "role": "..."}]
    organizer = Column(String(500))

    # Location/Links
    location = Column(Text)
    meeting_links = Column(JSONB, default=list)  # ["https://zoom.us/...", ...]

    # AI/Manual linking metadata
    auto_linked = Column(Boolean, default=False)
    confidence_score = Column(Float)  # 0.0 - 1.0

    # Extensible metadata
    metadata = Column(JSONB, default=dict)
    # Example: {"date_history": [...], "attachments": [...], "project": "Q4", ...}

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    linked_emails = relationship("CommitmentEmail", back_populates="commitment", cascade="all, delete-orphan")
    linked_calendar_events = relationship("CommitmentCalendarEvent", back_populates="commitment", cascade="all, delete-orphan")

    # Indexes defined in __table_args__
    __table_args__ = (
        Index('idx_commitments_dates', 'start_date', 'end_date'),
        Index('idx_commitments_type', 'commitment_type'),
        Index('idx_commitments_status', 'status'),
        Index('idx_commitments_certainty', 'date_certainty'),
        Index('idx_commitments_created_at', 'created_at'),
        Index('idx_commitments_metadata_gin', 'metadata', postgresql_using='gin'),
        Index('idx_commitments_participants_gin', 'participants', postgresql_using='gin'),
    )

    def __repr__(self):
        return f"<Commitment(id={self.id}, title='{self.title}', type={self.commitment_type})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert commitment to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "commitment_type": self.commitment_type,
            "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "timezone": self.timezone,
            "date_certainty": self.date_certainty,
            "participants": self.participants,
            "organizer": self.organizer,
            "location": self.location,
            "meeting_links": self.meeting_links,
            "auto_linked": self.auto_linked,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "email_count": len(self.linked_emails),
            "calendar_event_count": len(self.linked_calendar_events)
        }

    def add_date_history_entry(self, date_info: str, source: str):
        """
        Add an entry to the date_history in metadata.

        Args:
            date_info: Human-readable date info (e.g., "December 15-17", "Dec 15 at 2pm")
            source: Source identifier (e.g., "email-123", "calendar-event-456")
        """
        if self.metadata is None:
            self.metadata = {}

        if 'date_history' not in self.metadata:
            self.metadata['date_history'] = []

        self.metadata['date_history'].append({
            "date": date_info,
            "source": source,
            "updated_at": datetime.utcnow().isoformat()
        })


class CommitmentEmail(Base):
    """
    Many-to-many link between commitments and emails.
    Tracks which emails are related to which commitments.
    """

    __tablename__ = 'commitment_emails'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commitment_id = Column(UUID(as_uuid=True), ForeignKey('commitments.id', ondelete='CASCADE'), nullable=False)
    message_id = Column(String(255), nullable=False)  # References email_metadata.message_id

    # Link metadata
    linked_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    linked_by = Column(String(50), default='ai')  # 'ai' or 'manual'
    confidence_score = Column(Float)  # 0.0 - 1.0
    link_reason = Column(Text)  # Why was this linked?

    # Relationships
    commitment = relationship("Commitment", back_populates="linked_emails")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('commitment_id', 'message_id', name='uq_commitment_email'),
        Index('idx_commitment_emails_commitment', 'commitment_id'),
        Index('idx_commitment_emails_message', 'message_id'),
        Index('idx_commitment_emails_linked_at', 'linked_at'),
        Index('idx_commitment_emails_linked_by', 'linked_by'),
    )

    def __repr__(self):
        return f"<CommitmentEmail(commitment={self.commitment_id}, email={self.message_id}, by={self.linked_by})>"


class CommitmentCalendarEvent(Base):
    """
    Many-to-many link between commitments and calendar events.
    Tracks which calendar events are related to which commitments.
    """

    __tablename__ = 'commitment_calendar_events'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commitment_id = Column(UUID(as_uuid=True), ForeignKey('commitments.id', ondelete='CASCADE'), nullable=False)
    event_id = Column(String(255), nullable=False)  # Calendar event ID

    # Event data
    event_data = Column(JSONB)  # Full calendar event details

    # Link metadata
    linked_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    linked_by = Column(String(50), default='ai')  # 'ai' or 'manual'
    confidence_score = Column(Float)
    link_reason = Column(Text)

    # Relationships
    commitment = relationship("Commitment", back_populates="linked_calendar_events")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('commitment_id', 'event_id', name='uq_commitment_calendar_event'),
        Index('idx_commitment_calendar_commitment', 'commitment_id'),
        Index('idx_commitment_calendar_event', 'event_id'),
        Index('idx_commitment_calendar_linked_at', 'linked_at'),
    )

    def __repr__(self):
        return f"<CommitmentCalendarEvent(commitment={self.commitment_id}, event={self.event_id}, by={self.linked_by})>"


# ============================================================================
# Helper functions for working with commitments
# ============================================================================

def create_commitment(
    session,
    title: str,
    commitment_type: str = 'meeting',
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    date_certainty: str = 'unknown',
    **kwargs
) -> Commitment:
    """
    Create a new commitment.

    Args:
        session: SQLAlchemy session
        title: Commitment title
        commitment_type: Type of commitment ('meeting', 'event', 'project', etc.)
        start_date: Start date/time
        end_date: End date/time
        date_certainty: How certain is the date? ('unknown', 'month', 'week', 'day', 'exact', 'time_confirmed')
        **kwargs: Additional fields (description, location, participants, etc.)

    Returns:
        Commitment: Created commitment object
    """
    commitment = Commitment(
        title=title,
        commitment_type=commitment_type,
        start_date=start_date,
        end_date=end_date,
        date_certainty=date_certainty,
        **kwargs
    )
    session.add(commitment)
    session.commit()
    return commitment


def link_email_to_commitment(
    session,
    commitment_id: uuid.UUID,
    message_id: str,
    linked_by: str = 'ai',
    confidence_score: Optional[float] = None,
    link_reason: Optional[str] = None
) -> CommitmentEmail:
    """
    Link an email to a commitment.

    Args:
        session: SQLAlchemy session
        commitment_id: UUID of the commitment
        message_id: Gmail message ID
        linked_by: 'ai' or 'manual'
        confidence_score: Confidence score (0.0 - 1.0)
        link_reason: Explanation for the link

    Returns:
        CommitmentEmail: Created link object
    """
    link = CommitmentEmail(
        commitment_id=commitment_id,
        message_id=message_id,
        linked_by=linked_by,
        confidence_score=confidence_score,
        link_reason=link_reason
    )
    session.add(link)
    session.commit()
    return link


def update_commitment_date(
    session,
    commitment_id: uuid.UUID,
    start_date: datetime,
    end_date: Optional[datetime] = None,
    date_certainty: str = 'exact',
    source: str = 'update'
):
    """
    Update commitment date and add to date history.

    Args:
        session: SQLAlchemy session
        commitment_id: UUID of the commitment
        start_date: New start date
        end_date: New end date (optional)
        date_certainty: New certainty level
        source: Source of the update (e.g., 'email-123')
    """
    commitment = session.query(Commitment).filter_by(id=commitment_id).first()
    if not commitment:
        raise ValueError(f"Commitment {commitment_id} not found")

    # Add to history
    date_info = f"{start_date.isoformat()}"
    if end_date:
        date_info += f" to {end_date.isoformat()}"
    commitment.add_date_history_entry(date_info, source)

    # Update dates
    commitment.start_date = start_date
    if end_date:
        commitment.end_date = end_date
    commitment.date_certainty = date_certainty

    session.commit()
