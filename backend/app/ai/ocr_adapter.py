import importlib.util

from app.ai.base import AdapterHealth


class LocalOCRAdapter:
    name = "Local OCR"
    provider = "local-ocr"

    def health_check(self) -> AdapterHealth:
        try:
            pdfplumber_available = importlib.util.find_spec("pdfplumber") is not None
        except ModuleNotFoundError:
            pdfplumber_available = False
        try:
            pymupdf_available = importlib.util.find_spec("fitz") is not None
        except ModuleNotFoundError:
            pymupdf_available = False
        available = pdfplumber_available or pymupdf_available
        return AdapterHealth(
            name=self.name,
            available=available,
            provider=self.provider,
            model_name="pdfplumber/PyMuPDF",
            message="At least one local PDF extraction library is available."
            if available
            else "No local PDF extraction library is installed.",
            setup_hint=None if available else "Install pdfplumber or PyMuPDF before OCR use cases.",
        )
