from __future__ import annotations

import os
import secrets
import shlex
import subprocess
import tempfile
from pathlib import PurePath

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ALLOWED_EXTENSIONS = frozenset({"txt", "eml", "msg", "pdf"})


def extension_from_upload_filename(filename: str | None) -> tuple[str | None, str | None]:
    """
    Returns (lowercase extension without dot, None) or (None, error_code).
    Rejects path separators and traversal in the original name (metadata only).
    """
    if not filename or not filename.strip():
        return None, "no_file_name"
    if any(sep in filename for sep in ("/", "\\")):
        return None, "unsafe_filename"
    if ".." in filename:
        return None, "unsafe_filename"
    base = PurePath(filename).name
    if not base or base.startswith("."):
        return None, "unsafe_filename"
    lower = base.lower()
    if "." not in lower:
        return None, "unsupported"
    ext = lower.rsplit(".", 1)[-1]
    if ext not in ALLOWED_EXTENSIONS:
        return None, "unsupported"
    return ext, None


def sniff_content_kind(data: bytes) -> str:
    """
    Classify file content using magic bytes / light heuristics (not only extension).
    Returns one of: pdf, msg, eml, txt, unknown.
    """
    if not data:
        return "unknown"
    if data.startswith(b"%PDF"):
        return "pdf"
    if len(data) >= len(OLE_MAGIC) and data[: len(OLE_MAGIC)] == OLE_MAGIC:
        return "msg"
    head = data[: 16384]
    lowered = head.lower()
    if b"mime-version:" in lowered or head.lstrip().startswith(b"From "):
        return "eml"
    if b"return-path:" in lowered or b"received:" in lowered:
        return "eml"
    sample = data[: 8192]
    if b"\x00" in sample:
        return "unknown"
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    printable = sum(1 for b in sample if b >= 32 or b in (9, 10, 13))
    if len(sample) == 0 or printable / max(len(sample), 1) > 0.85:
        return "txt"
    return "unknown"


def reconcile_extension(*, declared_ext: str, sniffed: str) -> tuple[str | None, str | None]:
    """
    Ensure declared extension matches detected kind for strong binary types;
    allow txt/eml ambiguity only when sniff says unknown (weak text).
    Returns (canonical_ext, None) or (None, error_code).
    """
    if declared_ext not in ALLOWED_EXTENSIONS:
        return None, "unsupported"

    if sniffed == "unknown":
        if declared_ext in ("pdf", "msg"):
            return None, "invalid_file_type"
        return declared_ext, None

    if sniffed != declared_ext:
        return None, "invalid_file_type"

    return declared_ext, None


async def read_upload_with_size_limit(file: UploadFile, max_bytes: int) -> tuple[bytes | None, str | None]:
    """
    Read upload into memory with a hard size cap (streaming).
    Returns (content, None) or (None, error_code).
    """
    chunks: list[bytes] = []
    total = 0
    chunk_size = 64 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            return None, "file_too_large"
        chunks.append(chunk)
    return b"".join(chunks), None


def build_safe_temp_path(ext: str) -> str:
    """
    Random name under the system temp dir (never uses client-supplied path segments).
    """
    safe_ext = ext.lower() if ext in ALLOWED_EXTENSIONS else "bin"
    name = f"invoice_upload_{secrets.token_hex(16)}.{safe_ext}"
    return os.path.join(tempfile.gettempdir(), name)


def run_optional_antivirus_scan(
    *,
    file_path: str,
    file_extension: str,
    enabled: bool,
    pdf_only: bool,
    command_template: str | None,
    timeout_seconds: int,
) -> str | None:
    """
    Optional AV: run a shell command with {path} replaced by the temp file path.
    Returns None if OK, or an error_code string on failure / infection.
    """
    if not enabled:
        return None
    if pdf_only and file_extension.lower() != "pdf":
        return None
    if not command_template or not command_template.strip():
        return "av_misconfigured"
    cmd = command_template.replace("{path}", file_path)
    try:
        argv = shlex.split(cmd, posix=os.name != "nt")
        result = subprocess.run(
            argv,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return "av_unavailable"
    except subprocess.TimeoutExpired:
        return "av_timeout"
    if result.returncode != 0:
        return "av_rejected"
    return None
