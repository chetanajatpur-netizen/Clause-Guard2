"""Segment contract text into clause-sized chunks."""
import logging
import re

logger = logging.getLogger(__name__)

MIN_CHUNK_LEN = 50
MAX_CHUNK_LEN = 2000


def segment_text(
    text: str,
    min_len: int = MIN_CHUNK_LEN,
    max_len: int = MAX_CHUNK_LEN,
) -> list[str]:
    """Split contract text into clause-sized chunks.
    
    Strategy:
    1. Split on paragraph boundaries (double newlines, section headers)
    2. Merge tiny chunks (< min_len) with adjacent chunks
    3. Split huge chunks (> max_len) at sentence boundaries
    
    Args:
        text: Full contract text.
        min_len: Minimum chunk length in characters.
        max_len: Maximum chunk length in characters.
    
    Returns:
        List of clause-sized text chunks.
    """
    if not text or not text.strip():
        return []
    
    # Split on double newlines, section headings, or numbered sections
    raw_chunks = re.split(
        r'\n\s*\n|\n(?=[A-Z][A-Z\s]{3,})|\n(?=\d+\.\s)|\n(?=Section\s+\d)|\n(?=ARTICLE\s+)',
        text,
    )
    
    # Clean and filter
    raw_chunks = [c.strip() for c in raw_chunks if c and c.strip()]
    
    # Merge tiny chunks
    merged: list[str] = []
    buffer = ""
    
    for chunk in raw_chunks:
        if len(buffer) + len(chunk) < min_len:
            buffer = (buffer + " " + chunk).strip()
        else:
            if buffer:
                merged.append(buffer)
            buffer = chunk
    
    if buffer:
        merged.append(buffer)
    
    # Split huge chunks at sentence boundaries
    final: list[str] = []
    
    for chunk in merged:
        if len(chunk) <= max_len:
            final.append(chunk)
        else:
            sentences = re.split(r'(?<=[.!?])\s+', chunk)
            sub_buffer = ""
            for sent in sentences:
                if len(sub_buffer) + len(sent) > max_len and sub_buffer:
                    final.append(sub_buffer.strip())
                    sub_buffer = sent
                else:
                    sub_buffer = (sub_buffer + " " + sent).strip()
            if sub_buffer:
                final.append(sub_buffer.strip())
    
    # Final filter
    result = [c for c in final if len(c) >= 20]
    
    logger.info("Segmented text into %d chunks (from %d chars)", len(result), len(text))
    return result
