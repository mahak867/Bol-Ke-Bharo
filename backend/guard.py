"""Rejection guard: cross-field rules declared in the schema.

Rules are data, never code - each rule type is implemented here, so a schema
cannot run arbitrary expressions.
"""
from difflib import SequenceMatcher


def _norm(s: str) -> str:
    return " ".join(str(s).lower().split())


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a).replace(" ", ""), _norm(b).replace(" ", "")).ratio()


def check(schema: dict, values: dict) -> list[dict]:
    """Return failed rules as {id, fields, message}. Rules whose fields are not filled yet are skipped."""
    failures = []
    for rule in schema.get("rules", []):
        t = rule["type"]
        fmt = {k: v for k, v in values.items()}
        if t == "min":
            v = values.get(rule["field"])
            if v is not None and v < rule["value"]:
                failures.append({"id": rule["id"], "fields": [rule["field"]],
                                 "message": rule["message"]["hi"].format(**fmt)})
        elif t == "must_be_true":
            v = values.get(rule["field"])
            if v is False:
                failures.append({"id": rule["id"], "fields": [rule["field"]],
                                 "message": rule["message"]["hi"].format(**fmt)})
        elif t == "name_match":
            a, b = values.get(rule["a"]), values.get(rule["b"])
            # Portals match names exactly, so any difference (even spacing) is a rejection risk.
            if a is not None and b is not None and _norm(a) != _norm(b):
                failures.append({"id": rule["id"], "fields": [rule["a"], rule["b"]],
                                 "similarity": round(name_similarity(a, b), 2),
                                 "message": rule["message"]["hi"].format(**fmt)})
        else:
            raise ValueError(f"unknown rule type {t!r} in {rule['id']}")
    return failures
