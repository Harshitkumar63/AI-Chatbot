"""
Tests for Document Processing.

Tests cover:
- File validation (empty, unsupported types, size limits)
- Multi-format support (PDF, DOCX, TXT)
- Text chunking with overlap
"""

import pytest
from app.core.document_processor import DocumentProcessor


def test_validate_file_rejects_empty():
    """Empty files should be rejected."""
    processor = DocumentProcessor()
    with pytest.raises(Exception):
        processor._validate_file(b"", "test.pdf")


def test_validate_file_rejects_unsupported_types():
    """Unsupported file types should be rejected."""
    processor = DocumentProcessor()
    unsupported_extensions = [".jpg", ".png", ".exe", ".zip", ".csv", ".xlsx"]
    for ext in unsupported_extensions:
        with pytest.raises(Exception):
            processor._validate_file(b"content", f"test{ext}")


def test_validate_file_accepts_supported_types():
    """PDF, DOCX, and TXT files should be accepted."""
    processor = DocumentProcessor()
    # These should NOT raise exceptions
    processor._validate_file(b"content", "test.pdf")
    processor._validate_file(b"content", "test.docx")
    processor._validate_file(b"content", "test.txt")


def test_validate_file_rejects_large_files():
    """Files exceeding the size limit should be rejected."""
    processor = DocumentProcessor()
    large_content = b"x" * (10 * 1024 * 1024 + 1)  # Just over 10MB
    with pytest.raises(Exception):
        processor._validate_file(large_content, "test.pdf")


def test_split_into_chunks():
    """Text should be split into chunks with overlap."""
    processor = DocumentProcessor()
    text = "A" * 1500  # 1500 characters
    chunks, metadatas = processor._split_into_chunks(text, "test.pdf")

    assert len(chunks) > 1
    assert len(chunks) == len(metadatas)
    assert all(m["source"] == "test.pdf" for m in metadatas)


def test_split_into_chunks_short_text():
    """Short text should result in a single chunk."""
    processor = DocumentProcessor()
    text = "Hello world"
    chunks, metadatas = processor._split_into_chunks(text, "test.pdf")

    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_split_into_chunks_preserves_metadata():
    """Each chunk should have source and page metadata."""
    processor = DocumentProcessor()
    text = "[PAGE 1]\nFirst page content\n" + "A" * 1000 + "\n[PAGE 2]\nSecond page content"
    chunks, metadatas = processor._split_into_chunks(text, "notes.pdf")

    assert len(chunks) > 0
    assert all("source" in m for m in metadatas)
    assert all("page" in m for m in metadatas)
    assert all("chunk_index" in m for m in metadatas)
    assert all(m["source"] == "notes.pdf" for m in metadatas)


def test_extract_text_txt(tmp_path):
    """TXT extraction should read the file contents."""
    processor = DocumentProcessor()
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello, this is a test document.", encoding="utf-8")

    text = processor._extract_text(txt_file, ".txt")
    assert "Hello, this is a test document." in text
