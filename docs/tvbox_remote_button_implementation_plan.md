# TVBox Remote Button Implementation Plan

## Target Button Semantics

```text
Back / last-channel = normal in-app Back
Home / Guide        = soft TVBox home / preserve state where safe
Menu                = current app's own home/menu
Exit                = hard close current app/session
App                 = Plex launcher
Red C               = YouTube launcher
```

Remote-to-key mapping already chosen:

```text
Home / Guide -> F12
Menu         -> F4
Exit         -> F5
App          -> F6
C            -> F7
```

---

# Phase 0 — Verify Inputs Before Script Work

## 0.1 Confirm Flirc raw events

Run:

```bash
sudo evtest /dev/input/by-id/usb-flirc.tv_flirc_0BCB17BE50584832322E3120FF022B15-if01-event-kbd
```

Confirm:

```text
Home -> KEY_F12
Menu -> KEY_F4
Exit -> KEY_F5
App  -> KEY_F6
C    -> KEY_F7
```

Do not continue until these are correct.

## 0.2 Check for existing F4-F7 usage

Run:

```bash
grep -RniE 'F4|F5|F6|F7|<f4>|<f5>|<f6>|<f7>' \
  ~/.config/labwc \
  ~/.kodi/userdata/keymaps \
  ~/.kodi/addons \
  /usr/local/bin 2>/dev/null
```

Expected: no important existing TVBox use.

---

# Phase 1 — Add Global Keybinds Only

Goal: make the remote buttons call scripts, even if some scripts are temporary placeholders.

## 1.1 Create backups

```bash
cp ~/.config/labwc/rc.xml ~/.config/labwc/rc.xml.bak.$(date +%Y%m%d-%H%M%S)
```

## 1.2 Add labwc keybinds

Inside `~/.config/labwc/rc.xml`, add or update:

```xml
<keybind key="F12">
  <action name="Execute" command="/usr/local/bin/tvbox-home" />
</keybind>

<keybind key="F4">
  <action name="Execute" command="/usr/local/bin/tvbox-menu" />
</keybind>

<keybind key="F5">
  <action name="Execute" command="/usr/local/bin/tvbox-exit" />
</keybind>

<keybind key="F6">
  <action name="Execute" command="/usr/local/bin/tvbox-plex" />
</keybind>

<keybind key="F7">
  <action name="Execute" command="/usr/local/bin/tvbox-youtube" />
</keybind>
```

## 1.3 Add temporary placeholders for missing scripts

If these do not exist yet, create harmless placeholders:

```bash
sudo tee /usr/local/bin/tvbox-menu >/dev/null <<'EOF2'
#!/bin/bash
logger -t tvbox-menu "placeholder called"
exit 0
EOF2

sudo tee /usr/local/bin/tvbox-exit >/dev/null <<'EOF2'
#!/bin/bash
logger -t tvbox-exit "placeholder called"
/usr/local/bin/tvbox-home
exit 0
EOF2

sudo tee /usr/local/bin/tvbox-plex >/dev/null <<'EOF2'
#!/bin/bash
logger -t tvbox-plex "placeholder called"
/usr/local/bin/tvbox-kodi
exit 0
EOF2

sudo chmod +x /usr/local/bin/tvbox-menu /usr/local/bin/tvbox-exit /usr/local/bin/tvbox-plex
```

## 1.4 Apply keybinds

Use the reliable method:

```bash
sudo reboot
```

## 1.5 Test after reboot

Press:

```text
Home -> existing tvbox-home behavior
C    -> existing YouTube launcher
App  -> launches/opens Kodi for now
Exit -> falls back to Home for now
Menu -> no visible action for now
```

Do not move on until the keys reliably trigger.

---

# Phase 2 — Implement Red C / YouTube First

Goal: make the red `C` button useful immediately with minimal risk.

## 2.1 Keep F7 bound directly to existing YouTube launcher

```text
F7 -> /usr/local/bin/tvbox-youtube
```

Do not modify YouTube preserve/resume behavior yet.

Expected behavior for now:

```text
Press C
-> current tvbox-youtube behavior runs
-> Kodi closes if needed
-> Chromium YouTube TV opens
-> when YouTube exits, Kodi returns by the existing wrapper behavior
```

## 2.2 Test from common contexts

Test C from:

```text
Kodi Favourites
Kodi/Plex playback
Desktop
Spotify mode, if safe
```

Expected: it should behave exactly like selecting the current YouTube launcher from Kodi.

---

# Phase 3 — Build Hard Exit Foundation

Goal: make `Exit` safely close active external sessions before changing Home behavior.

Create or replace:

```bash
/usr/local/bin/tvbox-exit
```

## 3.1 Required config variable

At the top of the script:

```bash
EXIT_CLOSES_KODI=0
```

Meaning:

```text
0 = Exit from Kodi stops playback / returns to a sane Kodi state
1 = Exit from plain Kodi closes Kodi
```

Default must remain `0` until the system is fully tested.

## 3.2 Exit priority order

Implement in this order:

```text
1. If Moonlight is active:
     run /usr/local/bin/tvbox-quit-moonlight-session
     return/allow return to Kodi
     exit

2. If Spotify mode is active:
     run /usr/local/bin/tvbox-stop-spotify
     launch /usr/local/bin/tvbox-kodi
     exit

3. If YouTube Chromium mode is active:
     run /usr/local/bin/tvbox-close-youtube
     launch /usr/local/bin/tvbox-kodi
     exit

4. If Kodi is active:
     stop playback
     if EXIT_CLOSES_KODI=1 and not obviously playing:
       close Kodi
     else:
       open Favourites or Kodi Home fallback
     exit

5. If nothing known is active:
     launch /usr/local/bin/tvbox-kodi
```

## 3.3 Moonlight behavior

Exit from Moonlight must be destructive:

```bash
/usr/local/bin/tvbox-quit-moonlight-session
```

This is different from Home, which uses local Moonlight disconnect only.

## 3.4 Spotify behavior

Use the existing Spotify stop path:

```bash
/usr/local/bin/tvbox-stop-spotify
```

Then return to Kodi:

```bash
/usr/local/bin/tvbox-kodi
```

## 3.5 YouTube close dependency

Do not make Home preserve YouTube until this exists:

```bash
/usr/local/bin/tvbox-close-youtube
```

Expected job:

```text
Close only the TVBox YouTube Chromium profile.
Do not kill Spotify Chromium.
Do not kill unrelated Chromium.
Return control to Kodi when called by tvbox-exit.
```

Likely process match should include the YouTube profile path, for example:

```text
chromium-tvbox-youtube
```

Avoid broad `pkill chromium`.

## 3.6 Kodi behavior

For Kodi/Plex playback:

```bash
kodi-send --action="PlayerControl(Stop)"
sleep 1
kodi-send --action="ActivateWindow(FavouritesBrowser)"
```

If `EXIT_CLOSES_KODI=1`, only close Kodi when there is no obvious playback state.

First implementation can avoid Plex-vs-Kodi detection. Treat Kodi as Kodi.

---

# Phase 4 — Build App / Plex Launcher

Goal: make `App` launch Plex from anywhere.

Create:

```bash
/usr/local/bin/tvbox-plex
```

## 4.1 Determine exact Plex launch command

Run:

```bash
grep -i plex ~/.kodi/userdata/favourites.xml
```

Extract the exact `ActivateWindow(...)` command Kodi uses for the Plex favourite.

## 4.2 Desired behavior

```text
If Moonlight active:
  use Home-style local disconnect, not destructive quit

If Spotify active:
  stop Spotify mode

If YouTube active:
  initial version may hard-close YouTube
  later version may preserve YouTube in background

Ensure Kodi is running:
  /usr/local/bin/tvbox-kodi

Open Plex:
  use kodi-send or JSON-RPC with the extracted Plex target
```

## 4.3 Initial acceptable implementation

Start simple:

```text
Stop conflicting external app if needed.
Launch Kodi.
Wait briefly.
Send Plex favourite/plugin activation command.
```

Do not require perfect detection of whether Plex is already open yet.

---

# Phase 5 — Add State Tracking

Goal: make Menu/Home/Exit reliable once apps can remain open in the background.

## 5.1 Use a simple runtime state directory

Preferred path:

```bash
/run/user/1000/tvbox
```

State file:

```bash
/run/user/1000/tvbox/active-context
```

Fallback if needed:

```bash
/tmp/tvbox-active-context
```

## 5.2 Context values

Use plain text values:

```text
kodi
plex
youtube
spotify
moonlight:steam
moonlight:minecraft
moonlight:desktop
moonlight:gui
desktop
unknown
```

## 5.3 Scripts that should set context

```text
tvbox-kodi      -> kodi
tvbox-home      -> kodi or preserved-source-aware state
tvbox-youtube   -> youtube
tvbox-plex      -> plex
tvbox-moonlight -> moonlight:<target>
tvbox-spotify-mode-foreground -> spotify
tvbox-exit      -> context after action, usually kodi or desktop
```

## 5.4 Do not overtrust state

State is a routing hint, not truth.

Each script should still verify important processes before acting:

```text
Moonlight process check before Moonlight exit
Chromium YouTube profile check before YouTube close
Spotify UI/profile check before Spotify stop
Kodi process check before kodi-send
```

---

# Phase 6 — Build Context Menu Button

Goal: make `Menu` mean current app's home/menu.

Create:

```bash
/usr/local/bin/tvbox-menu
```

## 6.1 Menu behavior matrix

```text
Context              Menu behavior
----------------------------------------------------------------
youtube              go to YouTube TV home / landing page
plex                 stop playback if needed, open Plex home
kodi                 open Kodi main home screen, not Favourites
moonlight:steam      run host-side Steam menu/home helper if implemented
moonlight:minecraft  no-op initially
moonlight:desktop    no-op initially
moonlight:gui        no-op initially
spotify              no-op or show Spotify placeholder
unknown/desktop      launch Kodi main home
```

## 6.2 Kodi main home

For plain Kodi context:

```bash
kodi-send --action="ActivateWindow(Home)"
```

This is intentionally different from Home/F12, which opens Favourites.

## 6.3 Plex home

Use the same extracted Plex launch command as `tvbox-plex`.

Before opening Plex home:

```bash
kodi-send --action="PlayerControl(Stop)"
sleep 1
```

Then activate Plex.

## 6.4 YouTube home

Initial reliable version:

```text
Close/relaunch YouTube at https://www.youtube.com/tv
```

Better later version:

```text
Use Chromium remote debugging or another controlled method to navigate existing YouTube Chromium to https://www.youtube.com/tv
```

Avoid trying to spam Back keys into YouTube TV.

## 6.5 Moonlight Steam menu

Treat as phase 6B, not required for first menu script.

Possible future behavior:

```text
tvbox-menu detects moonlight:steam
-> SSH to Obtuse
-> run /home/obtuse/bin/steam-menu-tv.sh
```

Possible host command:

```bash
/snap/bin/steam steam://open/gamepadui
```

This needs testing because Steam focus behavior is not guaranteed.

---

# Phase 7 — Change Home / YouTube to Soft Preserve

Goal: make Home from YouTube return to Kodi without killing YouTube.

Do not start this phase until:

```text
tvbox-exit can hard-close YouTube reliably
tvbox-youtube can avoid duplicate Chromium instances
state tracking exists
tvbox-menu exists or is at least harmless
```

## 7.1 New Home behavior from YouTube

```text
If YouTube is active/visible:
  pause YouTube if possible
  leave Chromium running
  launch Kodi
  set active context to kodi
```

## 7.2 YouTube resume behavior

Update `/usr/local/bin/tvbox-youtube`:

```text
If YouTube Chromium is already running:
  stop Kodi playback if needed
  close or hide Kodi
  reveal existing YouTube session
  set context youtube

If YouTube Chromium is not running:
  launch normal YouTube Chromium mode
  set context youtube
```

Simplest reveal method:

```text
Close Kodi and let the already-fullscreen YouTube Chromium window be visible again.
```

Avoid duplicate Chromium profiles.

## 7.3 Audio safety

Home must pause YouTube before returning to Kodi.

If pause is unreliable, do not preserve YouTube yet. Revert to destructive close-on-Home until pause/resume is predictable.

---

# Phase 8 — Loading Screens / Transition Covers

Goal: hide desktop and transition ugliness after control behavior is stable.

Do not implement before Phases 1-7 are stable.

## 8.1 TVBox-side loading screen script

Create:

```bash
/usr/local/bin/tvbox-loading-screen
```

Suggested interface:

```bash
/usr/local/bin/tvbox-loading-screen show steam
/usr/local/bin/tvbox-loading-screen show minecraft
/usr/local/bin/tvbox-loading-screen show youtube
/usr/local/bin/tvbox-loading-screen show plex
/usr/local/bin/tvbox-loading-screen close
```

Must be non-blocking and non-critical.

Rule:

```text
If loading screen fails, launcher continues anyway.
```

Use a dedicated profile if Chromium is used:

```bash
~/.config/chromium-tvbox-loading
```

Do not match or kill broad Chromium processes.

## 8.2 TVBox launch wrappers using loading screen

Add later to:

```text
tvbox-moonlight
tvbox-youtube
tvbox-plex
possibly tvbox-kodi
```

Pattern:

```text
show loading screen
start transition
start target app
close loading screen when target app is visible/running
```

## 8.3 Obtuse-side loading screen

Create host-side helpers later:

```bash
/home/obtuse/bin/tv-loading-screen.sh
/home/obtuse/bin/steam-loading-monitor.sh
/home/obtuse/bin/minecraft-loading-monitor.sh
```

Preferred host-side model:

```text
launch-steam-tv.sh:
  show fullscreen loading image
  launch Steam
  start background monitor
  exit quickly

background monitor:
  wait for Steam/Gamepad UI window
  close loading screen
```

Same pattern for Minecraft.

Do not turn Sunshine detached launch wrappers into long-running foreground scripts.

---

# Phase 9 — Final Regression Test Matrix

After each major phase, test these paths.

## 9.1 Home

```text
Kodi menu -> Favourites
Plex playback -> stop playback, Favourites
YouTube -> current phase behavior, either close or preserve
Moonlight -> local disconnect only, host app stays running
Spotify -> stop Spotify mode and return Kodi
Desktop -> launch Kodi
```

## 9.2 Exit

```text
Moonlight Steam -> Sunshine session quits, Steam closes on Obtuse, Kodi returns
Moonlight Minecraft -> Sunshine session quits, Minecraft closes on Obtuse, Kodi returns
YouTube -> YouTube Chromium closes, Kodi returns
Spotify -> Spotify mode/audio stops, Kodi returns
Kodi playback -> playback stops, sane Kodi state
Plain Kodi -> respects EXIT_CLOSES_KODI
```

## 9.3 App / Plex

```text
From Kodi -> opens Plex
From YouTube -> opens Plex according to current YouTube policy
From Moonlight -> local disconnect then opens Plex
From Spotify -> stops Spotify then opens Plex
From desktop -> launches Kodi then opens Plex
```

## 9.4 C / YouTube

```text
From Kodi -> opens YouTube
From Plex playback -> stops/pauses as designed, opens YouTube
From preserved YouTube -> resumes existing session, no duplicate Chromium
From Spotify -> stops Spotify, opens YouTube
From Moonlight -> local disconnect or policy-defined behavior
```

## 9.5 Menu

```text
Kodi -> Kodi main home, not Favourites
Plex -> Plex home
YouTube -> YouTube home
Moonlight Steam -> host Steam menu/home if implemented
Other Moonlight -> no-op initially
Spotify -> no-op or placeholder
```

---

# Implementation Priority Summary

```text
1. Verify Flirc F12/F4/F5/F6/F7 events.
2. Add labwc global keybinds with safe placeholder scripts.
3. Bind C/F7 to existing tvbox-youtube and test.
4. Implement tvbox-exit with Moonlight destructive quit first.
5. Add tvbox-close-youtube and integrate it into Exit.
6. Implement tvbox-plex for App/F6.
7. Add simple active-context state tracking.
8. Implement tvbox-menu.
9. Change Home/YouTube to preserve/resume YouTube.
10. Add loading screens after controls are stable.
```
