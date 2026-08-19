"""Verified live-company INNs — shared constants for seed, enrich, and queue filters."""

# Five companies seeded with verified facts only (no social re-search).
LIVE_SEED_INNS = frozenset({
    "4217184336",   # ООО «СУПЕР СИЛА»
    "771579995573",  # ИП Елисеев — terminated, excluded from live queue
    "7801711200",   # АО «ИМ»
    "9709052492",   # ООО «МОЛОЧНЫЙ ДОМ»
    "9103100540",   # ООО «РУСЬ»
})

# Closed / terminated entities — must not appear in active company queue.
INACTIVE_COMPANY_INNS = frozenset({
    "771579995573",
})


def skip_social_discovery(inn: str) -> bool:
    """Do not re-run TenChat / Setka / LinkedIn discovery for seeded companies."""
    return bool(inn and inn.strip() in LIVE_SEED_INNS)


def is_active_company(inn: str) -> bool:
    return bool(inn and inn.strip() not in INACTIVE_COMPANY_INNS)
