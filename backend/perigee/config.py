"""All tunable screening and risk settings live here, not in domain logic."""

from dataclasses import dataclass
from os import getenv


def _int(name: str, default: int) -> int:
    return int(getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(getenv(name, str(default)))


@dataclass(frozen=True, slots=True)
class ScreeningConfig:
    catalog_url: str = getenv(
        "CELESTRAK_CATALOG_URL",
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=JSON",
    )
    object_limit: int = _int("OBJECT_LIMIT", 250)
    horizon_hours: int = _int("SCREENING_HORIZON_HOURS", 24)
    conjunction_threshold_km: float = _float("CONJUNCTION_THRESHOLD_KM", 5.0)
    coarse_step_seconds: int = _int("COARSE_STEP_SECONDS", 600)
    fine_step_seconds: int = _int("FINE_STEP_SECONDS", 30)
    coarse_candidate_distance_km: float = _float("COARSE_CANDIDATE_DISTANCE_KM", 2_000.0)
    altitude_band_padding_km: float = _float("ALTITUDE_BAND_PADDING_KM", 150.0)


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Weights total 100, making the stored factor contributions explainable."""

    distance_weight: float = _float("RISK_DISTANCE_WEIGHT", 55.0)
    velocity_weight: float = _float("RISK_VELOCITY_WEIGHT", 20.0)
    object_type_weight: float = _float("RISK_OBJECT_TYPE_WEIGHT", 15.0)
    trend_weight: float = _float("RISK_TREND_WEIGHT", 10.0)
    critical_threshold: float = _float("RISK_CRITICAL_THRESHOLD", 75.0)
    elevated_threshold: float = _float("RISK_ELEVATED_THRESHOLD", 40.0)
