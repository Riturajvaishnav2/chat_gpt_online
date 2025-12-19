from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOADS_DIR = BASE_DIR / "uploads"
AGREEMENTS_DIR = UPLOADS_DIR / "agreements"
STANDARDS_DIR = UPLOADS_DIR / "standards"
OUTPUT_DIR = BASE_DIR / "output"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".xlsx"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB per file
CHUNK_SIZE = 1024 * 1024  # 1 MB


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def generate_ulid_like_id() -> str:
    # A compact, sortable-enough id without external dependencies.
    return uuid.uuid4().hex


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = name.replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]+", "", name)
    if not name or name in {".", ".."}:
        return f"file_{uuid.uuid4().hex}.bin"
    return name[:180]


def safe_agreement_base_name(stored_filename: str, agreement_id: str) -> str:
    # stored pattern: {agreement_id}__{original_filename}
    if stored_filename.startswith(f"{agreement_id}__"):
        original = stored_filename.split("__", 1)[1]
    else:
        original = stored_filename
    stem = Path(original).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return stem or "agreement"


def validate_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {allowed}",
        )
    return suffix


async def save_multipart_upload(
    *,
    upload_file: UploadFile,
    dest_dir: Path,
    id_prefix: Optional[str],
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> str:
    if not upload_file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    validate_extension(upload_file.filename)
    ensure_dir(dest_dir)

    safe_name = sanitize_filename(upload_file.filename)
    unique_prefix = id_prefix or uuid.uuid4().hex[:10]
    stored_name = f"{unique_prefix}__{safe_name}"
    dest_path = dest_dir / stored_name

    size = 0
    try:
        with dest_path.open("wb") as f:
            while True:
                chunk = await upload_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max allowed is {max_bytes} bytes.",
                    )
                f.write(chunk)
    except HTTPException:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to store upload: {exc}") from exc
    finally:
        await upload_file.close()

    if size == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    return stored_name


def find_file_by_id_prefix(directory: Path, file_id: str) -> Path:
    matches = list(directory.glob(f"{file_id}__*"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"Unknown agreement_id: {file_id}")
    return matches[0]


def create_versioned_output_dir(parent: Path, base_name: str) -> Path:
    ensure_dir(parent)

    candidates = [base_name] + [f"{base_name}_v{i}" for i in range(2, 10_000)]
    for name in candidates:
        p = parent / name
        try:
            p.mkdir(parents=True, exist_ok=False)
            return p
        except FileExistsError:
            continue

    raise RuntimeError("Failed to allocate a versioned output directory (too many existing versions).")
