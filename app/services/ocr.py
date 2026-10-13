from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import fitz
from rapidocr_onnxruntime import RapidOCR


@lru_cache(maxsize=1)
def _get_ocr_engine() -> RapidOCR:
    """Create and cache a single RapidOCR engine instance."""

    return RapidOCR()


def _result_to_text(result: Any) -> str:
    """Normalize RapidOCR outputs to a newline-separated text block."""

    if not result:
        return ""
    lines: list[str] = []
    for row in result:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            text = row[1]
            if isinstance(text, str) and text.strip():
                lines.append(text.strip())
    return "\n".join(lines)


def extract_text_from_image(image_path: str) -> str:
    """Run OCR over an image and return normalized text."""

    engine = _get_ocr_engine()
    result, _ = engine(image_path)
    return _result_to_text(result)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Rasterize PDF pages with PyMuPDF and OCR each page with RapidOCR."""

    engine = _get_ocr_engine()
    page_texts: list[str] = []
    with fitz.open(pdf_path) as document:
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            png_bytes = pixmap.tobytes("png")
            result, _ = engine(png_bytes)
            page_texts.append(_result_to_text(result))
    return "\n".join([text for text in page_texts if text])


def extract_text(file_path: str) -> str:
    """Extract OCR text from either an image file or PDF file path."""

    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    return extract_text_from_image(file_path)
