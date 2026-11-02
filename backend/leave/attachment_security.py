from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import unicodedata
import warnings

from django.conf import settings
from django.utils.module_loading import import_string
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import EmptyFileError, PdfReadError, PdfStreamError


MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_TYPES = {
    "pdf": ("application/pdf", "application/pdf"),
    "png": ("image/png", "image/png"),
    "jpg": ("image/jpeg", "image/jpeg"),
    "jpeg": ("image/jpeg", "image/jpeg"),
}


class InvalidAttachment(ValueError):
    pass


class AttachmentScannerUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ValidatedAttachment:
    filename: str
    content_type: str
    content: bytes
    scan_status: str


def normalize_attachment_filename(filename: str) -> str:
    if not filename or len(filename) > 1024 or "/" in filename or "\\" in filename:
        raise InvalidAttachment("Invalid attachment filename.")

    normalized = unicodedata.normalize("NFKC", filename).strip()
    if (
        not normalized
        or normalized in {".", ".."}
        or len(normalized) > 255
        or any(unicodedata.category(char).startswith("C") for char in normalized)
        or ":" in normalized
    ):
        raise InvalidAttachment("Invalid attachment filename.")

    return normalized


def _validate_pdf(content: bytes) -> bool:
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
        return False
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        return not reader.is_encrypted and len(reader.pages) > 0
    except (EmptyFileError, PdfReadError, PdfStreamError, ValueError, KeyError, IndexError):
        return False


def _validate_image(content: bytes, expected_format: str) -> bool:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format != expected_format:
                    return False
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    return False
                image.verify()
        return True
    except (Image.DecompressionBombError, Image.DecompressionBombWarning,
            UnidentifiedImageError, OSError, SyntaxError, ValueError):
        return False


def scan_attachment(content: bytes) -> str:
    scanner_path = getattr(settings, "ZSH_ATTACHMENT_SCANNER", "")
    if not scanner_path:
        return "unscanned"

    try:
        scanner = import_string(scanner_path)
        clean = scanner(content)
    except Exception as exc:
        raise AttachmentScannerUnavailable from exc

    if not isinstance(clean, bool):
        raise AttachmentScannerUnavailable("Scanner must return a boolean result.")
    if not clean:
        raise InvalidAttachment("The attachment was rejected by the malware scanner.")
    return "clean"


def validate_attachment(upload) -> ValidatedAttachment:
    if upload.size <= 0 or upload.size > MAX_ATTACHMENT_SIZE:
        raise InvalidAttachment("Attachment size is outside the allowed range.")

    filename = normalize_attachment_filename(upload.name or "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    expected = ALLOWED_TYPES.get(extension)
    if expected is None:
        raise InvalidAttachment("Attachment extension is not allowed.")

    content = upload.read(MAX_ATTACHMENT_SIZE + 1)
    if len(content) != upload.size or len(content) > MAX_ATTACHMENT_SIZE:
        raise InvalidAttachment("Attachment size does not match the uploaded content.")
    upload.seek(0)

    detected_type, declared_type = expected
    if upload.content_type != declared_type:
        raise InvalidAttachment("Attachment MIME type does not match its allowed type.")

    if detected_type == "application/pdf":
        valid = _validate_pdf(content)
    elif detected_type == "image/png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n") and _validate_image(
            content, "PNG",
        )
    else:
        valid = content.startswith(b"\xff\xd8\xff") and _validate_image(
            content, "JPEG",
        )
    if not valid:
        raise InvalidAttachment("Attachment content is malformed or has an invalid signature.")

    return ValidatedAttachment(
        filename=filename,
        content_type=detected_type,
        content=content,
        scan_status=scan_attachment(content),
    )
