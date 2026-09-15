"""
test_ocr_processor.py — Unit tests for ocr_processor.py [v2]

Scaffolded Day 2, completed Day 3. No real Tesseract call is made: OCR
availability, PIL and pytesseract are all patched, so these run identically on a
machine with no OCR engine installed.
"""
from unittest.mock import patch, MagicMock


def test_ocr_disabled_returns_none():
    """When OCR_ENABLED=false, ocr_page must return None without calling Tesseract."""
    with patch("app.services.ocr_processor.OCR_ENABLED", False):
        from app.services.ocr_processor import ocr_page
        result = ocr_page(MagicMock())
        assert result is None


def test_ocr_unavailable_returns_none():
    """When Tesseract is not installed, ocr_page must return None gracefully."""
    with patch("app.services.ocr_processor.is_ocr_available", return_value=False):
        from app.services.ocr_processor import ocr_page
        result = ocr_page(MagicMock())
        assert result is None


def test_is_ocr_available_returns_bool():
    """is_ocr_available must return a bool in all environments."""
    from app.services.ocr_processor import is_ocr_available
    result = is_ocr_available()
    assert isinstance(result, bool)


def test_ocr_page_returns_text_on_success():
    """With mocked PyMuPDF rendering + pytesseract, ocr_page must return the OCR text."""
    from app.services.ocr_processor import ocr_page

    mock_page = MagicMock()
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = b"fake-png-bytes"
    mock_page.get_pixmap.return_value = mock_pix

    with patch("app.services.ocr_processor.is_ocr_available", return_value=True), \
         patch("PIL.Image.open", return_value=MagicMock()), \
         patch("pytesseract.image_to_string", return_value="Recovered OCR text"):
        result = ocr_page(mock_page)

    assert result == "Recovered OCR text"


def test_ocr_page_returns_none_when_ocr_yields_empty_text():
    """If Tesseract returns only whitespace, ocr_page must return None (page stays textless)."""
    from app.services.ocr_processor import ocr_page

    mock_page = MagicMock()
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = b"fake-png-bytes"
    mock_page.get_pixmap.return_value = mock_pix

    with patch("app.services.ocr_processor.is_ocr_available", return_value=True), \
         patch("PIL.Image.open", return_value=MagicMock()), \
         patch("pytesseract.image_to_string", return_value="   \n  "):
        result = ocr_page(mock_page)

    assert result is None
