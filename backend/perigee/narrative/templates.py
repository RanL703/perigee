from datetime import UTC, datetime


def format_distance(km: float) -> str:
    return f"{km:.1f} km" if km >= 1 else f"{km * 1000:.0f} m"


def format_velocity(kmps: float) -> str:
    return f"{kmps:.2f} km/s"


def time_to_tca(tca: datetime, *, now: datetime | None = None) -> str:
    seconds = max(0, int((tca - (now or datetime.now(UTC))).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"in {hours}h {minutes}m"
    return f"in {minutes}m"


def relative_time(when: datetime, *, now: datetime | None = None) -> str:
    seconds = max(0, int(((now or datetime.now(UTC)) - when).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m ago"


def event_summary(
    object_a: str, object_b: str, miss_distance_km: float, tca: datetime
) -> str:
    return (
        f"{object_a} and {object_b} will pass within {format_distance(miss_distance_km)} "
        f"of each other {time_to_tca(tca)}."
    )


def factor_caption(name: str, raw_value: float, contribution: float) -> str:
    captions = {
        "miss_distance": f"The predicted gap is {format_distance(raw_value)}; closer passes contribute more risk.",
        "relative_velocity": f"The objects are moving at {format_velocity(raw_value)} relative to each other.",
        "object_type": "The object types increase or reduce operational concern.",
        "trend": "The score is increasing as repeated screenings show a closer pass.",
    }
    return captions.get(name, f"This factor contributes {contribution:.1f} points to the score.")


def object_type_description(object_type: str) -> str:
    return {
        "payload": "Active satellite — operators may be able to maneuver it.",
        "debris": "Debris — it cannot maneuver to avoid a collision.",
        "rocket_body": "Rocket body — an inert upper stage in orbit.",
    }.get(object_type, "Tracked orbital object.")
