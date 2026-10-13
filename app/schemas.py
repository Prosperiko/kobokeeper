from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class LineItemData(BaseModel):
    """Structured representation of one extracted receipt line item."""

    name: str | None = None
    qty: float = 1
    unit_price: float | None = None
    amount: float | None = None

    @field_validator("qty", mode="before")
    @classmethod
    def default_qty(cls, value: object) -> float:
        """Apply phase rule: missing quantity defaults to 1."""

        if value in (None, ""):
            return 1
        return float(value)


class ReceiptData(BaseModel):
    """Structured output expected from the OCR+LLM extraction pipeline."""

    vendor: str | None = None
    date: str | None = None
    currency: str = "NGN"
    total: float | None = None
    tax: float | None = None
    items: list[LineItemData] = Field(default_factory=list)
    suggested_category: str | None = None
