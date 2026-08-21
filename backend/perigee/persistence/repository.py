"""Small asyncpg repository; domain and orbital calculations stay database-free."""

import json
from dataclasses import asdict
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg

from perigee.domain import CloseApproach, OrbitalObject, RiskAssessment


class PerigeeRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=5)
        async with self._connection_pool.acquire() as connection:
            await connection.execute(
                """CREATE TABLE IF NOT EXISTS agent_recommendations (
                    event_id UUID NOT NULL REFERENCES conjunction_events(id) ON DELETE CASCADE,
                    screened_at TIMESTAMPTZ NOT NULL,
                    recommendation_text TEXT NOT NULL,
                    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (event_id, screened_at)
                )"""
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def _connection_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Repository is not connected")
        return self._pool

    async def upsert_objects(self, objects: list[OrbitalObject]) -> None:
        records = [
            (
                object_.norad_id,
                object_.name,
                object_.object_type.value,
                object_.tle_line1,
                object_.tle_line2,
                object_.epoch,
                json.dumps(object_.gp_data) if object_.gp_data is not None else None,
            )
            for object_ in objects
        ]
        query = """
            INSERT INTO objects (norad_id, name, object_type, tle_line1, tle_line2, epoch, gp_data, last_updated)
            VALUES ($1, $2, $3::object_type, $4, $5, $6, $7::jsonb, NOW())
            ON CONFLICT (norad_id) DO UPDATE SET
                name = EXCLUDED.name,
                object_type = EXCLUDED.object_type,
                tle_line1 = EXCLUDED.tle_line1,
                tle_line2 = EXCLUDED.tle_line2,
                epoch = EXCLUDED.epoch,
                gp_data = EXCLUDED.gp_data,
                last_updated = NOW()
        """
        async with self._connection_pool.acquire() as connection:
            await connection.executemany(query, records)

    async def save_assessment(
        self, event: CloseApproach, assessment: RiskAssessment, screened_at: datetime
    ) -> UUID:
        object_a_id, object_b_id = sorted((event.object_a.norad_id, event.object_b.norad_id))
        pair_key = f"{object_a_id}:{object_b_id}"
        event_id = uuid5(NAMESPACE_URL, f"perigee/conjunction/{pair_key}")
        factor_breakdown = json.dumps(
            {name: asdict(factor) for name, factor in assessment.factors.items()}
        )
        event_query = """
            INSERT INTO conjunction_events (
                id, pair_key, object_a_id, object_b_id, tca, miss_distance_km,
                relative_velocity_kmps, risk_score, risk_tier, factor_breakdown, screened_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::risk_tier, $10::jsonb, $11, NOW())
            ON CONFLICT (pair_key) DO UPDATE SET
                tca = EXCLUDED.tca,
                miss_distance_km = EXCLUDED.miss_distance_km,
                relative_velocity_kmps = EXCLUDED.relative_velocity_kmps,
                risk_score = EXCLUDED.risk_score,
                risk_tier = EXCLUDED.risk_tier,
                factor_breakdown = EXCLUDED.factor_breakdown,
                screened_at = EXCLUDED.screened_at,
                updated_at = NOW()
        """
        history_query = """
            INSERT INTO event_history (event_id, screened_at, risk_score, miss_distance_km)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (event_id, screened_at) DO NOTHING
        """
        async with self._connection_pool.acquire() as connection, connection.transaction():
            await connection.execute(
                event_query,
                event_id,
                pair_key,
                object_a_id,
                object_b_id,
                event.tca,
                event.miss_distance_km,
                event.relative_velocity_kmps,
                assessment.score,
                assessment.tier.value,
                factor_breakdown,
                screened_at,
            )
            await connection.execute(
                history_query,
                event_id,
                screened_at,
                assessment.score,
                event.miss_distance_km,
            )
        return event_id

    async def previous_miss_distances(self, event_id: UUID, limit: int = 5) -> list[float]:
        query = """
            SELECT miss_distance_km
            FROM event_history
            WHERE event_id = $1
            ORDER BY screened_at DESC
            LIMIT $2
        """
        async with self._connection_pool.acquire() as connection:
            rows = await connection.fetch(query, event_id, limit)
            return list(reversed([float(row["miss_distance_km"]) for row in rows]))

    async def list_events(
        self, *, tier: str | None, sort: str, offset: int, limit: int
    ) -> list[asyncpg.Record]:
        order_by = {
            "score_desc": "e.risk_score DESC, e.tca ASC",
            "tca_asc": "e.tca ASC, e.risk_score DESC",
        }[sort]
        query = f"""
            SELECT e.id, e.tca, e.miss_distance_km, e.relative_velocity_kmps,
                   e.risk_score, e.risk_tier, e.factor_breakdown, e.screened_at,
                   a.norad_id AS object_a_id, a.name AS object_a_name,
                   a.object_type AS object_a_type, b.norad_id AS object_b_id,
                   b.name AS object_b_name, b.object_type AS object_b_type
            FROM conjunction_events e
            JOIN objects a ON a.norad_id = e.object_a_id
            JOIN objects b ON b.norad_id = e.object_b_id
            WHERE ($1::risk_tier IS NULL OR e.risk_tier = $1::risk_tier)
            ORDER BY {order_by}
            OFFSET $2 LIMIT $3
        """
        async with self._connection_pool.acquire() as connection:
            return await connection.fetch(query, tier, offset, limit)

    async def get_event(self, event_id: UUID) -> dict[str, object] | None:
        query = """
            SELECT e.id, e.tca, e.miss_distance_km, e.relative_velocity_kmps,
                   e.risk_score, e.risk_tier, e.factor_breakdown, e.screened_at,
                   a.norad_id AS object_a_id, a.name AS object_a_name,
                   a.object_type AS object_a_type, a.tle_line1 AS object_a_tle_line1,
                   a.tle_line2 AS object_a_tle_line2, a.epoch AS object_a_epoch,
                   a.gp_data AS object_a_gp_data, b.norad_id AS object_b_id,
                   b.name AS object_b_name, b.object_type AS object_b_type,
                   b.tle_line1 AS object_b_tle_line1, b.tle_line2 AS object_b_tle_line2,
                   b.epoch AS object_b_epoch, b.gp_data AS object_b_gp_data
            FROM conjunction_events e
            JOIN objects a ON a.norad_id = e.object_a_id
            JOIN objects b ON b.norad_id = e.object_b_id
            WHERE e.id = $1
        """
        history_query = """
            SELECT screened_at, risk_score, miss_distance_km
            FROM event_history
            WHERE event_id = $1
            ORDER BY screened_at ASC
        """
        async with self._connection_pool.acquire() as connection:
            event = await connection.fetchrow(query, event_id)
            if event is None:
                return None
            history = await connection.fetch(history_query, event_id)
            event_data = dict(event)
            for key in ("factor_breakdown", "object_a_gp_data", "object_b_gp_data"):
                if isinstance(event_data.get(key), str):
                    event_data[key] = json.loads(event_data[key])
            return {**event_data, "history": [dict(row) for row in history]}

    async def get_object(self, norad_id: int) -> dict[str, object] | None:
        query = """
            SELECT norad_id, name, object_type, tle_line1, tle_line2, epoch, gp_data, last_updated
            FROM objects
            WHERE norad_id = $1
        """
        async with self._connection_pool.acquire() as connection:
            row = await connection.fetchrow(query, norad_id)
            if row is None:
                return None
            data = dict(row)
            if isinstance(data.get("gp_data"), str):
                data["gp_data"] = json.loads(data["gp_data"])
            return data

    async def get_recommendation(self, event_id: UUID, screened_at: datetime) -> str | None:
        query = """SELECT recommendation_text FROM agent_recommendations
                   WHERE event_id = $1 AND screened_at = $2"""
        async with self._connection_pool.acquire() as connection:
            value = await connection.fetchval(query, event_id, screened_at)
            return str(value) if value is not None else None

    async def save_recommendation(self, event_id: UUID, screened_at: datetime, text: str) -> None:
        query = """INSERT INTO agent_recommendations (event_id, screened_at, recommendation_text)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (event_id, screened_at) DO UPDATE SET
                     recommendation_text = EXCLUDED.recommendation_text,
                     generated_at = NOW()"""
        async with self._connection_pool.acquire() as connection:
            await connection.execute(query, event_id, screened_at, text)

    async def agent_event_context(self, limit: int = 25) -> list[dict[str, object]]:
        query = """SELECT e.id, a.name AS object_a_name, b.name AS object_b_name,
                          e.risk_score, e.risk_tier, e.miss_distance_km,
                          e.relative_velocity_kmps, e.tca, e.screened_at
                   FROM conjunction_events e
                   JOIN objects a ON a.norad_id = e.object_a_id
                   JOIN objects b ON b.norad_id = e.object_b_id
                   ORDER BY e.risk_score DESC, e.tca ASC LIMIT $1"""
        async with self._connection_pool.acquire() as connection:
            return [dict(row) for row in await connection.fetch(query, limit)]

    async def stats(self) -> asyncpg.Record:
        query = """
            SELECT
                (SELECT count(*) FROM objects) AS objects_tracked,
                (SELECT count(*) FROM conjunction_events) AS events_screened,
                (SELECT count(*) FROM conjunction_events WHERE risk_tier = 'critical') AS critical_count,
                (SELECT count(*) FROM conjunction_events WHERE risk_tier = 'elevated') AS elevated_count,
                (SELECT count(*) FROM conjunction_events WHERE risk_tier = 'low') AS low_count,
                (SELECT max(screened_at) FROM conjunction_events) AS last_screened_at
        """
        async with self._connection_pool.acquire() as connection:
            return await connection.fetchrow(query)
