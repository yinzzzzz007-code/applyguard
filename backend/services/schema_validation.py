"""Validate C module boundaries against the frozen Draft 2020-12 contracts."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


_CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


@lru_cache(maxsize=9)
def _validator(name: str) -> Draft202012Validator:
    allowed = {path.stem.removesuffix(".schema") for path in _CONTRACTS.glob("*.schema.json")}
    if name not in allowed:
        raise ValueError(f"Unknown contract: {name}")
    with (_CONTRACTS / f"{name}.schema.json").open(encoding="utf-8") as stream:
        schema = json.load(stream)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_contract(name: str, value: dict[str, Any]) -> None:
    def finite(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError(f"{name} contains a non-finite number")
        if isinstance(item, dict):
            for child in item.values():
                finite(child)
        elif isinstance(item, list):
            for child in item:
                finite(child)
    finite(value)
    errors = sorted(_validator(name).iter_errors(value), key=lambda error: tuple(str(part) for part in error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<root>"
        raise ValueError(f"{name} schema error at {location}: {error.message}")
