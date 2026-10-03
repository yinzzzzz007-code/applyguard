"""Upstream ASu Resume Skills metric arithmetic, copied without modification.

Source: Claycui828/ASu-resume-skills, commit
f460582b1a48c7770496d7999ae3a14a2ce0452b,
skills/asu-resume-audit-skill/scripts/validate_report.py (fail, validate_metric).
Copyright (c) 2026 Claycui828.
See THIRD_PARTY_NOTICES.md and third_party_licenses/ASu-MIT.txt.
"""

from __future__ import annotations

import math


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_metric(claim: dict, errors: list[str]) -> None:
    metric = claim.get("metric")
    if metric is None:
        return

    cid = claim.get("id", "<无编号>")
    if not isinstance(metric, dict):
        fail(errors, f"{cid} metric 必须是对象")
        return

    ratio_keys = {"numerator", "denominator", "displayed_percent"}
    if ratio_keys <= set(metric):
        try:
            expected = float(metric["numerator"]) / float(metric["denominator"]) * 100
            displayed = float(metric["displayed_percent"])
        except (TypeError, ValueError, ZeroDivisionError):
            fail(errors, f"{cid} metric 指标字段无法计算")
        else:
            if not math.isclose(expected, displayed, abs_tol=0.5):
                fail(errors, f"{cid} metric 百分比与分子分母不一致")

    change_keys = {"baseline", "result", "change_type", "displayed_change"}
    if not change_keys <= set(metric):
        return

    try:
        baseline = float(metric["baseline"])
        result = float(metric["result"])
        displayed_change = float(metric["displayed_change"])
    except (TypeError, ValueError):
        fail(errors, f"{cid} metric 变化字段无法计算")
        return

    change_type = metric["change_type"]
    if change_type == "relative_percent":
        if baseline == 0:
            fail(errors, f"{cid} metric 相对百分比变化的 baseline 不能为 0")
            return
        expected_change = (result - baseline) / baseline * 100
    elif change_type == "percentage_points":
        expected_change = result - baseline
    else:
        fail(errors, f"{cid} metric change_type 非法：{change_type}")
        return

    if not math.isclose(expected_change, displayed_change, abs_tol=0.5):
        fail(errors, f"{cid} metric 变化值与基线结果不一致")
