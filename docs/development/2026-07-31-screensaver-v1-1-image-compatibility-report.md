# Screensaver v1.1 Image Compatibility Report

Date: 2026-07-31

Status: validated; physical cursor observation pending user confirmation

## Goal

Harden the existing GTK 3/GtkLayerShell black and slideshow renderers for
household use: overlay-owned hidden cursors, permanently opaque composition,
real phone/web image decoding, and Syncthing-safe discovery and failure
isolation without changing scheduling or lifecycle architecture.

## Current behavior

The v1 overlay manager and renderers are implemented but uncommitted. Both
renderers use GTK 3.24, GDK Wayland, GdkPixbuf 2.42, and GtkLayerShell. Black
is Cairo-painted and slideshow uses a black window draw plus centered
`Gtk.Image`. Slideshow scans by extension once at startup, decodes on the GTK
thread, preloads one image synchronously, and does not yet filter Syncthing
internals or support HEIC/HEIF/AVIF through installed loaders.

## Problem being solved

Cursor visibility, incomplete decoder coverage, UI-thread decode, scan races,
and one-time discovery make the v1 implementation unsuitable for a live
Syncthing-backed household photo directory.

## Files expected to change

- `lib/tvbox/overlay/renderer.py`
- `lib/tvbox/screensaver/slideshow.py`
- `bin/tvbox-render-black`
- `bin/tvbox-render-slideshow`
- `bin/tvbox-screensaver`
- `config/screensaver.toml`
- `install.sh`
- focused slideshow/renderer/decoder tests and small fixtures
- canonical screensaver and redeployment documentation

## Proposed implementation

Keep GTK/GdkPixbuf and the existing manager. Add a shared overlay cursor and
opaque-window setup helper, a candidate/stat/decode layer with per-file
diagnostics and change-sensitive failure deduplication, bounded asynchronous
decode/preload and periodic rescan, explicit supported-format diagnostics,
and distribution-packaged HEIF/AVIF GdkPixbuf loaders.

## Commands used

```text
git status --short
git log -8 --oneline --decorate
rg/sed inspection of renderers, manager, policy, installer, tests, and docs
GTK/GdkPixbuf version and loader inspection
dpkg-query and apt-cache package inspection
```

## Validation checklist

### Repository validation

- [x] Shared overlay-owned invisible cursor for black and slideshow.
- [x] Opaque full-output black composition on every renderer path.
- [x] Contain geometry for landscape, portrait, square, small, and exact-ratio images.
- [x] RGBA pixels composite over black without transparency leakage.
- [x] Required and optional extension filtering is case-insensitive.
- [x] Syncthing temporary/internal, hidden, video, directory, and non-regular entries are ignored.
- [x] Removed, changed, unreadable, empty, malformed, oversized, and unsupported files are isolated.
- [x] Failure logs deduplicate until file metadata changes.
- [x] Periodic rescan handles additions/removals and invalid current images.
- [x] Decode/preload runs outside the GTK event path.
- [x] Real JPEG, PNG, WebP, HEIC/HEIF, and AVIF fixtures decode.
- [x] EXIF orientation and static first-frame behavior are verified.
- [x] Existing manager replacement and schedule tests remain passing.
- [x] Shell syntax, Python compilation, systemd verification, and `git diff --check` pass.

### Deployment and live validation

- [x] Installer reproducibly installs/checks required loaders.
- [x] Runtime reports every required format decoder available.
- [x] Blank and slideshow services launch without duplicates.
- [x] Required formats render on the live Pi.
- [x] Landscape, portrait, square, small, and transparent images retain black coverage.
- [x] Syncthing-style temporary/bad/video files do not interrupt valid images.
- [x] Active slideshow-to-black and black-to-slideshow replacement remains gapless.
- [x] Captured display shows no underlying pixels during black/fallback paths.
- [ ] Cursor hidden while physically moved in both modes (user-visible observation required).
- [ ] Cursor restored after dismiss (user-visible observation required).
- [x] Final state is inactive overlay, no renderer, stable Kodi, and active TV source.

## Test results

### Automatically tested

```text
python3 -m unittest discover -s tests -v
Ran 100 tests ... OK
```

Real fixtures decode through GdkPixbuf for JPEG, PNG, WebP, HEIC, HEIF, and
AVIF. Tests also cover EXIF orientation, portrait HEIF/AVIF, alpha flattening,
static GIF first frame, contain geometry, Syncthing filtering, zero/truncated/
random data, before/during-decode changes, disappearing files, failure
deduplication, bounded scan, asynchronous worker/rescan contracts, and all
existing overlay, schedule, state, and lifecycle behavior.

Shell syntax, Python compilation, `systemd-analyze --user verify`, and
`git diff --check` passed.

### Live-machine tested and visually captured

- `heif-gdk-pixbuf` 1.19.8-1 installed. HEVC uses the installed
  `libheif-plugin-libde265`; AV1 uses `libheif-plugin-dav1d`.
- `tvbox-screensaver formats` reports all required formats available. JPEG,
  PNG, and WebP use named loaders; HEIC/HEIF/AVIF use `heif/avif`.
- Actual JPEG, PNG, WebP, HEIC, HEIF, and AVIF each rendered in a ready
  slideshow generation above Kodi.
- Landscape, portrait, square, 4x3-pixel, and transparent PNG captures were
  centered/contained with black corners. Single-pass Cairo composition gave
  the transparent source an exact black exterior.
- A live folder containing valid JPEG, zero-byte JPEG, truncated WebP,
  `.syncthing.*.tmp`, and `.mov` stayed healthy. Removing the current image
  produced all black; adding completed HEIC later displayed it with the same
  renderer PID.
- Slideshow-to-black and black-to-slideshow retained the manager instance with
  zero sampled inactive states. The black capture had no non-black pixels.
- Pointer movement was injected while both overlays were active. Ordinary
  `grim` captures do not contain the hardware cursor, so cursor visibility and
  post-dismiss restoration are not claimed visually verified.
- Temporary fixtures/config were removed, the prior household config was
  backed up as `screensaver.toml.bak.20260731-v11-final`, the canonical v1.1
  config was deployed byte-for-byte from the repo, and temporary encoder-only
  packages were removed.

### Manual visual checklist

Still requiring user observation:

1. Start black, physically move the mouse, and confirm no cursor appears.
2. Stop/Home and confirm the normal cursor returns.
3. Repeat both observations with slideshow active.

## Final implementation

Both overlays call `Gdk.Window.set_cursor()` with a surface-owned
`Gdk.CursorType.BLANK_CURSOR`; destroying the surface restores compositor
cursor behavior without global configuration or pointer movement.

Slideshow paints black with Cairo SOURCE, then its centered opaque pixbuf with
Cairo OVER in the same callback. Transparent input is flattened over black.
`contain` is the validated default.

Discovery always includes the configured root and eligible nested directories
as one collection. It uses non-following regular-file stats, prunes directory
symlinks and Syncthing/hidden internals, deduplicates device/inode identities,
and excludes unsupported/video extensions and oversized files. Directory
failures are logged and isolated, and an iterative worklist avoids recursion
limits and traversal loops.
The loader validates content, bounds decode dimensions, applies embedded
orientation, checks size/mtime/inode before and after decode, and logs each
unchanged failure once. One worker holds current plus next decoded images; a
bounded rescan discovers additions/removals and retries changed files.

## Packages

Runtime packages managed by `install.sh`:

```text
gir1.2-gtk-3.0
gir1.2-gtklayershell-0.1
libgdk-pixbuf2.0-bin
heif-gdk-pixbuf
```

`libheif-examples`, `libheif-plugin-x265`, and `libheif-plugin-aomenc` were
used temporarily to generate legal tiny fixtures and removed afterward. They
are not runtime dependencies.

## Known risks

Very large compressed images can cause decoder memory pressure. V1.1 will use
bounded dimensions/file size and one-worker/current-plus-next buffering rather
than a persistent cache. Cursor absence cannot be proven from ordinary
screenshots on all Wayland compositors and must be reported separately.

## Rollback notes

Restore the pre-v1.1 Git revision and rerun `/opt/tvbox-system/install.sh`.
If package rollback is required, remove only packages newly documented here
after stopping `tvbox-screensaver-policy.service` and `tvbox-overlay.service`.
Do not kill renderers by executable name; stop the manager unit so its owned
control group is cleaned up.
