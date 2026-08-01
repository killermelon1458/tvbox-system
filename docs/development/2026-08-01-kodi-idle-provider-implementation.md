# Kodi idle provider implementation

## Goal

Production-enable conservative automatic idle handling for Kodi and Plex by publishing current-run Kodi playback observations and consuming them in the existing Kodi idle provider.

## Current behavior

The canonical idle engine, automatic screensaver consumer, scheduling, and overlay stack are deployed. The Kodi provider remains disabled because no durable, process-bound playback observation record exists. Discovery proved native Plex-in-Kodi player events, while unauthenticated JSON-RPC is unavailable.

## Problem being solved

Kodi must become idle-eligible only while current-session playback is authoritatively stopped. Starting, playing, paused, unknown, stale, unhealthy, or session-mismatched observations must inhibit. Playback ending must begin a fresh idle epoch so movie duration is never inherited as idle time.

## Files expected to change

- `bin/tvbox-kodi-observerd`
- `config/systemd-user/tvbox-kodi-observer.service`
- `lib/tvbox/idle/`
- `config/idle.toml`
- `install.sh`
- `tests/`
- canonical idle/screensaver plans and `docs/current-system-redeploy.md`

## Proposed implementation

The preferred native service add-on was implemented and tested first, but this Kodi installation registers a newly copied service add-on disabled. Remote `EnableAddon` did not enable it, and making deployment depend on database edits or Kodi credentials would violate the safety contract. That attempt was removed and its disabled live copy was moved out of Kodi's add-on path.

The final implementation is the approved persistent log-follower fallback. `tvbox-kodi-observerd` maintains an incremental inode/offset and partial-line buffer, parses only six allowlisted player events, binds observations to exact Kodi PID/start ticks/executable/boot ID, and atomically publishes mode-0600 `kodi-state.json`. Rotation, truncation, Kodi restart, and observer restart reset playback to unknown. No log body or media metadata is retained. `PrivateTmp=true` was intentionally omitted because live systemd validation proved its mount namespace prevents `/proc/<kodi-pid>/exe` resolution on this appliance; `NoNewPrivileges=true` remains.

The Kodi provider validates freshness, health, stable Kodi process+toplevel readiness, exact current `/proc` session identity, and conservative playback policy. No observer/provider component performs screensaver, overlay, scheduling, input-profile, application-context, Home, or recovery actions.

## Commands used

- `git status --short`
- repository unit, syntax, compile, systemd, and diff checks listed below
- repository `install.sh` for approved deployment
- bounded live status and playback validation commands

## Validation checklist

- [x] Player events normalize starting/playing/paused/stopped safely
- [x] Initial/restarted observer fails safe as unknown
- [x] Atomic mode-0600 current-boot state contains no private media data
- [x] PID and process start identity reject stale Kodi sessions
- [x] Healthy stopped Kodi is eligible; all other playback states inhibit
- [x] Playback/observer/session changes create correct fresh epochs
- [x] Rotation, truncation, partial lines, and multiple-event reads are tested
- [x] Existing activity source, transition, recovery, and disagreement inhibition remains intact
- [x] Full existing tests pass
- [x] Installer deploys/enables the daemon and safely migrates only Kodi provider configuration
- [x] Accelerated live Kodi/Plex validation passes and production timeout is restored
- [x] Appliance is returned to stable Kodi with no overlay active

## Test results

`python3 -m unittest discover -s tests -v`: 153 tests passed.

`bash -n install.sh`: passed. Python sources passed `compileall`; Kodi XML parsed; `git diff --check` passed. `systemd-analyze --user verify` passed outside the restricted tool sandbox, and the deployed unit loaded and ran successfully under the real user manager.

Live validation proved current-session `OnPlay`/`OnAVStart` -> playing, `OnPause` -> paused, `OnResume` -> playing, and `OnStop` -> stopped. Playing and paused remained inhibited with no overlay. Stop created a fresh 600-second epoch. With an isolated live 10-second timeout and existing 3-second stability delay, Kodi progressed active -> idle-pending -> idle and created exactly one ready automatic slideshow request. The user visually confirmed slideshow appearance and FLIRC, physical-keyboard, and physical-pointer dismissal. Production timeout 600 was restored; final state was stable Kodi, stopped, active/non-idle, transition clear, and overlay inactive.

During final cleanup after the production 600-second timeout elapsed, a manual `tvbox-screensaver stop` released generation 25 but the already-running policy daemon recreated generation 26 instead of persisting same-epoch suppression. Canonical non-destructive Home safely cleared it and began a fresh epoch. Unit coverage for suppression still passes; this live daemon-state discrepancy is not caused by the Kodi provider and remains a screensaver-policy follow-up rather than being silently claimed as validated here.

## Known risks

- The fallback cannot infer stopped from silence. After Kodi/observer restart, rotation, or truncation, playback remains unknown until a current-run allowlisted event establishes state. This is deliberately conservative.
- Native gamepad navigation remains outside approved activity coverage.
- One live same-epoch manual-stop suppression discrepancy remains in the
  pre-existing screensaver policy daemon; Home remains a safe workaround.

## Rollback notes

Set `[providers.kodi] enabled = false` in the deployed idle configuration. Disable only `tvbox-kodi-observer.service` if observer rollback is required. The canonical idle engine, desktop provider, automatic consumer, manual screensaver, scheduling, and renderers remain installed.

## Status

Status: validated
