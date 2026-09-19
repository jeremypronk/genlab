import json
import os
import tempfile
from pathlib import Path

import piexif
import piexif.helper
from mutagen.mp4 import MP4, MP4FreeForm, AtomDataType
from PIL import Image
from PIL.PngImagePlugin import PngInfo

PNG_KEY = "genlab"
MP4_KEY = "----:genlab:meta"  

PNG_EXTS = {".png"}
JPEG_EXTS = {".jpg", ".jpeg"}
MP4_EXTS = {".mp4", ".m4v", ".m4a"}
JPEG_EXIF_LIMIT = 65_000  # a JPEG APP1 (EXIF) segment can't exceed ~64 KB


def _to_json_text(metadata) -> str:
    """Accept a dict/list or a JSON string; return validated JSON text."""
    if isinstance(metadata, (str, bytes)):
        json.loads(metadata)  # raises ValueError if it isn't valid JSON
        return metadata.decode("utf-8") if isinstance(metadata, bytes) else metadata
    return json.dumps(metadata, ensure_ascii=False)


def _require_file(path: Path) -> None:
    """Give every format the same error for a missing file (mutagen raises its own type)."""
    if not path.is_file():
        raise FileNotFoundError(f"No such file: {path}")


def write_metadata(path, metadata) -> None:
    """Write JSON metadata (dict, list, or JSON string) into a PNG, JPEG or MP4 file."""
    path = Path(path)
    ext = path.suffix.lower()
    text = _to_json_text(metadata)
    _require_file(path)

    if ext in PNG_EXTS:
        _write_png(path, text)
    elif ext in JPEG_EXTS:
        _write_jpeg(path, text)
    elif ext in MP4_EXTS:
        _write_mp4(path, text)
    else:
        raise ValueError(f"Unsupported file type: {ext!r}")


def read_metadata(path):
    """Read back what write_metadata stored. Returns the parsed JSON, or None if absent."""
    path = Path(path)
    ext = path.suffix.lower()
    _require_file(path)

    if ext in PNG_EXTS:
        with Image.open(path) as img:
            raw = img.text.get(PNG_KEY)
    elif ext in JPEG_EXTS:
        user_comment = piexif.load(str(path))["Exif"].get(piexif.ExifIFD.UserComment)
        raw = piexif.helper.UserComment.load(user_comment) if user_comment else None
    elif ext in MP4_EXTS:
        tags = MP4(str(path)).tags
        values = tags.get(MP4_KEY) if tags else None
        raw = bytes(values[0]).decode("utf-8") if values else None
    else:
        raise ValueError(f"Unsupported file type: {ext!r}")

    return json.loads(raw) if raw else None


def _write_png(path: Path, text: str) -> None:
    with Image.open(path) as img:
        if getattr(img, "is_animated", False):
            raise ValueError("Animated PNGs would lose their animation when re-saved")

        info = PngInfo()
        for key, value in img.text.items():  # keep existing text chunks
            if key != PNG_KEY:
                info.add_text(key, value)
        info.add_text(PNG_KEY, text)

        # Write to a temp file, then swap it in, so a failure can't corrupt the original.
        fd, tmp = tempfile.mkstemp(suffix=".png", dir=path.parent)
        os.close(fd)
        try:
            img.save(tmp, format="PNG", pnginfo=info,
                     exif=img.info.get("exif"),           # keep existing EXIF block
                     icc_profile=img.info.get("icc_profile"),
                     dpi=img.info.get("dpi"))
        except BaseException:
            os.unlink(tmp)
            raise
    os.replace(tmp, path)


def _write_jpeg(path: Path, text: str) -> None:
    exif = piexif.load(str(path))  # returns empty tables if the file has no EXIF
    # ASCII is half the size of UTF-16, so only use "unicode" when the text needs it.
    encoding = "ascii" if text.isascii() else "unicode"
    exif["Exif"][piexif.ExifIFD.UserComment] = piexif.helper.UserComment.dump(
        text, encoding=encoding
    )
    exif_bytes = piexif.dump(exif)
    if len(exif_bytes) > JPEG_EXIF_LIMIT:
        raise ValueError(
            f"Metadata too large for a JPEG EXIF block ({len(exif_bytes)} bytes, "
            f"limit ~{JPEG_EXIF_LIMIT}). Store an ID and keep the JSON elsewhere."
        )
    piexif.insert(exif_bytes, str(path))  # in place; pixels are not re-encoded


def _write_mp4(path: Path, text: str) -> None:
    mp4 = MP4(str(path))
    if mp4.tags is None:
        mp4.add_tags()
    mp4[MP4_KEY] = [MP4FreeForm(text.encode("utf-8"), dataformat=AtomDataType.UTF8)]
    mp4.save()
