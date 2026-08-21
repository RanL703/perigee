"""Seed the database with a fabricated DEMO dataset (PRD Phase 5, item 17).

This is a demo-safety-net dataset only, explicitly authorized by the product
owner. The close-approach GEOMETRY below is fabricated so the dashboard always
has a live-looking picture even if CelesTrak screening finds no natural events.
Every score, tier, factor breakdown and trend is still produced by the real
deterministic scoring engine (perigee.scoring.risk.assess) applied to that
geometry — nothing here invents scores.

Objects use valid TLE elements (validated through SGP4 at seed time) so
propagation-backed endpoints like /api/objects/{norad_id} keep working.

Run with:
    .venv/bin/python backend/scripts/seed_demo_events.py
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from perigee.config import DatabaseConfig, ScreeningConfig
from perigee.domain import CloseApproach, ObjectType, OrbitalObject
from perigee.persistence.repository import PerigeeRepository
from perigee.propagation.screening import propagate
from perigee.scoring.risk import assess


def _checksum(line_body: str) -> str:
    total = sum(int(char) if char.isdigit() else char == "-" for char in line_body)
    return f"{line_body}{total % 10}"


def _tle(
    norad_id: int,
    inclination_deg: float,
    raan_deg: float,
    argp_deg: float,
    mean_anomaly_deg: float,
    mean_motion_revday: float,
    epoch: datetime,
) -> tuple[str, str]:
    day_fraction = (
        epoch.hour * 3600 + epoch.minute * 60 + epoch.second + epoch.microsecond / 1e6
    ) / 86400
    # TLE epoch field is YYDDD.DDDDDDDD — exactly 14 characters.
    epoch_field = f"{epoch.astimezone(UTC).strftime('%y%j')}{day_fraction:.8f}"[1:]
    line1 = _checksum(f"1 {norad_id:05d}U 26001A   {epoch_field} -.00000000  00000-0  00000-0 0  999")
    line2 = _checksum(
        f"2 {norad_id:05d} {inclination_deg:8.4f} {raan_deg:8.4f} "
        f"{'0001500':>7} {argp_deg:8.4f} {mean_anomaly_deg:8.4f} {mean_motion_revday:11.8f}10000"
    )
    return line1, line2


def _object(
    norad_id: int,
    name: str,
    object_type: ObjectType,
    inclination: float,
    raan: float,
    mean_motion: float,
    epoch: datetime,
) -> OrbitalObject:
    line1, line2 = _tle(norad_id, inclination, raan, 90.0, 120.0, mean_motion, epoch)
    object_ = OrbitalObject(norad_id=norad_id, name=name, object_type=object_type, tle_line1=line1, tle_line2=line2, epoch=epoch)
    propagate(object_, epoch)  # fail fast when SGP4 rejects the elements
    return object_


def _event_id(event: CloseApproach) -> uuid.UUID:
    pair_key = ":".join(map(str, sorted((event.object_a.norad_id, event.object_b.norad_id))))
    return uuid.uuid5(uuid.NAMESPACE_URL, f"perigee/conjunction/{pair_key}")


DEMO_OBJECTS = [
    ("SENTINEL-6A", 44932, ObjectType.PAYLOAD, 66.04, 100.0, 13.29),
    ("FENGYUN 1C DEB", 48271, ObjectType.DEBRIS, 98.72, 210.0, 14.12),
    ("STARLINK-3042", 52142, ObjectType.PAYLOAD, 53.05, 45.0, 15.06),
    ("COSMOS 2251 DEB", 39155, ObjectType.DEBRIS, 74.02, 310.0, 14.36),
    ("SL-16 R/B", 28370, ObjectType.ROCKET_BODY, 82.96, 150.0, 14.32),
    ("IRIDIUM 109", 25197, ObjectType.PAYLOAD, 86.40, 250.0, 14.34),
    ("AQUA", 27424, ObjectType.PAYLOAD, 98.20, 20.0, 14.57),
    ("COSMOS 1408 DEB", 49863, ObjectType.DEBRIS, 82.64, 130.0, 15.21),
    ("ONEWEB-0357", 44057, ObjectType.PAYLOAD, 87.90, 280.0, 13.15),
    ("CZ-4B R/B", 25942, ObjectType.ROCKET_BODY, 98.70, 330.0, 14.85),
    ("GLOBALSTAR M061", 4962, ObjectType.PAYLOAD, 52.01, 175.0, 14.12),
]


async def main() -> None:
    now = datetime.now(UTC)
    catalog = [
        _object(norad_id, name, object_type, inclination, raan, mean_motion, now - timedelta(hours=6))
        for name, norad_id, object_type, inclination, raan, mean_motion in DEMO_OBJECTS
    ]
    by_name = {object_.name: object_ for object_ in catalog}
    sentinel, fengyun = by_name["SENTINEL-6A"], by_name["FENGYUN 1C DEB"]
    starlink, cosmos = by_name["STARLINK-3042"], by_name["COSMOS 2251 DEB"]
    sl16, iridium = by_name["SL-16 R/B"], by_name["IRIDIUM 109"]
    aqua, cosmos1408 = by_name["AQUA"], by_name["COSMOS 1408 DEB"]
    oneweb, cz4b = by_name["ONEWEB-0357"], by_name["CZ-4B R/B"]
    globalstar = by_name["GLOBALSTAR M061"]

    demo_events = [
        # Critical tier
        CloseApproach(object_a=sentinel, object_b=fengyun, tca=now + timedelta(hours=2), miss_distance_km=0.35, relative_velocity_kmps=13.8),
        CloseApproach(object_a=aqua, object_b=cosmos1408, tca=now + timedelta(hours=4, minutes=40), miss_distance_km=0.55, relative_velocity_kmps=12.4),
        # Elevated tier
        CloseApproach(object_a=starlink, object_b=cosmos, tca=now + timedelta(hours=7), miss_distance_km=1.8, relative_velocity_kmps=10.4),
        CloseApproach(object_a=oneweb, object_b=cz4b, tca=now + timedelta(hours=9, minutes=15), miss_distance_km=1.3, relative_velocity_kmps=10.8),
        CloseApproach(object_a=globalstar, object_b=fengyun, tca=now + timedelta(hours=13), miss_distance_km=2.1, relative_velocity_kmps=9.2),
        # Low tier
        CloseApproach(object_a=sl16, object_b=iridium, tca=now + timedelta(hours=20), miss_distance_km=4.1, relative_velocity_kmps=14.6),
        CloseApproach(object_a=aqua, object_b=sl16, tca=now + timedelta(hours=17), miss_distance_km=3.3, relative_velocity_kmps=8.4),
        CloseApproach(object_a=starlink, object_b=iridium, tca=now + timedelta(hours=22, minutes=30), miss_distance_km=4.4, relative_velocity_kmps=6.2),
    ]
    # Prior miss distances per pair drive the deterministic trend factor;
    # the critical pairs are deliberately closing in across screenings.
    prior_history = [
        [1.9, 1.1, 0.7],
        [1.4, 0.9],
        [1.75, 1.85],
        [1.25],
        [2.05],
        [4.0],
        [3.3],
        [4.4],
    ]

    repository = PerigeeRepository(DatabaseConfig().url)
    await repository.connect()
    try:
        await repository.upsert_objects(catalog)
        for event, priors in zip(demo_events, prior_history):
            assessment = assess(event, priors, screening=ScreeningConfig())
            screened_at = event.tca - timedelta(days=len(priors))
            await repository.save_assessment(event, assessment, screened_at)
            history = list(priors) + [event.miss_distance_km]
            async with repository._connection_pool.acquire() as connection:
                await connection.executemany(
                    """INSERT INTO event_history (event_id, screened_at, risk_score, miss_distance_km)
                       VALUES ($1, $2, $3, $4) ON CONFLICT (event_id, screened_at) DO NOTHING""",
                    [
                        (_event_id(event), screened_at + timedelta(days=index), assessment.score, miss_distance)
                        for index, miss_distance in enumerate(history)
                    ],
                )
            print(f"seeded {event.object_a.name} × {event.object_b.name}: score {assessment.score} tier {assessment.tier.value}")
    finally:
        await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
