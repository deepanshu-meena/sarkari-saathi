import json

from saathi.engine import ELIGIBLE, LIKELY, NOT_ELIGIBLE, Profile, evaluate, find_schemes, get_scheme, load_schemes
from saathi.lambda_handler import handler


def status(scheme_id, **kw):
    return evaluate(get_scheme(scheme_id), Profile.from_dict(kw)).status


def test_pm_kisan_eligible_and_not():
    assert status("pm-kisan", occupation="farmer", owns_land=True) == ELIGIBLE
    assert status("pm-kisan", occupation="salaried", owns_land=True) == NOT_ELIGIBLE


def test_unknown_fields_are_likely_not_eligible():
    assert status("pm-kisan", occupation="farmer") == LIKELY
    assert status("pm-kisan") == LIKELY


def test_any_group():
    assert status("pm-jay", age=72) == ELIGIBLE          # age >= 70
    assert status("pm-jay", is_bpl=True) == ELIGIBLE
    assert status("pm-jay", age=30, is_bpl=False) == NOT_ELIGIBLE
    assert status("pm-jay", age=30) == LIKELY            # BPL unknown


def test_age_boundaries():
    assert status("atal-pension", age=18, has_bank_account=True) == ELIGIBLE
    assert status("atal-pension", age=40, has_bank_account=True) == ELIGIBLE
    assert status("atal-pension", age=41, has_bank_account=True) == NOT_ELIGIBLE


def test_stand_up_india_all_plus_any():
    base = dict(age=30, wants_business=True)
    assert status("stand-up-india", gender="female", **base) == ELIGIBLE
    assert status("stand-up-india", gender="male", social_category="st", **base) == ELIGIBLE
    assert status("stand-up-india", gender="male", social_category="general", **base) == NOT_ELIGIBLE


def test_student_occupation_implies_is_student():
    assert Profile.from_dict({"occupation": "Student"}).is_student is True


def test_input_normalisation_and_unknown_keys_ignored():
    p = Profile.from_dict({"gender": " Female ", "occupation": "Self Employed", "bogus": 1})
    assert (p.gender, p.occupation) == ("female", "self_employed")


def test_find_schemes_shape_and_data_integrity():
    res = find_schemes(Profile.from_dict({"age": 34, "gender": "female", "occupation": "farmer",
                                          "owns_land": True, "is_bpl": True, "has_bank_account": True}))
    ids = {m["id"] for m in res["eligible"]}
    assert {"pm-kisan", "pm-jay", "pm-ujjwala", "atal-pension"} <= ids
    assert res["disclaimer"]
    for s in load_schemes()["schemes"]:  # every scheme is well-formed
        assert s["id"] and s["benefit"] and s["documents"] and s["apply_url"].startswith("https://")


def _evt(method, path, body=None):
    return {"rawPath": path, "requestContext": {"http": {"method": method}}, "body": json.dumps(body) if body else None}


def test_lambda_handler():
    r = handler(_evt("POST", "/eligibility", {"age": 72}))
    assert r["statusCode"] == 200 and "pm-jay" in r["body"]
    assert handler(_evt("GET", "/schemes"))["statusCode"] == 200
    assert handler(_evt("GET", "/nope"))["statusCode"] == 404
    bad = handler({"rawPath": "/eligibility", "requestContext": {"http": {"method": "POST"}}, "body": "{oops"})
    assert bad["statusCode"] == 400
