# 8BitDo Kodi Input Reconnect Bug

## Goal

Document the observed Kodi controller-input failure involving 8BitDo Ultimate 2C
wireless controllers, the delayed Home panic recovery, and the apparently
incorrect Kodi Favourites layout.

This note is a bug report and diagnostic record. It does not implement a fix.

## Current behavior

TVBox launches Kodi with the `kodi_native_minimal` input profile. Normal Kodi
navigation is handled by Kodi's native joystick support. AntiMicroX maps only
the controller recovery buttons:

- Home/Guide to F12
- Back/View to F5

Kodi opens `FavouritesBrowser` at startup and through Home/F12 recovery.

Five repeated Home presses are intended to run panic recovery, hard-restart
Kodi, and return to Favourites.

## Problem being solved

The following user-visible failures were observed:

- The 8BitDo controller stopped producing any visible response in Kodi.
- Pressing controller Home five times produced no immediate visible recovery.
- The normal remote still controlled Kodi.
- A single remote Home press produced no immediate visible result.
- Turning the controller off and back on did not immediately restore input.
- Kodi later closed and reopened, after which the controller worked.
- The Kodi Favourites screen appeared different from the expected layout.

## Diagnostic findings

### Controller identities

Linux exposed multiple 8BitDo receiver/controller identities concurrently.
During the initial diagnostic snapshot:

- USB path `1-1.1.2`, serial `E438326060`, exposed an active Ultimate 2C.
- USB path `1-1.3`, serial `8FCA7505C6`, exposed another active Ultimate 2C.
- USB path `1-1.4`, serial `E5245226B5`, exposed an `8BitDo IDLE` device.

The two active controllers were both presented to Kodi as:

```text
Generic X-Box pad
```

Kodi initialized both `/dev/input/js0` and `/dev/input/js1`. Identical names and
an AntiMicroX controller target of `all` make it difficult to associate input
state with one specific physical receiver.

### Receiver sleep and reconnect behavior

The receiver on USB path `1-1.3` repeatedly alternated between:

```text
2dc8:310a  8BitDo Ultimate 2C Wireless Controller
2dc8:301c  8BitDo IDLE
```

Each transition destroyed and recreated the Linux joystick device.

Kodi repeatedly logged:

```text
ScanEvents: failed to read joystick "Generic X-Box pad" on /dev/input/js1 - 19 (No such device)
```

On at least one reconnect, Kodi also logged:

```text
ScanForJoysticks: can't open /dev/input/js1 (errno=13)
```

Kodi sometimes rediscovered the joystick several seconds later, but recovery
was not reliable enough to maintain controller input.

### Confirmed failure timeline

On 2026-07-25, the reported failure correlated with this host timeline:

```text
01:32:53  Home recovery request received.
01:32:54  Additional Home events were counted while the control lock was held.
01:32:54  The counter reached 20 Home events.
01:32:56  Panic-local recovery started and captured a diagnostic snapshot.
01:32:57  USB path 1-1.3 disconnected; Kodi lost /dev/input/js1.
01:32:57  The receiver reappeared as 8BitDo IDLE.
01:32:58  The IDLE device disconnected.
01:32:59  The receiver reappeared as an Ultimate 2C controller.
01:32:59  Linux recreated the Generic X-Box pad input devices.
01:33:03  Panic recovery sent Kodi a termination signal.
01:33:11  Kodi restarted.
01:33:11+ Kodi and AntiMicroX reopened their input paths.
```

The user confirmed that the controller worked after Kodi restarted.

This establishes that the visible close/reopen was the configured Home panic
recovery, not an unexplained Kodi crash.

### Home button behavior

The recovery log recorded 20 Home events within approximately two seconds even
though the user did not intentionally perform 20 distinct presses. The exact
input source of every event is not present in the current log.

Confirmed:

- Home events can accumulate while `tvboxctl` holds its main control lock.
- The fifth counted event schedules panic recovery.
- The hard restart is delayed by cleanup and termination waits.
- The delay makes recovery appear unresponsive before Kodi closes.

Not yet confirmed:

- Whether the repeated events came from keyboard repeat, the remote, the
  controller, duplicated receivers, or more than one input path.
- Whether the current counter should count auto-repeat events as separate
  presses.

### AntiMicroX behavior

The selected input profile was `kodi_native_minimal`, and AntiMicroX was running
after the incident. It was configured without `--profile-controller`, so the
profile target was `all`.

Every Home recovery assertion restarts the TVBox-owned AntiMicroX process. The
logs show several rapid AntiMicroX stop/start cycles during repeated Home
handling. This increases input churn while Kodi is also rescanning controllers.

The minimal profile itself maps only two buttons and leaves ordinary Kodi
navigation native. Therefore, restarting AntiMicroX alone cannot repair a stale
native Kodi joystick handle.

### Kodi Favourites layout

A diagnostic screenshot showed Kodi's stock Estuary Favourites list view:

- large selected-item artwork on the left
- a five-item list on the right
- 1920x1080 output resolution
- skin zoom set to zero

The five entries and their artwork paths in `favourites.xml` were valid.

Kodi's `ViewModes6.db` was modified at `01:16:43`, shortly before the reported
layout concern. The evidence supports a changed Favourites view mode rather
than corrupt favourites or an incorrect display resolution. It is not yet
confirmed which input changed the view.

Kodi also briefly lost and reacquired the HDMI display around `01:26`, but it
returned to 1920x1080. No evidence currently connects that display event to the
saved Favourites view.

## Files expected to change

For this bug report:

```text
docs/development/2026-07-25-8bitdo-kodi-input-reconnect-bug.md
```

Possible future implementation files, subject to a separate approved change:

```text
bin/tvbox-inputctl
bin/tvboxctl
input-profiles/kodi_native_minimal.gamecontroller.amgp
install.sh or a repo-owned udev/systemd component
docs/current-system-redeploy.md
```

## Proposed implementation

No implementation is included in this report.

Potential fixes to evaluate:

1. Test with only one 8BitDo receiver connected and identify whether duplicate
   active receivers are required to reproduce the failure.
2. Bind AntiMicroX to an explicit controller instead of targeting `all`.
3. Detect controller remove/add events and refresh the local input profile after
   the joystick node is stable.
4. Determine whether Kodi can safely reload its peripheral subsystem without a
   full restart.
5. If Kodi cannot reliably reacquire the joystick, add a narrowly scoped
   reconnect recovery that restarts Kodi only after a confirmed controller
   re-add and failed input rescan.
6. Debounce Home/Exit recovery events so one physical press or key-repeat burst
   cannot count as many deliberate presses.
7. Add the input source and monotonic timestamp to Home/Exit recovery logging
   where the input layer can provide them.
8. Preserve Home/F12 recovery through a path that does not depend solely on
   Kodi's native joystick handle.
9. Define and deploy the intended Kodi Favourites view rather than relying on a
   mutable per-user view-mode database, if a stable appliance layout is
   required.

## Commands used

Read-only diagnostic commands included:

```text
git status --short
rg
sed
awk
find
sha256sum
lsusb
bluetoothctl
ps
ls -l /dev/input
journalctl -k
strings
curl to Kodi's local JSON-RPC endpoint
grim to /tmp/tvbox-kodi-diagnostic.png
```

No installer, service restart, reboot, or live configuration change was run.

## Validation checklist

### Repo validation

- [x] Confirm the report distinguishes confirmed observations from hypotheses.
- [x] Record the controller identities and relevant USB paths.
- [x] Record the Kodi joystick errors.
- [x] Record the controller reconnect and panic-recovery timeline.
- [x] Explain why Kodi restarted and why input worked afterward.
- [x] Record the Favourites layout findings.
- [x] Identify safe follow-up tests without claiming an implemented fix.
- [x] Confirm no code or configuration files changed.

### Deploy validation

- [ ] Reproduce with exactly one 8BitDo receiver connected.
- [ ] Reproduce controller sleep/wake while Kodi remains open.
- [ ] Verify whether Kodi automatically reacquires the recreated joystick.
- [ ] Identify the source of repeated Home events.
- [ ] Verify any future debounce behavior with remote and controller inputs.
- [ ] Verify any future reconnect recovery without breaking Home/F12 safety.
- [ ] Confirm the intended Favourites view with the user.

## Test results

### Repo validation

The bug report was compared against the collected live logs and diagnostic
snapshot. It documents the observed sequence without changing behavior.

### Deploy validation

Not run. The incident itself supplied live diagnostic evidence, but no proposed
fix has been deployed or tested.

## Known risks

- Automatically restarting Kodi on every controller reconnect could interrupt
  playback or react to normal controller sleep.
- Restarting AntiMicroX does not necessarily refresh Kodi's native joystick
  handle.
- Multiple identical receivers can make index-based controller selection
  unstable across reconnects.
- Aggressive input-device monitoring may create loops between profile changes,
  Kodi recovery, and USB reconnect events.
- Removing or weakening Home panic recovery could trap the user in a broken
  application state.
- A Favourites view-mode enforcement mechanism could override intentional user
  customization.

## Rollback notes

Documentation-only change. Rollback consists of removing:

```text
docs/development/2026-07-25-8bitdo-kodi-input-reconnect-bug.md
```

No live file, service, symlink, Kodi configuration, or input profile requires
restoration.

## Status

Status: draft

The failure is documented and supported by logs. Root-cause isolation and a
validated fix remain pending.
