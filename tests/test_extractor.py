from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.extractor import ExtractError, extract_receipt_data

NIGERIAN_RECEIPT_JSON = """
{
  "vendor": "Shoprite Ikeja",
  "date": "2026-10-05",
  "currency": "NGN",
  "total": 15250.00,
  "tax": 1125.00,
  "items": [
    {"name": "Rice 5kg", "qty": 1, "unit_price": 8200.00, "amount": 8200.00},
    {"name": "Vegetable Oil", "unit_price": 4300.00, "amount": 4300.00},
    {"name": "Bread", "qty": 2, "unit_price": 1375.00, "amount": 2750.00}
  ],
  "suggested_category": "Food"
}
"""


@dataclass
class _FakeMessage:
    content: str


@dataclass
class _FakeResponse:
    message: _FakeMessage


class _FakeOllamaClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    def chat(self, **_: object) -> _FakeResponse:
        self.calls += 1
        return _FakeResponse(message=_FakeMessage(content=self.content))


def test_extract_receipt_data_valid_json_parse() -> None:
    client = _FakeOllamaClient(NIGERIAN_RECEIPT_JSON)

    data = extract_receipt_data("This is a valid OCR payload with enough text.", client=client)

    assert data.vendor == "Shoprite Ikeja"
    assert data.currency == "NGN"
    assert data.tax == 1125.0
    assert len(data.items) == 3
    assert data.items[0].name == "Rice 5kg"
    assert client.calls == 1


def test_extract_receipt_data_repairs_wrapped_json_once() -> None:
    wrapped = f"model preface\n{NIGERIAN_RECEIPT_JSON}\ntrailing notes"
    client = _FakeOllamaClient(wrapped)

    data = extract_receipt_data("Receipt line one and line two with sufficient text.", client=client)

    assert data.vendor == "Shoprite Ikeja"
    assert data.total == 15250.0


def test_extract_receipt_data_defaults_qty_and_null_tax() -> None:
    content = """
    {
      "vendor": "Ebeano Supermarket",
      "date": "2026-09-13",
      "currency": "NGN",
      "total": 5200.00,
      "tax": null,
      "items": [{"name": "Milk", "qty": null, "unit_price": 2600.00, "amount": 5200.00}],
      "suggested_category": "Food"
    }
    """
    client = _FakeOllamaClient(content)

    data = extract_receipt_data("Adequate OCR text for defaults check in extractor.", client=client)

    assert data.tax is None
    assert len(data.items) == 1
    assert data.items[0].qty == 1


def test_extract_receipt_data_raises_for_too_short_ocr_text() -> None:
    client = _FakeOllamaClient(NIGERIAN_RECEIPT_JSON)

    with pytest.raises(ExtractError):
        extract_receipt_data("too short", client=client)

    assert client.calls == 0
