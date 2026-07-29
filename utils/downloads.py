import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def download_file(url: str, dest: Path, retries: int = 3, timeout: int = 60, backoff: float = 1.5) -> bool:
    """Stream a URL to disk with retries. Returns False (and cleans up) if every attempt fails."""
    delay = 1.0
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}, stream=True
            )
            response.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
            if dest.stat().st_size == 0:
                raise ValueError("downloaded file is empty")
            return True
        except Exception as e:
            logger.warning(f"Download attempt {attempt}/{retries} failed for {url}: {e}")
            dest.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(delay)
                delay *= backoff
    return False


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _attribution_path(media_path: Path) -> Path:
    return media_path.with_suffix(media_path.suffix + ".attribution.json")


def delete_media_file(path: Path) -> None:
    path.unlink(missing_ok=True)
    _attribution_path(path).unlink(missing_ok=True)


def dedupe_folder(folder: Path, extensions: set) -> int:
    """Remove files that are byte-for-byte duplicates of another file already in the folder
    (keeping the oldest copy). Returns the number of duplicates removed."""
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in extensions]
    files.sort(key=lambda p: p.stat().st_mtime)

    seen_hashes = {}
    removed = 0
    for path in files:
        try:
            digest = sha256_file(path)
        except Exception as e:
            logger.warning(f"Could not hash {path.name} for dedup check: {e}")
            continue

        if digest in seen_hashes:
            logger.info(f"Removing duplicate media file {path.name} (identical to {seen_hashes[digest].name})")
            delete_media_file(path)
            removed += 1
        else:
            seen_hashes[digest] = path

    return removed


def write_attribution(
    media_path: Path,
    source: str,
    license: str,
    attribution_required: bool,
    credit: str = "",
    query: str = "",
    url: str = "",
) -> None:
    data = {
        "source": source,
        "license": license,
        "attribution_required": attribution_required,
        "credit": credit,
        "query": query,
        "url": url,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(_attribution_path(media_path), "w") as f:
        json.dump(data, f)


def read_attribution(media_path: Path) -> Optional[dict]:
    path = _attribution_path(media_path)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def attribution_credit_line(media_path: Path) -> Optional[str]:
    data = read_attribution(media_path)
    if data and data.get("attribution_required") and data.get("credit"):
        return data["credit"]
    return None
