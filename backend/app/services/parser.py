"""Extract text from uploaded contract files (PDF, DOCX, TXT)."""
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file.
    
    Args:
        file_bytes: Raw bytes of the PDF file.
    
    Returns:
        Extracted text content.
    
    Raises:
        ValueError: If no text could be extracted.
    """
    from pypdf import PdfReader
    
    reader = PdfReader(io.BytesIO(file_bytes))
    text_parts: list[str] = []
    
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    
    text = "\n".join(text_parts).strip()
    if not text:
        raise ValueError("No text extracted from PDF. It may be a scanned document.")
    
    logger.info("Extracted %d characters from PDF (%d pages)", len(text), len(reader.pages))
    return text


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file.
    
    Args:
        file_bytes: Raw bytes of the DOCX file.
    
    Returns:
        Extracted text content.
    """
    from docx import Document
    
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n\n".join(paragraphs).strip()
    
    if not text:
        raise ValueError("No text extracted from DOCX.")
    
    logger.info("Extracted %d characters from DOCX (%d paragraphs)", len(text), len(paragraphs))
    return text


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract text from a TXT file.
    
    Args:
        file_bytes: Raw bytes of the TXT file.
    
    Returns:
        Extracted text content.
    """
    # Try UTF-8 first, fall back to latin-1
    for encoding in ["utf-8", "latin-1"]:
        try:
            text = file_bytes.decode(encoding).strip()
            if text:
                logger.info("Extracted %d characters from TXT (encoding: %s)", len(text), encoding)
                return text
        except UnicodeDecodeError:
            continue
    
    raise ValueError("Could not decode TXT file.")


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from a file based on its extension.
    
    Args:
        file_bytes: Raw bytes of the file.
        filename: Original filename (used to determine type).
    
    Returns:
        Extracted text content.
    
    Raises:
        ValueError: If file type is unsupported or no text extracted.
    """
    suffix = Path(filename).suffix.lower()
    
    extractors = {
        ".pdf": extract_text_from_pdf,
        ".docx": extract_text_from_docx,
        ".txt": extract_text_from_txt,
    }
    
    extractor = extractors.get(suffix)
    if extractor is None:
        raise ValueError(f"Unsupported file type: {suffix}")
    
    return extractor(file_bytes)
