from datetime import UTC, datetime

from perigee.config import ScreeningConfig
from perigee.domain import ObjectType, OrbitalObject
from perigee.propagation.screening import screen

LINE_1 = "1 25544U 98067A   24001.00000000  .00016717  00000+0  30157-3 0  9997"
LINE_2 = "2 25544  51.6406  33.7703 0005037 102.0979  24.6411 15.50087279431168"


def _object(norad_id: int, name: str) -> OrbitalObject:
    return OrbitalObject(
        norad_id=norad_id,
        name=name,
        object_type=ObjectType.PAYLOAD,
        tle_line1=LINE_1,
        tle_line2=LINE_2,
        epoch=datetime(2024, 1, 1, tzinfo=UTC),
    )


def test_screen_reports_a_close_pass_with_km_units() -> None:
    # Identical valid TLEs intentionally create a zero-distance control case.
    # It protects the coarse-to-fine flow from regressing without inventing orbit math.
    config = ScreeningConfig(
        horizon_hours=1,
        coarse_step_seconds=600,
        fine_step_seconds=60,
        conjunction_threshold_km=0.01,
    )

    events = screen([_object(25544, "A"), _object(25545, "B")], datetime(2024, 1, 1, tzinfo=UTC), config)

    assert len(events) == 1
    assert events[0].miss_distance_km == 0
    assert events[0].relative_velocity_kmps == 0
