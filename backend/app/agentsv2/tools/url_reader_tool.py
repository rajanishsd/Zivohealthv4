#!/usr/bin/env python3
"""
URL Reader Tool
Fetch and read content from URLs (HTML and PDF) with local caching.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

try:
    from PyPDF2 import PdfReader  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None  # type: ignore

from langchain_core.tools import tool

from app.core.config import settings
from app.agentsv2.tools.ocr_tools import OCRToolkit  # Fallback for scanned PDFs


@dataclass
class FetchResult:
    url: str
    content_type: str
    byte_size: int
    title: str
    text: str
    pages: Optional[int]
    cache_path: str
    meta_path: str


def _ensure_dir(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _detect_content_type(url: str, timeout: float = 10.0) -> Dict[str, Optional[str]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0 Safari/537.36"
        )
    }
    try:
        head = requests.head(url, headers=headers, allow_redirects=True, timeout=timeout)
        ct = head.headers.get("Content-Type")
        etag = head.headers.get("ETag")
        lm = head.headers.get("Last-Modified")
        cl = head.headers.get("Content-Length")
        return {"content_type": ct, "etag": etag, "last_modified": lm, "content_length": cl}
    except Exception:
        return {"content_type": None, "etag": None, "last_modified": None, "content_length": None}


def _download_to_cache(url: str, cache_dir: Path, max_bytes: int, meta: Dict[str, Optional[str]]) -> Path:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0 Safari/537.36"
        )
    }
    # Determine extension
    content_type = (meta.get("content_type") or "").lower()
    ext = ".pdf" if "pdf" in content_type or url.lower().endswith(".pdf") else ".html"
    file_hash = _hash_url(url)
    file_path = cache_dir / f"{file_hash}{ext}"
    meta_path = cache_dir / f"{file_hash}.json"

    # If we already have the file, respect cache
    if file_path.exists() and meta_path.exists():
        return file_path

    with requests.get(url, headers=headers, stream=True, timeout=20) as r:
        r.raise_for_status()
        total = 0
        _ensure_dir(cache_dir)
        with open(file_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    f.close()
                    try:
                        file_path.unlink(missing_ok=True)  # type: ignore[arg-type]
                    except Exception:
                        pass
                    raise ValueError("File exceeds size limit")
                f.write(chunk)

    # Write metadata for future conditional requests
    try:
        meta_out = {
            "url": url,
            "etag": meta.get("etag"),
            "last_modified": meta.get("last_modified"),
            "content_type": content_type or ("application/pdf" if ext == ".pdf" else "text/html"),
            "path": str(file_path),
        }
        with open(meta_path, "w", encoding="utf-8") as m:
            json.dump(meta_out, m)
    except Exception:
        pass

    return file_path


def _read_html(path: Path) -> FetchResult:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
    except UnicodeDecodeError:
        with open(path, "rb") as f:
            html = f.read().decode("utf-8", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title").get_text().strip() if soup.find("title") else ""
    # Remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    # Normalize whitespace
    text = " ".join(text.split())
    # Cap output to manageable size
    max_chars = 50000
    text = text[:max_chars]

    stat = path.stat()
    return FetchResult(
        url="",
        content_type="text/html",
        byte_size=stat.st_size,
        title=title,
        text=text,
        pages=None,
        cache_path=str(path),
        meta_path=str(path.with_suffix(".json")),
    )


def _read_pdf(path: Path) -> FetchResult:
    pages = None
    text_parts: list[str] = []

    if PdfReader is not None:
        try:
            reader = PdfReader(str(path))
            pages = len(reader.pages)
            for page in reader.pages:
                try:
                    extracted = page.extract_text() or ""
                except Exception:
                    extracted = ""
                if extracted:
                    text_parts.append(extracted)
        except Exception:
            # Fall through to OCR
            text_parts = []

    text = "\n".join(tp.strip() for tp in text_parts if tp.strip())

    if not text:
        # Fallback to OCR/Textract pathway (may require AWS credentials)
        try:
            toolkit = OCRToolkit()
            with open(path, "rb") as f:
                pdf_bytes = f.read()
            ocr_text = toolkit._extract_text_from_pdf_bytes(pdf_bytes)
            if isinstance(ocr_text, str):
                text = ocr_text
        except Exception:
            text = ""

    # Cap output size to keep token usage reasonable
    max_chars = 75000
    text = text[:max_chars]

    stat = path.stat()
    return FetchResult(
        url="",
        content_type="application/pdf",
        byte_size=stat.st_size,
        title=path.name,
        text=text,
        pages=pages,
        cache_path=str(path),
        meta_path=str(path.with_suffix(".json")),
    )


def _fetch_and_read_sync(url: str, max_bytes: int = 10_000_000) -> Dict[str, Any]:
    # Choose cache directory under backend/data to persist across runs
    base_dir = Path(settings.BASE_DIR if hasattr(settings, "BASE_DIR") else ".").resolve()
    # Default to backend/data/web_cache relative to repo root
    repo_root = base_dir
    # Try to detect repository root if BASE_DIR points to backend/app
    if (base_dir / "app").exists() and (base_dir.parent / "data").exists():
        repo_root = base_dir.parent
    cache_dir = repo_root / "data" / "web_cache"
    _ensure_dir(cache_dir)

    # Detect content type and metadata
    meta = _detect_content_type(url)
    # Check declared size before downloading
    declared_len = None
    try:
        if meta.get("content_length") is not None:
            declared_len = int(meta.get("content_length"))  # type: ignore[arg-type]
    except Exception:
        declared_len = None
    if declared_len is not None and declared_len > max_bytes:
        return {
            "url": url,
            "error": "too_large",
            "too_large": True,
            "limit_bytes": max_bytes,
            "content_length_bytes": declared_len,
            "content_type": meta.get("content_type") or "",
        }

    try:
        file_path = _download_to_cache(url, cache_dir, max_bytes, meta)
    except ValueError as e:
        # Catch explicit size limit breaches during streaming
        if "size limit" in str(e).lower():
            return {
                "url": url,
                "error": "too_large",
                "too_large": True,
                "limit_bytes": max_bytes,
                "content_length_bytes": declared_len,
                "content_type": meta.get("content_type") or "",
            }
        raise
    content_type = (meta.get("content_type") or "").lower()

    if file_path.suffix.lower() == ".pdf" or "pdf" in content_type:
        result = _read_pdf(file_path)
    else:
        result = _read_html(file_path)

    # Attach URL and recompute content-type by extension if missing
    result.url = url
    if not result.content_type:
        result.content_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "text/html"

    return {
        "url": result.url,
        "content_type": result.content_type,
        "byte_size": result.byte_size,
        "title": result.title,
        "text": result.text,
        "pages": result.pages,
        "cache_path": result.cache_path,
        "meta_path": result.meta_path,
    }


@tool
async def fetch_and_read_url(url: str, max_bytes: Optional[int] = None) -> Dict[str, Any]:
    """
    Fetch a URL and return extracted text content and metadata.

    - Supports HTML and PDF URLs
    - Caches downloads under backend/data/web_cache to avoid re-downloading
    - For PDFs, uses PyPDF2 text extraction, falling back to AWS Textract OCR when needed

    Args:
        url: The URL to fetch
        max_bytes: Maximum allowed download size (default 10 MB)

    Returns:
        Dict with keys: url, content_type, byte_size, title, text, pages?, cache_path, meta_path
        If the file is too large, returns a structured error with keys: error, too_large, limit_bytes, content_length_bytes.
    """
    # Use settings default if not provided
    default_max = getattr(settings, "URL_FETCH_MAX_BYTES", 25_000_000)
    limit = max_bytes if isinstance(max_bytes, int) and max_bytes > 0 else default_max
    try:
        return await asyncio.to_thread(_fetch_and_read_sync, url, limit)
    except Exception as e:
        # Final safety net - return error as dict rather than raising
        return {"url": url, "error": str(e)}


__all__ = ["fetch_and_read_url"]


