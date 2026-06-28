# TVBox Plan Amendment: Focus Recovery and Context Refocus

## Purpose

This amendment defines a focus-recovery patch for the TVBox control layer.

The problem being addressed is intermittent loss of keyboard/remote control inside Plex/Kodi after the TVBox has been idle for a long time. The box still receives remote input, but the intended app no longer receives those key events until a mouse is used to click back inside Plex/Kodi.

This indicates a window/input-focus problem, not a Flirc, remote, or raw input problem.

The fix should be baked into the next `tvboxctl` build instead of treated as a one-off Plex workaround.

---

## Problem Statement

Observed behavior:

```text
TVBox sits unused for a long period.
Remote input still reaches the system.
Plex/Kodi no longer responds to remote navigation.
A hidden/background/desktop-level window or popup may have stolen keyboard focus.
The display may still visually show Plex/Kodi.
Clicking inside Plex/Kodi with a mouse restores remote control immediately.
```

Likely cause:

```text
The focused Wayland/labwc window no longer matches the TVBox active context.
```

Important distinction:

```text
Input is still working.
The active application is not necessarily receiving the input.
```

This failure is especially dangerous because TVBox is intended to be remote-first. A normal user should not need a mouse to recover the appliance.

---

## Design Principle

`tvboxctl` should not only know which app is logically active. It should also be able to repair focus so that the logical active context matches the compositor's actual focused window.

The existing state model already treats `active-context` as the app/session that should currently own the foreground. This amendment makes that state actionable for focus repair.

For Kodi and Plex:

```text
active-context=kodi
active-context=plex
```

both mean:

```text
Focus the Kodi window.
```

Plex is not a separate local process from the TVBox control layer's perspective when it runs inside Kodi. Plex is Kodi state.

---

## Required New Primitive

Add a focus primitive to `tvboxctl`.

Recommended command:

```bash
tvboxctl refocus
```

Equivalent internal helper name:

```bash
focus_context
```

Purpose:

```text
Read active-context.
Determine the expected owning window/process.
Focus that window if it exists.
Log what was focused.
Return success/failure without disrupting app state.
```

This command should be safe to run repeatedly.

---

## Context-to-Focus Mapping

Initial mapping:

```text
active-context=kodi
active-context=plex
  -> focus Kodi window

active-context=youtube
active-context=chromium:youtube
  -> focus Chromium window using the YouTube TVBox profile

active-context=spotify
  -> focus Chromium window using the Spotify dummy UI profile

active-context=moonlight:*
  -> focus moonlight-qt or moonlight

active-context=steamlink
  -> focus Steam Link window or active Steam Link streaming window

active-context=chromium:<app_id>
  -> focus Chromium window using that app's dedicated profile

active-context=desktop
active-context=unknown
missing active-context
  -> do not guess blindly; caller should usually run show_kodi/home recovery
```

Kodi/Plex focus target:

```text
Kodi window / kodi.bin process
```

YouTube focus target should be matched narrowly by profile path:

```bash
/home/tvbox/.config/chromium-tvbox-youtube
```

Spotify dummy UI focus target should be matched narrowly by profile path:

```bash
/home/tvbox/.config/chromium-tvbox-spotify-ui
```

Do not broad-focus or broad-kill all Chromium windows.

---

## Required `show_kodi` Behavior

`show_kodi` must become a full recovery operation, not merely a Kodi launch operation.

Required behavior:

```text
1. Start Kodi through /usr/local/bin/tvbox-kodi if Kodi is not running.
2. If Kodi is already running, do not start a duplicate instance.
3. Focus the Kodi window using the compositor/window-control tool.
4. Stop playback if requested by the caller or if Home behavior requires it.
5. Open Kodi Favourites.
6. Set active-context=kodi.
7. Set input profile to kodi_native or equivalent.
8. Log the recovery action.
```

For Plex:

```text
Home from Plex playback should stop playback, focus Kodi, then open Favourites.
Home from Plex menu should focus Kodi, then open Favourites.
```

The focus step is mandatory.

---

## Required Home Behavior

`tvboxctl home` means:

```text
Make the TVBox usable again from the remote.
```

It must repair all of these:

```text
wrong app open
wrong context state
wrong input profile
wrong window focus
Kodi not running
Kodi running but unfocused
Plex playback intercepting navigation
external local app still open
```

Required Home flow:

```text
Acquire tvboxctl lock.
Detect active local app/processes.
If a known external app is active, close or disconnect it according to policy.
Run show_kodi.
Focus Kodi.
Open Favourites.
Set active-context=kodi.
Set input-profile=kodi_native or equivalent.
Release lock.
```

Home should not depend on the currently focused window. It should work even if a hidden popup, desktop window, terminal, browser, or file manager has focus.

---

## Required Context-Shift Behavior

Every user-facing context transition should either call `tvboxctl refocus` or perform equivalent focus logic.

Required cases:

```text
tvboxctl home
tvboxctl exit
tvboxctl menu
tvboxctl launch plex
tvboxctl launch chromium-app youtube
tvboxctl launch chromium-app <app_id>
tvboxctl launch moonlight <target>
tvboxctl launch steamlink
Spotify takeover
Moonlight return to Kodi
YouTube return to Kodi
Steam Link return to Kodi
Spotify return to Kodi
```

Rule:

```text
After a launch or return transition, focus the app that now owns active-context.
```

Examples:

```text
Launching YouTube:
  close conflicting apps
  launch Chromium YouTube profile
  focus YouTube Chromium window
  set active-context=youtube

Returning from YouTube:
  close YouTube Chromium profile
  show_kodi
  focus Kodi
  set active-context=kodi

Launching Plex:
  show/focus Kodi
  open Plex
  set active-context=plex
  focus Kodi

Returning from Moonlight:
  local Moonlight disconnect
  show_kodi
  focus Kodi
  set active-context=kodi
```

---

## Focus Watchdog Policy

A focus watchdog is allowed, but it must be conservative.

Do not implement this as an aggressive always-running focus hammer.

Bad design:

```text
Every few seconds, force-focus Kodi no matter what.
```

Problems with that approach:

```text
It can fight intentional setup/debugging work.
It can hide legitimate popups.
It can make the desktop difficult to use.
It can break future app launch flows.
It can cause confusing focus flicker.
```

Allowed design:

```text
A user-level service checks whether the focused window matches active-context.
If the focused window is wrong and no transition lock is active, it refocuses once and logs the correction.
```

Recommended interval:

```text
10-30 seconds
```

Recommended constraints:

```text
Only run during stable TVBox mode.
Do not run while tvboxctl lock is held.
Do not run during app launch/close transitions.
Do not override Moonlight, Steam Link, YouTube, Spotify, or Chromium app focus unless their active-context says they own focus.
Do not force Kodi focus if active-context is an external app.
Do not use broad Chromium matching.
```

The watchdog is backup protection. The primary fix is to make Home/context transitions refocus correctly.

---

## Logging Requirements

Focus failures are hard to diagnose after the fact. Add explicit logging.

Recommended log:

```bash
/home/tvbox/.cache/tvboxctl.log
```

or dedicated focus log:

```bash
/home/tvbox/.cache/tvbox-focus.log
```

Every focus operation should log:

```text
timestamp
requested command
active-context
detected focused window if available
target focus window
focus command used
success/failure
```

Example log shape:

```text
2026-06-15T12:00:00 focus_context requested; context=plex
2026-06-15T12:00:00 focused_window_before="PackageKit prompt"
2026-06-15T12:00:00 target="Kodi"
2026-06-15T12:00:00 focus result=success
```

The goal is to identify focus thieves instead of only masking them.

---

## Diagnostic Command

Add a diagnostic command for future failures.

Recommended command:

```bash
tvboxctl focus-debug
```

or:

```bash
tvboxctl debug-focus
```

It should print/log:

```bash
date
cat /run/user/1000/tvbox/active-context
cat /run/user/1000/tvbox/input-profile
pgrep -a kodi || true
pgrep -a kodi.bin || true
pgrep -af 'chromium|moonlight|steamlink|spotify|orca|packagekit|pcmanfm|lxqt|zenity|yad' || true
wlrctl window list
```

Purpose:

```text
Capture the state when the remote stops controlling the visible app.
```

This should be runnable from SSH and optionally bindable to a temporary debug key during testing.

---

## Focus Tooling

Preferred tool:

```bash
wlrctl
```

because TVBox uses labwc/Wayland.

Required capabilities:

```text
list windows
identify titles/app IDs if available
focus a matching window
```

If `wlrctl` cannot reliably focus Kodi in labwc, evaluate alternative Wayland/labwc-compatible tools before adding brittle hacks.

Do not use X11-only assumptions unless the session is confirmed to expose the needed compatibility layer.

---

## Popup / Focus Thief Reduction

The focus patch should be paired with reducing common focus thieves.

Likely categories:

```text
PackageKit prompts
accessibility prompts
keyring prompts
browser restore-session bubbles
desktop notifications
file manager dialogs
power/display prompts
crash reporter dialogs
```

Specific known risk:

```text
TVBox previously had an accidental Orca/PackageKit event caused by input activity.
```

Policy:

```text
A dedicated TV appliance should suppress or neutralize desktop popups that can steal keyboard focus during normal use.
```

This is secondary to `tvboxctl` focus repair but should be handled during hardening.

---

## Interaction With Global Keybinds

Global Home/Exit/Menu/App/YouTube buttons must remain outside per-app input profiles.

They should be handled by labwc global keybinds or equivalent global mechanism.

Minimum critical binding:

```text
F12 -> /usr/local/bin/tvbox-home
```

Planned bindings:

```text
F12 -> /usr/local/bin/tvbox-home
F5  -> /usr/local/bin/tvbox-exit
F4  -> /usr/local/bin/tvbox-menu
F6  -> /usr/local/bin/tvbox-plex
F7  -> /usr/local/bin/tvbox-youtube
```

These global actions must work even when the wrong app or popup has focus.

Kodi-local keymaps may remain as fallback, but they are not enough because they only work when Kodi has focus.

---

## Implementation Order

### Phase 1 — Manual Refocus Primitive

Implement:

```bash
tvboxctl refocus
```

Test from:

```text
Kodi menu
Plex menu
Plex playback
desktop
terminal
Chromium YouTube
Spotify dummy UI
Moonlight
Steam Link
```

Expected:

```text
The active-context owning window receives focus.
No duplicate apps are launched.
No unrelated Chromium windows are affected.
```

---

### Phase 2 — Harden `show_kodi`

Update `show_kodi` so it:

```text
starts Kodi if needed
avoids duplicates
focuses Kodi
opens Favourites
sets active-context=kodi
sets input-profile=kodi_native or equivalent
logs all actions
```

Test:

```text
Home from desktop
Home from terminal
Home from unfocused Kodi
Home from Plex playback
Home after random desktop popup
```

---

### Phase 3 — Integrate Refocus Into Global Actions

Update:

```text
tvboxctl home
tvboxctl exit
tvboxctl menu
tvboxctl launch plex
tvboxctl launch chromium-app youtube
tvboxctl launch moonlight <target>
tvboxctl launch steamlink
```

Rule:

```text
Each command must leave focus on the app that owns active-context.
```

---

### Phase 4 — Add Focus Debugging

Implement:

```bash
tvboxctl focus-debug
```

Use it during any future failure before clicking with a mouse.

Goal:

```text
Identify the actual focus thief.
```

---

### Phase 5 — Optional Conservative Watchdog

Only after manual refocus and Home recovery are reliable, add an optional user-level focus watchdog.

Recommended service name:

```text
tvbox-focus-watchdog.service
```

Recommended script:

```bash
/usr/local/bin/tvbox-focus-watchdog
```

This should be easy to disable:

```bash
systemctl --user disable --now tvbox-focus-watchdog.service
```

Do not make the watchdog the only recovery mechanism.

---

## Test Matrix

### Kodi/Plex Focus Tests

```text
Kodi visible, desktop window focused -> Home focuses Kodi and opens Favourites
Plex menu visible, focus stolen -> Home focuses Kodi and opens Favourites
Plex playback visible, focus stolen -> Home stops playback, focuses Kodi, opens Favourites
Kodi already focused -> Home still works normally
Kodi not running -> Home launches Kodi, focuses it, opens Favourites
```

### External App Tests

```text
YouTube active -> Home closes YouTube, launches/focuses Kodi
Spotify dummy UI active -> Home stops Spotify mode, launches/focuses Kodi
Moonlight active -> Home soft-disconnects local Moonlight, launches/focuses Kodi
Steam Link active -> Home closes local Steam Link, launches/focuses Kodi
Chromium game active -> Home closes game, launches/focuses Kodi
```

### Recovery Tests

```text
Terminal focused over Kodi -> F12/Home recovers Kodi
File manager focused over Kodi -> F12/Home recovers Kodi
Browser focused over Kodi -> F12/Home recovers Kodi
Desktop popup steals focus -> F12/Home recovers Kodi if popup is not security-critical
```

### Non-Regression Tests

```text
No duplicate Kodi instances
No broad-killed Chromium profiles
No Home/Exit lock deadlocks
No broken Moonlight soft disconnect
No destructive Sunshine quit from Home
No input profile blocks Home/Exit
No focus watchdog fighting intentional external app focus
```

---

## Done Criteria

This amendment is complete when:

```text
tvboxctl has a refocus/focus_context primitive.
show_kodi always focuses Kodi as part of recovery.
Home works even when Kodi/Plex is visible but not focused.
Plex playback recovery does not require a mouse.
Context transitions leave focus on the new active context.
Focus actions are logged.
A focus-debug command can capture the focused-window state.
A conservative watchdog is available or explicitly deferred.
```

Minimum acceptable V1 patch:

```text
Home, Plex launch, and show_kodi all focus Kodi through wlrctl.
```

Full preferred patch:

```text
All tvboxctl context transitions repair focus based on active-context.
Optional watchdog provides backup correction and logging.
```

---

## Maintenance Rules

```text
Do not solve focus drift with broad process kills.
Do not broad-kill Chromium.
Do not force Kodi focus while another app is the active context.
Do not make the watchdog aggressive.
Do not depend on Kodi-local keymaps as the only recovery path.
Do not let input profiles capture Home/Exit.
Do not allow long-running app launches to inherit the tvboxctl lock.
Do not hide the focus problem without logging what was corrected.
```

Design decision:

```text
TVBox active-context must describe not only what app is logically active, but what app should own keyboard focus.
```
