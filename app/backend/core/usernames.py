import re


def normalize_username_seed(value: str, *, fallback: str = "user") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    if not normalized:
        normalized = fallback

    if normalized[0].isdigit():
        normalized = f"{fallback}_{normalized}"

    if len(normalized) < 3:
        normalized = f"{fallback}_{normalized}"

    return normalized[:32].rstrip("_") or fallback
