"""Selected unchanged helpers from Resume Matcher improver.py at 9c05e423. Apache-2.0."""
from __future__ import annotations
import re
from typing import Any

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?above",
    r"forget\s+(everything|all)",
    r"new\s+instructions?:",
    r"system\s*:",
    r"<\s*/?\s*system\s*>",
    r"\[\s*INST\s*\]",
    r"\[\s*/\s*INST\s*\]",
]

def _validate_string_list_field(
    result: dict[str, Any],
    field: str,
) -> list[str]:
    """Return a normalized required list of non-empty strings."""
    value = result.get(field)
    if not isinstance(value, list):
        raise ValueError(f"LLM response requires a '{field}' list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"LLM response field '{field}' must contain text")
    return [item.strip() for item in value]

def _sanitize_user_input(text: str) -> str:
    """LLM-011: Sanitize user input to prevent prompt injection.

    Removes or redacts common injection patterns that could manipulate LLM behavior.
    """
    sanitized = text
    for pattern in _INJECTION_PATTERNS:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized
