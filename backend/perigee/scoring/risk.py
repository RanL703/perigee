from collections.abc import Sequence

from perigee.config import RiskConfig, ScreeningConfig
from perigee.domain import CloseApproach, Factor, RiskAssessment, RiskTier


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def assess(
    event: CloseApproach,
    previous_miss_distances_km: Sequence[float] = (),
    *,
    screening: ScreeningConfig | None = None,
    risk: RiskConfig | None = None,
) -> RiskAssessment:
    """Calculate a bounded, stored factor breakdown for a real close approach."""
    screening, risk = screening or ScreeningConfig(), risk or RiskConfig()
    distance_signal = _clamp(1 - event.miss_distance_km / screening.conjunction_threshold_km)
    velocity_signal = _clamp(event.relative_velocity_kmps / 15.0)
    type_signal = {
        ("payload", "payload"): 1.0,
        ("debris", "debris"): 0.25,
    }.get(tuple(sorted((event.object_a.object_type.value, event.object_b.object_type.value))), 0.65)
    if previous_miss_distances_km:
        prior = previous_miss_distances_km[-1]
        trend_signal = _clamp((prior - event.miss_distance_km) / max(prior, 0.001))
    else:
        trend_signal = 0.0
    factors = {
        "miss_distance": Factor(event.miss_distance_km, distance_signal * risk.distance_weight, risk.distance_weight),
        "relative_velocity": Factor(event.relative_velocity_kmps, velocity_signal * risk.velocity_weight, risk.velocity_weight),
        "object_type": Factor(type_signal, type_signal * risk.object_type_weight, risk.object_type_weight),
        "trend": Factor(trend_signal, trend_signal * risk.trend_weight, risk.trend_weight),
    }
    score = round(sum(factor.contribution for factor in factors.values()), 1)
    tier = (
        RiskTier.CRITICAL
        if score >= risk.critical_threshold
        else RiskTier.ELEVATED if score >= risk.elevated_threshold else RiskTier.LOW
    )
    return RiskAssessment(score=score, tier=tier, factors=factors)
