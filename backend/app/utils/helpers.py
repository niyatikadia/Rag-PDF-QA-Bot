"""
helpers.py — Shared utility functions: UUID generation, file utilities.
"""
import uuid
import os
from pathlib import Path


def generate_id() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def safe_filename(filename: str) -> str:
    """
    Return a filesystem-safe version of a filename.
    Actual storage always uses UUID names; this is for display purposes only.
    """
    return Path(filename).name


def file_size_mb(path: str | Path) -> float:
    """Return file size in MB."""
    return os.path.getsize(path) / (1024 * 1024)
