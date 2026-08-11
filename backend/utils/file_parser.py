"""File parsing utilities — extract plain text from .txt and .pdf files."""
from pathlib import Path
from typing import Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)


def extract_text_from_txt(filepath: str) -> Optional[str]:
    """Read plain text from a .txt file.

    Tries UTF-8 first, then falls back to latin-1 encoding.

    Args:
        filepath: Absolute path to the .txt file.

    Returns:
        Extracted text content, or None if the file cannot be read.
    """
    for encoding in ('utf-8', 'latin-1'):
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            if content.strip():
                return content.strip()
            logger.warning("File '%s' is empty after reading with %s", filepath, encoding)
            return None
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.warning("Failed to read '%s': %s", filepath, e)
            return None

    logger.warning("Could not decode '%s' with any supported encoding", filepath)
    return None


def extract_text_from_pdf(filepath: str) -> Optional[str]:
    """Extract text from a PDF file using PyPDF2.

    Args:
        filepath: Absolute path to the .pdf file.

    Returns:
        Concatenated page text, or None if the file is corrupt or empty.
    """
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(filepath)
        pages_text = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            except Exception as e:
                logger.warning("Error extracting page %d from '%s': %s", i, filepath, e)

        combined = "\n".join(pages_text).strip()
        if not combined:
            logger.warning("PDF '%s' yielded no extractable text", filepath)
            return None
        return combined

    except Exception as e:
        logger.warning("Failed to parse PDF '%s': %s", filepath, e)
        return None


def extract_text(filepath: str) -> Optional[str]:
    """Extract text from a file based on its extension.

    Args:
        filepath: Absolute path to the file.

    Returns:
        Extracted text content, or None if extraction fails.
    """
    ext = Path(filepath).suffix.lower()
    if ext == '.txt':
        return extract_text_from_txt(filepath)
    elif ext == '.pdf':
        return extract_text_from_pdf(filepath)
    else:
        logger.warning("Unsupported file type '%s' for '%s'", ext, filepath)
        return None
