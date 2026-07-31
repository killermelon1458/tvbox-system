import base64
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.screensaver.slideshow import (
    DEFAULT_EXTENSIONS, FailureReporter, ImageLoadError, candidate_for_path,
    decoder_support, fitted_size, load_oriented_pixbuf, scan_images,
    valid_images,
)


HEIC = base64.b64decode(
    "AAAAHGZ0eXBoZWljAAAAAG1pZjFoZWljbWlhZgAAAX1tZXRhAAAAAAAAACFoZGxy"
    "AAAAAAAAAABwaWN0AAAAAAAAAAAAAAAAAAAAAA5waXRtAAAAAAABAAAAImlsb2MAAAAAREAA"
    "AQABAAAAAAGhAAEAAAAAAAAAUQAAACNpaW5mAAAAAAABAAAAFWluZmUCAAAAAAEAAGh2YzEA"
    "AAAA/WlwcnAAAADdaXBjbwAAAHZodmNDAQNwAAAAAAAAAAAAHvAA/P34+AAADwMgAAEAGEAB"
    "DAH//wNwAAADAJAAAAMAAAMAHroCQCEAAQAqQgEBA3AAAAMAkAAAAwAAAwAeoCCBBZbqrprm"
    "4CGgwIAAAAMAgAAAAwCEIgABAAZEAcFzwYkAAAATY29scm5jbHgAAQANAAaAAAAAFGlzcGUA"
    "AAAAAAAAQAAAAEAAAAAoY2xhcAAAAAQAAAABAAAABgAAAAH////EAAAAAv///8YAAAACAAAAEH"
    "BpeGkAAAAAAwgICAAAABhpcG1hAAAAAAAAAAEAAQWBAgMFhAAAAFltZGF0AAAATSgBrw7IbE"
    "YW6OSfMosGYgohw5x2qf//0b4/y9nssXtujD/+cQAAyAMSllYUCsh9Zgw8MANnaWaofoD3f"
    "AEQmXCQ1TUChT7Kxum+bokg")
AVIF = base64.b64decode(
    "AAAAHGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZgAAAOptZXRhAAAAAAAAACFoZGxyAAAAAAAAAABwaWN0AAAAAAAAAAAAAAAAAAAAAA5waXRtAAAAAAABAAAAImlsb2MAAAAAREAAAQABAAAAAAEOAAEAAAAAAAAAJQAAACNpaW5mAAAAAAABAAAAFWluZmUCAAAAAAEAAGF2MDEAAAAAamlwcnAAAABLaXBjbwAAAAxhdjFDgQAMAAAAABNjb2xybmNseAABAA0ABoAAAAAUaXNwZQAAAAAAAAAEAAAABgAAABBwaXhpAAAAAAMICAgAAAAXaXBtYQAAAAAAAAABAAEEgQIDBAAAAC1tZGF0EgAKCBgEusEBDQaEMhcUwAQQQQQAAHlM39uQsO6SyzGsYcdfQA==")


class Pixbuf:
    def __init__(self, width=10, height=20):
        self.width, self.height = width, height

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height


class SlideshowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make_image(self, name, mode="RGB", size=(8, 5), color=None, **save):
        color = color if color is not None else ((20, 80, 160, 0)
                                                   if mode == "RGBA"
                                                   else (20, 80, 160))
        path = self.root / name
        Image.new(mode, size, color).save(path, **save)
        return path

    def test_contain_geometry_for_household_shapes(self):
        cases = {
            (1600, 900): (1920, 1080),
            (900, 1600): (608, 1080),
            (1000, 1000): (1080, 1080),
            (2, 1): (1920, 960),
            (16, 9): (1920, 1080),
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(fitted_size(*source, 1920, 1080, "contain"),
                                 expected)
        self.assertEqual(fitted_size(100, 50, 200, 200, "cover"), (400, 200))

    def test_required_mixed_case_and_optional_extensions(self):
        for index, extension in enumerate(DEFAULT_EXTENSIONS):
            suffix = extension.upper() if index % 2 else extension.title()
            (self.root / f"image{index}.{suffix}").write_bytes(b"candidate")
        found = scan_images(self.root, False, DEFAULT_EXTENSIONS, 100)
        self.assertEqual(len(found), len(DEFAULT_EXTENSIONS))

    def test_syncthing_hidden_video_directory_and_nonregular_filtering(self):
        valid = self.root / "valid.JPG"
        valid.write_bytes(b"x")
        for name in (
            ".syncthing.photo.jpg.tmp", "~syncthing~photo.png.tmp",
            ".hidden.jpg", ".stignore", "clip.mov", "clip.mp4", "raw.dng",
            "graphic.svg",
        ):
            (self.root / name).write_bytes(b"x")
        for name in (".stfolder", ".stversions", "ordinary-dir.jpg"):
            folder = self.root / name
            folder.mkdir()
            (folder / "buried.jpg").write_bytes(b"x")
        fifo = self.root / "pipe.jpg"
        os.mkfifo(fifo)
        found = scan_images(self.root, True, DEFAULT_EXTENSIONS, 100)
        self.assertEqual([item.path.name for item in found],
                         ["buried.jpg", "valid.JPG"])

    def test_bounded_recursive_scan_and_missing_source(self):
        nested = self.root / "nested"
        nested.mkdir()
        for path in (self.root / "one.jpg", nested / "two.png"):
            path.write_bytes(b"x")
        self.assertEqual(len(scan_images(self.root, True, DEFAULT_EXTENSIONS, 1)), 1)
        self.assertEqual(len(scan_images(self.root, False, DEFAULT_EXTENSIONS, 10)), 1)
        self.assertEqual(scan_images(self.root / "missing", True,
                                     DEFAULT_EXTENSIONS, 10), [])

    def test_zero_byte_oversize_and_removed_candidate(self):
        zero = self.root / "zero.jpg"
        zero.touch()
        zero_candidate = candidate_for_path(zero, DEFAULT_EXTENSIONS)
        with self.assertRaisesRegex(ImageLoadError, "empty-file"):
            load_oriented_pixbuf(zero_candidate)
        large = self.root / "large.jpg"
        large.write_bytes(b"12345")
        self.assertIsNone(candidate_for_path(
            large, DEFAULT_EXTENSIONS, max_file_bytes=4))
        candidate = candidate_for_path(large, DEFAULT_EXTENSIONS)
        large.unlink()
        with self.assertRaisesRegex(ImageLoadError, "file-disappeared"):
            load_oriented_pixbuf(candidate)

    def test_corrupt_truncated_and_random_valid_extension_are_isolated(self):
        good = self.make_image("good.jpg")
        for name, data in (("zero.png", b""), ("truncated.webp", b"RIFF"),
                           ("random.jpeg", os.urandom(32))):
            (self.root / name).write_bytes(data)
        paths = scan_images(self.root, False, DEFAULT_EXTENSIONS, 20)
        valid = valid_images(paths)
        self.assertEqual([path.name for path, _ in valid], [good.name])

    def test_file_changed_before_decode_is_rejected_then_retryable(self):
        path = self.make_image("changing.png")
        candidate = candidate_for_path(path, DEFAULT_EXTENSIONS)
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ImageLoadError, "file-changed-before-decode"):
            load_oriented_pixbuf(candidate)
        refreshed = candidate_for_path(path, DEFAULT_EXTENSIONS)
        self.assertGreater(refreshed.size, candidate.size)

    def test_file_changed_during_decode_is_rejected(self):
        path = self.make_image("during.png")
        candidate = candidate_for_path(path, DEFAULT_EXTENSIONS)

        def changing_decoder(image_path, _maximum):
            import gi
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
            image_path.write_bytes(image_path.read_bytes() + b"changed")
            return pixbuf

        with self.assertRaisesRegex(ImageLoadError, "file-changed-during-decode"):
            load_oriented_pixbuf(candidate, decoder=changing_decoder)

    def test_failure_report_deduplicates_until_metadata_changes(self):
        path = self.root / "bad.jpg"
        path.write_bytes(b"bad")
        first = candidate_for_path(path, DEFAULT_EXTENSIONS)
        reporter = FailureReporter(logging.getLogger("test"))
        with self.assertLogs("test", level="WARNING") as logs:
            self.assertTrue(reporter.failure(first, "decoder-error"))
            self.assertFalse(reporter.failure(first, "decoder-error"))
        self.assertEqual(len(logs.output), 1)
        path.write_bytes(b"changed")
        changed = candidate_for_path(path, DEFAULT_EXTENSIONS)
        with self.assertLogs("test", level="WARNING"):
            self.assertTrue(reporter.failure(changed, "decoder-error"))

    def test_real_required_format_decoding(self):
        fixtures = {
            "jpg": self.make_image("sample.jpg"),
            "png": self.make_image("sample.png"),
            "webp": self.make_image("sample.webp"),
            "heic": self.root / "sample.heic",
            "heif": self.root / "sample.heif",
            "avif": self.root / "sample.avif",
        }
        fixtures["heic"].write_bytes(HEIC)
        fixtures["heif"].write_bytes(HEIC)
        fixtures["avif"].write_bytes(AVIF)
        for extension, path in fixtures.items():
            with self.subTest(extension=extension):
                pixbuf = load_oriented_pixbuf(
                    candidate_for_path(path, DEFAULT_EXTENSIONS))
                self.assertGreater(pixbuf.get_width(), 0)
                self.assertGreater(pixbuf.get_height(), 0)
                if extension in {"heic", "heif", "avif"}:
                    self.assertEqual((pixbuf.get_width(), pixbuf.get_height()),
                                     (4, 6))

    def test_exif_orientation_and_transparency_are_normalized(self):
        oriented = self.root / "portrait-oriented.jpg"
        image = Image.new("RGB", (6, 4), (100, 20, 30))
        exif = Image.Exif()
        exif[274] = 6
        image.save(oriented, exif=exif)
        pixbuf = load_oriented_pixbuf(
            candidate_for_path(oriented, DEFAULT_EXTENSIONS))
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (4, 6))

        transparent = self.make_image("transparent.png", mode="RGBA")
        flattened = load_oriented_pixbuf(
            candidate_for_path(transparent, DEFAULT_EXTENSIONS))
        self.assertFalse(flattened.get_has_alpha())
        pixels = bytes(flattened.get_pixels())
        self.assertEqual(pixels[:3], b"\x00\x00\x00")

    def test_animated_gif_uses_a_static_first_frame(self):
        path = self.root / "animated.gif"
        frames = [Image.new("RGB", (5, 3), color)
                  for color in ((255, 0, 0), (0, 255, 0))]
        frames[0].save(path, save_all=True, append_images=frames[1:],
                       duration=20, loop=0)
        pixbuf = load_oriented_pixbuf(
            candidate_for_path(path, DEFAULT_EXTENSIONS))
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (5, 3))

    def test_decoder_diagnostic_has_every_required_format(self):
        support = decoder_support()
        for extension in ("jpg", "jpeg", "png", "webp", "heic", "heif", "avif"):
            self.assertTrue(support[extension]["available"], extension)
            self.assertTrue(support[extension]["decoder"])

    def test_renderer_async_rescan_and_black_fallback_contract(self):
        source = (Path(__file__).parents[1] /
                  "bin/tvbox-render-slideshow").read_text()
        for contract in (
            "ThreadPoolExecutor", "max_workers=1", "self._rescan",
            "self.scaled = None", "_draw_black", "no-valid-images-black-fallback",
            "report_after_first_paint",
        ):
            self.assertIn(contract, source)


if __name__ == "__main__":
    unittest.main()
