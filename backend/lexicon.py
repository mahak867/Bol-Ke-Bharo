"""Words and characters shared by the extractor, the type coercion and the dialog (one copy only)."""

DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
PUNCT = "।,.?!:;\"'"

YES = {"haan", "han", "ha", "ji", "yes", "sahi", "theek", "हाँ", "हां", "हा", "जी", "सही", "ठीक", "बिल्कुल"}
NO = {"nahi", "nahin", "na", "no", "galat", "नहीं", "नही", "ना", "गलत", "ग़लत"}


def tokens(text: str) -> list[str]:
    """Words with punctuation stripped and Devanagari digits made ASCII."""
    return [t.strip(PUNCT) for t in text.translate(DIGITS).split() if t.strip(PUNCT)]


def answer(text: str) -> str | None:
    """'yes' / 'no' if the utterance opens with one (or says 'no' early), else None."""
    low = [t.lower() for t in tokens(text)]
    if not low:
        return None
    if low[0] in YES:
        return "yes"
    if low[0] in NO or any(t in NO for t in low[:3]):
        return "no"
    return None
