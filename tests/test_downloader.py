"""Tests for download and checksum verification."""

import hashlib
import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from rich.progress import Progress

from carrus.core.downloader import download_file, verify_checksum


@pytest.fixture
def temp_file():
    """Create a temporary file."""
    with tempfile.NamedTemporaryFile() as tmp:
        yield Path(tmp.name)

@pytest.fixture
def mock_progress():
    """Create a mock progress bar."""
    progress = Progress()
    progress.add_task = MagicMock(return_value=1)
    progress.update = MagicMock()
    return progress

@pytest.mark.asyncio
async def test_download_file(temp_file, mock_progress, caplog):
    """Test file download with progress tracking."""
    test_content = b"Test content"
    test_url = "https://example.com/test.dmg"
    
    # Create async iterator for chunks
    class MockChunkIterator:
        def __init__(self, chunks):
            self.chunks = chunks
            self.index = 0
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.index >= len(self.chunks):
                raise StopAsyncIteration
            chunk = self.chunks[self.index]
            self.index += 1
            return chunk

    # Mock aiohttp response
    mock_response = AsyncMock()
    mock_response.headers = {"content-length": str(len(test_content))}
    mock_response.content.iter_chunked = AsyncMock(
        return_value=MockChunkIterator([test_content])
    )
    
    # Mock aiohttp ClientSession
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_response
    
    with caplog.at_level(logging.DEBUG):
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await download_file(test_url, temp_file, mock_progress)
            
            # Verify file was downloaded
            assert result == temp_file
            assert temp_file.read_bytes() == test_content
            
            # Verify progress tracking
            mock_progress.add_task.assert_called_once()
            mock_progress.update.assert_called()
            
            # Verify logging
            assert "Starting download" in caplog.text
            assert "Successfully downloaded" in caplog.text

@pytest.mark.asyncio
async def test_download_file_error(temp_file, mock_progress, caplog):
    """Test file download error handling."""
    test_url = "https://example.com/test.dmg"
    
    # Mock aiohttp session with error
    mock_session = AsyncMock()
    mock_session.get.side_effect = aiohttp.ClientError("Download failed")
    
    with caplog.at_level(logging.DEBUG):
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(aiohttp.ClientError) as exc_info:
                await download_file(test_url, temp_file, mock_progress)
            
            assert "Download failed" in str(exc_info.value)
            assert "Failed to download" in caplog.text

def test_verify_checksum(temp_file, caplog):
    """Test checksum verification."""
    # Create test file with known content
    test_content = b"Test content"
    temp_file.write_bytes(test_content)
    
    # Calculate expected checksum
    expected_checksum = hashlib.sha256(test_content).hexdigest()
    
    with caplog.at_level(logging.DEBUG):
        # Test valid checksum
        assert verify_checksum(temp_file, expected_checksum)
        assert "Checksum verification passed" in caplog.text
        
        # Test invalid checksum
        assert not verify_checksum(temp_file, "invalid_checksum")
        assert "Checksum verification failed" in caplog.text

def test_verify_checksum_error(temp_file, caplog):
    """Test checksum verification error handling."""
    with caplog.at_level(logging.DEBUG):
        with patch('builtins.open', side_effect=IOError("File read error")):
            with pytest.raises(Exception) as exc_info:
                verify_checksum(temp_file, "any_checksum")
            
            assert "File read error" in str(exc_info.value)
            assert "Failed to verify checksum" in caplog.text