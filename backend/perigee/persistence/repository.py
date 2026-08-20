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
            )
            for object_ in objects
        ]
        query = """
            INSERT INTO objects (norad_id, name, object_type, tle_line1, tle_line2, epoch, last_updated)
            VALUES ($1, $2, $3::object_type, $4, $5, $6, NOW())
            ON CONFLICT (norad_id) DO UPDATE SET
                name = EXCLUDED.name,
                object_type = EXCLUDED.object_type,
                tle_line1 = EXCLUDED.tle_line1,
                tle_line2 = EXCLUDED.tle_line2,
                epoch = EXCLUDED.epoch,
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
