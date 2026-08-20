"""Verified live-company INNs — shared constants for seed, enrich, and queue filters."""

# Five companies seeded with verified facts only (no social re-search).
LIVE_SEED_INNS = frozenset({
    "4217184336",   # ООО «СУПЕР СИЛА»
    "771579995573",  # ИП Елисеев — terminated, excluded from live queue
    "7801711200",   # АО «ИМ»
    "9709052492",   # ООО «МОЛОЧНЫЙ ДОМ»
    "9103100540",   # ООО «РУСЬ»
})

# Habr Career buyer seeds — trigger-only, skip social re-search on enrich.
HABR_BUYER_SEED_INNS = frozenset({
    "7706729736",   # АО «Гринатом»
    "7702235133",   # Банк России
    "7812014560",   # ПАО «МегаФон»
    "7705986635",   # АО «УК Аэропорты Регионов»
    "6165115558",   # АО «Автоформула»
    "7708400979",   # ООО «МКК А ДЕНЬГИ»
    "6670381056",   # ООО «Екатеринбург Яблоко»
    "7736279160",   # ООО «Облачные технологии» / Cloud.ru
    "7707067683",   # ПАО «СК Росгосстрах»
    "9710089137",   # ООО «ГРИ»
    "5401305707",   # ООО «НЛ Континент»
    "4217204769",   # АО «СГМК»
})

# 1C integrators — never seed as buyer signals.
INTEGRATOR_INNS = frozenset({
    "5835090155",   # ООО «Джетлин»
    "7811090505",   # КОРУС
    "9715350151",   # Aston
    "9731028047",   # Лоция
    "9707055441",   # AGIMA
})

# Closed / terminated entities — must not appear in active company queue.
INACTIVE_COMPANY_INNS = frozenset({
    "771579995573",
})


def skip_social_discovery(inn: str) -> bool:
    """Do not re-run TenChat / Setka / LinkedIn discovery for seeded companies."""
    key = (inn or "").strip()
    return key in LIVE_SEED_INNS or key in HABR_BUYER_SEED_INNS


def is_integrator(inn: str) -> bool:
    return bool(inn and inn.strip() in INTEGRATOR_INNS)


def is_active_company(inn: str) -> bool:
    return bool(inn and inn.strip() not in INACTIVE_COMPANY_INNS)
