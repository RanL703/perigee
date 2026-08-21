"""Advisory boundary enforcement for local-model output.

The deterministic pipeline never depends on this module. Its job is to keep
model-generated prose inside the advisory boundary defined by PRD 5.6: no
collision-probability figures and no machine-executable or maneuver-directive
language. The model may still *discuss* measures, monitoring, and review
actions freely — only sentences that direct an operational action or assert a
quantified probability are removed. Everything else passes through untouched,
so grounded answers are no longer discarded over a single word.
"""

import re

_PROBABILITY_FIGURE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|percent(?:age)?\b|\s?(?:in|chance|odds)\b)", re.IGNORECASE
)
# Sentences that push an operator toward an operational action (maneuvers,
# burns, avoidance actions) — advisory discussion of such topics is fine.
_DIRECTIVE_ACTION = re.compile(
    r"(?:\b(?:must|should|need(?:s)? to|has? to|recommend(?:s|ed|s)?|advis\w+|"
    r"consider|perform|execute|initiate|conduct|begin|start)\b|"
    r"^\s*(?:maneuver|burn|dodge|avoid)\b)"
    r"[^.!?]*\b(?:maneuver|manoeuvre|burn|thruster|avoidance action|"
    r"collision avoidance|dodge)\b",
    re.IGNORECASE,
)
_MACHINE_COMMAND = re.compile(
    r"\bexecute command\b|\bcommand execution\b|\bfire thrusters?\b",
    re.IGNORECASE,
)
_SEGMENT_SPLIT = re.compile(r"(?<=[.!?:])\s+|\n+")


def _is_unsafe(segment: str) -> bool:
    if _PROBABILITY_FIGURE.search(segment) or _MACHINE_COMMAND.search(segment):
        return True
    return bool(_DIRECTIVE_ACTION.search(segment.strip()))


def sanitize_advisory_text(text: str) -> str:
    """Return `text` with directive/probability sentences removed.

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
