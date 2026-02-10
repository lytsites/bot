import re


def normalize_phone_digits(raw: str | None) -> str:
    """
    Normalize phone input to digits-only form (e.g. '+7 (708) 123-45-67' -> '77081234567').

    We keep digits-only format because existing DB records/logs use this form.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("PHONE_REQUIRED")
    digits = re.sub(r"\D", "", s)
    if not digits:
        raise ValueError("PHONE_NUMBER_INVALID")
    # E.164 max is 15 digits; minimum depends, but <10 is almost certainly invalid here.
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("PHONE_NUMBER_INVALID")
    return digits


def phone_variants(digits: str) -> tuple[str, str]:
    """
    Provide lookup variants for legacy DB rows that may store phone with or without leading '+'.
    """
    d = re.sub(r"\D", "", str(digits or ""))
    return (d, "+" + d)

