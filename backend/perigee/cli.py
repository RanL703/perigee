"""Headless Phase 1 verification entrypoint."""

import argparse
import asyncio
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from perigee.config import DatabaseConfig, ScreeningConfig
from perigee.ingestion.celestrak import fetch_catalog_result
from perigee.persistence.repository import PerigeeRepository
from perigee.propagation.screening import screen
from perigee.scoring.risk import assess


async def run(*, ingest_only: bool = False) -> None:
    config = ScreeningConfig()
    fetch_result = fetch_catalog_result(
        config.catalog_url,
        config.object_limit,
        cache_path=config.cache_path,
        retries=config.fetch_retries,
        backoff_seconds=config.fetch_backoff_seconds,
    )
    objects = fetch_result.objects
    events = screen(objects, datetime.now(UTC), config)
    repository = PerigeeRepository(DatabaseConfig().url)
    await repository.connect()
    await repository.upsert_objects(objects)
    if ingest_only:
        await repository.close()
        print(f"Loaded {len(objects)} CelesTrak objects from {fetch_result.source} into Postgres.")
        return
    screened_at = datetime.now(UTC)
    print(
        f"Loaded {len(objects)} CelesTrak objects from {fetch_result.source}; "
        f"found {len(events)} close approaches."
    )
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
    parser = argparse.ArgumentParser(description="Fetch CelesTrak data and screen conjunctions")
    parser.add_argument(
        "--ingest-only",
        action="store_true",
        help="Persist the fetched object set without running the propagation screen",
    )
    args = parser.parse_args()
    asyncio.run(run(ingest_only=args.ingest_only))


if __name__ == "__main__":
    main()
