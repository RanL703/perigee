from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from itertools import combinations
from math import sqrt

from sgp4.api import SGP4_ERRORS, Satrec
from sgp4.conveniences import jday_datetime

from perigee.config import ScreeningConfig
from perigee.domain import CloseApproach, OrbitalObject, StateVector

EARTH_RADIUS_KM = 6378.137
EARTH_MU_KM3_S2 = 398600.4418


def propagate(object_: OrbitalObject, at: datetime) -> StateVector:
    """Return a TEME state vector in kilometres and kilometres per second."""
    utc_at = at.astimezone(UTC)
    satellite = Satrec.twoline2rv(object_.tle_line1, object_.tle_line2)
    jd, fraction = jday_datetime(utc_at)
    error, position, velocity = satellite.sgp4(jd, fraction)
    if error:
        raise ValueError(f"SGP4 failed for NORAD {object_.norad_id}: {SGP4_ERRORS[error]}")
    return StateVector(utc_at, tuple(position), tuple(velocity))


def _norm(vector: tuple[float, float, float]) -> float:
    return sqrt(sum(component * component for component in vector))


def _distance(a: StateVector, b: StateVector) -> float:
    return _norm(tuple(left - right for left, right in zip(a.position_km, b.position_km)))


def _relative_velocity(a: StateVector, b: StateVector) -> float:
    return _norm(tuple(left - right for left, right in zip(a.velocity_kmps, b.velocity_kmps)))


def _altitude_band_km(object_: OrbitalObject) -> tuple[float, float]:
    satellite = Satrec.twoline2rv(object_.tle_line1, object_.tle_line2)
    mean_motion_rad_s = satellite.no_kozai / 60.0
    semi_major_axis = (EARTH_MU_KM3_S2 / (mean_motion_rad_s * mean_motion_rad_s)) ** (1 / 3)
    eccentricity = satellite.ecco
    return (
        semi_major_axis * (1 - eccentricity) - EARTH_RADIUS_KM,
        semi_major_axis * (1 + eccentricity) - EARTH_RADIUS_KM,
    )


def _overlapping_altitude_bands(
    a: OrbitalObject, b: OrbitalObject, padding_km: float
) -> bool:
    a_low, a_high = _altitude_band_km(a)
    b_low, b_high = _altitude_band_km(b)
    return a_low <= b_high + padding_km and b_low <= a_high + padding_km


def _times(start: datetime, duration_seconds: int, step_seconds: int) -> Iterable[datetime]:
    steps = duration_seconds // step_seconds
    for step in range(steps + 1):
        yield start + timedelta(seconds=step * step_seconds)


def screen(objects: list[OrbitalObject], start: datetime, config: ScreeningConfig) -> list[CloseApproach]:
    """Find genuine close passes with altitude, coarse, then fine filtering.

    The algorithm deliberately propagates only altitude-compatible pairs at a
    10-minute cadence, then re-propagates the local minimum at 30-second cadence.
    All calculations preserve SGP4's km and km/s units.
    """
    start = start.astimezone(UTC)
    duration_seconds = config.horizon_hours * 3600
    candidates = [
        pair
        for pair in combinations(sorted(objects, key=lambda item: item.norad_id), 2)
        if _overlapping_altitude_bands(*pair, config.altitude_band_padding_km)
    ]
    coarse_times = list(_times(start, duration_seconds, config.coarse_step_seconds))
    states = {
        object_.norad_id: [propagate(object_, at) for at in coarse_times] for object_ in objects
    }
    coarse_hits: list[tuple[OrbitalObject, OrbitalObject, datetime]] = []
    for object_a, object_b in candidates:
        distances = [
            _distance(left, right)
            for left, right in zip(states[object_a.norad_id], states[object_b.norad_id])
        ]
        closest_index = min(range(len(distances)), key=distances.__getitem__)
        if distances[closest_index] <= config.coarse_candidate_distance_km:
            coarse_hits.append((object_a, object_b, coarse_times[closest_index]))

    events: list[CloseApproach] = []
    half_window = config.coarse_step_seconds
    for object_a, object_b, coarse_tca in coarse_hits:
        window_start = max(start, coarse_tca - timedelta(seconds=half_window))
        window_end = min(start + timedelta(seconds=duration_seconds), coarse_tca + timedelta(seconds=half_window))
        fine_times = list(
            _times(window_start, int((window_end - window_start).total_seconds()), config.fine_step_seconds)
        )
        fine_states = [(propagate(object_a, at), propagate(object_b, at)) for at in fine_times]
        closest_a, closest_b = min(fine_states, key=lambda pair: _distance(*pair))
        miss_distance = _distance(closest_a, closest_b)
        if miss_distance <= config.conjunction_threshold_km:
            events.append(
                CloseApproach(
                    object_a=object_a,
                    object_b=object_b,
                    tca=closest_a.at,
                    miss_distance_km=miss_distance,
                    relative_velocity_kmps=_relative_velocity(closest_a, closest_b),
                )
            )
    return sorted(events, key=lambda event: event.miss_distance_km)
