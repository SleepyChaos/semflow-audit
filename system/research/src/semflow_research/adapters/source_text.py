"""Decode source deterministically without guessing an undeclared legacy charset."""

from codecs import BOM_UTF16_BE, BOM_UTF16_LE, BOM_UTF32_BE, BOM_UTF32_LE
from io import BytesIO
from pathlib import Path
from tokenize import detect_encoding


def decode_source(path: Path, content: bytes) -> str:
    if path.suffix.lower() in {".py", ".pyi", ".pyw"}:
        try:
            encoding, _ = detect_encoding(BytesIO(content).readline)
        except SyntaxError as exc:
            raise UnicodeError(str(exc)) from exc
    elif content.startswith((BOM_UTF32_BE, BOM_UTF32_LE)):
        encoding = "utf-32"
    elif content.startswith((BOM_UTF16_BE, BOM_UTF16_LE)):
        encoding = "utf-16"
    else:
        encoding = "utf-8-sig"
    try:
        return content.decode(encoding)
    except LookupError as exc:
        raise UnicodeError(f"Unsupported source encoding {encoding!r}") from exc


def read_source_text(path: Path) -> str:
    return decode_source(path, path.read_bytes())
