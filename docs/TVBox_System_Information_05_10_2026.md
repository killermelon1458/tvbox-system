# TV Box System Information

## Purpose

This machine is configured as a Raspberry Pi based TV box for Kodi/Plex playback, with future support for launching external applications such as Moonlight from Kodi.

The system is currently set up so Kodi can be launched in three ways:

1. Automatically at desktop login.
2. Manually from a desktop icon.
3. Manually from terminal using the canonical wrapper command.

All Kodi launch paths should call the same wrapper:

```bash
/usr/local/bin/tvbox-kodi
```

Do not use plain `kodi` as the normal launch path unless intentionally testing Kodi without the TV box wrapper.

---

## System Identity

| Item                                | Current Value                            |
| ----------------------------------- | ---------------------------------------- |
| Hostname                            | `tvbox`                                  |
| Main user                           | `tvbox`                                  |
| Platform                            | Raspberry Pi, ARM64 / `aarch64`          |
| OS family                           | Debian GNU/Linux / Raspberry Pi OS based |
| Kernel observed                     | `6.12.47+rpt-rpi-2712`                   |
| Kodi binary                         | `/usr/bin/kodi`                          |
| Audio stack present                 | PipeWire / WirePlumber / ALSA            |
| Confirmed PipeWire version observed | `1.4.2`                                  |

---

## Design Decision: Kodi Uses ALSA Directly

Kodi is intentionally launched with the ALSA audio backend instead of the default PipeWire backend.

Reason: the system had a failure where PipeWire/WirePlumber stopped exposing the HDMI audio sink and fell back to Dummy Output, even though direct ALSA audio to HDMI still worked. When Kodi used PipeWire during that failure, Kodi only saw PipeWire Default/Dummy output and produced no audio.

The stable working audio path is:

```text
Kodi -> ALSA -> HDMI -> TV
```

The avoided path is:

```text
Kodi -> PipeWire/WirePlumber -> ALSA -> HDMI -> TV
```

This is a deliberate low-maintenance choice for a dedicated TV box. It avoids depending on PipeWire HDMI sink detection for Kodi playback.

---

## Known Working HDMI Audio Device

Direct ALSA testing showed that HDMI card 1 works:

```text
card 1: vc4-hdmi-1
```

The successful test command was:

```bash
speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2 -t wav
```

The non-working HDMI path during troubleshooting was:

```text
card 0: vc4-hdmi-0
```

That path returned an error during direct ALSA testing:

```text
Playback open error: -524, Unknown error 524
```

Kodi should use the ALSA HDMI output matching:

```text
vc4-hdmi-1
card 1
MAI PCM
```

Kodi audio settings should remain:

```text
Channels: 2.0
Passthrough: Off
```

---

## Canonical Kodi Wrapper

The Kodi wrapper is located at:

```bash
/usr/local/bin/tvbox-kodi
```

Current intended contents:

```bash
#!/bin/bash

# Launch Kodi using ALSA directly instead of PipeWire.
# This avoids PipeWire/WirePlumber HDMI sink failures on this Pi.

exec /usr/bin/kodi --audio-backend=alsa "$@"
```

The file should be executable:

```bash
-rwxr-xr-x
```

Verify with:

```bash
cat /usr/local/bin/tvbox-kodi
ls -l /usr/local/bin/tvbox-kodi
```

Launch Kodi manually with:

```bash
tvbox-kodi
```

or:

```bash
/usr/local/bin/tvbox-kodi
```

---

## Desktop Launcher

A desktop launcher exists for manually starting Kodi if Kodi is closed or crashes.

Expected file:

```bash
~/Desktop/Kodi.desktop
```

Expected launcher contents:

```ini
[Desktop Entry]
Type=Application
Name=Kodi
Comment=Launch Kodi with ALSA audio backend
Exec=/usr/local/bin/tvbox-kodi
Icon=kodi
Terminal=false
Categories=AudioVideo;Player;TV;
StartupNotify=false
```

The important line is:

```ini
Exec=/usr/local/bin/tvbox-kodi
```

The launcher should be executable:

```bash
chmod +x ~/Desktop/Kodi.desktop
```

---

## Desktop Executable Prompt Behavior

The desktop originally prompted with options such as:

```text
Execute
Execute in Terminal
Open
Cancel
```

That prompt was disabled through the PCManFM/libfm configuration.

Expected config file:

```bash
~/.config/libfm/libfm.conf
```

Expected setting:

```ini
quick_exec=1
```

Verify with:

```bash
grep -n "quick_exec" ~/.config/libfm/libfm.conf
```

Expected result:

```text
quick_exec=1
```

Security note: this makes executable files launch directly from the file manager instead of asking for confirmation. This is acceptable for this dedicated TV box use case but would be less ideal on a general-purpose desktop.

---

## Autostart Configuration

Kodi autostarts through the user desktop session, not through a root/system service.

Reason: Kodi is a GUI application and should start inside the logged-in user’s graphical desktop session, with access to the correct display, user environment, input devices, and audio/session permissions.

Expected autostart file:

```bash
~/.config/autostart/tvbox-kodi.desktop
```

Expected contents:

```ini
[Desktop Entry]
Type=Application
Name=TVBox Kodi Autostart
Comment=Launch Kodi on login using the tvbox ALSA wrapper
Exec=sh -c 'sleep 5; /usr/local/bin/tvbox-kodi'
Terminal=false
X-GNOME-Autostart-enabled=true
```

The 5-second delay gives the desktop/display session time to settle before Kodi starts.

The important line is:

```ini
Exec=sh -c 'sleep 5; /usr/local/bin/tvbox-kodi'
```

The file should be executable:

```bash
chmod +x ~/.config/autostart/tvbox-kodi.desktop
```

---

## Why Autostart Is Not a Restarting Service

Kodi should not currently be managed by a `Restart=always` systemd service.

Reason: future Moonlight integration will intentionally close Kodi, run Moonlight, then relaunch Kodi afterward. A restart-always service would fight that design by immediately restarting Kodi as soon as the Moonlight script exits or kills it.

Current intended launch model:

```text
Boot/login -> desktop autostart launches Kodi once
Manual recovery -> desktop icon launches Kodi
Future Moonlight handoff -> script closes Kodi, launches Moonlight, waits, then relaunches Kodi
```

This avoids multiple components trying to restart Kodi at the same time.

---

## Future Moonlight Handoff Design

Future external-app launch scripts should call the same Kodi wrapper when returning to Kodi.

Planned flow:

```text
Kodi button selected
-> external script runs
-> Kodi exits
-> Moonlight starts
-> script waits for Moonlight to exit
-> script relaunches Kodi using /usr/local/bin/tvbox-kodi
```

Example script structure:

```bash
#!/bin/bash

pkill kodi 2>/dev/null
pkill kodi.bin 2>/dev/null
sleep 2

moonlight-qt

/usr/local/bin/tvbox-kodi
```

The exact Moonlight command may change depending on how Moonlight is installed.

---

## Current Audio Health Checks

Check current PipeWire state:

```bash
wpctl status
```

Healthy PipeWire state may show:

```text
Built-in Audio Digital Stereo (HDMI)
```

Broken PipeWire state previously showed only:

```text
Dummy Output
```

Check PipeWire sinks:

```bash
pactl list sinks short
```

Healthy HDMI sink example:

```text
alsa_output.platform-107c706400.hdmi.hdmi-stereo
```

Check PipeWire card profile state:

```bash
pactl list cards | grep -E "Card #|Name:|alsa.card_name|Profiles:|output:|Active Profile"
```

Healthy HDMI card 1 profile example:

```text
alsa.card_name = "vc4-hdmi-1"
output:hdmi-stereo: Digital Stereo (HDMI) Output ... available: yes
Active Profile: output:hdmi-stereo
```

Check ALSA hardware devices:

```bash
aplay -l
```

Expected HDMI cards:

```text
card 0: vc4hdmi0 [vc4-hdmi-0]
card 1: vc4hdmi1 [vc4-hdmi-1]
```

Directly test the known working ALSA HDMI device:

```bash
speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2 -t wav
```

Stop the speaker test with:

```text
Ctrl+C
```

---

## Kodi Process Management

Stop Kodi hard if needed:

```bash
pkill -9 -x kodi 2>/dev/null
pkill -9 -x kodi.bin 2>/dev/null
```

Launch Kodi correctly:

```bash
/usr/local/bin/tvbox-kodi
```

Check whether Kodi is running:

```bash
pgrep -a kodi
pgrep -a kodi.bin
```

Check Kodi audio backend logs:

```bash
grep -iE "Enumerated|ALSA|PIPEWIRE|m_displayName|audio-backend|CActiveAESink" ~/.kodi/temp/kodi.log | tail -n 120
```

Expected long-term goal when using the wrapper:

```text
Kodi should use ALSA, not PipeWire, for playback audio.
```

---

## Plain Kodi Versus TVBox Kodi Wrapper

Plain Kodi command:

```bash
kodi
```

This uses Kodi’s default behavior and may use PipeWire.

TV box wrapper command:

```bash
tvbox-kodi
```

This forces Kodi to use ALSA directly:

```bash
/usr/bin/kodi --audio-backend=alsa
```

Normal operation should use `tvbox-kodi`, not plain `kodi`.

Plain `kodi` is useful only for testing whether PipeWire behavior has changed.

---

## Current Stable State Summary

The TV box is currently working with:

```text
Kodi installed at /usr/bin/kodi
Kodi wrapper at /usr/local/bin/tvbox-kodi
Kodi launched with --audio-backend=alsa
Desktop icon launching /usr/local/bin/tvbox-kodi
Desktop executable prompt disabled through libfm quick_exec=1
Kodi desktop autostart configured through ~/.config/autostart/tvbox-kodi.desktop
HDMI audio working through ALSA HDMI card 1 / vc4-hdmi-1
Kodi audio configured for 2.0 channels with passthrough off
```

The system should be maintained around the principle that all normal Kodi launch paths call:

```bash
/usr/local/bin/tvbox-kodi
```
# TV Box System Information

## Purpose

This machine is configured as a Raspberry Pi based TV box for Kodi/Plex playback, with future support for launching external applications such as Moonlight from Kodi.

The system is currently set up so Kodi can be launched in three ways:

1. Automatically at desktop login.
2. Manually from a desktop icon.
3. Manually from terminal using the canonical wrapper command.

All Kodi launch paths should call the same wrapper:

```bash
/usr/local/bin/tvbox-kodi
```

Do not use plain `kodi` as the normal launch path unless intentionally testing Kodi without the TV box wrapper.

---

## System Identity

| Item                                | Current Value                            |
| ----------------------------------- | ---------------------------------------- |
| Hostname                            | `tvbox`                                  |
| Main user                           | `tvbox`                                  |
| Platform                            | Raspberry Pi, ARM64 / `aarch64`          |
| OS family                           | Debian GNU/Linux / Raspberry Pi OS based |
| Kernel observed                     | `6.12.47+rpt-rpi-2712`                   |
| Kodi binary                         | `/usr/bin/kodi`                          |
| Audio stack present                 | PipeWire / WirePlumber / ALSA            |
| Confirmed PipeWire version observed | `1.4.2`                                  |

---

## Design Decision: Kodi Uses ALSA Directly

Kodi is intentionally launched with the ALSA audio backend instead of the default PipeWire backend.

Reason: the system had a failure where PipeWire/WirePlumber stopped exposing the HDMI audio sink and fell back to Dummy Output, even though direct ALSA audio to HDMI still worked. When Kodi used PipeWire during that failure, Kodi only saw PipeWire Default/Dummy output and produced no audio.

The stable working audio path is:

```text
Kodi -> ALSA -> HDMI -> TV
```

The avoided path is:

```text
Kodi -> PipeWire/WirePlumber -> ALSA -> HDMI -> TV
```

This is a deliberate low-maintenance choice for a dedicated TV box. It avoids depending on PipeWire HDMI sink detection for Kodi playback.

---

## Known Working HDMI Audio Device

Direct ALSA testing showed that HDMI card 1 works:

```text
card 1: vc4-hdmi-1
```

The successful test command was:

```bash
speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2 -t wav
```

The non-working HDMI path during troubleshooting was:

```text
card 0: vc4-hdmi-0
```

That path returned an error during direct ALSA testing:

```text
Playback open error: -524, Unknown error 524
```

Kodi should use the ALSA HDMI output matching:

```text
vc4-hdmi-1
card 1
MAI PCM
```

Kodi audio settings should remain:

```text
Channels: 2.0
Passthrough: Off
```

---

## Canonical Kodi Wrapper

The Kodi wrapper is located at:

```bash
/usr/local/bin/tvbox-kodi
```

Current intended contents:

```bash
#!/bin/bash

# Launch Kodi using ALSA directly instead of PipeWire.
# This avoids PipeWire/WirePlumber HDMI sink failures on this Pi.

exec /usr/bin/kodi --audio-backend=alsa "$@"
```

The file should be executable:

```bash
-rwxr-xr-x
```

Verify with:

```bash
cat /usr/local/bin/tvbox-kodi
ls -l /usr/local/bin/tvbox-kodi
```

Launch Kodi manually with:

```bash
tvbox-kodi
```

or:

```bash
/usr/local/bin/tvbox-kodi
```

---

## Desktop Launcher

A desktop launcher exists for manually starting Kodi if Kodi is closed or crashes.

Expected file:

```bash
~/Desktop/Kodi.desktop
```

Expected launcher contents:

```ini
[Desktop Entry]
Type=Application
Name=Kodi
Comment=Launch Kodi with ALSA audio backend
Exec=/usr/local/bin/tvbox-kodi
Icon=kodi
Terminal=false
Categories=AudioVideo;Player;TV;
StartupNotify=false
```

The important line is:

```ini
Exec=/usr/local/bin/tvbox-kodi
```

The launcher should be executable:

```bash
chmod +x ~/Desktop/Kodi.desktop
```

---

## Desktop Executable Prompt Behavior

The desktop originally prompted with options such as:

```text
Execute
Execute in Terminal
Open
Cancel
```

That prompt was disabled through the PCManFM/libfm configuration.

Expected config file:

```bash
~/.config/libfm/libfm.conf
```

Expected setting:

```ini
quick_exec=1
```

Verify with:

```bash
grep -n "quick_exec" ~/.config/libfm/libfm.conf
```

Expected result:

```text
quick_exec=1
```

Security note: this makes executable files launch directly from the file manager instead of asking for confirmation. This is acceptable for this dedicated TV box use case but would be less ideal on a general-purpose desktop.

---

## Autostart Configuration

Kodi autostarts through the user desktop session, not through a root/system service.

Reason: Kodi is a GUI application and should start inside the logged-in user’s graphical desktop session, with access to the correct display, user environment, input devices, and audio/session permissions.

Expected autostart file:

```bash
~/.config/autostart/tvbox-kodi.desktop
```

Expected contents:

```ini
[Desktop Entry]
Type=Application
Name=TVBox Kodi Autostart
Comment=Launch Kodi on login using the tvbox ALSA wrapper
Exec=sh -c 'sleep 5; /usr/local/bin/tvbox-kodi'
Terminal=false
X-GNOME-Autostart-enabled=true
```

The 5-second delay gives the desktop/display session time to settle before Kodi starts.

The important line is:

```ini
Exec=sh -c 'sleep 5; /usr/local/bin/tvbox-kodi'
```

The file should be executable:

```bash
chmod +x ~/.config/autostart/tvbox-kodi.desktop
```

---

## Why Autostart Is Not a Restarting Service

Kodi should not currently be managed by a `Restart=always` systemd service.

Reason: future Moonlight integration will intentionally close Kodi, run Moonlight, then relaunch Kodi afterward. A restart-always service would fight that design by immediately restarting Kodi as soon as the Moonlight script exits or kills it.

Current intended launch model:

```text
Boot/login -> desktop autostart launches Kodi once
Manual recovery -> desktop icon launches Kodi
Future Moonlight handoff -> script closes Kodi, launches Moonlight, waits, then relaunches Kodi
```

This avoids multiple components trying to restart Kodi at the same time.

---

## Future Moonlight Handoff Design

Future external-app launch scripts should call the same Kodi wrapper when returning to Kodi.

Planned flow:

```text
Kodi button selected
-> external script runs
-> Kodi exits
-> Moonlight starts
-> script waits for Moonlight to exit
-> script relaunches Kodi using /usr/local/bin/tvbox-kodi
```

Example script structure:

```bash
#!/bin/bash

pkill kodi 2>/dev/null
pkill kodi.bin 2>/dev/null
sleep 2

moonlight-qt

/usr/local/bin/tvbox-kodi
```

The exact Moonlight command may change depending on how Moonlight is installed.

---

## Current Audio Health Checks

Check current PipeWire state:

```bash
wpctl status
```

Healthy PipeWire state may show:

```text
Built-in Audio Digital Stereo (HDMI)
```

Broken PipeWire state previously showed only:

```text
Dummy Output
```

Check PipeWire sinks:

```bash
pactl list sinks short
```

Healthy HDMI sink example:

```text
alsa_output.platform-107c706400.hdmi.hdmi-stereo
```

Check PipeWire card profile state:

```bash
pactl list cards | grep -E "Card #|Name:|alsa.card_name|Profiles:|output:|Active Profile"
```

Healthy HDMI card 1 profile example:

```text
alsa.card_name = "vc4-hdmi-1"
output:hdmi-stereo: Digital Stereo (HDMI) Output ... available: yes
Active Profile: output:hdmi-stereo
```

Check ALSA hardware devices:

```bash
aplay -l
```

Expected HDMI cards:

```text
card 0: vc4hdmi0 [vc4-hdmi-0]
card 1: vc4hdmi1 [vc4-hdmi-1]
```

Directly test the known working ALSA HDMI device:

```bash
speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2 -t wav
```

Stop the speaker test with:

```text
Ctrl+C
```

---

## Kodi Process Management

Stop Kodi hard if needed:

```bash
pkill -9 -x kodi 2>/dev/null
pkill -9 -x kodi.bin 2>/dev/null
```

Launch Kodi correctly:

```bash
/usr/local/bin/tvbox-kodi
```

Check whether Kodi is running:

```bash
pgrep -a kodi
pgrep -a kodi.bin
```

Check Kodi audio backend logs:

```bash
grep -iE "Enumerated|ALSA|PIPEWIRE|m_displayName|audio-backend|CActiveAESink" ~/.kodi/temp/kodi.log | tail -n 120
```

Expected long-term goal when using the wrapper:

```text
Kodi should use ALSA, not PipeWire, for playback audio.
```

---

## Plain Kodi Versus TVBox Kodi Wrapper

Plain Kodi command:

```bash
kodi
```

This uses Kodi’s default behavior and may use PipeWire.

TV box wrapper command:

```bash
tvbox-kodi
```

This forces Kodi to use ALSA directly:

```bash
/usr/bin/kodi --audio-backend=alsa
```

Normal operation should use `tvbox-kodi`, not plain `kodi`.

Plain `kodi` is useful only for testing whether PipeWire behavior has changed.

---

## Current Stable State Summary

The TV box is currently working with:

```text
Kodi installed at /usr/bin/kodi
Kodi wrapper at /usr/local/bin/tvbox-kodi
Kodi launched with --audio-backend=alsa
Desktop icon launching /usr/local/bin/tvbox-kodi
Desktop executable prompt disabled through libfm quick_exec=1
Kodi desktop autostart configured through ~/.config/autostart/tvbox-kodi.desktop
HDMI audio working through ALSA HDMI card 1 / vc4-hdmi-1
Kodi audio configured for 2.0 channels with passthrough off
```

The system should be maintained around the principle that all normal Kodi launch paths call:

```bash
/usr/local/bin/tvbox-kodi
```

---

## YouTube TVBox Chromium Launcher

YouTube is currently handled through a custom Chromium app-mode launcher, not through the official Kodi YouTube add-on.

The launcher is located at:

```bash
/usr/local/bin/tvbox-youtube
```

Purpose:

```text
Close Kodi
-> launch YouTube TV web UI in Chromium app mode
-> wait until Chromium exits
-> relaunch Kodi through /usr/local/bin/tvbox-kodi
```

The launcher uses Chromium with a dedicated profile:

```bash
~/.config/chromium-tvbox-youtube
```

The launcher uses the YouTube TV interface:

```text
https://www.youtube.com/tv
```

It also uses a Smart TV style user agent so YouTube loads the remote-friendly TV UI instead of the normal desktop site.

Important Chromium launch options currently used or expected:

```bash
--user-data-dir="$PROFILE"
--no-first-run
--disable-session-crashed-bubble
--password-store=basic
--start-fullscreen
--user-agent="Mozilla/5.0 (SMART-TV; Linux; Tizen 7.0) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.0.0 Safari/537.36"
--app="https://www.youtube.com/tv"
```

The `--password-store=basic` flag is intentional. It avoids Chromium asking to unlock the desktop keyring after reboot/autologin.

Expected YouTube remote behavior:

```text
Arrow keys  -> navigate
Enter       -> select
Backspace   -> back
Space       -> play/pause
F12         -> global TVBox Home action
Alt+F4      -> close Chromium and return to Kodi
```

The YouTube launcher should be started with:

```bash
/usr/local/bin/tvbox-youtube
```

When Chromium exits, Kodi should relaunch automatically through:

```bash
/usr/local/bin/tvbox-kodi
```

---

## Official Kodi YouTube Add-on State

The official Kodi YouTube add-on was installed and tested, but later removed from Kodi because its UI was poor for normal TV-box use.

The current preferred YouTube path is:

```text
Kodi -> YouTube TVBox local launcher add-on -> /usr/local/bin/tvbox-youtube -> Chromium YouTube TV UI
```

During official add-on setup, this dependency was installed through apt:

```bash
sudo apt install kodi-inputstream-adaptive
```

Installed packages included:

```text
kodi-inputstream-adaptive
libwebm1
```

These packages may still be installed and are not currently harmful.

The official YouTube add-on required personal YouTube API credentials before it would work. Personal API keys were created through Google Cloud and added through the YouTube add-on API configuration webpage during testing.

Because the official Kodi YouTube add-on has been removed, any leftover YouTube add-on data, API key files, or Google Cloud credentials are no longer part of the active TV-box YouTube path. They may still exist unless manually cleaned up.

Expected active state:

```text
Official Kodi YouTube add-on removed
Chromium YouTube TVBox mode preferred for day-to-day use
kodi-inputstream-adaptive may remain installed
Google API project/credentials may still exist externally unless deleted from Google Cloud
```

---

## YouTube TVBox Kodi Video Add-on

A local Kodi video add-on exists to launch the Chromium YouTube TVBox mode from Kodi.

This is separate from the official Kodi YouTube add-on.

Expected add-on folder:

```bash
~/.kodi/addons/plugin.video.tvbox.youtube
```

Expected add-on name in Kodi:

```text
YouTube TVBox
```

Expected Kodi location:

```text
Kodi -> Add-ons -> Video add-ons -> YouTube TVBox
```

The add-on calls the external launcher:

```bash
/usr/local/bin/tvbox-youtube
```

Expected files:

```bash
~/.kodi/addons/plugin.video.tvbox.youtube/addon.xml
~/.kodi/addons/plugin.video.tvbox.youtube/default.py
~/.kodi/addons/plugin.video.tvbox.youtube/icon.png
```

The add-on is intentionally only a Kodi-facing launcher. The actual YouTube behavior is controlled by:

```bash
/usr/local/bin/tvbox-youtube
```

The icon file should be:

```bash
~/.kodi/addons/plugin.video.tvbox.youtube/icon.png
```

A YouTube icon was copied from:

```bash
/home/tvbox/Downloads/youtube-6062251_1280.png
```

to:

```bash
~/.kodi/addons/plugin.video.tvbox.youtube/icon.png
```

If Kodi does not display the icon, clear Kodi’s artwork cache:

```bash
pkill -9 -x kodi 2>/dev/null
pkill -9 -x kodi.bin 2>/dev/null
rm -f ~/.kodi/userdata/Database/Textures*.db
rm -rf ~/.kodi/userdata/Thumbnails/*
tvbox-kodi
```

---

## Kodi Favourites Startup Service

Kodi is configured to open Favourites automatically shortly after startup.

This is handled through a local Kodi service add-on instead of the deprecated `autoexec.py` method.

Expected service add-on folder:

```bash
~/.kodi/addons/service.tvbox.startup
```

Expected files:

```bash
~/.kodi/addons/service.tvbox.startup/addon.xml
~/.kodi/addons/service.tvbox.startup/startup.py
```

Expected `startup.py` behavior:

```python
import xbmc

monitor = xbmc.Monitor()

# Short delay so the skin has time to load.
if not monitor.waitForAbort(1):
    xbmc.executebuiltin("ActivateWindow(FavouritesBrowser)")
```

The 1-second delay is intentional. It is short enough to feel like Favourites is the startup page, but long enough that Kodi’s skin is usually ready.

Expected startup behavior:

```text
Kodi launches
-> waits about 1 second
-> opens Favourites
```

If Favourites sometimes fails to open on startup, increase the delay from `1` to `2`.

---

## TVBox Home Script

A global Home behavior is centralized in:

```bash
/usr/local/bin/tvbox-home
```

Purpose:

```text
If Kodi is running:
  stop playback if needed
  open Kodi Favourites

If Chromium YouTube mode is running:
  close Chromium
  allow the YouTube launcher to relaunch Kodi

If nothing relevant is running:
  launch Kodi through /usr/local/bin/tvbox-kodi
```

Kodi command behavior used by the script:

```bash
kodi-send --action="PlayerControl(Stop)"
sleep 1
kodi-send --action="ActivateWindow(FavouritesBrowser)"
```

The `PlayerControl(Stop)` action is intentional. It makes the Home action work from Plex playback as well as Kodi menus.

The `sleep 1` delay is intentional because stopping playback is asynchronous. Without the delay, Kodi/Plex may leave fullscreen playback but fail to reach Favourites.

The script was tested successfully from:

```text
Kodi menu
Plex menu
Plex playback
YouTube Chromium mode
Desktop
```

Expected result from each location:

```text
Kodi menu        -> opens Favourites
Plex menu        -> opens Favourites
Plex playback    -> stops playback, then opens Favourites
YouTube mode     -> closes Chromium, then Kodi relaunches
Desktop          -> launches Kodi
```

---

## kodi-send Requirement

The `tvbox-home` script depends on `kodi-send` to control Kodi externally.

Install package if needed:

```bash
sudo apt install kodi-eventclients-kodi-send
```

Verify:

```bash
command -v kodi-send
```

Expected:

```bash
/usr/bin/kodi-send
```

Test Kodi communication:

```bash
kodi-send --action="Notification(TVBox,kodi-send works,3000)"
```

If Kodi does not receive the command, enable local control in Kodi:

```text
Settings -> Services -> Control -> Allow remote control from applications on this system
```

---

## Global F12 Home Keybind Through labwc

The desktop compositor/window manager is labwc.

Confirmed process:

```bash
/usr/bin/labwc -m
```

The global Home key is bound through labwc, not Wayfire or Openbox.

Expected labwc config:

```bash
~/.config/labwc/rc.xml
```

Before modifying the labwc config, a backup was created with a timestamped name like:

```bash
~/.config/labwc/rc.xml.bak.YYYYMMDD-HHMMSS
```

Verify backups with:

```bash
ls -lh ~/.config/labwc/rc.xml.bak.*
```

The F12 global keybind calls:

```bash
/usr/local/bin/tvbox-home
```

Expected keybind inside `~/.config/labwc/rc.xml`:

```xml
<keybind key="F12">
  <action name="Execute" command="/usr/local/bin/tvbox-home" />
</keybind>
```

A reboot is the simplest reliable way to apply labwc keybind changes:

```bash
sudo reboot
```

Current tested global F12 behavior:

```text
F12 from YouTube Chromium mode -> closes YouTube and returns to Kodi
F12 from desktop              -> launches Kodi
F12 from Kodi menu            -> opens Favourites
F12 from Plex menu            -> opens Favourites
F12 from Plex playback        -> stops playback, then opens Favourites
```

The remote Home button should be programmed through Flirc to send:

```text
F12
```

---

## Kodi F12 Keymap Fallback

A Kodi-local F12 keymap may still exist as a fallback.

Expected file:

```bash
~/.kodi/userdata/keymaps/tvbox-remote.xml
```

Expected Kodi-local binding:

```xml
<f12>ActivateWindow(FavouritesBrowser)</f12>
```

This is now redundant with the global labwc F12 binding, but it is harmless and can be left in place.

Reason to keep it:

```text
If the global labwc keybind ever fails inside Kodi fullscreen,
Kodi’s own keymap may still catch F12 and open Favourites.
```

Only remove the Kodi keymap if it causes double-trigger behavior, flickering, or inconsistent results.

---

## Accidental Orca Screen Reader Install and Removal

An accidental keyboard/input event triggered installation of the Orca screen reader through PackageKit.

Apt history showed:

```text
Commandline: packagekit role='install-packages'
Install: orca
```

Orca was disabled and removed.

Commands used/expected:

```bash
pkill -f orca
gsettings set org.gnome.desktop.a11y.applications screen-reader-enabled false
sudo apt purge orca
sudo apt autoremove --purge
```

Verify Orca is not running:

```bash
pgrep -a orca
```

Expected result:

```text
no output
```

A user-level autostart override may exist:

```bash
~/.config/autostart/orca-autostart.desktop
```

Expected safety line if present:

```ini
Hidden=true
```

---

## Current User-Facing TVBox Flow

Current intended user flow:

```text
Boot TVBox
-> desktop autologin
-> Kodi autostarts
-> Kodi opens Favourites after about 1 second
-> user selects Plex, YouTube TVBox, or another favourite
```

YouTube flow:

```text
Select YouTube TVBox in Kodi
-> Kodi closes
-> Chromium opens YouTube TV interface
-> remote controls YouTube
-> F12/Home closes Chromium
-> Kodi relaunches
-> Favourites opens
```

Plex flow:

```text
Select Plex
-> browse or play media
-> F12/Home stops playback if needed
-> Kodi opens Favourites
```

The system should continue to follow this principle:

```text
All normal Kodi launches go through /usr/local/bin/tvbox-kodi.
All global Home behavior goes through /usr/local/bin/tvbox-home.
All YouTube TV mode launches go through /usr/local/bin/tvbox-youtube.
```
# TVBox System Info Append: Updating Kodi Add-on Thumbnails

## Purpose

Kodi Program add-ons can use local image files for their icons. For TVBox launcher add-ons, place the desired image in the add-on folder as `icon.png`, then update Kodi metadata/cache if the icon does not refresh automatically.

This applies to launcher add-ons such as:

```text
Moonlight
Moonlight - Steam
Moonlight - Minecraft
YouTube / other local TVBox launcher add-ons
```

---

## Icon File Location

Each Kodi add-on can include an icon directly in its add-on directory.

Expected filename:

```text
icon.png
```

Recommended image format:

```text
PNG
Square image preferred
256x256 or 512x512 recommended
```

Example Moonlight launcher icon paths:

```bash
/home/tvbox/.kodi/addons/plugin.program.tvbox.moonlight/icon.png
/home/tvbox/.kodi/addons/plugin.program.tvbox.moonlight.steam/icon.png
/home/tvbox/.kodi/addons/plugin.program.tvbox.moonlight.minecraft/icon.png
```

Example copy commands:

```bash
cp ~/Downloads/moonlight.png ~/.kodi/addons/plugin.program.tvbox.moonlight/icon.png
cp ~/Downloads/steam-icon-28.png ~/.kodi/addons/plugin.program.tvbox.moonlight.steam/icon.png
cp ~/Downloads/minecraft.png ~/.kodi/addons/plugin.program.tvbox.moonlight.minecraft/icon.png
```

Verify the files:

```bash
for d in \
  ~/.kodi/addons/plugin.program.tvbox.moonlight \
  ~/.kodi/addons/plugin.program.tvbox.moonlight.steam \
  ~/.kodi/addons/plugin.program.tvbox.moonlight.minecraft
do
  echo "=== $d ==="
  ls -lh "$d/icon.png"
  file "$d/icon.png"
done
```

---

## Add-on XML Metadata

Kodi may not always refresh icon metadata just because `icon.png` exists.

Each add-on should include an explicit asset entry in `addon.xml`:

```xml
<assets>
  <icon>icon.png</icon>
</assets>
```

The asset block belongs inside the metadata extension:

```xml
<extension point="xbmc.addon.metadata">
  <summary>...</summary>
  <description>...</description>
  <platform>all</platform>
  <assets>
    <icon>icon.png</icon>
  </assets>
</extension>
```

After changing metadata, bump the add-on version, for example:

```xml
version="1.0.2"
```

Validate XML syntax:

```bash
python3 - <<'EOF'
from pathlib import Path
import xml.etree.ElementTree as ET

for p in [
    Path.home() / ".kodi/addons/plugin.program.tvbox.moonlight/addon.xml",
    Path.home() / ".kodi/addons/plugin.program.tvbox.moonlight.steam/addon.xml",
    Path.home() / ".kodi/addons/plugin.program.tvbox.moonlight.minecraft/addon.xml",
]:
    try:
        ET.parse(p)
        print(f"OK: {p}")
    except Exception as e:
        print(f"BROKEN: {p}: {e}")
EOF
```

---

## Favourites Thumbnail Cache

Kodi Favourites can keep their own cached thumbnail reference. If icons do not update after adding `icon.png` and bumping the add-on version, patch `favourites.xml` directly.

Favourites file:

```bash
/home/tvbox/.kodi/userdata/favourites.xml
```

Check relevant favourites:

```bash
grep -n "plugin.program.tvbox" ~/.kodi/userdata/favourites.xml 2>/dev/null || true
```

Back up before editing:

```bash
cp ~/.kodi/userdata/favourites.xml ~/.kodi/userdata/favourites.xml.bak.$(date +%Y%m%d-%H%M%S)
```

Patch Moonlight favourite thumbnails:

```bash
python3 - <<'EOF'
from pathlib import Path
import re

p = Path.home() / ".kodi/userdata/favourites.xml"
s = p.read_text()

thumbs = {
    "plugin.program.tvbox.moonlight.minecraft": "special://home/addons/plugin.program.tvbox.moonlight.minecraft/icon.png",
    "plugin.program.tvbox.moonlight.steam": "special://home/addons/plugin.program.tvbox.moonlight.steam/icon.png",
    "plugin.program.tvbox.moonlight": "special://home/addons/plugin.program.tvbox.moonlight/icon.png",
}

new_lines = []
for line in s.splitlines():
    for addon_id, thumb in thumbs.items():
        if addon_id in line:
            if ' thumb="' in line:
                line = re.sub(r' thumb="[^"]*"', f' thumb="{thumb}"', line)
            else:
                line = line.replace("<favourite ", f'<favourite thumb="{thumb}" ', 1)
            break
    new_lines.append(line)

p.write_text("\n".join(new_lines) + "\n")
EOF

cat ~/.kodi/userdata/favourites.xml
```

Expected favourite entry shape:

```xml
<favourite thumb="special://home/addons/plugin.program.tvbox.moonlight.minecraft/icon.png" name="Moonlight - Minecraft">ActivateWindow(10001,"plugin://plugin.program.tvbox.moonlight.minecraft",return)</favourite>
```

---

## Clear Kodi Texture Cache

Kodi may continue showing stale artwork until the texture cache is cleared.

This does not remove add-ons or settings. It forces Kodi to rebuild cached artwork.

```bash
pkill -TERM -x kodi 2>/dev/null || true
pkill -TERM -x kodi.bin 2>/dev/null || true
sleep 3

rm -f ~/.kodi/userdata/Database/Textures*.db
rm -rf ~/.kodi/userdata/Thumbnails/*

/usr/local/bin/tvbox-kodi
```

If icons still do not update, remove the affected favourites inside Kodi and re-add them from:

```text
Add-ons -> Program add-ons
```

Then repeat the `favourites.xml` thumbnail patch if needed.

---

## Known Working Procedure

For stubborn Kodi Favourite icons, the reliable sequence is:

```text
1. Copy the new image to the add-on folder as icon.png.
2. Ensure addon.xml has <assets><icon>icon.png</icon></assets>.
3. Bump the add-on version.
4. Validate addon.xml syntax.
5. Patch favourites.xml thumb= paths directly.
6. Clear Textures*.db and Thumbnails.
7. Restart Kodi through /usr/local/bin/tvbox-kodi.
```

Use `/usr/local/bin/tvbox-kodi` for the restart so Kodi comes back through the normal TVBox launch path.
