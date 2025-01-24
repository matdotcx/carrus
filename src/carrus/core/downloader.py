import hashlib
from pathlib import Path

import aiohttp
from rich.progress import Progress

from .logging import get_audit_logger, get_debug_logger

audit_log = get_audit_logger()
debug_log = get_debug_logger()

async def download_file(url: str, dest_path: Path, progress: Progress) -> Path:
    """Download a file with progress bar."""
    debug_log.info(f"Starting download of {url} to {dest_path}")
    
    try:
        session = aiohttp.ClientSession()
        async with session:
            response = await session.get(url)
            total_size = int(response.headers.get('content-length', 0))
            debug_log.debug(f"Content length: {total_size} bytes")
            
            task_id = progress.add_task(
                f"Downloading {dest_path.name}",
                total=total_size
            )
            
            bytes_downloaded = 0
            with open(dest_path, 'wb') as f:
                chunk_iterator = await response.content.iter_chunked(8192)
                async for chunk in chunk_iterator:
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    progress.update(task_id, advance=len(chunk))
                    
            debug_log.debug(f"Downloaded {bytes_downloaded} of {total_size} bytes")
            
            if bytes_downloaded == total_size:
                debug_log.info(f"Successfully downloaded {dest_path.name}")
                audit_log.info(f"Downloaded {url} to {dest_path} ({bytes_downloaded} bytes)")
            else:
                debug_log.warning(
                    f"Download size mismatch for {dest_path.name}: "
                    f"expected {total_size}, got {bytes_downloaded}"
                )
            
            return dest_path
                
    except Exception as e:
        error_msg = f"Failed to download {url}: {str(e)}"
        debug_log.error(error_msg)
        audit_log.error(error_msg)
        raise

def verify_checksum(file_path: Path, expected_checksum: str) -> bool:
    """Verify file's SHA256 checksum."""
    debug_log.info(f"Verifying checksum for {file_path}")
    debug_log.debug(f"Expected checksum: {expected_checksum}")
    
    try:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
                
        actual_checksum = sha256.hexdigest()
        debug_log.debug(f"Actual checksum: {actual_checksum}")
        
        is_valid = actual_checksum == expected_checksum
        if is_valid:
            debug_log.info(f"Checksum verification passed for {file_path}")
            audit_log.info(f"Verified checksum for {file_path}")
        else:
            error_msg = (
                f"Checksum verification failed for {file_path}: "
                f"expected {expected_checksum}, got {actual_checksum}"
            )
            debug_log.error(error_msg)
            audit_log.error(error_msg)
            
        return is_valid
        
    except Exception as e:
        error_msg = f"Failed to verify checksum for {file_path}: {str(e)}"
        debug_log.error(error_msg)
        audit_log.error(error_msg)
        raise
