"""Unit tests for genlab.metadata (write_metadata / read_metadata).

Uses only the standard library's unittest. Run from the project root:

    pip install pillow piexif mutagen
    python -m unittest discover -v          # needs an empty tests/__init__.py
    python -m unittest tests.test_metadata -v

The MP4 tests use a tiny hand-built file, so ffmpeg is not required. One extra
test builds a real MP4 with ffmpeg and is skipped automatically if it's missing.
"""
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import piexif
import piexif.helper
from mutagen.mp4 import MP4, AtomDataType, MP4FreeForm
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from .unittests import BaseTestCase

from genlab.metadata import MP4_KEY, PNG_KEY, read_metadata, write_metadata

EXIF_ARTIST = 0x013B

PAYLOADS = {
    "flat-dict": {"title": "Sunset", "seed": 42},
    "nested": {"a": {"b": [1, 2.5, None, True]}},
    "list": ["x", 1, {"k": "v"}],
    "unicode": {"title": "Sunset ☀️ café 日本語 😀"},
    "empty-dict": {},
}


# --------------------------------------------------------------------------- helpers


def _gradient(mode="RGB", size=(64, 64)):
    """A non-trivial image, so 'pixels unchanged' assertions actually mean something."""
    return Image.linear_gradient("L").resize(size).convert(mode)


def _mp4_box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def _minimal_mp4() -> bytes:
    """Smallest file mutagen accepts: an ftyp box plus a moov box holding an mvhd header."""
    ftyp = _mp4_box(b"ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2mp41")
    # mvhd v0: version/flags, created, modified, timescale, duration, then unused fields
    mvhd = _mp4_box(b"mvhd", bytes(12) + struct.pack(">II", 1000, 1000) + bytes(80))
    return ftyp + _mp4_box(b"moov", mvhd)


def _listing(path):
    """Names of every file next to `path`, used to prove no temp files are left behind."""
    return sorted(p.name for p in path.parent.iterdir())


def _png_text(path):
    with Image.open(path) as img:
        return dict(img.text)


def _jpeg_scan_data(path):
    """The compressed image data. 0xFF is always byte-stuffed inside it, so the last
    FF DA in the file is the start-of-scan marker."""
    data = path.read_bytes()
    return data[data.rindex(b"\xff\xda"):]


def _user_comment_raw(path):
    return piexif.load(str(path))["Exif"][piexif.ExifIFD.UserComment]


class MetadataTestCase(BaseTestCase):
    """Gives every test its own scratch directory, deleted afterwards."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.tmp = Path(scratch.name)

    def fresh_dir(self):
        """A new empty directory, so a test can list its contents without noise."""
        return Path(tempfile.mkdtemp(dir=self.tmp))


# --------------------------------------------------------------------------- shared behaviour


class CommonBehaviour:
    """Behaviour every format must share. Not a TestCase itself, so unittest doesn't
    collect it; the concrete classes below mix it in and supply the file factory."""

    suffix = None         # extension of the files new_file() creates
    alt_suffixes = ()     # other spellings that must also work

    def new_file(self):
        raise NotImplementedError

    def test_round_trip(self):
        for name, payload in PAYLOADS.items():
            with self.subTest(payload=name):
                path = self.new_file()
                write_metadata(path, payload)
                self.assertEqual(read_metadata(path), payload)

    def test_accepts_json_string(self):
        path = self.new_file()
        write_metadata(path, '{"v": 1}')
        self.assertEqual(read_metadata(path), {"v": 1})

    def test_accepts_json_bytes(self):
        path = self.new_file()
        write_metadata(path, b'{"v": 1}')
        self.assertEqual(read_metadata(path), {"v": 1})

    def test_accepts_str_and_path_objects(self):
        path = self.new_file()
        write_metadata(str(path), {"v": 1})
        self.assertEqual(read_metadata(path), {"v": 1})
        self.assertEqual(read_metadata(str(path)), {"v": 1})

    def test_second_write_replaces_first(self):
        path = self.new_file()
        write_metadata(path, {"v": 1, "old": True})
        write_metadata(path, {"v": 2})
        self.assertEqual(read_metadata(path), {"v": 2})

    def test_read_returns_none_when_nothing_stored(self):
        self.assertIsNone(read_metadata(self.new_file()))

    def test_invalid_json_string_is_rejected_and_file_untouched(self):
        path = self.new_file()
        original = path.read_bytes()
        with self.assertRaises(ValueError):
            write_metadata(path, "{not json")
        self.assertEqual(path.read_bytes(), original)

    def test_no_stray_files_left_behind(self):
        path = self.new_file()
        before = _listing(path)
        write_metadata(path, {"v": 1})
        self.assertEqual(_listing(path), before)

    def test_alternate_and_uppercase_extensions(self):
        for suffix in self.alt_suffixes:
            with self.subTest(suffix=suffix):
                source = self.new_file()
                target = source.with_name(f"renamed{suffix}")
                shutil.copy(source, target)
                write_metadata(target, {"v": 1})
                self.assertEqual(read_metadata(target), {"v": 1})

    def test_missing_file_raises_file_not_found(self):
        path = self.fresh_dir() / f"missing{self.suffix}"
        with self.assertRaises(FileNotFoundError):
            write_metadata(path, {"v": 1})
        with self.assertRaises(FileNotFoundError):
            read_metadata(path)


class UnsupportedFileTests(MetadataTestCase):
    def test_unsupported_extension_raises(self):
        for name in ("anim.gif", "notes.txt", "clip.mov", "no_extension"):
            with self.subTest(name=name):
                path = self.tmp / name
                path.write_bytes(b"data")
                with self.assertRaisesRegex(ValueError, "Unsupported"):
                    write_metadata(path, {"v": 1})
                with self.assertRaisesRegex(ValueError, "Unsupported"):
                    read_metadata(path)
                self.assertEqual(path.read_bytes(), b"data")


# --------------------------------------------------------------------------- PNG


class PngTests(CommonBehaviour, MetadataTestCase):
    suffix = ".png"
    alt_suffixes = (".PNG",)

    def new_file(self):
        path = self.fresh_dir() / "image.png"
        info = PngInfo()
        info.add_text("Software", "test-suite")
        _gradient().save(path, pnginfo=info)
        return path

    def test_stores_json_under_png_key(self):
        path = self.new_file()
        write_metadata(path, {"a": 1})
        self.assertEqual(_png_text(path)[PNG_KEY], '{"a": 1}')

    def test_preserves_existing_text_chunks(self):
        path = self.new_file()
        write_metadata(path, {"a": 1})
        self.assertEqual(_png_text(path)["Software"], "test-suite")

    def test_pixels_and_mode_unchanged(self):
        for mode in ("L", "RGB", "RGBA", "P"):
            with self.subTest(mode=mode):
                path = self.fresh_dir() / "image.png"
                _gradient(mode).save(path)
                with Image.open(path) as img:
                    before = (img.mode, img.tobytes(), img.getpalette())

                write_metadata(path, {"a": 1})

                with Image.open(path) as img:
                    self.assertEqual((img.mode, img.tobytes(), img.getpalette()), before)

    def test_preserves_exif(self):
        path = self.fresh_dir() / "exif.png"
        img = _gradient()
        exif = img.getexif()
        exif[EXIF_ARTIST] = "Ann Artist"
        img.save(path, exif=exif)

        write_metadata(path, {"a": 1})

        with Image.open(path) as saved:
            self.assertEqual(saved.getexif().get(EXIF_ARTIST), "Ann Artist")

    def test_preserves_icc_profile(self):
        try:
            from PIL import ImageCms
        except ImportError:
            self.skipTest("Pillow was built without ImageCms")
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        path = self.fresh_dir() / "icc.png"
        _gradient().save(path, icc_profile=icc)

        write_metadata(path, {"a": 1})

        with Image.open(path) as saved:
            self.assertEqual(saved.info["icc_profile"], icc)

    def test_animated_png_is_rejected_and_file_untouched(self):
        path = self.fresh_dir() / "anim.png"
        frames = [Image.new("RGB", (16, 16), color) for color in ("red", "blue")]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=100)
        original = path.read_bytes()

        with self.assertRaisesRegex(ValueError, "Animated"):
            write_metadata(path, {"a": 1})

        self.assertEqual(path.read_bytes(), original)

    def test_failed_save_keeps_original_and_cleans_up_temp_file(self):
        path = self.new_file()
        original, listing = path.read_bytes(), _listing(path)

        with mock.patch.object(Image.Image, "save", side_effect=RuntimeError("disk full")):
            with self.assertRaisesRegex(RuntimeError, "disk full"):
                write_metadata(path, {"a": 1})

        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(_listing(path), listing)


# --------------------------------------------------------------------------- JPEG


class JpegTests(CommonBehaviour, MetadataTestCase):
    suffix = ".jpg"
    alt_suffixes = (".jpeg", ".JPG")

    def new_file(self):
        path = self.fresh_dir() / "photo.jpg"
        _gradient().save(path, quality=90)  # no EXIF block at all
        return path

    def test_stores_json_in_exif_user_comment(self):
        path = self.new_file()
        write_metadata(path, {"a": 1})
        self.assertEqual(piexif.helper.UserComment.load(_user_comment_raw(path)), '{"a": 1}')

    def test_edit_is_lossless(self):
        path = self.new_file()
        with Image.open(path) as img:
            pixels_before = img.tobytes()
        scan_before = _jpeg_scan_data(path)

        write_metadata(path, {"a": 1})

        self.assertEqual(_jpeg_scan_data(path), scan_before)  # compressed bytes identical
        with Image.open(path) as img:
            self.assertEqual(img.tobytes(), pixels_before)

    def test_preserves_existing_exif(self):
        path = self.fresh_dir() / "exif.jpg"
        img = _gradient()
        exif = img.getexif()
        exif[EXIF_ARTIST] = "Ann Artist"
        img.save(path, exif=exif)

        write_metadata(path, {"a": 1})

        self.assertEqual(piexif.load(str(path))["0th"][piexif.ImageIFD.Artist], b"Ann Artist")
        self.assertEqual(read_metadata(path), {"a": 1})

    def test_uses_ascii_encoding_when_possible_and_unicode_otherwise(self):
        path = self.new_file()

        write_metadata(path, {"title": "plain"})
        self.assertTrue(_user_comment_raw(path).startswith(b"ASCII\x00\x00\x00"))

        write_metadata(path, {"title": "café"})
        self.assertTrue(_user_comment_raw(path).startswith(b"UNICODE\x00"))

    def test_large_ascii_payload_fits(self):
        path = self.new_file()
        payload = {"blob": "x" * 50_000}
        write_metadata(path, payload)
        self.assertEqual(read_metadata(path), payload)

    def test_oversized_payload_is_rejected_and_file_untouched(self):
        oversized = {
            "ascii-70k": {"blob": "x" * 70_000},
            "unicode-40k-chars": {"blob": "é" * 40_000},  # 2 bytes each in UTF-16
        }
        for name, payload in oversized.items():
            with self.subTest(payload=name):
                path = self.new_file()
                original = path.read_bytes()
                with self.assertRaisesRegex(ValueError, "too large"):
                    write_metadata(path, payload)
                self.assertEqual(path.read_bytes(), original)


# --------------------------------------------------------------------------- MP4


class Mp4Tests(CommonBehaviour, MetadataTestCase):
    suffix = ".mp4"
    alt_suffixes = (".m4v", ".m4a", ".MP4")

    def new_file(self):
        path = self.fresh_dir() / "clip.mp4"
        path.write_bytes(_minimal_mp4())  # no tags at all
        return path

    def test_stores_json_in_utf8_freeform_atom(self):
        path = self.new_file()
        write_metadata(path, {"title": "café"})

        (value,) = MP4(str(path))[MP4_KEY]
        self.assertIsInstance(value, MP4FreeForm)
        self.assertEqual(value.dataformat, AtomDataType.UTF8)
        self.assertEqual(bytes(value).decode("utf-8"), '{"title": "café"}')

    def test_adds_tag_container_when_file_has_none(self):
        path = self.new_file()
        self.assertIsNone(MP4(str(path)).tags)
        write_metadata(path, {"a": 1})
        self.assertIsNotNone(MP4(str(path)).tags)

    def test_preserves_existing_tags(self):
        path = self.new_file()
        mp4 = MP4(str(path))
        mp4.add_tags()
        mp4["\xa9nam"] = "My title"
        mp4.save()

        write_metadata(path, {"a": 1})

        self.assertEqual(MP4(str(path))["\xa9nam"], ["My title"])
        self.assertEqual(read_metadata(path), {"a": 1})

    @unittest.skipIf(shutil.which("ffmpeg") is None, "ffmpeg not installed")
    def test_real_file_still_decodes_after_write(self):
        path = self.fresh_dir() / "real.mp4"
        build = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-f", "lavfi", "-i", "testsrc=duration=1:size=128x72:rate=10",
                "-f", "lavfi", "-i", "sine=duration=1",
                "-c:v", "mpeg4", "-c:a", "aac", "-shortest",
                "-movflags", "+faststart",  # moov before mdat, so tags force offset rewrites
                str(path),
            ],
            capture_output=True,
        )
        if build.returncode != 0:
            self.skipTest("ffmpeg could not build a test MP4")
        raw = path.read_bytes()
        self.assertLess(raw.index(b"moov"), raw.index(b"mdat"), "test premise: moov must precede mdat")

        write_metadata(path, {"a": 1})

        self.assertEqual(read_metadata(path), {"a": 1})
        decode = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True
        )
        self.assertEqual(decode.returncode, 0)
        self.assertEqual(decode.stderr, b"")
