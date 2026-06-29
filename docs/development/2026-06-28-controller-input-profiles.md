# Starter Controller Input Profiles

## Goal

Document the first starter TVBox controller input profiles and the repo structure they should use before creating real AntiMicroX profile files.

The profiles are:

```text
controller_kbm_generic
kodi_native_minimal
passthrough
```

## Current Behavior

`bin/tvbox-inputctl` now has a first AntiMicroX backend in the repo. It can start a TVBox-owned AntiMicroX process for local keyboard/mouse profiles and stop that TVBox-owned process for Kodi-native and passthrough profiles.

Current known profile names in `bin/tvbox-inputctl` are:

```text
none
kodi_native
kodi_native_minimal
passthrough
controller_kbm_generic
youtube_remote
spotify_ui
desktop_mouse
```

`input-profiles/README.md` exists and documents current input profile policy. `input-profiles/controller_kbm_generic.gamecontroller.amgp` exists as the first real manually-created AntiMicroX profile.

Existing plan docs already point toward:

```text
input-profiles/antimicrox/
input-profiles/standards/
input-profiles/devices/
input-profiles/normalization/
```

The current implementation keeps the first working profile at `input-profiles/controller_kbm_generic.gamecontroller.amgp`. A later controller-specific structure can be added when there is a second tested controller profile.

## Problem Being Solved

TVBox needs a small set of starter profile definitions before implementing the remapper backend. The goal is to avoid building arbitrary profile files without first documenting:

```text
what each profile is for
which contexts should use it
which buttons are intentionally mapped
which buttons are intentionally left alone
what must be tested on the actual TVBox
```

## Files Expected To Change

Implementation pass:

```text
bin/tvbox-inputctl
bin/tvbox-kodi
bin/tvbox-youtube
bin/tvboxctl
bin/tvbox-moonlight
input-profiles/README.md
input-profiles/controller_kbm_generic.gamecontroller.amgp
config/kodi/userdata/keymaps/tvbox-controller-guide.xml
docs/development/2026-06-28-controller-input-profiles.md
```

Possible later implementation files, not created in this pass:

```text
input-profiles/antimicrox/controller_kbm_generic.gamecontroller.amgp
input-profiles/antimicrox/kodi_native_minimal.gamecontroller.amgp
input-profiles/antimicrox/passthrough.gamecontroller.amgp
input-profiles/standards/tvbox_xinput_core_v1.md
input-profiles/devices/*.md
```

## Proposed Implementation

`controller_kbm_generic.gamecontroller.amgp` was created manually on TVBox and placed in `input-profiles/`.

Use `tvbox-inputctl` as the single command for applying profile state and the first AntiMicroX backend:

```text
controller_kbm_generic:
  stop old TVBox-owned AntiMicroX instance
  set the TVBox GUI environment if needed
  start AntiMicroX hidden with input-profiles/controller_kbm_generic.gamecontroller.amgp
  close tvbox-inputctl lock fd before execing AntiMicroX
  record input-profile=controller_kbm_generic

youtube_remote, spotify_ui, desktop_mouse:
  initially alias to controller_kbm_generic

kodi_native, kodi_native_minimal:
  stop old TVBox-owned AntiMicroX instance
  record Kodi-native input profile state

passthrough:
  stop old TVBox-owned AntiMicroX instance
  record passthrough input profile state
```

Context wiring in repo:

```text
bin/tvbox-youtube -> controller_kbm_generic
bin/tvbox-kodi -> kodi_native_minimal
bin/tvboxctl show_kodi/home paths -> kodi_native_minimal
bin/tvboxctl launch steamlink -> passthrough
bin/tvbox-moonlight -> passthrough
```

Kodi-native Guide handling:

```text
Do not run AntiMicroX for Kodi-native controller handling.
Use a Kodi joystick keymap to map the controller Guide/Xbox logical button to the same Kodi action currently used by the F12 keyboard keymap: ActivateWindow(FavouritesBrowser).
Install repo-owned Kodi keymaps from config/kodi/userdata/keymaps/ into /home/tvbox/.kodi/userdata/keymaps/.
```

Only stop AntiMicroX processes started by `tvbox-inputctl` and recorded in its PID file. Do not broad-kill unrelated manually-started AntiMicroX instances.

Use this repo structure for the first backend-specific profiles:

```text
input-profiles/
  controller_kbm_generic.gamecontroller.amgp
```

The existing profile is at the root of `input-profiles/` because that is where it was manually created and tested. A future controller-specific layout can move or copy profiles into subdirectories when there is more than one controller-specific profile to manage.

If the controller standard docs are created in the same implementation pass, use:

```text
input-profiles/
  standards/
    tvbox_xinput_core_v1.md
```

`tvbox-inputctl` should eventually know these profile names and apply them through the backend. For now, this is design documentation only.

## Profile 1: controller_kbm_generic

Purpose:

Generic keyboard/mouse controller profile for non-TV-native apps.

Use cases:

```text
Desktop rescue
Generic Chromium apps
Web apps
YouTube-like browser contexts as a starting point
Local web games unless they need custom controls
```

Mapping:

```text
D-pad              -> Arrow keys
Left stick         -> Arrow keys
Right stick        -> Mouse movement
A                  -> Enter
B                  -> Backspace
X                  -> Space / play-pause
Y                  -> Escape
Right trigger      -> Left mouse click
Left trigger       -> Right mouse click
Right bumper       -> PageDown or scroll down
Left bumper        -> PageUp or scroll up
View / Back        -> Alt+Left by default, unless testing shows Backspace is better
Menu / Start       -> Context menu / Shift+F10
Xbox / Guide       -> F12 / TVBox Home
Left stick click   -> unmapped for now
Right stick click  -> unmapped for now
```

Design notes:

```text
X is Space because A needs to stay Enter and Space is the most useful browser/media play-pause key.
Menu / Start should not be Home. It should be context/options/menu.
B and View/Back should not be duplicated unless testing proves duplication is better.
A future youtube_remote profile may clone this profile but tune browser-back behavior.
```

## Profile 2: kodi_native_minimal

Purpose:

Kodi-specific controller behavior.

Policy:

Kodi already has its own input/keymap layer. Avoid remapping the entire controller on top of Kodi unless testing proves it is necessary.

Preferred behavior:

```text
D-pad              -> native Kodi/default
Left stick         -> native Kodi/default
A                  -> native Kodi/default select
B                  -> native Kodi/default back
Xbox / Guide       -> F12 / TVBox Home if technically possible
Menu / Start       -> Kodi context menu if technically possible
View / Back        -> Kodi back/exit behavior if technically possible
Everything else    -> native/default unless a problem is proven
```

Concern:

If AntiMicroX or another mapper sends keyboard events while Kodi also receives original controller input, Kodi may receive duplicate or conflicting input. Investigate before implementing. This profile may end up being a Kodi keymap change, a minimal AntiMicroX profile, or no remapper at all.

Implementation decision:

```text
kodi_native_minimal is implemented as "stop TVBox-owned AntiMicroX and let Kodi receive native controller input".
The Guide/Xbox button is handled by Kodi's native joystick keymap, not by AntiMicroX.
config/kodi/userdata/keymaps/tvbox-controller-guide.xml maps <guide> to ActivateWindow(FavouritesBrowser) in global Kodi UI and FullscreenVideo.
```

## Profile 3: passthrough

Purpose:

Streaming-client profile where the remote host/client should receive controller input.

Use cases:

```text
Moonlight
Moonlight Steam
Moonlight Minecraft
Steam Link
```

Policy:

```text
Do not remap controller buttons.
Do not steal Xbox / Guide for F12 in streaming contexts unless explicitly approved later.
TVBox recovery remains available through the IR remote / FLIRC F12 path.
```

Implementation note:

`passthrough` may not need an AntiMicroX profile file at all. It may mean "stop any active remapper and record input-profile=passthrough".

## Repo Inspection Results

Commands run:

```bash
git status --short
find . -maxdepth 4 \( -path './.git' -o -path './.mypy_cache' \) -prune -o \( -iname '*input*' -o -iname '*controller*' -o -iname '*antimicro*' -o -name 'tvbox-inputctl' \) -print
rg -n "tvbox-inputctl|input-profile|input profile|controller|AntiMicroX|antimicro|Xbox|Guide|FLIRC|passthrough|youtube_remote|kodi_native" .
sed -n '1,220p' docs/Tvbox_controller_plan.md
sed -n '1,180p' input-profiles/README.md
sed -n '1,220p' bin/tvbox-inputctl
sed -n '1,180p' 'docs/TVBox Generic Controller Keyboard Mouse Emulation Plan.md'
find input-profiles -maxdepth 3 -type f -printf '%p\n' | sort
```

Findings:

```text
bin/tvbox-inputctl exists.
input-profiles/README.md exists.
No input-profiles/antimicrox/ directory exists yet.
input-profiles/controller_kbm_generic.gamecontroller.amgp exists and was manually tested.
docs/Tvbox_controller_plan.md already recommends input-profiles/antimicrox/ and standards/devices/normalization subdirectories.
docs/TVBox Generic Controller Keyboard Mouse Emulation Plan.md already names controller_kbm_generic as the preferred generic local profile.
The repo now has one working profile file, but not yet a broader controller-specific file convention.
```

Preferred profile directory:

```text
input-profiles/antimicrox/
```

Starter profile filenames:

```text
input-profiles/controller_kbm_generic.gamecontroller.amgp
```

Future controller-specific filenames may use:

```text
input-profiles/antimicrox/xbox360/controller_kbm_generic.gamecontroller.amgp
input-profiles/antimicrox/8bitdo/controller_kbm_generic.gamecontroller.amgp
input-profiles/antimicrox/gamesir/controller_kbm_generic.gamecontroller.amgp
```

## Open Technical Questions

Xbox 360 logical button names versus Linux event names:

```text
How does each target controller report A/B/X/Y, Guide, View, Menu, triggers, bumpers, stick clicks, and axes through evdev?
Does AntiMicroX see the Xbox / Guide button at all?
Does the Guide button arrive as a normal button, a special key, or a system-reserved event?
Do LT/RT report as buttons, axes, or shared trigger axis on the current controllers?
Do D-pad directions report as buttons or hat axes?
Does AntiMicroX distinguish View/Back and Menu/Start consistently across Xbox 360, Xbox One, GameSir, 8BitDo, PowerA, and Voye-style controllers?
Does Kodi receive native controller input at the same time AntiMicroX-generated keyboard input is active?
Can AntiMicroX suppress original joystick events, or does it only add keyboard/mouse events?
Is a "passthrough" profile an empty AntiMicroX profile, no AntiMicroX process, or a backend stop action?
Does Kodi reload joystick keymap changes on restart only, or can they be reloaded without restarting Kodi?
Should the Guide override also apply in FullscreenLiveTV, FullscreenRadio, or FullscreenGame after testing?
```

## Manual TVBox Test Requirements

Controller/device discovery:

```text
Record evdev/js event names for the reference controller.
Confirm AntiMicroX sees the intended controller.
Confirm AntiMicroX profile files generated on TVBox are stable enough to track.
Confirm whether Guide/Xbox is visible to AntiMicroX.
```

`controller_kbm_generic` tests:

```text
D-pad and left stick navigate a Chromium/web UI with sane repeat behavior.
Right stick moves the pointer with usable speed.
A activates selected UI.
B goes back or exits current browser panel.
View/Back sends Alt+Left and does not duplicate B badly.
X toggles play/pause in YouTube-like contexts.
Y escapes overlays/menus without causing harmful behavior.
Triggers click correctly.
Bumpers page or scroll correctly.
Menu/Start opens context/options behavior if supported.
Xbox/Guide sends F12 only in local TVBox contexts if technically possible.
IR remote / FLIRC F12 still works even if the profile is broken.
```

`kodi_native_minimal` tests:

```text
Kodi native D-pad/stick/select/back still work.
No duplicate navigation occurs.
Menu/Start reaches Kodi context menu if implemented.
View/Back reaches Kodi back/exit behavior if implemented.
Xbox/Guide can trigger TVBox Home/F12 without breaking Kodi native input, if technically possible.
Plex playback and Plex menus still respond correctly.
```

`passthrough` tests:

```text
Moonlight receives controller input normally.
Moonlight Steam receives controller input normally.
Moonlight Minecraft receives controller input normally.
Steam Link receives controller input normally.
Xbox/Guide remains available to the stream/client and is not stolen for TVBox Home.
IR remote / FLIRC F12 still recovers TVBox from streaming contexts.
Any active local remapper is stopped before entering passthrough.
```

## Validation Checklist

Documentation-only validation:

```text
Confirm this document captures the requested starter profile mappings.
Confirm no live appliance paths were edited.
Confirm no real AntiMicroX profiles were created.
Confirm existing repo support was inspected.
Show git status --short and git diff --stat.
```

Future implementation validation:

```text
bash -n bin/tvbox-inputctl after adding new known profile names.
XML parse config/kodi/userdata/keymaps/tvbox-controller-guide.xml.
bash -n install.sh after adding the Kodi keymap deploy path.
AntiMicroX profile loads without parse errors.
tvbox-inputctl can start/stop/status the backend.
Home/F12 recovery still works regardless of active profile.
Passthrough contexts receive native controller input.
```

## Test Results

Manual result reported by user:

```text
controller_kbm_generic works well on desktop.
controller_kbm_generic works well in Chromium YouTube.
controller_kbm_generic causes duplicate input in Kodi, confirming Kodi should use native/passthrough behavior for now.
The manually-tested profile affected the real Xbox 360 controller.
The 8BitDo controller was not affected in current testing.
Repo-owned Kodi Guide keymap was installed and tested by the user.
Kodi native Guide/Xbox mapping opens Kodi Favourites exactly as desired without AntiMicroX duplicate D-pad/stick input.
```

Repo implementation test results are recorded after command validation.

Repo validation results:

```text
bash -n bin/tvbox-inputctl bin/tvbox-kodi bin/tvbox-youtube bin/tvboxctl bin/tvbox-moonlight: passed
XML parse of input-profiles/controller_kbm_generic.gamecontroller.amgp: passed
controller_kbm_generic dry-run command: /usr/bin/antimicrox --hidden --profile /opt/tvbox-system/input-profiles/controller_kbm_generic.gamecontroller.amgp
tvbox-inputctl sets TVBox GUI environment before starting AntiMicroX.
tvbox-inputctl closes lock fd 9 before execing AntiMicroX so later profile switches are not blocked.
youtube_remote dry-run uses controller_kbm_generic profile: passed
kodi_native_minimal dry-run records profile and stops TVBox-owned AntiMicroX if present: passed
passthrough dry-run records profile and stops TVBox-owned AntiMicroX if present: passed
controller-specific dry-run command with TVBOX_ANTIMICROX_CONTROLLER='Xbox 360 Pro EX Controller': passed
antimicrox --list aborts in the non-GUI command environment unless QT_QPA_PLATFORM=offscreen or minimal is set.
QT_QPA_PLATFORM=offscreen antimicrox --list runs in repo validation but finds zero joysticks in this non-desktop context.
```

Kodi keymap repo validation results:

```text
bash -n install.sh bin/tvbox-inputctl bin/tvbox-kodi bin/tvbox-youtube bin/tvboxctl bin/tvbox-moonlight: passed
XML parse config/kodi/userdata/keymaps/tvbox-controller-guide.xml: passed
XML parse input-profiles/controller_kbm_generic.gamecontroller.amgp: passed
XML parse input-profiles/kodi_native_minimal.gamecontroller.amgp: passed
find config/kodi -maxdepth 4 -type f -print shows config/kodi/userdata/keymaps/tvbox-controller-guide.xml.
```

Deploy/live validation:

```text
User ran the install/test path on TVBox and confirmed the Kodi Guide keymap works exactly as desired.
The assistant did not personally run install.sh in this final documentation pass.
```

Repo inspection completed and documented above.

## Known Risks

```text
Guide/Xbox may not be visible to AntiMicroX.
AntiMicroX may generate duplicate input if the app also receives native controller events.
Trigger and D-pad event shapes may differ by controller.
Kodi may be better solved with Kodi keymaps than AntiMicroX.
The Kodi Guide keymap maps to Kodi FavouritesBrowser, matching the current Kodi F12 keymap, but it does not emit an OS-level F12 event.
Passthrough should probably be implemented as "stop remapper" rather than an empty remapper profile.
```

## Rollback Notes

Rollback for the repo changes is:

```bash
git revert <commit>
```

Live rollback after deployment is:

```bash
rm -f /home/tvbox/.kodi/userdata/keymaps/tvbox-controller-guide.xml
sudo /opt/tvbox-system/install.sh
```

Then restart Kodi or reboot.

## Status

validated
