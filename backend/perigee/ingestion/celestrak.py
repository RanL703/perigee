"""Reliable CelesTrak GP JSON ingestion with transparent cache fallback."""

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sgp4 import omm
from sgp4.api import Satrec

from perigee.domain import ObjectType, OrbitalObject

_TYPE_MAP = {
    "PAYLOAD": ObjectType.PAYLOAD,
    "DEBRIS": ObjectType.DEBRIS,
    "ROCKET BODY": ObjectType.ROCKET_BODY,
    "ROCKET_BODY": ObjectType.ROCKET_BODY,
}
_OMM_REQUIRED = {
    "OBJECT_ID",
    "EPOCH",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
    "EPHEMERIS_TYPE",
    "CLASSIFICATION_TYPE",
    "ELEMENT_SET_NO",
    "REV_AT_EPOCH",
    "BSTAR",
    "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
    "NORAD_CAT_ID",
}


class CatalogError(RuntimeError):
    """Raised when live data and the last known-good cache are unavailable."""


@dataclass(frozen=True, slots=True)
class CatalogResult:
    objects: list[OrbitalObject]
    source: str
    cache_path: Path


def _parse_epoch(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _object_type(row: dict[str, object]) -> ObjectType:
    declared = row.get("OBJECT_TYPE")
    if declared is not None:
        type_value = _TYPE_MAP.get(str(declared).strip().upper())
        if type_value is not None:
            return type_value
    name = str(row.get("OBJECT_NAME", "")).upper()
    if "DEB" in name or "DEBRIS" in name:
        return ObjectType.DEBRIS
    if "R/B" in name or "ROCKET BODY" in name:
        return ObjectType.ROCKET_BODY
    # The GP endpoint does not currently include OBJECT_TYPE. Active-group
    # records therefore default to payload; named debris/rocket bodies above
    # remain classified without inventing orbital data.
    return ObjectType.PAYLOAD


def _validate_gp_fields(row: dict[str, object]) -> dict[str, object]:
    if not _OMM_REQUIRED.issubset(row):
        missing = ", ".join(sorted(_OMM_REQUIRED - row.keys()))
        raise ValueError(f"missing GP/OMM fields: {missing}")
    satellite = Satrec()
    omm.initialize(satellite, row)
    return {key: row[key] for key in row if key in _OMM_REQUIRED or key == "OBJECT_NAME"}


def parse_catalog_rows(rows: Iterable[dict[str, object]], limit: int) -> list[OrbitalObject]:
    """Turn CelesTrak GP JSON rows into validated objects, skipping malformed rows."""
    objects: list[OrbitalObject] = []
    for row in rows:
        if len(objects) >= limit:
            break
        try:
            type_value = _object_type(row)
            raw_line1, raw_line2 = row.get("TLE_LINE1"), row.get("TLE_LINE2")
            line1 = str(raw_line1) if raw_line1 is not None else None
            line2 = str(raw_line2) if raw_line2 is not None else None
            gp_data = None
            if line1 is not None or line2 is not None:
                if line1 is None or line2 is None or len(line1) != 69 or len(line2) != 69:
                    continue
                Satrec.twoline2rv(line1, line2)
            else:
                gp_data = _validate_gp_fields(row)
            objects.append(
                OrbitalObject(
                    norad_id=int(row["NORAD_CAT_ID"]),
                    name=str(row["OBJECT_NAME"]).strip() or f"NORAD {row['NORAD_CAT_ID']}",
                    object_type=type_value,
                    tle_line1=line1,
                    tle_line2=line2,
                    epoch=_parse_epoch(str(row["EPOCH"])),
                    gp_data=gp_data,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not objects:
        raise CatalogError("CelesTrak returned no valid GP/TLE records")
    return objects


def _read_cache(path: Path, limit: int, url: str) -> list[OrbitalObject]:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict) or envelope.get("url") != url:
            raise ValueError("cached catalog URL does not match the requested source")
        payload = envelope.get("records")
        if not isinstance(payload, list):
            raise TypeError("cached records are not a JSON list")
        return parse_catalog_rows(payload, limit)
    except (OSError, TypeError, ValueError, json.JSONDecodeError, CatalogError) as exc:
        raise CatalogError(f"Cached CelesTrak data is unavailable at {path}: {exc}") from exc


def _write_cache(path: Path, payload: list[dict[str, Any]], url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    envelope = {"url": url, "cached_at": datetime.now(UTC).isoformat(), "records": payload}
    temporary_path.write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")
    temporary_path.replace(path)


def fetch_catalog_result(
    url: str,
    limit: int,
    timeout_seconds: float = 20.0,
    *,
    cache_path: str | Path = "data/cache/celestrak_active.json",
    retries: int = 3,
    backoff_seconds: float = 1.0,
    transport: httpx.BaseTransport | None = None,
) -> CatalogResult:
    """Fetch live GP JSON, cache validated responses, and fall back on failure."""
    path = Path(cache_path)
    timeout = httpx.Timeout(
        connect=min(timeout_seconds, 10.0), read=timeout_seconds, write=10.0, pool=10.0
    )
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, transport=transport) as client:
                response = client.get(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Perigee/0.1 (+https://github.com/RanL703/perigee)",
                    },
                )
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
                raise CatalogError("CelesTrak response was not a JSON list of records")
            objects = parse_catalog_rows(payload, limit)
            _write_cache(path, payload, url)
            return CatalogResult(objects=objects, source="live", cache_path=path)
        except (httpx.HTTPError, ValueError, CatalogError) as exc:
            last_error = exc
            if attempt + 1 < max(1, retries):
                time.sleep(backoff_seconds * (2**attempt))

    try:
        objects = _read_cache(path, limit, url)
    except CatalogError as cache_error:
        raise CatalogError(
            f"CelesTrak unavailable after {max(1, retries)} attempts ({last_error}); {cache_error}"
        ) from last_error
    return CatalogResult(objects=objects, source="cache", cache_path=path)


def fetch_catalog(
    url: str,
    limit: int,
    timeout_seconds: float = 20.0,
    *,
    cache_path: str | Path = "data/cache/celestrak_active.json",
    retries: int = 3,
    backoff_seconds: float = 1.0,
) -> list[OrbitalObject]:
    """Compatibility wrapper returning only normalized objects."""
    return fetch_catalog_result(
        url,
        limit,
        timeout_seconds,
        cache_path=cache_path,
        retries=retries,
        backoff_seconds=backoff_seconds,
    ).objects
