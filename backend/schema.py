"""Load form schemas and coerce raw extracted values to each field's type."""
import json
import re
from pathlib import Path

from .lexicon import DIGITS, NO, YES

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def load_schema(form_id: str) -> dict:
    if not re.fullmatch(r"[a-z0-9_]+", form_id):
        raise ValueError(f"bad form id: {form_id!r}")
    path = SCHEMA_DIR / f"{form_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_schemas() -> list[str]:
    return sorted(p.stem for p in SCHEMA_DIR.glob("*.json") if not p.stem.startswith("_"))


def field_map(schema: dict) -> dict[str, dict]:
    return {f["key"]: f for f in schema["fields"]}


_YES = YES | {"true", "y", "1"}
_NO = NO | {"false", "n", "0"}


def coerce(field: dict, raw):
    """Return the value in the field's type, or raise ValueError."""
    if raw is None:
        raise ValueError("empty")
    t = field["type"]
    s = str(raw).strip().translate(DIGITS)
    if t == "int":
        numbers = re.findall(r"\d+(?:\.\d+)?", re.sub(r"(?<=\d),(?=\d)", "", s))   # "30,000" -> 30000
        if len(numbers) != 1:   # "65-70" or "1.5 lakh" is ambiguous: ask again rather than guess
            raise ValueError(f"need exactly one number: {s!r}")
        return int(float(numbers[0]))
    if t == "bool":
        low = s.lower()
        if low in _YES:
            return True
        if low in _NO:
            return False
        raise ValueError(f"not yes/no: {s!r}")
    if t == "enum":
        low = s.lower()
        if low not in field["options"]:
            raise ValueError(f"{s!r} not in {field['options']}")
        return low
    # string
    if field.get("pattern"):
        compact = re.sub(r"[\s-]", "", s).upper() if field["key"] == "ifsc" else re.sub(r"[\s-]", "", s)
        if not re.fullmatch(field["pattern"], compact):
            raise ValueError(f"{s!r} does not match pattern")
        return compact
    if not s:
        raise ValueError("empty")
    return s
