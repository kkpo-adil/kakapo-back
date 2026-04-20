import hashlib
from pathlib import Path


CHUNK_SIZE = 65536  # 64 KB


def compute_sha256_file(file_path: str | Path) -> str:
    """Compute SHA-256 hash of a file, reading in chunks to handle large files."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hash of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def verify_file_hash(file_path: str | Path, expected_hash: str) -> bool:
    """Return True if file's SHA-256 matches expected_hash."""
    actual = compute_sha256_file(file_path)
    return actual == expected_hash
