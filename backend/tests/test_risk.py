from datetime import UTC, datetime

from perigee.config import RiskConfig, ScreeningConfig
from perigee.domain import CloseApproach, ObjectType, OrbitalObject, RiskTier
from perigee.scoring.risk import assess


def _object(norad_id: int, object_type: ObjectType) -> OrbitalObject:
    return OrbitalObject(
        norad_id=norad_id,
        name=str(norad_id),
        object_type=object_type,
        tle_line1="1" * 69,
        tle_line2="2" * 69,
        epoch=datetime(2024, 1, 1, tzinfo=UTC),
    )


def test_scoring_is_bounded_and_explains_each_contribution() -> None:
    event = CloseApproach(
        _object(1, ObjectType.PAYLOAD),
        _object(2, ObjectType.PAYLOAD),
        datetime(2024, 1, 1, tzinfo=UTC),
        miss_distance_km=0.5,
        relative_velocity_kmps=12,
    )

    result = assess(
        event,
        previous_miss_distances_km=[2.0],
        screening=ScreeningConfig(conjunction_threshold_km=5),
        risk=RiskConfig(),
    )

    assert result.tier is RiskTier.CRITICAL
    assert 0 <= result.score <= 100
    assert set(result.factors) == {"miss_distance", "relative_velocity", "object_type", "trend"}
    assert result.score == round(sum(item.contribution for item in result.factors.values()), 1)
