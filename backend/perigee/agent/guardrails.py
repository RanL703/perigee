"""Advisory guardrail enforcement for local-model output.

The deterministic pipeline never depends on this module. Its job is to keep
model-generated prose inside the advisory boundary defined by PRD 5.6: no
collision-probability figures, no maneuver/avoidance directives, no
machine-executable commands. Unsafe sentences are removed rather than failing
the whole response, so a single slip of phrasing no longer discards an
otherwise grounded answer.
"""

import re

_FORBIDDEN_PATTERN = re.compile(
    r"\b("
    r"manoeuvre|maneuver|avoidance|avoid\s+collisions?|collision-avoidance"
    r"|probability|probable|likelihood|odds|chance\s+of\s+collision"
    r"|approv(?:e|es|ed|al)|reject(?:s|ed|ing|ion)?"
    r"|execute\s+command|command\s+execution|fire\s+thrusters?"
    r")\b",
    re.IGNORECASE,
)
_PROBABILITY_FIGURE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|percent(?:age)?\b|\s?(?:in|chance|odds)\b)", re.IGNORECASE
)
_SEGMENT_SPLIT = re.compile(r"(?<=[.!?:])\s+|\n+")


def _is_unsafe(segment: str) -> bool:
    return bool(_FORBIDDEN_PATTERN.search(segment) or _PROBABILITY_FIGURE.search(segment))


def sanitize_advisory_text(text: str) -> str:
    """Return `text` with unsafe sentences removed.

    Raises ValueError when nothing advisory-safe remains, so callers still
    fail closed to their deterministic template instead of emitting risky copy.
    """
    segments = [segment.strip() for segment in _SEGMENT_SPLIT.split(text) if segment.strip()]
    safe = [re.sub(r"^[-*•]\s*", "", segment).strip() for segment in segments if not _is_unsafe(segment)]
    cleaned = " ".join(segment for segment in safe if segment)
    if not cleaned:
        raise ValueError("Agent output contained only guarded content")
    return cleaned


def safe_advisory_text(text: str) -> str | None:
    """Sanitized text, or None when the whole fragment was guarded content."""
    try:
        return sanitize_advisory_text(text)
    except ValueError:
        return None
