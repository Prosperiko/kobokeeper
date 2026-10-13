from __future__ import annotations

import re
from difflib import SequenceMatcher, get_close_matches

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Receipt, Vendor


def normalize_vendor(name: str) -> str:
    """
    Normalize vendor text into a stable key for fuzzy comparison.

    The normalization intentionally uses only stdlib primitives so the
    "learning loop" works fully offline and remains easy to audit in the
    competition write-up: lowercase, strip punctuation, and collapse spacing.
    """

    lowered = name.lower().strip()
    no_punct = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", no_punct).strip()


def lookup(db: Session, name: str) -> tuple[Vendor | None, float]:
    """
    Fuzzy match a vendor name against known vendor names and aliases.

    Returns the matched vendor and confidence score in the [0, 1] range.
    A cutoff of 0.75 keeps recall high enough for noisy OCR while reducing
    accidental cross-vendor matches for short or generic names.
    """

    normalized_input = normalize_vendor(name)
    if not normalized_input:
        return None, 0.0

    vendors = db.scalars(select(Vendor)).all()
    index_to_vendor: dict[str, Vendor] = {}
    candidates: list[str] = []

    for vendor in vendors:
        normalized_name = normalize_vendor(vendor.name)
        if normalized_name:
            candidates.append(normalized_name)
            index_to_vendor[normalized_name] = vendor
        for alias in vendor.aliases or []:
            normalized_alias = normalize_vendor(alias)
            if normalized_alias:
                candidates.append(normalized_alias)
                index_to_vendor[normalized_alias] = vendor

    if not candidates:
        return None, 0.0

    matches = get_close_matches(normalized_input, candidates, n=1, cutoff=0.75)
    if not matches:
        return None, 0.0

    best_key = matches[0]
    confidence = SequenceMatcher(a=normalized_input, b=best_key).ratio()
    return index_to_vendor[best_key], confidence


def learn(db: Session, receipt: Receipt) -> None:
    """
    Learn from a confirmed receipt to improve future vendor/category prefill.

    If the vendor already exists, store a normalized alias once so future OCR
    variants still map correctly. If not, create a new vendor and attach the
    user-confirmed category as its default, which is the core "gets smarter"
    product loop after every confirmation.
    """

    vendor_name = receipt.vendor_name.strip()
    if not vendor_name:
        return

    existing_vendor, _ = lookup(db, vendor_name)
    normalized_alias = normalize_vendor(vendor_name)

    if existing_vendor:
        aliases = existing_vendor.aliases or []
        normalized_aliases = {normalize_vendor(alias) for alias in aliases}
        if normalized_alias and normalized_alias not in normalized_aliases:
            aliases.append(vendor_name)
            existing_vendor.aliases = aliases
        if receipt.category_id and existing_vendor.default_category_id is None:
            existing_vendor.default_category_id = receipt.category_id
        return

    category_id = receipt.category_id
    if category_id is None:
        other = db.scalar(select(Category).where(Category.name == "Other"))
        category_id = other.id if other else None

    db.add(
        Vendor(
            name=vendor_name,
            aliases=[vendor_name] if normalized_alias else [],
            default_category_id=category_id,
        )
    )
