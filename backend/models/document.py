"""Document model — immutable representation of a parsed document."""
from dataclasses import dataclass, field


@dataclass
class Document:
    """Represents a single uploaded and parsed document.

    Attributes:
        doc_id: Unique identifier (sequential integer assigned on ingestion).
        filename: Original sanitized filename.
        content: Extracted plain-text content of the document.
        word_count: Number of whitespace-delimited tokens in content.
        file_type: File extension ('.txt' or '.pdf').
    """
    doc_id: int
    filename: str
    content: str
    word_count: int = field(init=False)
    file_type: str = ''

    def __post_init__(self):
        self.word_count = len(self.content.split()) if self.content else 0
