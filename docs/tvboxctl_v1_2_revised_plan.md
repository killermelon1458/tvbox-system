# TVBoxCtl V1.1 Revised Implementation Plan

## 1. Purpose

`tvboxctl` is the central control layer for a Raspberry Pi based TV appliance. It turns several different local and streaming apps into one console-like experience controlled by a TV remote and game controllers.

The system is built around two separate responsibilities:

```text
1. App/session lifecycle control
   Handled by tvboxctl.

2. Controller/input translation
   Handled by tvbox-inputctl.
```

The goal is not to make every app behave the same internally. The goal is to make every app launch, close, focus, and receive controller input predictably from the user's point of view.

---

# 2. Core V1.1 Policy

## 2.1 One local app at a time

V1.1 allows only one TVBox-local foreground app/session at a time.

```text
Kodi is the home shell.
External local apps do not remain open behind Kodi.
Launching one external app closes other local external apps first.
Home closes the local external app and returns to Kodi.
Exit closes the local external app and returns to Kodi.
```

This is intentionally simpler than keeping one background app alive. The Pi should not accumulate YouTube, Steam Link, Chromium games, Spotify UI, and Kodi all at once.

## 2.2 Kodi is special

Kodi is the TVBox home shell. Kodi is allowed to stay running during Kodi/Plex usage. Kodi may be closed when launching external local apps if doing so makes focus, audio, or controller behavior more reliable. Plex inside Kodi is treated as Kodi state, not as a separate app process.

## 2.3 Streaming-client exception

Moonlight and Steam Link are local clients for remote systems. The local TVBox client should still be controlled aggressively, but remote host state is separate.

```text
Moonlight Home:
  Close/disconnect the local Moonlight client.
  Do not automatically kill Sunshine or the remote host app.
  Return Kodi.

Moonlight Exit:
  Use the destructive quit path.
  End the remote Sunshine session/app if configured.
  Return Kodi.

Steam Link Home:
  Stop/close the local Steam Link client or stream.
  Preserve remote host/game state if Steam Link supports that cleanly.
  Return Kodi.

Steam Link Exit:
  Stop/close the local Steam Link client or stream.
  If a reliable host-side close shortcut exists later, use it only for Exit or an explicit hard-close command.
```

The key distinction:

```text
No background local apps on the Pi.
Remote host state may remain alive when that is useful and intentional.
```

---

# 3. Main Components

## 3.1 tvboxctl

Main command:

```bash
/usr/local/bin/tvboxctl
```

Source of truth:

```bash
/opt/tvbox-system/bin/tvboxctl
```

Live path should be a symlink:

```bash
/usr/local/bin/tvboxctl -> /opt/tvbox-system/bin/tvboxctl
```

Responsibilities:

```text
Track current app context.
Launch apps.
Close conflicting local apps before launching a new app.
Route Home / Exit / Menu / App / YouTube / Steam Link actions.
Focus the correct window.
Update state files.
Call tvbox-inputctl to switch controller mappings.
Avoid race conditions with a lock.
```

## 3.2 tvbox-inputctl

Main command:

```bash
/usr/local/bin/tvbox-inputctl
```

Responsibilities:

```text
Start the correct controller/input remapping profile.
Stop old remapping profiles.
Reset input to passthrough/native mode.
Report current input profile.
Avoid remapping global TVBox control buttons.
```

Recommended first implementation: AntiMicroX profiles. Future implementation option: custom evdev/uinput remapper.

## 3.3 App wrappers

Each app may have a small wrapper script, but wrappers should not contain global TVBox policy.

Examples:

```bash
/usr/local/bin/tvbox-kodi
/usr/local/bin/tvbox-steamlink
/usr/local/bin/tvbox-youtube
/usr/local/bin/tvbox-chromium-app
/usr/local/bin/tvbox-stop-moonlight
/usr/local/bin/tvbox-quit-moonlight-session
/usr/local/bin/tvbox-stop-spotify
```

Wrapper rule:

```text
Wrappers can start/stop/focus one app.
Wrappers should not decide what Home, Exit, Menu, App, or C mean globally.
```

Global policy belongs in `tvboxctl`.

---

# 4. State Model

## 4.1 Runtime directory

Preferred runtime state directory:

```bash
/run/user/1000/tvbox
```

Fallback:

```bash
/tmp/tvbox
```

State files:

```bash
/run/user/1000/tvbox/active-context
/run/user/1000/tvbox/input-profile
/run/user/1000/tvbox/lock
/run/user/1000/tvbox/last-action.log
```

Optional dormant V2 files:

```bash
/run/user/1000/tvbox/preserved-app
/run/user/1000/tvbox/preserved-since
```

V1.1 should clear or ignore `preserved-app`.

## 4.2 active-context

`active-context` describes the app/session that should currently own the foreground.

Examples:

```text
kodi
plex
youtube
steamlink
moonlight:steam
moonlight:minecraft
moonlight:desktop
spotify
chromium:fireboy-watergirl
chromium:fixitfelix
desktop
unknown
```

## 4.3 input-profile

`input-profile` describes how controller input should be translated right now.

Examples:

```text
kodi_native
passthrough
controller_remote_clone
youtube_remote
fireboy_watergirl
fixitfelix
none
unknown
```

Important rule:

```text
context and input_profile are related but not identical.
```

Multiple app contexts may share one input profile.

Examples:

```text
context=youtube
input_profile=controller_remote_clone

context=chromium:generic-tv-site
input_profile=controller_remote_clone

context=chromium:fireboy-watergirl
input_profile=fireboy_watergirl

context=moonlight:steam
input_profile=passthrough

context=steamlink
input_profile=passthrough
```

---

# 5. Locking Policy

`tvboxctl` must use a lock for app/session transitions.

Lock file:

```bash
/run/user/1000/tvbox/lock
```

Purpose:

```text
Prevent Home + Exit from running at the same time.
Prevent repeated remote presses from overlapping transitions.
Prevent two app launchers from fighting over foreground state.
Prevent state file corruption during app changes.
```

Required behavior:

```text
Only one tvboxctl transition runs at a time.
If the lock is already held, the new command should log and exit.
Long-running apps must not inherit the lock file descriptor.
```

Use a helper for background launches:

```bash
start_bg() {
  "$@" 9>&- &
}
```

Do not launch Kodi, Chromium, Steam Link, Moonlight, or other long-running apps while they still hold the `tvboxctl` lock FD.

---

# 6. App Lifecycle Model

## 6.1 close_local_apps_except(target)

V1.1 should use a central cleanup function.

Concept:

```text
close_local_apps_except(target):
  close Steam Link unless target is steamlink
  close YouTube/Chromium apps unless target is that Chromium app
  stop Spotify mode unless target is spotify
  close local Moonlight client unless target is moonlight
  close Kodi when launching external local apps if needed
  clear preserved-app
```

Moonlight/Sunshine rule:

```text
Do not close Sunshine or the remote host app from this generic cleanup function.
Only use hard remote/session cleanup from Exit or an explicit hard-close command.
```

## 6.2 show_kodi

`show_kodi` should make the box usable again.

Expected behavior:

```text
Start Kodi if needed.
Focus Kodi using wlrctl.
Stop playback if appropriate.
Open Favourites.
Set context=kodi.
Set input_profile=kodi_native or none.
```

Do not compositor-force fullscreen with `wlrctl window fullscreen Kodi` because that can interfere with Kodi's own fullscreen toggle.

Kodi fresh launch should use the Kodi wrapper and may launch with `-fs` if stable:

```bash
/usr/bin/kodi -fs --audio-backend=alsa
```

## 6.3 close_kodi

When launching external local apps, Kodi may be closed to avoid focus/audio/control conflicts.

Expected behavior:

```text
Stop playback.
Terminate Kodi.
Force kill only if it fails to exit.
```

## 6.4 close_steamlink_current

Steam Link window detection must handle both launcher and streaming state.

Observed Steam Link windows:

```text
shell: SteamLink
shell: <game title> [Streaming]
```

Close logic must close both.

```text
If window title is SteamLink, close it.
If app_id is shell and title ends with [Streaming], close shell window.
Then terminate steamlink process if still alive.
```

Do not broad-kill unrelated `shell` processes unless window list confirms it is a Steam Link streaming window.

## 6.5 close_youtube_current

YouTube should use its own Chromium profile.

Expected profile:

```bash
/home/tvbox/.config/chromium-tvbox-youtube
```

Close only the YouTube Chromium profile. Do not use broad `pkill chromium`.

## 6.6 close_chromium_app(app_id)

Generic Chromium apps should use unique profiles.

Examples:

```bash
/home/tvbox/.config/chromium-tvbox-youtube
/home/tvbox/.config/chromium-tvbox-fireboy-watergirl
/home/tvbox/.config/chromium-tvbox-fixitfelix
```

Close logic should match the app-specific profile path.

---

# 7. Input Profile Model

## 7.1 Global buttons stay global

These controls must remain outside per-app input profiles:

```text
Home
Exit
Menu
App/Plex
YouTube/C
possibly future Steam Link button
```

They should be captured by labwc/global keybinds where possible. App-specific input profiles should not steal or block the emergency path back to Kodi.

## 7.2 Controller profiles

Initial profiles:

```text
kodi_native:
  No remapping or minimal remapping.
  Let Kodi handle controller natively where possible.

passthrough:
  No remapping.
  Used for Moonlight and Steam Link so controllers pass through to the remote host/client.

controller_remote_clone:
  D-pad/stick -> arrow keys
  A -> Enter
  B -> Backspace or browser Back
  Start/Menu -> context/menu if needed
  Guide/Home remains global if possible

youtube_remote:
  Can initially equal controller_remote_clone.
  Later can add YouTube-specific shortcuts.

fireboy_watergirl:
  Custom mapping for game controls.
  May need keyboard movement plus mouse/menu support.

fixitfelix:
  Custom mapping to the game's logical keyboard controls.
```

## 7.3 tvbox-inputctl commands

Minimum V1.1 commands:

```bash
tvbox-inputctl status
tvbox-inputctl set kodi_native
tvbox-inputctl set passthrough
tvbox-inputctl set controller_remote_clone
tvbox-inputctl set youtube_remote
tvbox-inputctl set fireboy_watergirl
tvbox-inputctl set fixitfelix
tvbox-inputctl reset
```

Behavior:

```text
Stop current remapper profile.
Start requested profile if needed.
Write input-profile state.
Log failures.
Never block Home/Exit from working.
```

## 7.4 AntiMicroX first implementation

Recommended first implementation:

```text
Use AntiMicroX for controller-to-keyboard/mouse profiles.
One profile file per input profile.
Use tvbox-inputctl to kill old AntiMicroX instance and start the new one.
```

Possible profile location:

```bash
/opt/tvbox-system/input-profiles/antimicrox/controller_remote_clone.gamecontroller.amgp
/opt/tvbox-system/input-profiles/antimicrox/fireboy_watergirl.gamecontroller.amgp
/opt/tvbox-system/input-profiles/antimicrox/fixitfelix.gamecontroller.amgp
```

Fail-safe rule:

```text
If AntiMicroX fails to start, still launch the app and log the error.
```

---

# 8. Chromium App Framework

Chromium apps should be generic, not one-off scripts forever.

## 8.1 Generic app definition

Each Chromium app should have a simple config definition.

Example fields:

```text
app_id=youtube
name=YouTube
url=https://www.youtube.com/tv
profile=/home/tvbox/.config/chromium-tvbox-youtube
input_profile=youtube_remote
icon=/opt/tvbox-system/assets/icons/youtube.png
mode=app

app_id=fireboy-watergirl
name=Fireboy and Watergirl
url=<game URL or local file>
profile=/home/tvbox/.config/chromium-tvbox-fireboy-watergirl
input_profile=fireboy_watergirl
icon=/opt/tvbox-system/assets/icons/fireboy-watergirl.png
mode=app

app_id=fixitfelix
name=Fix-It Felix
url=<game URL or local file>
profile=/home/tvbox/.config/chromium-tvbox-fixitfelix
input_profile=fixitfelix
icon=/opt/tvbox-system/assets/icons/fixitfelix.png
mode=app
```

## 8.2 Generic launch command

Desired command shape:

```bash
tvboxctl launch chromium-app youtube
tvboxctl launch chromium-app fireboy-watergirl
tvboxctl launch chromium-app fixitfelix
```

Expected launch behavior:

```text
Acquire tvboxctl lock.
Close local apps except target.
Set input profile.
Launch Chromium with app-specific profile and URL.
Focus Chromium window.
Set active-context=chromium:<app_id>.
```

## 8.3 Chromium launch requirements

Each Chromium app should use:

```text
Dedicated user data/profile directory.
App/kiosk/fullscreen style if appropriate.
Narrow process matching by profile path.
No shared profile between apps.
No broad Chromium kills.
```

Possible command pattern:

```bash
chromium \
  --user-data-dir=/home/tvbox/.config/chromium-tvbox-APPID \
  --app=URL \
  --start-fullscreen
```

Exact flags should be tested per app.

---

# 9. Remote Button Mapping

Current remote/Flirc plan:

```text
Home / Guide        F12 -> tvboxctl home
Menu                F4  -> tvboxctl menu
Exit                F5  -> tvboxctl exit
App                 F6  -> tvboxctl launch plex
Red C               F7  -> tvboxctl launch chromium-app youtube
Back                Backspace -> normal app back unless global handling is needed
D-pad               Arrow keys
OK                  Enter
```

Global labwc keybinds should call stable wrapper paths:

```bash
/usr/local/bin/tvbox-home
/usr/local/bin/tvbox-exit
/usr/local/bin/tvbox-menu
/usr/local/bin/tvbox-plex
/usr/local/bin/tvbox-youtube
```

Those wrappers should be tiny shims into `tvboxctl`.

Example:

```bash
#!/bin/bash
exec /usr/local/bin/tvboxctl home "$@"
```

---

# 10. Command Interface

## 10.1 tvboxctl required commands

```bash
tvboxctl status
tvboxctl get-context
tvboxctl set-context <context>
tvboxctl home
tvboxctl exit
tvboxctl menu
tvboxctl launch plex
tvboxctl launch steamlink
tvboxctl launch moonlight <target>
tvboxctl launch chromium-app <app_id>
tvboxctl close-local-apps-except <target>
```

## 10.2 tvbox-inputctl required commands

```bash
tvbox-inputctl status
tvbox-inputctl set <profile>
tvbox-inputctl reset
```

## 10.3 Compatibility wrapper scripts

```bash
/usr/local/bin/tvbox-home
/usr/local/bin/tvbox-exit
/usr/local/bin/tvbox-menu
/usr/local/bin/tvbox-plex
/usr/local/bin/tvbox-youtube
/usr/local/bin/tvbox-steamlink
```

---

# 11. Home Behavior

`tvboxctl home` means:

```text
Make this a TV again.
Close local external apps.
Return Kodi to Favourites.
Focus Kodi.
Set Kodi input profile.
```

Behavior matrix:

```text
Current local state       Home behavior
------------------------------------------------------------
Kodi/Plex                 Stop playback if needed, open Favourites, focus Kodi
YouTube/Chromium app      Close Chromium app, show Kodi
Spotify mode              Stop Spotify mode, show Kodi
Steam Link                Close local Steam Link client/stream, show Kodi
Moonlight                 Soft-disconnect local Moonlight client, show Kodi
Desktop/unknown           Show Kodi
```

Moonlight Home should not automatically kill Sunshine or the remote host app.

---

# 12. Exit Behavior

`tvboxctl exit` means:

```text
Hard close current local app/session where possible.
Return Kodi.
```

Behavior matrix:

```text
Current local state       Exit behavior
------------------------------------------------------------
Kodi/Plex playback        Stop playback, Kodi remains usable
Plain Kodi                Usually same as Home unless EXIT_CLOSES_KODI=1
YouTube/Chromium app      Close Chromium app, show Kodi
Spotify mode              Stop Spotify mode, show Kodi
Steam Link                Close local Steam Link client/stream, show Kodi
Moonlight                 Run hard Moonlight/Sunshine quit path, show Kodi
Desktop/unknown           Show Kodi
```

Config:

```bash
EXIT_CLOSES_KODI=0
```

V1.1 should keep `EXIT_CLOSES_KODI=0` by default.

---

# 13. Menu Behavior

`tvboxctl menu` means:

```text
Go to the current app's top-level menu/home if possible.
Do not close the app.
```

Initial matrix:

```text
Kodi                  Activate Kodi main Home, not Favourites
Plex                  Open Plex home if reliable command is known
YouTube               Navigate/relaunch YouTube TV home
Chromium app/game     App-specific; often no-op or browser/app menu
Steam Link            Test later; may no-op or send Steam overlay/menu if possible
Moonlight Steam       Future: host-side Steam Big Picture menu helper
Moonlight game        No-op unless a safe host helper is defined
```

Menu should not be implemented until Home/Exit/Launch behavior is stable.

---

# 14. Steam Link Policy

Steam Link is treated as a streaming client, similar in concept to Moonlight but with different local behavior.

Known local window states:

```text
shell: SteamLink
shell: <game title> [Streaming]
```

V1.1 local policy:

```text
Launch Steam Link through tvboxctl.
Set input_profile=passthrough.
Close Kodi/local apps before launch.
Home closes local Steam Link and returns Kodi.
Exit closes local Steam Link and returns Kodi.
Do not preserve Steam Link locally behind Kodi.
```

Future exploration:

```text
Determine whether Steam Link has a reliable stop-streaming action that leaves game/server state alive.
Determine whether Steam Link can trigger host-side app close through shortcut or overlay.
Determine whether controller mapping interferes with Steam Link passthrough.
```

Do not add host-side hard close until tested.

---

# 15. Moonlight Policy

Moonlight already has two different behaviors and should keep them.

```text
Home:
  Soft-disconnect local Moonlight.
  Leave Sunshine/remote app alone.
  Return Kodi.

Exit:
  Run hard quit script.
  End remote Sunshine session/app if configured.
  Return Kodi.
```

Input profile:

```text
passthrough
```

The Pi should not remap controllers for Moonlight unless a specific use case requires it.

---

# 16. Repository and Deployment Model

Source of truth:

```bash
/opt/tvbox-system
```

Runtime stable paths:

```bash
/usr/local/bin/tvboxctl
/usr/local/bin/tvbox-inputctl
/usr/local/bin/tvbox-kodi
/usr/local/bin/tvbox-home
/usr/local/bin/tvbox-exit
/usr/local/bin/tvbox-menu
/usr/local/bin/tvbox-plex
/usr/local/bin/tvbox-youtube
/usr/local/bin/tvbox-steamlink
```

Recommended repo layout:

```text
tvbox-system/
├── bin/
│   ├── tvboxctl
│   ├── tvbox-inputctl
│   ├── tvbox-kodi
│   ├── tvbox-home
│   ├── tvbox-exit
│   ├── tvbox-menu
│   ├── tvbox-plex
│   ├── tvbox-youtube
│   └── tvbox-steamlink
│
├── config/
│   ├── tvboxctl.conf.example
│   ├── labwc/
│   │   └── rc.xml.snippet
│   └── chromium-apps/
│       ├── youtube.conf
│       ├── fireboy-watergirl.conf
│       └── fixitfelix.conf
│
├── input-profiles/
│   └── antimicrox/
│       ├── controller_remote_clone.*
│       ├── fireboy_watergirl.*
│       └── fixitfelix.*
│
├── kodi-addons/
│   ├── plugin.program.tvbox.steamlink/
│   ├── plugin.program.tvbox.youtube/
│   ├── plugin.program.tvbox.fireboy-watergirl/
│   └── plugin.program.tvbox.fixitfelix/
│
├── assets/
│   └── icons/
│
├── docs/
└── install.sh
```

Live scripts should either be symlinks into the repo or copied from the repo by an idempotent install script.

Configs may be copied/patched rather than symlinked if they contain machine-specific state.

---

# 17. Implementation Order

## Phase 1 — Stabilize current controller base

```text
Confirm tvboxctl status works.
Confirm Home works from Kodi, desktop, YouTube, Moonlight, Steam Link.
Confirm locks are clear after transitions.
Confirm repo and live scripts match.
```

## Phase 2 — Finish one-local-app lifecycle

Implement or harden:

```text
close_local_apps_except(target)
close_steamlink_current
close_youtube_current
close_chromium_app(app_id)
show_kodi
close_kodi
```

Goal:

```text
Launching any local external app cleans up other local external apps first.
```

## Phase 3 — Implement Exit

Implement:

```bash
tvboxctl exit
/usr/local/bin/tvbox-exit
```

Then bind F5 only after manual tests pass.

## Phase 4 — Implement Steam Link cleanly

Implement:

```bash
tvboxctl launch steamlink
/usr/local/bin/tvbox-steamlink
Kodi Steam Link add-on
```

Policy:

```text
Steam Link local client does not remain behind Kodi.
Home closes Steam Link local client and returns Kodi.
```

## Phase 5 — Implement tvbox-inputctl

Start with AntiMicroX profiles.

Implement:

```bash
tvbox-inputctl status
tvbox-inputctl set passthrough
tvbox-inputctl set kodi_native
tvbox-inputctl set controller_remote_clone
tvbox-inputctl reset
```

Then add app-specific profiles.

## Phase 6 — Generalize Chromium apps

Implement:

```bash
tvboxctl launch chromium-app <app_id>
```

Start with YouTube.

Then add:

```text
Fireboy and Watergirl
Fix-It Felix
```

## Phase 7 — Add Kodi launch add-ons

For each external app, create a Kodi Program add-on with icon:

```text
Steam Link
YouTube
Fireboy and Watergirl
Fix-It Felix
Moonlight targets
```

Add them to Kodi Favourites.

## Phase 8 — Add Menu/App/C behavior

Implement:

```bash
tvboxctl menu
tvboxctl launch plex
tvboxctl launch chromium-app youtube
```

Bind:

```text
F4 -> menu
F6 -> Plex
F7 -> YouTube
```

## Phase 9 — Optional future preservation

Do not implement preservation in V1.1.

Keep code modular enough that V2 could add:

```text
preserved remote sessions
one preserved Chromium app
timeout-based cleanup
resource-based cleanup
```

But do not let this complicate V1.1.

---

# 18. Testing Matrix

## 18.1 Home tests

```text
Kodi menu -> Favourites, Kodi focused
Plex playback -> playback stops, Favourites, Kodi focused
YouTube -> YouTube closes, Kodi returns
Steam Link launcher -> Steam Link closes, Kodi returns
Steam Link streaming -> streaming window closes, Kodi returns
Moonlight -> local Moonlight disconnects, Kodi returns, Sunshine remains
Spotify mode -> Spotify stops, Kodi returns
Desktop/Firefox/terminal focused -> Kodi focuses and opens Favourites
```

## 18.2 Exit tests

```text
Kodi playback -> playback stops, Kodi remains usable
YouTube -> closes, Kodi returns
Steam Link -> closes, Kodi returns
Moonlight -> hard quit path runs, Kodi returns
Spotify -> stops, Kodi returns
Unknown desktop state -> Kodi returns
```

## 18.3 Launch tests

```text
Launch Steam Link from Kodi add-on
Launch Steam Link from terminal
Launch YouTube from Kodi add-on
Launch Chromium game from Kodi add-on
Launch Moonlight from Kodi add-on
Launch app while another local external app is running
```

Expected:

```text
Only target local app remains active.
Input profile switches correctly.
Home always recovers to Kodi.
```

## 18.4 Input profile tests

```text
Kodi native controller input works.
Moonlight controller passthrough works.
Steam Link controller passthrough works.
YouTube controller remote-clone works.
Fireboy/Watergirl custom profile works.
Fix-It Felix custom profile works.
Home/Exit still work regardless of input profile.
```

---

# 19. Safety Rules

```text
Do not broad-kill Chromium.
Do not broad-kill shell.
Do not kill Sunshine except from explicit hard Moonlight Exit behavior.
Do not let local external apps remain behind Kodi in V1.1.
Do not compositor-force fullscreen on Kodi from Home.
Do not let input remapping block Home/Exit.
Do not run two tvboxctl transitions at once.
Do not launch long-running apps while inheriting tvboxctl lock FDs.
Do not bind new remote keys until commands pass manual tests.
Do not commit secrets, browser profiles, cache, logs, or tokens.
```

---

# 20. V1.1 Done Criteria

V1.1 is complete when:

```text
tvboxctl status accurately reports context and known app state.
Home works from every supported app/context.
Exit works from every supported app/context.
Steam Link launches from Kodi and Home reliably closes it.
YouTube launches as a Chromium app and Home reliably closes it.
At least one controller remapping profile works for a Chromium app.
Moonlight Home remains soft/local-only.
Moonlight Exit remains hard/destructive.
Only one local external app is alive at a time.
Kodi is always recoverable with Home.
All live scripts are backed by /opt/tvbox-system and pushed to Git.
```

Not required for V1.1:

```text
Background preserved local apps.
Automatic resource monitoring.
Loading screens.
Perfect host-side Steam Link app closing.
Custom uinput remapper.
Multi-app resume cache.
```

# Plan Amendment: Config Ownership, GUI-Rewrite Risk, and Redeployability

## 21. Config Ownership and GUI-Rewrite Risk

## 21.1 Problem

Some desktop GUI settings tools can rewrite configuration files instead of merging new settings into the existing file.

This happened with the labwc config:

```bash
~/.config/labwc/rc.xml
```

After changing mini-keyboard/trackpad pointer sensitivity through the GUI, the file was rewritten into a small config containing only the pointer/libinput section. The custom global keyboard block was removed, including the critical F12/Home binding.

Failure mode:

```text
F12 still worked inside Kodi because Kodi had its own local F12 fallback.
F12 stopped working from Steam Link, desktop, Firefox, Chromium apps, and other non-Kodi contexts because the labwc global keybind was gone.
```

This is a serious reliability issue because global Home/F12 is the recovery path for the entire TVBox.

## 21.2 Policy

The active desktop/user config files under `~/.config` are not the source of truth.

The source of truth is the Git-backed repo:

```bash
/opt/tvbox-system
```

Any configuration needed for TVBox recovery, global controls, app launch, controller profiles, Kodi add-ons, or redeployment must be tracked in the repo.

Live config files should be treated as deployed/generated copies.

```text
Repo copy:
  Canonical version.
  Backed up to Git.
  Used for redeploy/repair.

Live copy:
  What the desktop/session/app reads right now.
  Can be overwritten by GUI tools.
  Must be repairable from the repo.
```

## 21.3 labwc Config Ownership

The labwc config is critical because it owns global remote recovery buttons.

Canonical repo path:

```bash
/opt/tvbox-system/config/labwc/rc.xml
```

Live path:

```bash
/home/tvbox/.config/labwc/rc.xml
```

The canonical labwc config must include at minimum:

```xml
<keybind key="F12">
  <action name="Execute" command="/usr/local/bin/tvbox-home" />
</keybind>
```

It may also include pointer/libinput settings, such as:

```xml
<libinput>
  <device category="default">
    <pointerSpeed>0.400000</pointerSpeed>
  </device>
</libinput>
```

Important rule:

```text
Do not rely on GUI-edited labwc config unless it has been checked back into the repo and verified to still contain global TVBox keybinds.
```

## 21.4 Required Global Keybinds

The labwc global keybinds are the emergency/control layer and should be tracked in Git.

Minimum required:

```text
F12 -> /usr/local/bin/tvbox-home
```

Planned V1.1 bindings:

```text
F12 -> /usr/local/bin/tvbox-home
F5  -> /usr/local/bin/tvbox-exit
F4  -> /usr/local/bin/tvbox-menu
F6  -> /usr/local/bin/tvbox-plex
F7  -> /usr/local/bin/tvbox-youtube
```

These are global TVBox controls. They must work from:

```text
Kodi
Plex playback
YouTube Chromium app
Steam Link
Moonlight
Spotify mode
Firefox/desktop
terminal windows
future Chromium games
```

Kodi-local keymaps are allowed as fallback, but they are not enough because they only work inside Kodi.

## 21.5 Repair Script Requirement

V1.1 should include a repair/deploy script for labwc config.

Recommended path:

```bash
/opt/tvbox-system/bin/tvbox-restore-labwc-config
```

Live shim path:

```bash
/usr/local/bin/tvbox-restore-labwc-config
```

Required behavior:

```text
Back up the current live rc.xml.
Copy the canonical repo rc.xml into ~/.config/labwc/rc.xml.
Validate XML syntax.
Verify F12/Home keybind exists.
Print whether reboot/session restart is required.
```

Suggested behavior:

```text
Also verify F4/F5/F6/F7 once those bindings exist.
Also verify /usr/local/bin/tvbox-home exists and is executable.
Also verify /usr/local/bin/tvboxctl syntax is valid.
```

Example repair flow:

```bash
tvbox-restore-labwc-config
sudo reboot
```

## 21.6 GUI Settings Rule

Desktop GUI settings tools may be used, but they are unsafe for persistent TVBox-critical configuration unless followed by verification.

After using GUI tools that change pointer, keyboard, window manager, display, theme, or desktop behavior, run:

```bash
grep -n -A4 -B2 -E 'key="F12"|key="F5"|key="F4"|key="F6"|key="F7"' ~/.config/labwc/rc.xml
```

Then run:

```bash
bash -n /usr/local/bin/tvboxctl
tvboxctl status
```

If global keybinds are missing, restore them from the repo:

```bash
/usr/local/bin/tvbox-restore-labwc-config
sudo reboot
```

If a GUI setting is worth keeping, merge it into the repo copy instead of leaving it only in the live config.

Correct workflow:

```text
1. Change setting.
2. Inspect what file changed.
3. Verify TVBox global controls still exist.
4. Merge useful setting into /opt/tvbox-system/config/...
5. Commit to Git.
6. Treat repo version as canonical.
```

Incorrect workflow:

```text
1. Change setting in GUI.
2. Assume the system is still recoverable.
3. Reboot.
4. Discover Home/F12 no longer works outside Kodi.
```

## 21.7 Input Profiles Must Not Depend on labwc rc.xml

Future controller/input profiles must not be stored in `~/.config/labwc/rc.xml`.

Input profiles belong in the repo, separate from the compositor config.

Canonical profile path examples:

```bash
/opt/tvbox-system/input-profiles/antimicrox/controller_remote_clone.*
/opt/tvbox-system/input-profiles/antimicrox/youtube_remote.*
/opt/tvbox-system/input-profiles/antimicrox/fireboy_watergirl.*
/opt/tvbox-system/input-profiles/antimicrox/fixitfelix.*
```

`tvbox-inputctl` should apply those profiles at runtime.

This prevents desktop settings GUIs from deleting controller mappings.

The only input-related data that belongs in labwc is global TVBox keybinds such as Home, Exit, Menu, App, and YouTube.

## 21.8 Repo Layout Addition

Add or maintain this repo structure:

```text
tvbox-system/
├── config/
│   └── labwc/
│       ├── rc.xml
│       └── README.md
│
├── bin/
│   └── tvbox-restore-labwc-config
│
└── input-profiles/
    └── antimicrox/
        ├── controller_remote_clone.*
        ├── youtube_remote.*
        ├── fireboy_watergirl.*
        └── fixitfelix.*
```

The labwc README should explain:

```text
The GUI may rewrite ~/.config/labwc/rc.xml.
The repo copy is canonical.
F12/Home must be global.
Kodi-local F12 fallback is not enough.
Use tvbox-restore-labwc-config to repair global controls.
```

## 21.9 Deployment Rule

A future fresh TVBox install should be recoverable from the repo with a small number of commands.

The install/deploy process should restore at least:

```text
/usr/local/bin/tvboxctl
/usr/local/bin/tvbox-home
/usr/local/bin/tvbox-kodi
/usr/local/bin/tvbox-steamlink
/usr/local/bin/tvbox-inputctl
~/.config/labwc/rc.xml
Kodi launcher add-ons
Input profiles
Config examples
Documentation
```

The repo does not need to contain browser profile data, cache, secrets, tokens, logs, or machine-specific credentials.

Do not commit:

```text
Chromium profile directories
Kodi cache and thumbnails
Spotify credentials/cache
API keys
VPN tokens
SSH keys
logs
runtime state
```

## 21.10 Test Criteria

After restoring or changing labwc config, these tests must pass:

```text
F12 from Kodi menu -> Kodi Favourites / Home behavior works
F12 from Plex playback -> playback stops and Kodi returns to Favourites
F12 from desktop/Firefox/terminal -> tvboxctl home runs
F12 from Steam Link -> Steam Link local client closes and Kodi returns
F12 from Moonlight -> local Moonlight disconnects and Kodi returns
F12 from YouTube/Chromium app -> Chromium app closes and Kodi returns
```

Verification command:

```bash
tail -n 30 /home/tvbox/.cache/tvboxctl.log
```

A successful global F12 press outside Kodi should create a fresh log line similar to:

```text
home requested; context=...
```

If F12 only works inside Kodi, assume labwc global keybinds are broken or not loaded.

## 21.11 Design Decision

The TVBox should not depend on fragile hand-edited live config files.

The correct design is:

```text
Git repo owns the system.
Repair scripts deploy the system.
GUI settings are allowed but not trusted.
Critical controls are verified after every config change.
```

This is required so the TVBox can survive:

```text
SD card corruption
Pi replacement
accidental GUI config rewrites
bad desktop settings changes
future input profile changes
remote-control recovery failures
```


