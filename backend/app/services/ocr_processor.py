"""
ocr_processor.py — OCR fallback for scanned / image-only PDF pages.
Uses PyMuPDF to render a page to an image, then Tesseract via pytesseract.

Implemented: Day 2 (scaffold) → Day 3 (wired into pdf_processor)
"""
import logging
from typing import Optional
from app.config import OCR_ENABLED, OCR_LANGUAGE, OCR_DPI, TESSERACT_CMD_PATH

logger = logging.getLogger(__name__)

# Set Tesseract path from env if provided (needed on Windows when not on PATH)
if TESSERACT_CMD_PATH:
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
    except ImportError:
        pass


def is_ocr_available() -> bool:
    """Return True if Tesseract is installed and reachable."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_page(pdf_page) -> Optional[str]:
    """
    Render a PyMuPDF page object to an image and run OCR on it.

    Args:
        pdf_page — a fitz.Page object

    Returns:
        Extracted text string, or None if OCR failed / is disabled.
    """
    if not OCR_ENABLED:
        logger.debug("OCR is disabled via OCR_ENABLED=false")
        return None

    if not is_ocr_available():
        logger.warning("Tesseract not available — skipping OCR for this page")
        return None

    try:
        import pytesseract
        from PIL import Image
        import io

        # Render page → image at configured DPI (higher = more accurate)
        try:
            import fitz  # PyMuPDF
            mat = fitz.Matrix(OCR_DPI / 72, OCR_DPI / 72)   # 72 is base DPI
            pix = pdf_page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        except Exception as e:
            logger.error("Failed to render PDF page to image: %s", e)
            return None

        # Convert PyMuPDF pixmap → PIL Image
        img_bytes = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes))

        # Run Tesseract OCR
        text = pytesseract.image_to_string(image, lang=OCR_LANGUAGE)

        if text and text.strip():
            logger.debug("OCR extracted %d chars from page", len(text))
            return text

        logger.debug("OCR returned empty text for this page")
        return None

    except Exception as exc:
        logger.error("OCR failed on page: %s", exc)
        return None
