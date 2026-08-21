CREATE TABLE IF NOT EXISTS agent_recommendations (
    event_id UUID NOT NULL REFERENCES conjunction_events(id) ON DELETE CASCADE,
    screened_at TIMESTAMPTZ NOT NULL,
    recommendation_text TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, screened_at)
);
