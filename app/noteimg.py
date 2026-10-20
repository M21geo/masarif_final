"""Pictures attached to notes: stored inside the database as base64 text (so backups carry them too)."""
import base64
import os

from .repo import AppError

MAX_BYTES = 6 * 1024 * 1024
EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif"]


def load(path: str) -> str:
    """Read an image file -> base64 text. Raises AppError for unsupported / too large files."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext not in EXTENSIONS:
        raise AppError("نوع الصورة غير مدعوم (jpg, png, webp)")
    if os.path.getsize(path) > MAX_BYTES:
        raise AppError("الصورة كبيرة (الحد 6 ميغا). صغّرها وجرب مرة ثانية")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def to_bytes(b64: str) -> bytes:
    return base64.b64decode(b64)


def guess_ext(b64: str) -> str:
    head = to_bytes(b64[:32])
    if head.startswith(b"\x89PNG"):
        return "png"
    if head[:4] == b"RIFF":
        return "webp"
    if head[:3] == b"GIF":
        return "gif"
    return "jpg"
