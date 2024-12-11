import aiohttp
import asyncio
from pathlib import Path
from typing import Optional
from rich.progress import Progress
import hashlib

async def download_file(url: str, dest_path: Path, progress: Progress) -> Path:
    """Download a file with progress bar."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            total_size = int(response.headers.get('content-length', 0))
            
            task_id = progress.add_task(
                f"Downloading {dest_path.name}",
                total=total_size
            )
            
            with open(dest_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))
            
            return dest_path

def verify_checksum(file_path: Path, expected_checksum: str) -> bool:
    """Verify file's SHA256 checksum."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_checksum
