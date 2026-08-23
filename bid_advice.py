"""Go / no-go for a procurement notice from seller offer + tender facts."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

VERDICT_GO = "go"
VERDICT_NO = "no_go"
VERDICT_REVIEW = "review"

VERDICT_LABELS = {
    VERDICT_GO: "Стоит смотреть",
    VERDICT_NO: "Скорее не участвовать",
    VERDICT_REVIEW: "Нужно уточнить",
}


def _tokens(text: str) -> List[str]:
    blob = (text or "").lower()
    raw = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]{3,}", blob)
    extra = re.findall(r"1[cс]", blob)
    stop = {
        "для", "при", "без", "или", "это", "наш", "компании", "компания",
        "поставка", "услуга", "услуги", "работы", "право",
    }
    out: List[str] = []
    seen = set()
    for t in extra + raw:
        if t in stop or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _overlap(offer_tokens: List[str], blob: str) -> List[str]:
    blob_l = (blob or "").lower()
    title_tokens = set(_tokens(blob_l))
    matched: List[str] = []
    for token in offer_tokens:
        if token in title_tokens or token in blob_l:
            matched.append(token)
            continue
        if len(token) >= 5 and token[:5] in blob_l:
            matched.append(token)
    return matched


def parse_money(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").replace(",", ".")
    matches = re.findall(r"(\d[\d\s]{2,}\d(?:\.\d{1,2})?)", cleaned)
    if not matches:
        return None
    best = max(matches, key=len)
    try:
        return float(best.replace(" ", ""))
    except ValueError:
        return None


def advise_bid(
    offer: Optional[Dict[str, Any]],
    *,
    title: str = "",
    note: str = "",
    price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Structured hint only — not a win forecast.
    Uses offer keywords and optional min/max deal size.
    """
    offer = offer or {}
    blob = f"{title} {note}".strip()
    reasons: List[str] = []
    product = " ".join([
        offer.get("product_name") or "",
        offer.get("product_description") or "",
    ])
    offer_tokens = _tokens(product)
    overlap = _overlap(offer_tokens, blob)

    if price is None:
        price = parse_money(blob)

    min_deal = offer.get("min_deal_amount")
    max_deal = offer.get("max_deal_amount")
    try:
        min_deal = float(min_deal) if min_deal not in (None, "") else None
    except (TypeError, ValueError):
        min_deal = None
    try:
        max_deal = float(max_deal) if max_deal not in (None, "") else None
    except (TypeError, ValueError):
        max_deal = None

    if not blob:
        return {
            "verdict": VERDICT_REVIEW,
            "verdict_label": VERDICT_LABELS[VERDICT_REVIEW],
            "reasons": ["В карточке мало данных о предмете закупки — откройте извещение."],
            "price": price,
            "matched_terms": [],
        }

    if not offer_tokens:
        reasons.append("В оффере не задан продукт — рекомендация слабая.")
        verdict = VERDICT_REVIEW
    elif not overlap:
        reasons.append("Предмет закупки не пересекается с тем, что вы продаёте.")
        verdict = VERDICT_NO
    elif len(overlap) == 1:
        reasons.append(f"Слабое совпадение с оффером: {overlap[0]}.")
        verdict = VERDICT_REVIEW
    else:
        reasons.append("Предмет похож на ваш оффер: " + ", ".join(overlap[:5]) + ".")
        verdict = VERDICT_GO

    if price and min_deal and price < min_deal:
        reasons.append(f"НМЦК {price:,.0f} ₽ ниже вашего минимума {min_deal:,.0f} ₽.")
        verdict = VERDICT_NO
    elif price and max_deal and price > max_deal:
        reasons.append(f"НМЦК {price:,.0f} ₽ выше вашего потолка {max_deal:,.0f} ₽.")
        if verdict == VERDICT_GO:
            verdict = VERDICT_REVIEW
    elif price:
        reasons.append(f"НМЦК около {price:,.0f} ₽ — сверьте с вашей себестоимостью.")

    reasons.append("Это не прогноз победы. Документацию и допуски смотрите в извещении.")
    return {
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS[verdict],
        "reasons": reasons,
        "price": price,
        "matched_terms": overlap[:8],
    }
