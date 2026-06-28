# TVBox Home / Exit / Panic Recovery Plan Amendment

## 1. Purpose

This document defines the revised Home, Exit, repeated-press, and panic-recovery behavior for TVBox.

This is a self-contained amendment to the existing `tvboxctl` plan. It supersedes earlier Home/Exit behavior where there is a conflict, but it does not replace the broader TVBox architecture.

The goal is to make the remote usable even when Kodi, Plex, Chromium, Moonlight, Spotify, Steam Link, or the Wayland display stack becomes confused.

The key distinction is:

```text
Home = recover to usable TV mode.
Exit = close or leave the current thing.
Panic = emergency repair when normal controls fail.
```

---

## 2. Background and Failure This Addresses

A recent failure showed that Kodi can remain alive but become visually or input wedged.

Observed behavior:

```text
/usr/local/bin/tvbox-kodi
```

made a sound but did not visibly recover the UI.

A hard Kodi restart did recover the system:

```bash
pkill -TERM -x kodi.bin 2>/dev/null || true
pkill -TERM -x kodi 2>/dev/null || true
sleep 4
pkill -9 -x kodi.bin 2>/dev/null || true
pkill -9 -x kodi 2>/dev/null || true
sleep 2
/usr/local/bin/tvbox-kodi &
```

Conclusion:

```text
Kodi process exists != Kodi is healthy.
kodi-send works != Kodi's Wayland/video surface is healthy.
A recovery path must be able to hard-restart Kodi from the remote.
```

This appears related to HDMI / Wayland / Kodi display state after idle, not a total Raspberry Pi freeze. SSH worked, the system was not overloaded, and hard-restarting Kodi fixed Plex.

---

## 3. Existing Design Rules Preserved

This amendment keeps these existing TVBox design rules:

```text
1. tvboxctl owns global policy.
2. Thin wrapper scripts should delegate to tvboxctl where possible.
3. Home and Exit must work globally through labwc keybinds.
4. Kodi is the home shell.
5. Plex is treated as Kodi state because it is a Kodi add-on.
6. External local apps should not pile up behind Kodi.
7. Moonlight Home is soft/local-only.
8. Moonlight Exit may be destructive and can stop the Sunshine host session/app.
9. Panic recovery must not broad-kill unrelated Chromium, shell, or host-side services.
10. The repo under /opt/tvbox-system remains the source of truth.
```

---

## 4. Button Semantics

### 4.1 Home / F12

Home means:

```text
Make the TVBox usable as a TV again.
Return to Kodi/Favourites.
Preserve remote host state where possible.
```

Home should be safe. It should not destructively stop Sunshine host apps.

### 4.2 Exit / F5

Exit means:

```text
Close or leave the current thing.
```

Exit is more aggressive than Home. It should work on one press in normal contexts.

The main exception is plain Kodi:

```text
Plain Kodi is the home shell.
Accidentally closing Kodi is annoying.
Therefore plain Kodi closes only on a second Exit press within the counter window.
```

### 4.3 Panic Mode

Panic mode means:

```text
The normal state model is probably wrong or the GUI is wedged.
Clean up local TVBox foreground apps and relaunch Kodi hard.
```

Panic mode is entered by repeated presses:

```text
Home pressed 5 times within the counter window.
Exit pressed 5 times within the counter window.
```

Home panic and Exit panic should call the same backend recovery function.

---

## 5. Repeated-Press Counter Policy

Use separate counters for Home and Exit.

Recommended runtime files:

```bash
/run/user/1000/tvbox/button-home-state
/run/user/1000/tvbox/button-exit-state
/run/user/1000/tvbox/last-panic
```

Recommended counter windows:

```text
Home counter window: 10 seconds
Exit counter window: 8 seconds
Panic threshold: 5 presses
Kodi close threshold on Exit: 2 presses
```

Counters should reset when:

```text
The counter window expires.
A panic recovery completes.
The box is rebooted.
```

Counters should not depend on active context being correct. The whole point is to recover when active context is stale or misleading.

---

## 6. Home Behavior Matrix

```text
Current local state       Home press 1 behavior
------------------------------------------------------------
Kodi menu/plain Kodi      Open Favourites, focus Kodi
Plex playback             Stop playback, open Favourites, focus Kodi
Plex UI                   Open Favourites, focus Kodi
YouTube/Chromium app      Close app-specific Chromium profile, return Kodi
Spotify mode              Stop Spotify mode/audio, return Kodi
Steam Link                Close local Steam Link client/stream, return Kodi
Moonlight                 Soft-disconnect local Moonlight client, return Kodi
Desktop/unknown           Show Kodi
```

Repeated Home behavior:

```text
Home press 1:
  Normal context-aware Home.

Home press 2 or 3:
  Optional stronger recovery.
  Recommended: hard Kodi restart if Kodi is the current/expected foreground and normal Home did not visually recover.

Home press 5:
  Panic local cleanup + hard Kodi restart.
```

Home must not run the destructive Moonlight/Sunshine quit path.

---

## 7. Revised Exit Behavior Matrix

Exit should work on one press and always try to close the current thing.

The only normal two-press behavior is plain Kodi shutdown, as a hedge against accidentally leaving the home shell.

```text
Current local state       Exit behavior
------------------------------------------------------------

Kodi menu / plain Kodi:
  press 1:
    no-op or open Favourites
  press 2 within 5-8 sec:
    close Kodi to desktop
  press 5:
    panic cleanup + hard Kodi restart
    or optional future variant: panic cleanup and leave desktop

Plex playback:
  press 1:
    stop playback
    try to exit Plex UI / return Kodi Favourites
  press 2:
    no-op
  press 5:
    panic cleanup + hard Kodi restart

Plex UI:
  press 1:
    try Back or add-on exit behavior
  press 2:
    force Kodi Favourites
  press 5:
    panic cleanup + hard Kodi restart

YouTube / Chromium app:
  press 1:
    close app-specific Chromium profile
    return Kodi
  press 5:
    panic cleanup + hard Kodi restart

Spotify:
  press 1:
    stop Spotify mode/audio
    return Kodi
  press 5:
    panic cleanup + hard Kodi restart

Steam Link:
  press 1:
    close local Steam Link client/stream
    return Kodi
  press 5:
    panic cleanup + hard Kodi restart

Moonlight:
  press 1:
    destructive Moonlight quit if this is intentionally the Exit button
    stop the active Sunshine session/app through the configured hard quit path
    return Kodi
  press 5:
    panic cleanup + hard Kodi restart
```

Important:

```text
Exit press 1 should be meaningful in every non-plain-Kodi context.
Exit press 2 exists mainly for plain Kodi shutdown and Plex UI fallback.
Exit press 5 is panic mode.
```

---

## 8. Plex-Specific Policy

Plex is hard because it is a Kodi add-on, not a separate TVBox process.

Do not spend V1 time trying to make Plex a perfectly separate app context.

Practical Plex policy:

```text
Home from Plex playback:
  Stop playback.
  Open Kodi Favourites.

Home from Plex UI:
  Open Kodi Favourites.

Exit from Plex playback:
  Stop playback.
  Try to return to Plex UI or Kodi Favourites.
  Prefer Kodi Favourites if reliable.

Exit from Plex UI:
  Try Back or add-on exit behavior.
  On second Exit, force Kodi Favourites.
```

If exact Plex window/add-on detection is unreliable, use Kodi JSON-RPC later to inspect:

```text
active player state
active window
current add-on path
script.plexmod state
```

Do not block the recovery work on perfect Plex detection.

---

## 9. Panic Recovery Scope

Panic mode must be aggressive locally but safe remotely.

Panic should do:

```text
1. Log that panic recovery was requested.
2. Capture a small diagnostic snapshot.
3. Stop app-specific local Chromium profiles.
4. Stop Spotify UI/audio mode.
5. Close local Steam Link client.
6. Soft-disconnect local Moonlight client.
7. Hard-stop Kodi.
8. Relaunch Kodi through /usr/local/bin/tvbox-kodi.
9. Set active-context=kodi.
10. Clear stale local state files.
```

Panic should not do:

```text
Do not broad-kill all Chromium.
Do not broad-kill shell.
Do not kill Sunshine on Obtuse unless the action was explicit Moonlight Exit.
Do not delete browser profiles, Kodi data, Spotify cache, or credentials.
Do not restart the whole desktop session unless a later, more severe recovery level is explicitly implemented.
```

The default panic mode should be:

```text
panic-local
```

Meaning:

```text
Clean up local TVBox foreground apps and hard-restart Kodi.
```

A future heavier mode may be:

```text
panic-desktop
```

Meaning:

```text
Restart lightdm / labwc graphical session.
```

But `panic-desktop` should not be the first implementation.

---

## 10. Recovery Backend Commands

Add these conceptual commands to `tvboxctl`:

```bash
tvboxctl recover soft
tvboxctl recover kodi-hard
tvboxctl recover panic-local
tvboxctl recover panic-desktop
```

### 10.1 recover soft

Purpose:

```text
Normal Home recovery.
```

Behavior:

```text
Stop playback if appropriate.
Open Kodi Favourites if Kodi is running.
Focus Kodi if possible.
Launch Kodi if no known foreground app exists.
```

### 10.2 recover kodi-hard

Purpose:

```text
Fix Kodi alive-but-wedged.
```

Behavior:

```bash
pkill -TERM -x kodi.bin 2>/dev/null || true
pkill -TERM -x kodi 2>/dev/null || true
sleep 4
pkill -9 -x kodi.bin 2>/dev/null || true
pkill -9 -x kodi 2>/dev/null || true
sleep 2
/usr/local/bin/tvbox-kodi &
```

### 10.3 recover panic-local

Purpose:

```text
Remote-controlled emergency cleanup without SSH.
```

Behavior:

```text
Stop Spotify mode.
Close YouTube/app-specific Chromium profiles.
Close local Steam Link.
Soft-disconnect local Moonlight.
Hard-restart Kodi.
Set active-context=kodi.
Clear stale local state.
```

### 10.4 recover panic-desktop

Purpose:

```text
Last-resort recovery for poisoned Wayland/labwc session.
```

Behavior:

```bash
sudo systemctl restart lightdm
```

Do not implement this until local panic recovery is proven and sudoers/security implications are reviewed.

---

## 11. Implementation Notes

### 11.1 Wrappers

Global keybind wrappers should stay thin.

Expected shape:

```bash
#!/bin/bash
exec /usr/local/bin/tvboxctl home "$@"
```

and:

```bash
#!/bin/bash
exec /usr/local/bin/tvboxctl exit "$@"
```

The policy should live in:

```bash
/opt/tvbox-system/bin/tvboxctl
```

Live path:

```bash
/usr/local/bin/tvboxctl -> /opt/tvbox-system/bin/tvboxctl
```

### 11.2 Locking

`tvboxctl` must still use a transition lock.

Lock path:

```bash
/run/user/1000/tvbox/lock
```

Repeated button presses create a conflict:

```text
The first press may still hold the lock while the next press arrives.
```

Required behavior:

```text
The button press counter must be updated before deciding to ignore a transition due to lock.
A locked second press should still count toward panic.
Long-running app launches must not inherit the lock file descriptor.
```

This is important because users usually hammer the button when the box is wedged.

### 11.3 Logging

Add a recovery log:

```bash
/home/tvbox/.cache/tvbox-recovery.log
```

Every Home/Exit/panic decision should log:

```text
timestamp
button
count
previous context
detected processes
chosen action
result
```

Example:

```text
2026-06-28T10:15:22-05:00 button=home count=5 context=kodi action=panic-local reason=repeated-press
```

### 11.4 Diagnostic Snapshot Before Panic

Before panic cleanup, write a small snapshot:

```bash
/home/tvbox/.cache/tvbox-panic-snapshot-YYYYMMDD-HHMMSS.log
```

Include:

```bash
date -Is
tvboxctl status
pgrep -a kodi || true
pgrep -a kodi.bin || true
pgrep -af 'chromium.*chromium-tvbox' || true
pgrep -a moonlight-qt || true
pgrep -a moonlight || true
pgrep -a steamlink || true
wlrctl toplevel list || true
for f in /sys/class/drm/card*-HDMI-A-*/status /sys/class/drm/card*-HDMI-A-*/modes /sys/class/drm/card*-HDMI-A-*/enabled; do
  [ -e "$f" ] && echo "--- $f ---" && cat "$f"
done
tail -n 80 /home/tvbox/.kodi/temp/kodi.log 2>/dev/null || true
journalctl -b --no-pager | grep -Ei 'vc4|hdmi|cec|drm|wayland|labwc|packet ram|hotplug|disconnect|connect' | tail -n 120 || true
```

This keeps root-cause evidence without requiring SSH during the failure.

---

## 12. Root-Cause Work

Panic is insurance, not the real fix.

The likely root problem from the recent failure is:

```text
TV/HDMI idle or hotplug event
-> Kodi sees display as Unknown/0 Hz or loses healthy Wayland surface
-> Kodi process remains alive
-> input and visible UI appear frozen
```

Root-cause work should proceed in this order.

### 12.1 HDMI State Collection

Run during a bad state before recovery when possible:

```bash
for f in /sys/class/drm/card*-HDMI-A-*/status /sys/class/drm/card*-HDMI-A-*/modes /sys/class/drm/card*-HDMI-A-*/enabled; do
  [ -e "$f" ] && echo "--- $f ---" && cat "$f"
done

command -v wlr-randr && wlr-randr || true

grep -nE "UpdateResolutions|Unknown Unknown|Hisense|Wayland|poll\\(\\)|CreateNewWindow|Surface size|Buffer size" \
  /home/tvbox/.kodi/temp/kodi.log | tail -n 80

journalctl -b --no-pager | grep -Ei 'vc4|hdmi|cec|drm|wayland|labwc|packet ram|hotplug|disconnect|connect' | tail -n 180
```

### 12.2 Confirm the DRM Connector

Before forcing a display mode, identify the connector:

```bash
ls -1 /sys/class/drm | grep HDMI
```

Then inspect:

```bash
for f in /sys/class/drm/card*-HDMI-A-*/status /sys/class/drm/card*-HDMI-A-*/modes /sys/class/drm/card*-HDMI-A-*/enabled; do
  [ -e "$f" ] && echo "--- $f ---" && cat "$f"
done
```

Only after confirming the connector should a kernel command-line override be considered, such as:

```text
video=HDMI-A-1:1920x1080@60D
```

or:

```text
video=HDMI-A-2:1920x1080@60D
```

Do not guess the connector.

### 12.3 TV-Side Settings

Check the Hisense TV settings for:

```text
HDMI-CEC
Auto power sync
Auto sleep
Energy saving
Screen saver
Fast start / quick start
HDMI signal format
```

The goal is to prevent the TV from dropping or renegotiating HDMI in a way that leaves Kodi wedged.

### 12.4 USB / Controller Isolation

The diagnostic showed controller disconnect/reconnect churn, especially around the 8BitDo controller.

Run one idle test with only:

```text
FLIRC
basic keyboard/mouse if needed
```

Temporarily remove:

```text
8BitDo receiver
GameSir controller
other nonessential USB input devices
```

If the wedge still happens, prioritize HDMI/Wayland/Kodi. If it stops, investigate USB power management, hub behavior, and receiver placement.

---

## 13. Button Binding Plan

Final intended keybinds:

```text
F12 -> /usr/local/bin/tvbox-home -> tvboxctl home
F5  -> /usr/local/bin/tvbox-exit -> tvboxctl exit
```

Planned later:

```text
F4 -> /usr/local/bin/tvbox-menu
F6 -> /usr/local/bin/tvbox-plex
F7 -> /usr/local/bin/tvbox-youtube
```

Do not bind new keys until the command works from terminal.

---

## 14. Testing Matrix

### 14.1 Home Tests

```text
Kodi menu -> Favourites, Kodi focused
Plex playback -> playback stops, Favourites, Kodi focused
Plex UI -> Favourites, Kodi focused
YouTube -> app-specific Chromium closes, Kodi returns
Spotify mode -> Spotify stops, Kodi returns
Steam Link -> local Steam Link closes, Kodi returns
Moonlight -> local Moonlight disconnects, Kodi returns, Sunshine remains
Desktop/unknown -> Kodi returns
Home x5 -> panic-local cleanup + hard Kodi restart
```

### 14.2 Exit Tests

```text
Kodi menu -> first press no-op/Favourites, second press closes Kodi to desktop
Plex playback -> first press stops playback and returns Favourites, second press no-op
Plex UI -> first press tries Back/add-on exit, second press forces Favourites
YouTube -> first press closes app-specific Chromium and returns Kodi
Spotify -> first press stops Spotify mode and returns Kodi
Steam Link -> first press closes local Steam Link and returns Kodi
Moonlight -> first press runs destructive Moonlight quit and returns Kodi
Exit x5 -> panic-local cleanup + hard Kodi restart
```

### 14.3 Wedged Kodi Test

Simulated or observed bad state:

```text
Kodi process exists.
Kodi may still make sound.
Normal /usr/local/bin/tvbox-kodi does not visually recover.
```

Expected:

```text
Home repeated to panic threshold hard-restarts Kodi.
Exit repeated to panic threshold hard-restarts Kodi.
Plex becomes usable again after Kodi relaunch.
```

### 14.4 Safety Tests

```text
Home from Moonlight must not stop Sunshine app.
Exit from Moonlight must stop Sunshine app through hard quit path.
Panic from Moonlight should soft-disconnect local Moonlight unless explicitly entered through Moonlight Exit logic.
Panic must not broad-kill arbitrary Chromium.
Panic must not delete profiles, caches, add-ons, or credentials.
```

---

## 15. Done Criteria

This amendment is complete when:

```text
tvboxctl home supports repeated-press escalation.
tvboxctl exit supports revised context matrix.
Plain Kodi closes only on second Exit press.
Both Home x5 and Exit x5 invoke panic-local.
panic-local hard-restarts wedged Kodi without SSH.
panic-local captures a diagnostic snapshot before cleanup.
Moonlight Home remains soft/local-only.
Moonlight Exit remains destructive.
Plex playback Exit stops playback and returns Favourites.
Plex UI second Exit forces Kodi Favourites.
All behavior is logged.
All scripts are backed by /opt/tvbox-system and committed.
```

---

## 16. Design Decision

The TVBox remote must have three recovery levels available without SSH:

```text
1. Normal Home / Exit.
2. Repeated-press escalation.
3. Panic-local recovery.
```

This is not a substitute for fixing the root cause. Root-cause work should focus first on HDMI/Wayland/Kodi display wedging after idle, then on USB/controller disconnect churn.

The final user-facing model should be simple:

```text
Home:
  get me back to the TV menu.

Exit:
  close what I am currently in.

Mash Home or Exit five times:
  fix the box enough to get Kodi back.
```
