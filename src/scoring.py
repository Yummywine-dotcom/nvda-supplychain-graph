"""Explainable confidence scoring.

Weights are fixed so a reviewer can recompute the integer total from the
stored component scores without re-fetching sources.

    confidence = source_authority + independence_directness + timeliness + quantifiable_info
    max        = 40                 + 25                      + 20         + 15
"""

from typing import Mapping

WEIGHTS = {
    "source_authority": 40,
    "independence_directness": 25,
    "timeliness": 20,
    "quantifiable_info": 15,
}

MAX_SCORE = sum(WEIGHTS.values())


def total_score(components: Mapping[str, int]) -> int:
    missing = set(WEIGHTS) - set(components)
    if missing:
        raise ValueError(f"Missing score components: {sorted(missing)}")
    total = 0
    for key, cap in WEIGHTS.items():
        value = int(components[key])
        if value < 0 or value > cap:
            raise ValueError(f"{key}={value} is outside 0-{cap}")
        total += value
    return total


def explain_weights() -> str:
    return (
        "Confidence (0-100) = source_authority (0-40) + independence_directness "
        "(0-25) + timeliness vs cut-off (0-20) + quantifiable_info (0-15). "
        "SEC statutory filings score highest on authority and independence; "
        "issuer newsrooms score lower on independence; older publications "
        "lose timeliness points."
    )
