"""Syncthing-safe slideshow discovery, decoding, and sizing."""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import random
import stat
import threading


REQUIRED_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "heic", "heif", "avif")
OPTIONAL_EXTENSIONS = ("gif", "tif", "tiff", "bmp")
DEFAULT_EXTENSIONS = REQUIRED_EXTENSIONS + OPTIONAL_EXTENSIONS
IGNORED_DIRECTORIES = {".stfolder", ".stversions"}
UNSUPPORTED_MEDIA = {"mov", "mp4", "m4v", "avi", "mkv", "dng", "svg"}


@dataclass(frozen=True)
class ImageCandidate:
    path: Path
    size: int
    mtime_ns: int
    inode: int
    device: int

    @property
    def fingerprint(self):
        return self.size, self.mtime_ns, self.inode


class ImageLoadError(RuntimeError):
    pass


class FailureReporter:
    """Log one failure per unchanged file, retrying changed files."""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("tvbox.slideshow")
        self._reported = {}
        self._lock = threading.Lock()

    def failure(self, candidate, reason):
        key = str(candidate.path)
        fingerprint = candidate.fingerprint
        with self._lock:
            if self._reported.get(key) == (fingerprint, reason):
                return False
            self._reported[key] = (fingerprint, reason)
        self.logger.warning("image skipped path=%r reason=%s size=%d mtime_ns=%d",
                            key, reason, candidate.size, candidate.mtime_ns)
        return True

    def success(self, path):
        with self._lock:
            self._reported.pop(str(path), None)


def _is_syncthing_temp(name):
    lowered = name.lower()
    return ((lowered.startswith(".syncthing.") and lowered.endswith(".tmp"))
            or (lowered.startswith("~syncthing~") and lowered.endswith(".tmp")))


def candidate_for_path(path, extensions, max_file_bytes=256 * 1024 * 1024):
    path = Path(path)
    name = path.name
    if not name or name.startswith(".") or _is_syncthing_temp(name):
        return None
    extension = path.suffix.lower().lstrip(".")
    allowed = {value.lower().lstrip(".") for value in extensions}
    if extension in UNSUPPORTED_MEDIA or extension not in allowed:
        return None
    try:
        info = path.stat(follow_symlinks=False)
    except (FileNotFoundError, PermissionError, OSError):
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    if info.st_size > max_file_bytes:
        return None
    return ImageCandidate(
        path, info.st_size, info.st_mtime_ns, info.st_ino, info.st_dev)


def scan_images(directory, recursive, extensions, max_files,
                max_file_bytes=256 * 1024 * 1024, logger=None):
    logger = logger or logging.getLogger("tvbox.slideshow")
    root = Path(directory)
    try:
        root_info = root.stat(follow_symlinks=False)
        if not stat.S_ISDIR(root_info.st_mode):
            return []
    except (FileNotFoundError, PermissionError, OSError):
        return []
    result = []
    seen_files = set()
    seen_directories = {(root_info.st_dev, root_info.st_ino)}
    pending = [(root, True)]

    while pending and len(result) < max_files:
        path, is_directory = pending.pop()
        name = path.name
        if is_directory:
            try:
                entries = sorted(os.scandir(path),
                                 key=lambda item: item.name.lower())
            except (FileNotFoundError, PermissionError, OSError) as exc:
                logger.warning("slideshow directory skipped path=%r reason=%s",
                               str(path), exc)
                continue
            children = []
            for entry in entries:
                name = entry.name
                if name.startswith(".") or _is_syncthing_temp(name):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if recursive and name.lower() not in IGNORED_DIRECTORIES:
                            info = entry.stat(follow_symlinks=False)
                            identity = (info.st_dev, info.st_ino)
                            if identity not in seen_directories:
                                seen_directories.add(identity)
                                children.append((Path(entry.path), True))
                        continue
                    if entry.is_file(follow_symlinks=False):
                        children.append((Path(entry.path), False))
                except OSError:
                    continue
            # A LIFO worklist processes the sorted entries in their original
            # depth-first order without Python call-stack recursion.
            pending.extend(reversed(children))
            continue

        if name.startswith(".") or _is_syncthing_temp(name):
            continue
        candidate = candidate_for_path(
            path, extensions, max_file_bytes=max_file_bytes)
        if candidate:
            identity = (candidate.device, candidate.inode)
            if identity in seen_files:
                continue
            seen_files.add(identity)
            result.append(candidate)
    return result


def fitted_size(image_width, image_height, area_width, area_height, fit_mode):
    if min(image_width, image_height, area_width, area_height) <= 0:
        return 1, 1
    contain = min(area_width / image_width, area_height / image_height)
    cover = max(area_width / image_width, area_height / image_height)
    scale = contain if fit_mode == "contain" else cover
    return max(1, round(image_width * scale)), max(1, round(image_height * scale))


def flatten_alpha_over_black(pixbuf):
    if not pixbuf.get_has_alpha():
        return pixbuf
    from gi.repository import GdkPixbuf
    result = GdkPixbuf.Pixbuf.new(
        GdkPixbuf.Colorspace.RGB, False, 8,
        pixbuf.get_width(), pixbuf.get_height())
    result.fill(0x000000ff)
    pixbuf.composite(
        result, 0, 0, result.get_width(), result.get_height(), 0, 0, 1, 1,
        GdkPixbuf.InterpType.NEAREST, 255)
    return result


def _decode_gdk(path, max_dimension):
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    _image_format, width, height = GdkPixbuf.Pixbuf.get_file_info(str(path))
    if width <= 0 or height <= 0:
        raise ImageLoadError("invalid-image-dimensions")
    if max(width, height) > max_dimension:
        scale = max_dimension / max(width, height)
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(path), max(1, round(width * scale)),
            max(1, round(height * scale)), True)
    return GdkPixbuf.Pixbuf.new_from_file(str(path))


def load_oriented_pixbuf(candidate, max_dimension=8192, decoder=_decode_gdk):
    if isinstance(candidate, (str, Path)):
        path = Path(candidate)
        candidate = candidate_for_path(path, DEFAULT_EXTENSIONS)
        if candidate is None:
            raise ImageLoadError("not-a-current-regular-image")
    try:
        before = candidate.path.stat(follow_symlinks=False)
        if (before.st_size, before.st_mtime_ns, before.st_ino) != candidate.fingerprint:
            raise ImageLoadError("file-changed-before-decode")
        if before.st_size <= 0:
            raise ImageLoadError("empty-file")
        pixbuf = decoder(candidate.path, max_dimension)
        pixbuf = pixbuf.apply_embedded_orientation()
        after = candidate.path.stat(follow_symlinks=False)
    except ImageLoadError:
        raise
    except FileNotFoundError as exc:
        raise ImageLoadError("file-disappeared") from exc
    except PermissionError as exc:
        raise ImageLoadError("permission-denied") from exc
    except Exception as exc:
        raise ImageLoadError(f"decoder-error:{exc.__class__.__name__}") from exc
    if (after.st_size, after.st_mtime_ns, after.st_ino) != candidate.fingerprint:
        raise ImageLoadError("file-changed-during-decode")
    if pixbuf.get_width() <= 0 or pixbuf.get_height() <= 0:
        raise ImageLoadError("invalid-image-dimensions")
    return flatten_alpha_over_black(pixbuf)


def valid_images(paths, loader=load_oriented_pixbuf):
    valid = []
    for item in paths:
        try:
            pixbuf = loader(item)
            if pixbuf and pixbuf.get_width() > 0 and pixbuf.get_height() > 0:
                path = item.path if isinstance(item, ImageCandidate) else item
                valid.append((path, pixbuf))
        except Exception:
            continue
    return valid


def order_images(paths, shuffle):
    result = list(paths)
    if shuffle:
        random.shuffle(result)
    return result


def decoder_support():
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    available = set()
    decoders = {}
    for image_format in GdkPixbuf.Pixbuf.get_formats():
        name = image_format.get_name()
        for extension in image_format.get_extensions():
            extension = extension.lower()
            available.add(extension)
            decoders[extension] = name
    return {
        extension: {
            "available": extension in available,
            "decoder": decoders.get(extension),
            "required": extension in REQUIRED_EXTENSIONS,
        }
        for extension in DEFAULT_EXTENSIONS
    }
