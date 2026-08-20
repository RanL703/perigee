-- Perigee's initial schema. This is run once by the Postgres image when the
-- named data volume is first created. Later schema changes belong in Alembic
-- migrations once the FastAPI service is added.

CREATE TYPE object_type AS ENUM ('payload', 'debris', 'rocket_body');
CREATE TYPE risk_tier AS ENUM ('critical', 'elevated', 'low');

CREATE TABLE objects (
    norad_id INTEGER PRIMARY KEY CHECK (norad_id > 0),
    name TEXT NOT NULL,
    object_type object_type NOT NULL,
    tle_line1 CHAR(69) NOT NULL,
    tle_line2 CHAR(69) NOT NULL,
    epoch TIMESTAMPTZ NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT objects_tle_lines_distinct CHECK (tle_line1 <> tle_line2)
);

CREATE TABLE conjunction_events (
    id UUID PRIMARY KEY,
    pair_key TEXT NOT NULL UNIQUE,
    object_a_id INTEGER NOT NULL REFERENCES objects(norad_id) ON DELETE RESTRICT,
    object_b_id INTEGER NOT NULL REFERENCES objects(norad_id) ON DELETE RESTRICT,
    tca TIMESTAMPTZ NOT NULL,
    miss_distance_km DOUBLE PRECISION NOT NULL CHECK (miss_distance_km >= 0),
    relative_velocity_kmps DOUBLE PRECISION NOT NULL CHECK (relative_velocity_kmps >= 0),
    risk_score DOUBLE PRECISION NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_tier risk_tier NOT NULL,
    factor_breakdown JSONB NOT NULL,
    screened_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT conjunction_events_distinct_objects CHECK (object_a_id < object_b_id)
);

CREATE TABLE event_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES conjunction_events(id) ON DELETE CASCADE,
    screened_at TIMESTAMPTZ NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    miss_distance_km DOUBLE PRECISION NOT NULL CHECK (miss_distance_km >= 0),
    UNIQUE (event_id, screened_at)
);

CREATE INDEX idx_objects_type ON objects (object_type);
CREATE INDEX idx_conjunction_events_tier_score ON conjunction_events (risk_tier, risk_score DESC);
CREATE INDEX idx_conjunction_events_tca ON conjunction_events (tca);
CREATE INDEX idx_conjunction_events_screened_at ON conjunction_events (screened_at DESC);
CREATE INDEX idx_event_history_event_screened_at ON event_history (event_id, screened_at DESC);
