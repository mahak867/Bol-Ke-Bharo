"""Privacy helpers: nothing sensitive leaves the browser session unmasked."""
import re

# 12-digit Aadhaar, spoken/typed with optional spaces or dashes: "1234 5678 9012"
_AADHAAR = re.compile(r"(?<!\d)(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})(?!\d)")
# OTP-like requests: we never want them in a transcript
_OTP_WORDS = re.compile(r"\b(otp|ओटीपी|pin|पिन|password|पासवर्ड)\b", re.I)


def mask_aadhaar(text: str) -> str:
    """Replace any full Aadhaar number with XXXX XXXX + last 4 digits."""
    return _AADHAAR.sub(lambda m: f"XXXX XXXX {m.group(3)}", text)


def mentions_secret(text: str) -> bool:
    return bool(_OTP_WORDS.search(text))


def mask_for_display(field: dict, value) -> str:
    if field.get("sensitive"):
        return f"XXXX XXXX {value}"
    return str(value)
