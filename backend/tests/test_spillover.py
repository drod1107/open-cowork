"""Tests for Spillover module (direct unit tests).

From PR-reviews.md TDD Process Audit (2026-05-03):
- Spillover module: tools/spillover.py
- Currently only tested indirectly via shell.py
- Needs direct unit tests per TDD process

From Dev-Plan.md:356-366:
- Tool result spillover for large outputs
- maybe_spillover() checks threshold (default 4096 bytes)
- write_spillover() writes to backend/db/spillover/
- read_spillover() reads with offset/limit pagination
- format_reference() creates compact reference
"""

import pytest
from backend.tools.spillover import (
    write_spillover,
    read_spillover,
    format_reference,
    maybe_spillover,
    SPILLOVER_DIR,
    DEFAULT_THRESHOLD,
)


def test_write_spillover_creates_file(tmp_path, monkeypatch):
    """Verify write_spillover() creates file in spillover dir.
    
    From Dev-Plan.md:358 - writes to backend/db/spillover/.
    """
    # Use tmp_path for testing
    monkeypatch.setattr("backend.tools.spillover.SPILLOVER_DIR", tmp_path / "spillover")
    
    content = "Test output content"
    file_id = write_spillover(content)
    
    assert file_id is not None
    assert (tmp_path / "spillover" / file_id).exists()
    assert (tmp_path / "spillover" / file_id).read_text() == content


def test_read_spillover_with_pagination(tmp_path, monkeypatch):
    """Verify read_spillover() returns correct pagination.
    
    From Dev-Plan.md:360 - offset/limit pagination.
    """
    monkeypatch.setattr("backend.tools.spillover.SPILLOVER_DIR", tmp_path / "spillover")
    
    # Create file with multiple lines
    content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    file_id = write_spillover(content)
    
    # Read with offset=1, limit=2
    result = read_spillover(file_id, offset=1, limit=2)
    
    assert result["ok"] is True
    assert result["offset"] == 1
    assert result["limit"] == 2
    assert result["total_lines"] == 5
    assert len(result["lines"]) == 2
    assert result["lines"][0] == "Line 2"


def test_read_spillover_invalid_file(tmp_path, monkeypatch):
    """Verify read_spillover() handles invalid file_id.
    
    Should return ok=False with error message.
    """
    monkeypatch.setattr("backend.tools.spillover.SPILLOVER_DIR", tmp_path / "spillover")
    
    result = read_spillover("nonexistent_file_id")
    
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_maybe_spillover_small_output_returns_original():
    """Verify maybe_spillover() returns original content for small outputs.
    
    From Dev-Plan.md:364 - only outputs exceeding threshold get spilled.
    """
    small_output = "Small output"
    assert len(small_output) < DEFAULT_THRESHOLD
    
    result = maybe_spillover(small_output)
    
    assert result == small_output, "Small outputs should stay inline"


def test_maybe_spillover_large_output_returns_reference(tmp_path, monkeypatch):
    """Verify maybe_spillover() returns reference for large outputs.
    
    From Dev-Plan.md:364 - large outputs get reference, not full content.
    """
    monkeypatch.setattr("backend.tools.spillover.SPILLOVER_DIR", tmp_path / "spillover")
    
    # Create output larger than threshold
    large_output = "x" * (DEFAULT_THRESHOLD + 100)
    assert len(large_output) > DEFAULT_THRESHOLD
    
    result = maybe_spillover(large_output, prefix="test")
    
    # Should NOT return original content
    assert result != large_output, "Large outputs should NOT stay inline"
    
    # Should contain reference to spillover file
    assert "test_" in result, "Reference should mention spillover file"
    assert "read_chunk" in result.lower(), "Reference should mention read_chunk tool"


def test_format_reference():
    """Verify format_reference() creates correct format.
    
    From Dev-Plan.md:366 - compact reference format.
    """
    file_id = "test_abc123"
    size = 5000
    
    reference = format_reference(file_id, size)
    
    assert file_id in reference
    assert "5KB" in reference or "5000" in reference
    assert "read_chunk" in reference.lower()
