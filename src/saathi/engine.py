"""Deterministic eligibility engine.

The LLM never decides eligibility. Rules live in ``schemes.json`` and are
evaluated here, so results are reproducible, testable and explainable.

Each scheme has ``rules`` with optional ``all`` (every condition must hold) and
``any`` (at least one must hold) groups. A condition on a field the user has
not told us yet is *unknown*; it never silently passes or fails.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DATA_FILE = Path(__file__).parent / "schemes.json"

ELIGIBLE, LIKELY, NOT_ELIGIBLE = "eligible", "likely", "not_eligible"

FIELD_LABELS = {
    "age": "your age",
    "gender": "your gender (male / female / other)",
    "occupation": "your occupation (farmer / student / self_employed / salaried / unemployed / homemaker / retired)",
    "annual_family_income": "your annual family income in rupees",
    "social_category": "your social category (general / obc / sc / st)",
    "owns_land": "whether you own agricultural land",
    "owns_pucca_house": "whether your family owns a pucca house",
    "is_bpl": "whether your household is BPL / has a ration card for poor families",
    "has_bank_account": "whether you have a bank account",
    "has_girl_child_under_10": "whether you have a girl child below 10 years",
    "is_student": "whether you are currently a student",
    "wants_business": "whether you want to start or expand a business",
}


@dataclass
class Profile:
    age: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    annual_family_income: Optional[int] = None
    social_category: Optional[str] = None
    owns_land: Optional[bool] = None
    owns_pucca_house: Optional[bool] = None
    is_bpl: Optional[bool] = None
    has_bank_account: Optional[bool] = None
    has_girl_child_under_10: Optional[bool] = None
    is_student: Optional[bool] = None
    wants_business: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        known = set(cls.__dataclass_fields__)
        clean = {k: v for k, v in (data or {}).items() if k in known and v not in (None, "")}
        for key in ("gender", "occupation", "social_category"):
            if isinstance(clean.get(key), str):
                clean[key] = clean[key].strip().lower().replace(" ", "_")
        if clean.get("occupation") == "student":
            clean.setdefault("is_student", True)
        return cls(**clean)


@dataclass
class Match:
    id: str
    name: str
    category: str
    status: str
    benefit: str
    documents: list[str]
    apply_url: str
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@lru_cache(maxsize=1)
def load_schemes() -> dict[str, Any]:
    with DATA_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def _check(cond: dict[str, Any], profile: Profile) -> Optional[bool]:
    """Return True / False, or None when the profile lacks the field."""
    actual = getattr(profile, cond["field"])
    if actual is None:
        return None
    op, expected = cond["op"], cond.get("value")
    if op == "eq":
        return actual == expected
    if op == "in":
        return actual in expected
    if op == "gte":
        return actual >= expected
    if op == "lte":
        return actual <= expected
    if op == "between":
        return expected[0] <= actual <= expected[1]
    if op == "is_true":
        return actual is True
    if op == "is_false":
        return actual is False
    raise ValueError(f"Unknown operator: {op}")


def _describe(cond: dict[str, Any]) -> str:
    f, op, v = cond["field"].replace("_", " "), cond["op"], cond.get("value")
    if op == "between":
        return f"{f} is between {v[0]} and {v[1]}"
    return {
        "eq": f"{f} is {v}", "in": f"{f} is one of {v}", "gte": f"{f} is at least {v}",
        "lte": f"{f} is at most {v}", "is_true": f"{f}: yes", "is_false": f"{f}: no",
    }[op]


def evaluate(scheme: dict[str, Any], profile: Profile) -> Match:
    rules = scheme["rules"]
    all_res = [(c, _check(c, profile)) for c in rules.get("all", [])]
    any_res = [(c, _check(c, profile)) for c in rules.get("any", [])]

    reasons: list[str] = []
    missing: list[str] = []
    failed = False

    for cond, res in all_res:
        if res is False:
            failed = True
            reasons.append(f"Does not meet: {_describe(cond)}")
        elif res is None:
            missing.append(cond["field"])
        else:
            reasons.append(f"Meets: {_describe(cond)}")

    if any_res:
        passed = [c for c, r in any_res if r is True]
        unknown = [c for c, r in any_res if r is None]
        if passed:
            reasons.append(f"Meets: {_describe(passed[0])}")
        elif unknown:
            missing.extend(c["field"] for c in unknown)
        else:
            failed = True
            reasons.append("Does not meet any of: " + " OR ".join(_describe(c) for c, _ in any_res))

    status = NOT_ELIGIBLE if failed else (LIKELY if missing else ELIGIBLE)
    return Match(
        id=scheme["id"], name=scheme["name"], category=scheme["category"], status=status,
        benefit=scheme["benefit"], documents=scheme["documents"], apply_url=scheme["apply_url"],
        reasons=reasons, missing_fields=sorted(set(missing)),
    )


def find_schemes(profile: Profile) -> dict[str, Any]:
    """Evaluate every scheme; return grouped results plus what to ask next."""
    data = load_schemes()
    matches = [evaluate(s, profile) for s in data["schemes"]]
    need = sorted({f for m in matches if m.status == LIKELY for f in m.missing_fields})
    return {
        "eligible": [m.to_dict() for m in matches if m.status == ELIGIBLE],
        "likely_need_more_info": [m.to_dict() for m in matches if m.status == LIKELY],
        "not_eligible_count": sum(m.status == NOT_ELIGIBLE for m in matches),
        "ask_user_next": [FIELD_LABELS[f] for f in need],
        "disclaimer": data["_meta"]["disclaimer"],
    }


def get_scheme(scheme_id: str) -> Optional[dict[str, Any]]:
    for s in load_schemes()["schemes"]:
        if s["id"] == scheme_id:
            return s
    return None
