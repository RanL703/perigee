"""Headless Phase 1 verification entrypoint."""

import asyncio
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from perigee.config import DatabaseConfig, ScreeningConfig
from perigee.ingestion.celestrak import fetch_catalog
from perigee.persistence.repository import PerigeeRepository
from perigee.propagation.screening import screen
from perigee.scoring.risk import assess


async def run() -> None:
    config = ScreeningConfig()
    objects = fetch_catalog(config.catalog_url, config.object_limit)
    events = screen(objects, datetime.now(UTC), config)
    repository = PerigeeRepository(DatabaseConfig().url)
    await repository.connect()
    await repository.upsert_objects(objects)
    screened_at = datetime.now(UTC)
    print(f"Fetched {len(objects)} real CelesTrak objects; found {len(events)} close approaches.")
    for event in events:
        pair_key = ":".join(map(str, sorted((event.object_a.norad_id, event.object_b.norad_id))))
        history = await repository.previous_miss_distances(uuid5(NAMESPACE_URL, f"perigee/conjunction/{pair_key}"))
        assessment = assess(event, history, screening=config)
        await repository.save_assessment(event, assessment, screened_at)
    await repository.close()
    for event in events[:10]:
        assessment = assess(event, screening=config)
        print(
            f"{assessment.tier.upper():8} {assessment.score:5.1f} | "
            f"{event.object_a.name} × {event.object_b.name} | "
            f"{event.miss_distance_km:.3f} km at {event.tca.isoformat()} | "
            f"{event.relative_velocity_kmps:.3f} km/s"
        )


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
