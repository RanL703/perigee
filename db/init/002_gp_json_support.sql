-- GP JSON is the primary CelesTrak source. Current responses may provide
-- OMM/GP fields without legacy TLE lines, so preserve those fields directly.
ALTER TABLE objects
    ALTER COLUMN tle_line1 DROP NOT NULL,
    ALTER COLUMN tle_line2 DROP NOT NULL;

ALTER TABLE objects
    ADD COLUMN IF NOT EXISTS gp_data JSONB;
