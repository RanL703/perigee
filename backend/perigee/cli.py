"""Headless Phase 1 verification entrypoint."""

from datetime import UTC, datetime

from perigee.config import ScreeningConfig
from perigee.ingestion.celestrak import fetch_catalog
from perigee.propagation.screening import screen
from perigee.scoring.risk import assess


def main() -> None:
    config = ScreeningConfig()
    objects = fetch_catalog(config.catalog_url, config.object_limit)
    events = screen(objects, datetime.now(UTC), config)
    print(f"Fetched {len(objects)} real CelesTrak objects; found {len(events)} close approaches.")
    for event in events[:10]:
        assessment = assess(event, screening=config)
        print(
            f"{assessment.tier.upper():8} {assessment.score:5.1f} | "
            f"{event.object_a.name} × {event.object_b.name} | "
            f"{event.miss_distance_km:.3f} km at {event.tca.isoformat()} | "
            f"{event.relative_velocity_kmps:.3f} km/s"
        )


if __name__ == "__main__":
    main()
