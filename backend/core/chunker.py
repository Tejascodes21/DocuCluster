"""Chunker — Recursive/semantic text chunking with section boundary preservation.

Splits document text into overlapping chunks suitable for embedding and retrieval.
Preserves paragraph and section boundaries where possible.
"""
import re
from typing import List, Dict, Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    min_chunk_size: int = 50
) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks, respecting paragraph boundaries.

    Strategy:
      1. Split by double-newline (paragraph boundaries) first.
      2. If a paragraph exceeds chunk_size, split by sentence.
      3. Merge small fragments into the current chunk up to chunk_size.
      4. Apply overlap by carrying trailing tokens from prev chunk.

    Args:
        text: Full document text.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap in characters between adjacent chunks.
        min_chunk_size: Minimum chunk size — fragments below this are merged.

    Returns:
        List of dicts with keys: 'text', 'chunk_index', 'char_start', 'char_end'.
    """
    if not text or not text.strip():
        return []

    # Split into paragraphs
    paragraphs = re.split(r'\n\s*\n', text.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # Further split long paragraphs into sentences
    segments = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            segments.append(para)
        else:
            # Split by sentence boundaries
            sentences = re.split(r'(?<=[.!?])\s+', para)
            segments.extend(sentences)

    # Merge segments into chunks
    chunks = []
    current_chunk = ""
    char_offset = 0

    for segment in segments:
        if not segment.strip():
            continue

        if current_chunk and len(current_chunk) + len(segment) + 1 > chunk_size:
            # Flush current chunk
            chunk_start = text.find(current_chunk, char_offset)
            if chunk_start == -1:
                chunk_start = char_offset
            chunk_end = chunk_start + len(current_chunk)

            chunks.append({
                'text': current_chunk.strip(),
                'chunk_index': len(chunks),
                'char_start': chunk_start,
                'char_end': chunk_end
            })

            # Apply overlap — carry trailing characters
            if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                overlap_text = current_chunk[-chunk_overlap:]
                current_chunk = overlap_text + " " + segment
            else:
                current_chunk = segment

            char_offset = chunk_end - chunk_overlap if chunk_overlap > 0 else chunk_end
        else:
            if current_chunk:
                current_chunk += " " + segment
            else:
                current_chunk = segment

    # Flush last chunk
    if current_chunk.strip() and len(current_chunk.strip()) >= min_chunk_size:
        chunk_start = text.find(current_chunk.strip(), max(0, char_offset - chunk_overlap))
        if chunk_start == -1:
            chunk_start = char_offset
        chunk_end = chunk_start + len(current_chunk.strip())
        chunks.append({
            'text': current_chunk.strip(),
            'chunk_index': len(chunks),
            'char_start': chunk_start,
            'char_end': chunk_end
        })
    elif current_chunk.strip() and chunks:
        # Merge tiny trailing fragment into last chunk
        chunks[-1]['text'] += " " + current_chunk.strip()
        chunks[-1]['char_end'] += len(current_chunk.strip()) + 1

    logger.info("Chunked text (%d chars) into %d chunks (target=%d, overlap=%d)",
                len(text), len(chunks), chunk_size, chunk_overlap)
    return chunks


def chunk_document(
    content: str,
    doc_id: int,
    filename: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    min_chunk_size: int = 50
) -> List[Dict[str, Any]]:
    """Chunk a single document and attach metadata (with exact line offsets).

    Args:
        content: Document text.
        doc_id: Document identifier.
        filename: Document filename.
        chunk_size: Target chunk size.
        chunk_overlap: Overlap between chunks.
        min_chunk_size: Minimum chunk size in characters.

    Returns:
        List of chunk dicts with keys: 'text', 'chunk_index', 'char_start',
        'char_end', 'doc_id', 'filename', 'start_line', 'end_line'.
    """
    raw_chunks = chunk_text(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap, min_chunk_size=min_chunk_size)
    for chunk in raw_chunks:
        chunk['doc_id'] = doc_id
        chunk['filename'] = filename
        
        # Calculate line numbers from character offsets
        start_offset = chunk.get('char_start', 0)
        end_offset = chunk.get('char_end', len(content))
        
        start_line = content[:start_offset].count('\n') + 1
        end_line = content[:end_offset].count('\n') + 1
        
        chunk['start_line'] = start_line
        chunk['end_line'] = end_line
        
    return raw_chunks

