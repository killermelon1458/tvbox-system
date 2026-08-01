# Kodi/Plex Playback Signal Validation

Date: 2026-08-01

Status: discovery validated; provider integration not implemented

## Goal

Determine whether current Plex playback inside Kodi can be distinguished from
stopped playback without enabling the production Kodi idle provider.

## Current behavior

Kodi is the stable application context and Plex runs as `script.plexmod` inside
Kodi. The Kodi idle provider remains disabled because observed state does not
yet publish trustworthy playback and menu/view facts.

## Problem being solved

Automatic screensaving over Kodi must never activate during video playback.
A future Kodi provider therefore needs current-run playing/stopped evidence and
a separate trustworthy menu/view signal.

## Files expected to change

Documentation only for this discovery. No provider or production configuration
is changed.

## Proposed implementation

Compare observation-only Kodi JSON-RPC, Wayland, process, audio, and sanitized
Kodi/Plex log evidence while playing and after one user-authorized Backspace.

## Commands used

```text
tvbox-diag snapshot
sanitized inspection of ~/.kodi/temp/kodi.log
wtype -k BackSpace (explicitly authorized by the user)
wlrctl toplevel list
```

## Validation checklist

- [x] Capture playing-state evidence before changing playback.
- [x] Confirm JSON-RPC availability/authentication state.
- [x] Stop playback with the authorized input.
- [x] Capture the corresponding stopped-state evidence.
- [x] Avoid recording Plex URLs, tokens, credentials, or media titles.
- [x] Leave production Kodi provider disabled.

## Test results

Kodi JSON-RPC at `127.0.0.1:8080/jsonrpc` returned HTTP 401 for ping, GUI
properties, and active-player queries, so it is not currently usable by the
unauthenticated diagnostic/state stack.

The current Kodi log provided clear Plex notification events:

```text
playing: script.plexmod Notification: xbmc Player.OnPlay
playing: script.plexmod Notification: xbmc Player.OnAVStart (speed 1)
stopped: script.plexmod Notification: xbmc Player.OnStop
```

The newest terminal event before Backspace was `OnAVStart`; after the one
authorized Backspace it was `OnStop`. Kodi remained the exact process and
Wayland toplevel throughout. This proves that current-run Plex playing versus
stopped state is observable from Kodi's log on this appliance.

## Known risks

- Log rotation, Kodi restart, truncation, event ordering, partial writes, and
  stale events must be handled before this becomes provider authority.
- The playback event does not by itself prove that the current stopped view is
  a safe Plex/Kodi menu. A trustworthy `kodi_view=menu` source remains missing.
- Pause policy needs an explicit decision; `Player.OnPause` is observable but
  should not automatically be treated as menu-idle.
- JSON-RPC credentials must not be scraped or logged. A future authenticated
  observer would need a deliberately managed credential path.

## Rollback notes

No implementation or live configuration changed. The authorized Backspace
stopped the test playback; the user can resume playback normally through Plex.
