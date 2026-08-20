"""CelesTrak GP JSON ingestion with strict validation before persistence."""

from collections.abc import Iterable
from datetime import UTC, datetime

import httpx
from sgp4.api import Satrec

from perigee.domain import ObjectType, OrbitalObject

_TYPE_MAP = {
    "PAYLOAD": ObjectType.PAYLOAD,
    "DEBRIS": ObjectType.DEBRIS,
    "ROCKET BODY": ObjectType.ROCKET_BODY,
    "ROCKET_BODY": ObjectType.ROCKET_BODY,
}


class CatalogError(RuntimeError):
    """Raised when CelesTrak data cannot be safely used."""


def _parse_epoch(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_catalog_rows(rows: Iterable[dict[str, object]], limit: int) -> list[OrbitalObject]:
    """Turn CelesTrak GP JSON rows into validated objects, skipping malformed rows."""
    objects: list[OrbitalObject] = []
    for row in rows:
        if len(objects) >= limit:
            break
        try:
            type_value = _TYPE_MAP.get(str(row["OBJECT_TYPE"]).strip().upper())
            line1, line2 = str(row["TLE_LINE1"]), str(row["TLE_LINE2"])
            if type_value is None or len(line1) != 69 or len(line2) != 69:
                continue
            # Parsing here rejects bad checksums/mean elements before the object reaches screening.
            Satrec.twoline2rv(line1, line2)
            objects.append(
                OrbitalObject(
                    norad_id=int(row["NORAD_CAT_ID"]),
                    name=str(row["OBJECT_NAME"]).strip() or f"NORAD {row['NORAD_CAT_ID']}",
                    object_type=type_value,
                    tle_line1=line1,
                    tle_line2=line2,
                    epoch=_parse_epoch(str(row["EPOCH"])),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not objects:
        raise CatalogError("CelesTrak returned no valid GP/TLE records")
    return objects


def fetch_catalog(url: str, limit: int, timeout_seconds: float = 20.0) -> list[OrbitalObject]:
    """Fetch the public CelesTrak catalog synchronously for the headless job."""
    try:
        response = httpx.get(url, timeout=timeout_seconds, follow_redirects=True)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CatalogError(f"Could not fetch CelesTrak catalog: {exc}") from exc
    if not isinstance(payload, list):
        raise CatalogError("CelesTrak response was not a JSON list")
    return parse_catalog_rows(payload, limit)
