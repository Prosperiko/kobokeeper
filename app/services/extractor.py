from __future__ import annotations

import json
from difflib import get_close_matches
from dataclasses import dataclass
from typing import Any

from ollama import Client
from pydantic import ValidationError

from app.config import get_settings
from app.db import SEED_CATEGORIES
from app.schemas import ReceiptData

EXTRACTION_SYSTEM_PROMPT = (
    "You are KoboKeeper, a receipt parser. Extract the receipt and respond with ONLY "
    "a valid JSON object matching this schema, no markdown fences, no prose: "
    "{vendor, date (YYYY-MM-DD or null), currency (ISO 4217 or 'NGN'), total (number), "
    "tax (number or null), items: [{name, qty (number, default 1), unit_price "
    "(number or null), amount (number)}], suggested_category (one of: "
    + ", ".join(SEED_CATEGORIES)
    + ")}. If a field is not present, use null. Never invent values."
)


@dataclass
class ExtractError(Exception):
    """Raised when extraction cannot produce valid structured JSON."""

    message: str
    raw_text: str

    def __str__(self) -> str:
        return self.message


def _extract_message_content(response: Any) -> str:
    """Read content text from ollama-python response shapes safely."""

    if isinstance(response, dict):
        message = response.get("message", {})
        if isinstance(message, dict):
            return str(message.get("content", ""))
    message_obj = getattr(response, "message", None)
    return str(getattr(message_obj, "content", "")) if message_obj else ""


def _parse_model_json(raw_text: str) -> dict[str, Any]:
    """Parse model text as JSON with one bounded repair attempt."""

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        repaired = raw_text[start : end + 1]
        return json.loads(repaired)


def _normalize_suggested_category(value: object) -> str:
    """Map noisy model category text to one seeded category or fallback Other."""

    if not isinstance(value, str):
        return "Other"
    normalized = value.strip().title()
    if not normalized:
        return "Other"
    if normalized in SEED_CATEGORIES:
        return normalized
    matches = get_close_matches(normalized, SEED_CATEGORIES, n=1, cutoff=0.75)
    return matches[0] if matches else "Other"


def extract_receipt_data(ocr_text: str, client: Client | None = None) -> ReceiptData:
    """
    Convert OCR text into structured receipt data using local Gemma via Ollama.

    The extractor is intentionally strict because this project's core promise is
    deterministic offline bookkeeping: we require JSON output, set temperature to 0,
    and reject short/low-signal OCR text before any model call to avoid wasteful,
    hallucinated results.
    """

    if len(ocr_text.strip()) < 20:
        raise ExtractError(message="OCR text too short for reliable extraction", raw_text=ocr_text)

    settings = get_settings()
    ollama_client = client or Client(host=settings.ollama_host)

    response = ollama_client.chat(
        model=settings.model_name,
        format="json",
        options={"temperature": 0},
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": ocr_text},
        ],
    )
    raw_text = _extract_message_content(response)

    try:
        payload = _parse_model_json(raw_text)
    except json.JSONDecodeError as exc:
        raise ExtractError(message="Model returned invalid JSON", raw_text=raw_text) from exc

    payload["suggested_category"] = _normalize_suggested_category(payload.get("suggested_category"))
    try:
        return ReceiptData.model_validate(payload)
    except ValidationError as exc:
        raise ExtractError(message="Model returned invalid receipt fields", raw_text=raw_text) from exc
