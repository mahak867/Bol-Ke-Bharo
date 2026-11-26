"""Rejection guard: cross-field rules declared in the schema.

Rules are data, never code - each rule type is implemented here, so a schema
cannot run arbitrary expressions.
"""
from . import names


def _failure(rule: dict, fields: list[str], fmt: dict, message_key: str = "message", **extra) -> dict:
    """One failed rule, with its label, spoken message and on-screen detail all taken from the schema."""
    message = rule.get(message_key, rule["message"])
    out = {"id": rule["id"], "fields": fields, "label": rule.get("label", {"en": rule["id"]}),
           "message": message["hi"].format(**fmt), **extra}
    if "detail" in rule:
        out["detail"] = rule["detail"]["en"].format(**fmt)
    return out


def check(schema: dict, values: dict) -> list[dict]:
    """Return failed rules. Rules whose fields are not filled yet are skipped."""
    # Values plus their portal (Latin) spelling, for use in messages: {name}, {name_latin}.
    fmt = dict(values) | {f"{k}_latin": names.to_latin(v) for k, v in values.items() if isinstance(v, str)}
    failures = []
    for rule in schema.get("rules", []):
        t = rule["type"]
        if t == "min":
            v = values.get(rule["field"])
            if v is not None and v < rule["value"]:
                failures.append(_failure(rule, [rule["field"]], fmt))
        elif t == "must_be_true":
            if values.get(rule["field"]) is False:
                failures.append(_failure(rule, [rule["field"]], fmt))
        elif t == "name_match":
            a, b = values.get(rule["a"]), values.get(rule["b"])
            # Same name in another script (रामवती / Ramvati) is fine. Any other difference, even a
            # space, is a rejection risk because portals compare names exactly.
            if a is not None and b is not None:
                result = names.compare(a, b)
                if result["verdict"] != "same":
                    key = "message_different" if result["verdict"] == "different" else "message"
                    failures.append(_failure(rule, [rule["a"], rule["b"]], fmt, key,
                                             verdict=result["verdict"], similarity=result["similarity"]))
        else:
            raise ValueError(f"unknown rule type {t!r} in {rule['id']}")
    return failures
