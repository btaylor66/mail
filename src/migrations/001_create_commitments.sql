-- Migration: Create commitments tables
-- Description: Add commitment tracking system for linking emails and calendar events
-- Created: 2025-12-18

-- ============================================================================
-- COMMITMENTS TABLE
-- ============================================================================
-- Core table for tracking commitments (meetings, events, projects, trips, etc.)
-- Supports progressive information refinement as more details become available

CREATE TABLE commitments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core metadata
    title VARCHAR(500) NOT NULL,
    description TEXT,
    commitment_type VARCHAR(100),  -- 'meeting', 'event', 'project', 'trip', 'deadline', etc.
    status VARCHAR(50) DEFAULT 'active',  -- 'active', 'completed', 'cancelled'

    -- Temporal data (supports vague → specific refinement)
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    timezone VARCHAR(100),
    date_certainty VARCHAR(50) DEFAULT 'unknown',  -- 'unknown', 'month', 'week', 'day', 'exact', 'time_confirmed'

    -- Participants
    participants JSONB DEFAULT '[]',  -- [{email, name, role}]
    organizer VARCHAR(500),

    -- Location/Links
    location TEXT,
    meeting_links JSONB DEFAULT '[]',  -- [zoom, teams, meet urls]

    -- Linking metadata
    auto_linked BOOLEAN DEFAULT false,  -- true if AI linked, false if manual
    confidence_score FLOAT,  -- AI confidence in auto-linking (0.0 - 1.0)

    -- Rich data (extensible)
    metadata JSONB DEFAULT '{}',  -- Store date_history, attachments, custom fields, etc.

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- COMMITMENT_EMAILS TABLE
-- ============================================================================
-- Many-to-many relationship: commitments ↔ emails
-- Tracks which emails belong to which commitments

CREATE TABLE commitment_emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    commitment_id UUID NOT NULL REFERENCES commitments(id) ON DELETE CASCADE,
    message_id VARCHAR(255) NOT NULL REFERENCES email_metadata(message_id),

    -- Link metadata
    linked_at TIMESTAMP DEFAULT NOW(),
    linked_by VARCHAR(50) DEFAULT 'ai',  -- 'ai' or 'manual'
    confidence_score FLOAT,  -- How confident is the AI about this link? (0.0 - 1.0)
    link_reason TEXT,  -- Optional: Why was this linked? (e.g., "same subject + attendees")

    UNIQUE(commitment_id, message_id)
);

-- ============================================================================
-- COMMITMENT_CALENDAR_EVENTS TABLE
-- ============================================================================
-- Many-to-many relationship: commitments ↔ calendar events
-- Tracks which calendar events belong to which commitments

CREATE TABLE commitment_calendar_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    commitment_id UUID NOT NULL REFERENCES commitments(id) ON DELETE CASCADE,
    event_id VARCHAR(255) NOT NULL,  -- Calendar event ID (from .ics, Google Calendar, etc.)

    -- Event data
    event_data JSONB,  -- Store the full calendar event details

    -- Link metadata
    linked_at TIMESTAMP DEFAULT NOW(),
    linked_by VARCHAR(50) DEFAULT 'ai',  -- 'ai' or 'manual'
    confidence_score FLOAT,
    link_reason TEXT,

    UNIQUE(commitment_id, event_id)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Commitments indexes
CREATE INDEX idx_commitments_dates ON commitments(start_date, end_date);
CREATE INDEX idx_commitments_type ON commitments(commitment_type);
CREATE INDEX idx_commitments_status ON commitments(status);
CREATE INDEX idx_commitments_certainty ON commitments(date_certainty);
CREATE INDEX idx_commitments_created_at ON commitments(created_at);
CREATE INDEX idx_commitments_metadata_gin ON commitments USING gin(metadata);
CREATE INDEX idx_commitments_participants_gin ON commitments USING gin(participants);

-- Commitment-Email link indexes
CREATE INDEX idx_commitment_emails_commitment ON commitment_emails(commitment_id);
CREATE INDEX idx_commitment_emails_message ON commitment_emails(message_id);
CREATE INDEX idx_commitment_emails_linked_at ON commitment_emails(linked_at);
CREATE INDEX idx_commitment_emails_linked_by ON commitment_emails(linked_by);

-- Commitment-Calendar link indexes
CREATE INDEX idx_commitment_calendar_commitment ON commitment_calendar_events(commitment_id);
CREATE INDEX idx_commitment_calendar_event ON commitment_calendar_events(event_id);
CREATE INDEX idx_commitment_calendar_linked_at ON commitment_calendar_events(linked_at);

-- ============================================================================
-- HELPER FUNCTION: Update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_commitments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_commitments_updated_at
    BEFORE UPDATE ON commitments
    FOR EACH ROW
    EXECUTE FUNCTION update_commitments_updated_at();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE commitments IS 'Core table for tracking commitments across multiple emails and calendar events';
COMMENT ON COLUMN commitments.date_certainty IS 'Tracks how specific the date information is: unknown → month → week → day → exact → time_confirmed';
COMMENT ON COLUMN commitments.metadata IS 'Flexible JSONB field for date_history, attachments, custom fields, etc.';
COMMENT ON TABLE commitment_emails IS 'Links emails to commitments (many-to-many)';
COMMENT ON TABLE commitment_calendar_events IS 'Links calendar events to commitments (many-to-many)';
