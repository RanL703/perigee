from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ObjectType(StrEnum):
    PAYLOAD = "payload"
    DEBRIS = "debris"
    ROCKET_BODY = "rocket_body"


class RiskTier(StrEnum):
    CRITICAL = "critical"
    ELEVATED = "elevated"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class OrbitalObject:
    norad_id: int
    name: str
    object_type: ObjectType
    tle_line1: str
    tle_line2: str
    epoch: datetime


@dataclass(frozen=True, slots=True)
class StateVector:
    at: datetime
    position_km: tuple[float, float, float]
    velocity_kmps: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class CloseApproach:
    object_a: OrbitalObject
    object_b: OrbitalObject
    tca: datetime
    miss_distance_km: float
    relative_velocity_kmps: float


@dataclass(frozen=True, slots=True)
class Factor:
    raw_value: float
    contribution: float
    weight: float


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    score: float
    tier: RiskTier
    factors: dict[str, Factor]
