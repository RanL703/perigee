import httpx
from perigee.domain import ObjectType
from perigee.ingestion.celestrak import fetch_catalog_result, parse_catalog_rows

ROW = {
    "NORAD_CAT_ID": 25544,
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_TYPE": "PAYLOAD",
    "EPOCH": "2024-01-01T00:00:00.000000",
    "TLE_LINE1": "1 25544U 98067A   24001.00000000  .00016717  00000+0  30157-3 0  9997",
    "TLE_LINE2": "2 25544  51.6406  33.7703 0005037 102.0979  24.6411 15.50087279431168",
}
GP_ROW = {
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "EPOCH": "2026-08-20T04:17:29.138208",
    "MEAN_MOTION": 15.49524101,
    "ECCENTRICITY": 0.00076743,
    "INCLINATION": 51.6332,
    "RA_OF_ASC_NODE": 343.3775,
    "ARG_OF_PERICENTER": 65.0551,
    "MEAN_ANOMALY": 295.1235,
    "EPHEMERIS_TYPE": 0,
    "CLASSIFICATION_TYPE": "U",
    "ELEMENT_SET_NO": 999,
    "REV_AT_EPOCH": 58167,
    "BSTAR": 0.00018153585,
    "MEAN_MOTION_DOT": 9.753e-05,
    "MEAN_MOTION_DDOT": 0,
    "NORAD_CAT_ID": 25544,
}


def test_parses_valid_celestrak_gp_json_row() -> None:
    rows = [ROW]

    result = parse_catalog_rows(rows, limit=10)

    assert len(result) == 1
    assert result[0].norad_id == 25544
    assert result[0].object_type is ObjectType.PAYLOAD
    assert result[0].epoch.tzinfo is not None


def test_successful_fetch_is_cached_and_used_when_dns_fails(tmp_path) -> None:
    def live(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[ROW], request=request)

    cache_path = tmp_path / "celestrak.json"
    live_result = fetch_catalog_result(
        "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=JSON",
        limit=1,
        cache_path=cache_path,
        retries=1,
        transport=httpx.MockTransport(live),
    )

    def dns_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("temporary DNS failure", request=request)

    cached_result = fetch_catalog_result(
        "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=JSON",
        limit=1,
        cache_path=cache_path,
        retries=2,
        backoff_seconds=0,
        transport=httpx.MockTransport(dns_failure),
    )

    assert live_result.source == "live"
    assert cached_result.source == "cache"
    assert cached_result.objects[0].norad_id == 25544


def test_parses_current_celestrak_gp_record_without_legacy_tle_lines() -> None:
    result = parse_catalog_rows([GP_ROW], limit=1)

    assert result[0].tle_line1 is None
    assert result[0].tle_line2 is None
    assert result[0].gp_data is not None
    assert result[0].norad_id == 25544
