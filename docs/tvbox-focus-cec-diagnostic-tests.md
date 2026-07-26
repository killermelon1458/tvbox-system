# TVBox Passive Diagnostic Test Matrix

These are manual/integration tests. Phase 1 observers must be running without
automatic recovery. Capture a baseline with `tvbox-diag snapshot` before each
test and a bundle afterward.

## Baseline

1. Start Kodi, set context to Kodi or Plex through normal TVBox controls, and
   verify `kodi_native_minimal`.
2. Confirm TV on, remote, keyboard, and intended controller navigate.
3. Run `tvbox-diag status`, `tvbox-diag test focus`, and a snapshot.
4. Expect no process/toplevel/profile mismatch. Focus may correctly be unknown.

## Deliberate focus theft

1. Leave context as Kodi/Plex and deliberately focus a terminal/file manager.
2. Confirm `focus_mismatch_confirmed` only if activation is truly exposed;
   otherwise expect `focus_mismatch_suspected` with the limitation.
3. Confirm no automatic refocus. Restore focus manually.

## Controlled state mismatches

Record the original values first. Use the normal repo-owned commands to set a
temporary nonmatching context and then a wrong profile, one test at a time.
Confirm `context_process_mismatch` and `input_profile_mismatch`. Restore both
immediately. Do not leave the appliance in the test state.

## One-receiver baseline

1. Disconnect all but one intended 8BitDo receiver.
2. Record serial, USB path, active and IDLE VID:PID, event/js nodes, and
   by-id/by-path links.
3. Confirm Kodi navigation, Home/Exit, and AntiMicroX target/profile.
4. Do not identify the receiver by `jsN`, `eventN`, or common product name alone.

## Controlled controller sleep/wake and Kodi reacquisition

1. Leave Kodi running and let the controller enter normal idle; then wake it.
2. Record USB, udev, event/js lifecycle, Kodi log, Kodi `/proc/<pid>/fd`, and
   AntiMicroX transitions.
3. Test navigation without changing anything.
4. If broken, verify FLIRC and keyboard independently and record toplevel state.
5. Restart only AntiMicroX manually, record whether native Kodi navigation
   changes, then restore the intended profile.
6. Only after capturing another snapshot, restart Kodi manually and record the
   comparison. No automatic restart may be enabled.

`kodi_controller_reacquisition_failed` requires combined evidence (Kodi
read/open errors plus stable recreated nodes not open by Kodi or a controlled
navigation failure). Renumbering alone is not sufficient.

## Multiple receivers

Repeat the baseline and sleep/wake test with the current receiver set. Compare
stable IDs, node reassignment, duplicate names, AntiMicroX target `all`, Home
event duplication, and Kodi acquisition. Do not call multiple receivers causal
unless the one-versus-multiple comparison demonstrates it.

## Remote-versus-controller isolation

During a controller failure, separately test FLIRC, a known keyboard, each
controller, and each receiver path. Record focus/toplevel, context/profile, and
Kodi state. If FLIRC/keyboard still control Kodi, do not classify the incident
as focus theft.

## Home/Exit source investigation

Use a temporary, explicitly identified-device passive input test only after
verifying it does not grab the device. Record monotonic/wall time, stable device
identity/path/serial, EV_KEY code, value (`0` release, `1` press, `2` repeat),
button counter, and transition-lock probe. Correlate with labwc/tvboxctl and
AntiMicroX logs. Never record arbitrary keyboard text.

Compare FLIRC, each 8BitDo receiver, keyboard repeat, AntiMicroX-generated F12,
and Kodi-local handling. Phase 1 does not change thresholds or debounce.

## CEC and TV power-cycle

After passive CEC coexistence is proven, perform at least three cycles:

```text
TV on baseline
TV off for at least 10 seconds
TV on
wait for HDMI/Wayland stabilization
```

Run one from plain Kodi, one in Plex UI, and one during Plex playback if safe.
Record CEC raw/parsed messages and any separately approved read-only query,
DRM/EDID/mode, Wayland output/toplevel/focus, Kodi process/JSON-RPC, context,
profile, controller nodes, FLIRC arrival, Kodi response, and whether a mouse
click restores behavior. Do not transmit standby/on/source/routing commands.

## Non-interference and retention

- Kodi CEC, remote, controller, Home/F12, and panic/Exit remain available.
- No observer grabs FLIRC/controller, steals focus, creates a window, changes
  profile/playback, restarts anything, sends CEC control, or changes HDMI.
- Moonlight Home remains soft; Spotify, YouTube, Steam Link behavior is unchanged.
- Inspect `systemctl --user status`, `ps`, and journal size/resource use.
- Snapshots remain at or below `SNAPSHOT_RETENTION`; journald supplies bounded
  system retention. Bundle journal export is capped at 2,000 observer lines.
