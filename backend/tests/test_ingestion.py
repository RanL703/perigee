from perigee.domain import ObjectType
from perigee.ingestion.celestrak import parse_catalog_rows


def test_parses_valid_celestrak_gp_json_row() -> None:
    rows = [
        {
            "NORAD_CAT_ID": 25544,
            "OBJECT_NAME": "ISS (ZARYA)",
            "OBJECT_TYPE": "PAYLOAD",
            "EPOCH": "2024-01-01T00:00:00.000000",
            "TLE_LINE1": "1 25544U 98067A   24001.00000000  .00016717  00000+0  30157-3 0  9997",
            "TLE_LINE2": "2 25544  51.6406  33.7703 0005037 102.0979  24.6411 15.50087279431168",
        }
    ]

    result = parse_catalog_rows(rows, limit=10)

    assert len(result) == 1
    assert result[0].norad_id == 25544
    assert result[0].object_type is ObjectType.PAYLOAD
    assert result[0].epoch.tzinfo is not None
