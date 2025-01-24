"""Tests for code signing verification."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from carrus.core.codesign import (
    DMGMount,
    SigningInfo,
    verify_codesign,
    verify_signature_requirements,
)


@pytest.fixture
def mock_dmg():
    """Create a mock DMG file."""
    with tempfile.NamedTemporaryFile(suffix='.dmg') as tmp:
        yield Path(tmp.name)

@pytest.fixture
def mock_app():
    """Create a mock app bundle."""
    with tempfile.NamedTemporaryFile(suffix='.app') as tmp:
        yield Path(tmp.name)

def test_signing_info_creation():
    """Test SigningInfo dataclass creation."""
    info = SigningInfo(signed=True, team_id="ABC123")
    assert info.signed
    assert info.team_id == "ABC123"
    assert info.errors == []

def test_dmg_mount_context_manager(mock_dmg):
    """Test DMG mounting context manager."""
    with patch('subprocess.run') as mock_run, \
         patch('pathlib.Path.glob') as mock_glob, \
         patch('pathlib.Path.rglob') as mock_rglob:
        
        # Mock successful mount
        mock_run.return_value.returncode = 0
        
        # Mock app discovery
        mock_app = Path(tempfile.mkdtemp(prefix='carrus_test_')) / 'app.app'
        mock_glob.return_value = [mock_app]
        mock_rglob.return_value = []  # Not needed since glob finds it
        
        with DMGMount(mock_dmg) as mount:
            assert mount.dmg_path == mock_dmg
            assert mount.mount_point is not None
            assert mount.app_path == mock_app
            
            # Verify mount command
            mount_call = mock_run.call_args_list[0]
            assert 'hdiutil' in mount_call[0][0]
            assert 'attach' in mount_call[0][0]
        
        # Verify unmount command
        unmount_call = mock_run.call_args_list[-1]
        assert 'hdiutil' in unmount_call[0][0]
        assert 'detach' in unmount_call[0][0]

@patch('carrus.core.codesign.run_command')
def test_verify_codesign_app(mock_run, mock_app):
    """Test code signing verification for app bundle."""
    # Mock command outputs
    mock_run.side_effect = [
        ("", "", 0),  # codesign verify
        ("", "TeamIdentifier=ABC123\nAuthority=Developer ID", 0),  # codesign details
        ("", "", 0)   # notarization check
    ]
    
    result = verify_codesign(mock_app)
    
    assert result.signed
    assert result.team_id == "ABC123"
    assert "Developer ID" in result.authority[0]
    assert result.notarized
    assert not result.errors

@patch('carrus.core.codesign.run_command')
def test_verify_codesign_dmg(mock_run, mock_dmg):
    """Test code signing verification for DMG."""
    # Mock command outputs
    mock_run.side_effect = [
        ("", "", 0),  # codesign verify
        ("", "TeamIdentifier=ABC123\nAuthority=Developer ID", 0),  # codesign details
        ("", "", 0)   # notarization check
    ]
    
    with patch('carrus.core.codesign.DMGMount') as mock_mount:
        mock_mount.return_value.__enter__.return_value.app_path = Path(tempfile.mkdtemp(prefix='carrus_test_')) / 'test.app'
        result = verify_codesign(mock_dmg)
        
        assert result.signed
        assert result.team_id == "ABC123"
        assert result.notarized

@patch('carrus.core.codesign.verify_codesign')
def test_verify_signature_requirements(mock_verify):
    """Test signature requirement verification."""
    # Test valid signature
    mock_verify.return_value = SigningInfo(
        signed=True,
        team_id="ABC123",
        notarized=True
    )
    
    success, errors = verify_signature_requirements(
        Path("test.app"),
        required_team_id="ABC123",
        require_notarized=True
    )
    assert success
    assert not errors
    
    # Test invalid team ID
    success, errors = verify_signature_requirements(
        Path("test.app"),
        required_team_id="XYZ789",
        require_notarized=True
    )
    assert not success
    assert "Team ID mismatch" in errors[0]
    
    # Test not notarized
    mock_verify.return_value = SigningInfo(
        signed=True,
        team_id="ABC123",
        notarized=False
    )
    success, errors = verify_signature_requirements(
        Path("test.app"),
        required_team_id="ABC123",
        require_notarized=True
    )
    assert not success
    assert "not notarized" in errors[0]

def test_verify_codesign_logging(mock_app, caplog):
    """Test logging in code signing verification."""
    with caplog.at_level(logging.DEBUG):
        with patch('carrus.core.codesign.run_command') as mock_run:
            mock_run.side_effect = [
                ("", "", 0),
                ("", "TeamIdentifier=ABC123", 0),
                ("", "", 0)
            ]
            
            verify_codesign(mock_app)
            
            # Verify debug logs
            assert "Starting code sign verification" in caplog.text
            assert "Basic verification result" in caplog.text
            
            # Verify audit logs
            assert "Code sign verification completed" in caplog.text