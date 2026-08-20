# Database

`init/001_initial_schema.sql` creates the Phase 0 schema on first startup of
the named Postgres volume. It models a stable conjunction pair using `pair_key`,
so repeated screenings can retain trend history for the same pair.

Run the database service with:

```bash
cp .env.example .env # only if .env does not already exist
docker compose up -d postgres
docker compose ps
```

The service is available only on `127.0.0.1:${POSTGRES_PORT}`. Future schema
changes will use Alembic migrations once the backend exists; changing an init
script does not affect an already-created named volume.

The ingestion cache is intentionally outside the repository at
`data/cache/celestrak_active.json`. A successful CelesTrak response replaces it
atomically; DNS, HTTP, or malformed-response failures use the previous valid
cache and report `source=cache` in the headless screening output.
