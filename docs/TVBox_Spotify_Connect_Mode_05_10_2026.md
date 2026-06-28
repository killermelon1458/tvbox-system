# TVBox Spotify Connect Mode

## Purpose

This document describes the Spotify Connect setup on the Raspberry Pi TVBox.

Spotify is configured so the TVBox appears as a Spotify Connect target named:

```text
TVBox Spotify
```

The intended user flow is:

```text
Open Spotify on phone
-> select TVBox Spotify
-> TVBox interrupts the current media app if needed
-> fullscreen Spotify placeholder UI opens on the TV
-> Spotify audio plays through HDMI
-> F12/Home stops Spotify mode and returns to Kodi
```

This setup is intentionally not a Kodi Spotify plug-in.

Reason:

```text
The household workflow is phone-controlled Spotify playback, like using a Roku Spotify endpoint.
The TVBox should behave like a visible Spotify Connect device, not require browsing Spotify through Kodi with the TV remote.
```

The phone remains the real Spotify controller.

The TV screen only shows a local placeholder UI so the TV does not appear stuck in Kodi/Plex/YouTube while Spotify is playing.

---

## Current Verified State

Verified after reboot:

```text
Spotify from Kodi menu       -> works
Spotify from Plex playback   -> stops playback, opens dummy UI, then plays audio
Spotify from YouTube mode    -> interrupts/closes YouTube mode, opens dummy UI, then plays audio
Spotify from TVBox desktop   -> opens dummy UI and plays audio almost immediately
F12/Home from Spotify mode   -> stops Spotify mode/audio and returns to Kodi
```

Known behavior:

```text
Starting Spotify from the desktop is fast.
Starting Spotify while Kodi/Plex/YouTube owns HDMI audio can have a short playback delay.
```

This delay is acceptable in the current stable setup.

Reason for delay:

```text
Kodi/Plex/YouTube may already own the HDMI ALSA device
-> Spotify Connect event arrives
-> TVBox closes/intercepts the active app
-> HDMI audio device becomes free
-> Raspotify/librespot recovers/reconnects
-> Spotify audio begins
```

---

## Current Confirmed Raspotify Config Values

Raspotify config file:

```bash
/etc/raspotify/conf
```

Confirmed important settings:

```bash
LIBRESPOT_BACKEND="alsa"
LIBRESPOT_CACHE="/home/tvbox/.cache/raspotify"
LIBRESPOT_DEVICE="sysdefault:CARD=vc4hdmi1"
LIBRESPOT_DEVICE_TYPE="tv"
LIBRESPOT_EMIT_SINK_EVENTS=
LIBRESPOT_NAME="TVBox Spotify"
LIBRESPOT_ONEVENT="/usr/local/bin/tvbox-spotify-event"
```

Verify current values:

```bash
sudo grep -nE 'LIBRESPOT_NAME|LIBRESPOT_BACKEND|LIBRESPOT_DEVICE|LIBRESPOT_DEVICE_TYPE|LIBRESPOT_ONEVENT|LIBRESPOT_EMIT_SINK_EVENTS|LIBRESPOT_CACHE' /etc/raspotify/conf
```

Restart Raspotify after editing:

```bash
sudo systemctl restart raspotify
```

---

## High-Level Architecture

Spotify mode has four major pieces:

```text
1. Raspotify/librespot system service
   -> provides Spotify Connect endpoint
   -> receives playback sessions from phone
   -> handles actual Spotify audio playback

2. Raspotify event hook
   -> receives playback/session events from librespot
   -> starts the visible Spotify mode user service

3. User-level Spotify mode service
   -> runs in the tvbox user session
   -> launches the fullscreen Chromium placeholder UI

4. TVBox Home/F12 integration
   -> stops Spotify mode
   -> restarts Raspotify to clear playback
   -> relaunches Kodi
```

Important design rule:

```text
Raspotify handles Spotify/audio.
The Chromium UI is only a visual TV mode indicator.
```

---

## Audio Path

Spotify uses ALSA direct to the same HDMI output used by the TVBox audio design:

```text
Raspotify/librespot -> ALSA -> vc4-hdmi-1 -> TV
```

Known working HDMI device:

```text
vc4-hdmi-1
card 1
MAI PCM
```

Observed compatible librespot devices:

```text
plughw:CARD=vc4hdmi1,DEV=0
sysdefault:CARD=vc4hdmi1
hdmi:CARD=vc4hdmi1,DEV=0
```

Current selected Raspotify device:

```bash
LIBRESPOT_DEVICE="sysdefault:CARD=vc4hdmi1"
```

Reason:

```text
plughw:CARD=vc4hdmi1,DEV=0 worked, but was more brittle during Kodi/Plex/YouTube audio handoff.
sysdefault:CARD=vc4hdmi1 is the current stable choice.
```

Check what librespot sees:

```bash
librespot -d ?
```

---

## Raspotify systemd Service

Raspotify service:

```bash
raspotify.service
```

Check status:

```bash
sudo systemctl status raspotify --no-pager
```

Check logs:

```bash
journalctl -u raspotify -n 100 --no-pager
```

Restart:

```bash
sudo systemctl restart raspotify
```

Recover after repeated crash/start-limit failure:

```bash
sudo systemctl stop raspotify
pkill -x librespot 2>/dev/null || true
sudo systemctl reset-failed raspotify
sudo systemctl restart avahi-daemon
sleep 2
sudo systemctl start raspotify
sudo systemctl status raspotify --no-pager
```

If the phone no longer sees `TVBox Spotify`, this recovery sequence is the first thing to try.

---

## Raspotify systemd Override

Override directory:

```bash
/etc/systemd/system/raspotify.service.d
```

Current override file:

```bash
/etc/systemd/system/raspotify.service.d/tvbox-user.conf
```

Verified current contents:

```ini
[Service]
User=tvbox
Group=tvbox

Environment=HOME=/home/tvbox
Environment=USER=tvbox
Environment=LOGNAME=tvbox
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=DISPLAY=:0

# Raspotify's default service sandbox is too tight for our TVBox event hook.
# The hook needs to access the tvbox desktop session and launch the visible Spotify UI.
ProtectHome=false
PrivateTmp=false
ReadWritePaths=/home/tvbox /run/user/1000 /tmp
```

Purpose:

```text
Run Raspotify as the tvbox user.
Expose the needed user environment.
Relax the default sandbox enough for the event hook/logging/user-service trigger to work.
```

Important:

```text
Do not hardcode WAYLAND_DISPLAY=wayland-1 here.
That value was wrong on this machine and caused Chromium to fail.
The active socket has been observed as wayland-0.
The Spotify foreground launcher now auto-detects the correct Wayland socket.
```

Verify active merged service configuration:

```bash
systemctl cat raspotify
```

Verify specific active properties:

```bash
systemctl show raspotify \
  -p User \
  -p Group \
  -p DynamicUser \
  -p ProtectHome \
  -p PrivateTmp \
  -p ReadWritePaths \
  -p Environment \
  -p ExecStart
```

Reload after editing override files:

```bash
sudo systemctl daemon-reload
sudo systemctl restart raspotify
```

---

## Raspotify Event Hook

Event hook path:

```bash
/usr/local/bin/tvbox-spotify-event
```

Configured by:

```bash
LIBRESPOT_ONEVENT="/usr/local/bin/tvbox-spotify-event"
```

Purpose:

```text
Receive librespot playback/session events.
Start the user-level Spotify mode service when Spotify activity begins.
Avoid direct GUI launching from the Raspotify system service.
Avoid duplicate launches during the burst of startup events.
```

The event hook starts:

```bash
systemctl --user start tvbox-spotify-mode.service
```

It must provide the tvbox user systemd bus environment:

```bash
XDG_RUNTIME_DIR=/run/user/1000
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
```

Accepted trigger events include:

```text
session_connected
session_client_changed
play_request_id_changed
loading
track_changed
playing
```

Ignored/non-launch events include:

```text
volume_changed
auto_play_changed
filter_explicit_content_changed
shuffle_changed
repeat_changed
sink
paused
```

Event hook log:

```bash
/home/tvbox/.cache/tvbox-spotify-event.log
```

Check it:

```bash
tail -n 160 /home/tvbox/.cache/tvbox-spotify-event.log
```

Expected successful trigger lines:

```text
Trigger event accepted: playing
Starting tvbox-spotify-mode.service through user systemd
systemctl --user start exit code: 0
```

---

## User-Level Spotify Mode Service

User service file:

```bash
/home/tvbox/.config/systemd/user/tvbox-spotify-mode.service
```

Expected current service:

```ini
[Unit]
Description=TVBox Spotify visible mode

[Service]
Type=simple
Environment=HOME=/home/tvbox
Environment=USER=tvbox
Environment=LOGNAME=tvbox
Environment=XDG_RUNTIME_DIR=/run/user/1000
ExecStart=/usr/local/bin/tvbox-spotify-mode-foreground
Restart=no
```

Purpose:

```text
Launch and supervise the visible fullscreen Spotify placeholder UI in the tvbox user's graphical session.
```

Important:

```text
This service must be Type=simple.
The foreground launcher must keep Chromium in the foreground.
Do not use Type=oneshot with Chromium backgrounded.
```

Reason:

```text
When Chromium was launched in the background from a oneshot service, systemd treated the service as finished and the UI did not reliably stay open.
```

Reload user services after editing:

```bash
systemctl --user daemon-reload
```

Start manually:

```bash
systemctl --user start tvbox-spotify-mode.service
```

Stop manually:

```bash
systemctl --user stop tvbox-spotify-mode.service
```

Check status:

```bash
systemctl --user status tvbox-spotify-mode.service --no-pager
```

Expected status while the dummy UI is open:

```text
Active: active (running)
Main PID: chromium
```

---

## Foreground Spotify Mode Launcher

Foreground launcher:

```bash
/usr/local/bin/tvbox-spotify-mode-foreground
```

Purpose:

```text
Prepare the TVBox for Spotify mode and launch the fullscreen placeholder UI.
```

Expected behavior:

```text
1. Set HOME/USER/LOGNAME/XDG_RUNTIME_DIR for tvbox.
2. Auto-detect the active Wayland socket.
3. Refuse to interrupt a real Moonlight session.
4. Stop Kodi/Plex playback if possible.
5. Kill Kodi quickly to release HDMI audio.
6. Stop YouTube mode if it is running.
7. Kick/recover Raspotify after the active app is closed.
8. Launch Chromium fullscreen/kiosk placeholder UI in the foreground.
```

Wayland detection:

```text
Do not hardcode wayland-1.
The observed active socket is:

/run/user/1000/wayland-0
```

Check the current socket:

```bash
ls -l /run/user/$(id -u tvbox)/wayland-* 2>/dev/null || echo "No wayland socket found"
```

Expected example:

```text
srwxrwxr-x ... /run/user/1000/wayland-0
-rw-rw---- ... /run/user/1000/wayland-0.lock
```

The script should set:

```bash
WAYLAND_DISPLAY=wayland-0
```

by auto-detecting the socket filename.

Chromium launches with:

```text
--ozone-platform=wayland
--user-data-dir=/home/tvbox/.config/chromium-tvbox-spotify-ui
--no-first-run
--disable-session-crashed-bubble
--password-store=basic
--start-fullscreen
--kiosk
--app=file:///home/tvbox/.local/share/tvbox/spotify.html
```

Important:

```text
Chromium is the foreground process of tvbox-spotify-mode.service.
Stopping the user service closes the dummy UI.
```

Launcher log:

```bash
/home/tvbox/.cache/tvbox-spotify-mode.log
```

Chromium UI log:

```bash
/home/tvbox/.cache/tvbox-spotify-ui.log
```

Check logs:

```bash
tail -n 160 /home/tvbox/.cache/tvbox-spotify-mode.log
tail -n 160 /home/tvbox/.cache/tvbox-spotify-ui.log
```

Harmless Chromium log noise may include:

```text
Registration response error message: DEPRECATED_ENDPOINT
ConnectionHandler failed with net error: -2
```

If the dummy UI opens and F12 works, those Chromium messages are not currently a problem.

---

## Spotify Placeholder Page

Placeholder page:

```bash
/home/tvbox/.local/share/tvbox/spotify.html
```

Purpose:

```text
Show a fullscreen Spotify screen while the phone controls playback.
```

This page does not authenticate with Spotify and does not play audio.

Actual Spotify audio is handled by:

```text
Raspotify/librespot
```

Safe edits:

```text
Changing the text, layout, logo, colors, or instructions is safe.
Do not expect spotify.html to control playback or audio.
```

---

## Stop Spotify Mode Script

Stop script:

```bash
/usr/local/bin/tvbox-stop-spotify
```

Purpose:

```text
Stop the visible Spotify UI service.
Kill leftover Spotify Chromium UI if needed.
Restart Raspotify to clear playback/audio state.
```

Expected behavior:

```text
F12/Home from Spotify mode
-> stop tvbox-spotify-mode.service
-> close Chromium dummy UI
-> restart Raspotify
-> return to Kodi through tvbox-home
```

The stop script should stop the user service through the tvbox user bus:

```bash
XDG_RUNTIME_DIR=/run/user/1000 \
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
systemctl --user stop tvbox-spotify-mode.service
```

It may also clean up with:

```bash
pkill -f "chromium.*chromium-tvbox-spotify-ui"
```

Restarting Raspotify here is intentional:

```text
It stops active Spotify playback and resets Spotify Connect/audio state.
```

Stop script stderr log:

```bash
/tmp/tvbox-stop-spotify.log
```

---

## sudoers Permissions

sudoers file:

```bash
/etc/sudoers.d/tvbox-spotify
```

Purpose:

```text
Allow the tvbox user/scripts to recover Raspotify without an interactive password.
```

Expected contents or equivalent:

```sudoers
raspotify ALL=(tvbox) NOPASSWD: /usr/local/bin/tvbox-spotify-mode
tvbox ALL=(root) NOPASSWD: /usr/bin/systemctl start raspotify
tvbox ALL=(root) NOPASSWD: /usr/bin/systemctl stop raspotify
tvbox ALL=(root) NOPASSWD: /usr/bin/systemctl restart raspotify
tvbox ALL=(root) NOPASSWD: /usr/bin/systemctl reset-failed raspotify
```

Validate after editing:

```bash
sudo visudo -cf /etc/sudoers.d/tvbox-spotify
```

Expected:

```text
/etc/sudoers.d/tvbox-spotify: parsed OK
```

Security note:

```text
These permissions are narrow and appliance-specific.
They are acceptable for the dedicated TVBox use case.
```

---

## F12/Home Integration

Global Home behavior is centralized in:

```bash
/usr/local/bin/tvbox-home
```

Expected Spotify branch near the top of `tvbox-home`:

```bash
# Spotify UI mode: stop Spotify playback and return to Kodi.
if pgrep -f "chromium.*chromium-tvbox-spotify-ui" >/dev/null 2>&1; then
  /usr/local/bin/tvbox-stop-spotify 2>/tmp/tvbox-stop-spotify.log || true
  sleep 1
  /usr/local/bin/tvbox-kodi
  exit 0
fi
```

Purpose:

```text
If Spotify dummy UI is open, F12/Home exits Spotify mode instead of trying to control Kodi.
```

Expected F12 behavior from Spotify mode:

```text
Stop Spotify audio
Close dummy UI
Restart Raspotify
Launch Kodi through /usr/local/bin/tvbox-kodi
Kodi startup service opens Favourites
```

---

## Kodi and YouTube Launcher Integration

Kodi launcher:

```bash
/usr/local/bin/tvbox-kodi
```

YouTube launcher:

```bash
/usr/local/bin/tvbox-youtube
```

Expected integration:

```text
Launching Kodi or YouTube should stop Spotify mode first.
```

Expected early line in both launchers or equivalent:

```bash
/usr/local/bin/tvbox-stop-spotify 2>/tmp/tvbox-stop-spotify.log || true
```

Reason:

```text
Spotify/Raspotify and Kodi/YouTube should not fight over the HDMI ALSA audio device.
Starting another TV app should end Spotify mode cleanly.
```

---

## Moonlight Protection

The Spotify foreground launcher should not interrupt a real Moonlight/game streaming session.

Correct process checks:

```bash
pgrep -x moonlight >/dev/null 2>&1
pgrep -x moonlight-qt >/dev/null 2>&1
```

Avoid broad checks like:

```bash
pgrep -fa 'moonlight|moonlight-qt'
```

Reason:

```text
Broad pgrep -f matching caused false-positive Moonlight detection during development.
Use exact process-name matching with pgrep -x.
```

---

## Manual Testing

### Test Raspotify visibility

```bash
sudo systemctl status raspotify --no-pager
```

Then check phone Spotify app:

```text
Spotify app -> device picker -> TVBox Spotify
```

### Test visible Spotify UI only

```bash
systemctl --user stop tvbox-spotify-mode.service 2>/dev/null || true
: > /home/tvbox/.cache/tvbox-spotify-mode.log
: > /home/tvbox/.cache/tvbox-spotify-ui.log 2>/dev/null || true
systemctl --user start tvbox-spotify-mode.service
sleep 3
systemctl --user status tvbox-spotify-mode.service --no-pager
tail -n 120 /home/tvbox/.cache/tvbox-spotify-mode.log
tail -n 120 /home/tvbox/.cache/tvbox-spotify-ui.log
```

Expected:

```text
Dummy UI opens
service is active/running
Main PID is chromium
```

Stop it:

```bash
systemctl --user stop tvbox-spotify-mode.service
```

### Test phone-triggered Spotify mode

From normal Kodi menu:

```text
Phone Spotify app -> select TVBox Spotify -> press play
```

Expected:

```text
Kodi closes
Dummy UI opens
Spotify audio plays
```

From Plex playback:

```text
Start Plex video playback
Phone Spotify app -> select TVBox Spotify -> press play
```

Expected:

```text
Plex playback stops
Kodi closes
Dummy UI opens
Spotify audio starts after a short delay
```

From YouTube mode:

```text
Start YouTube playback/mode
Phone Spotify app -> select TVBox Spotify -> press play
```

Expected:

```text
YouTube mode is interrupted/closed
Dummy UI opens
Spotify audio starts after a short delay
```

From desktop:

```text
Phone Spotify app -> select TVBox Spotify -> press play
```

Expected:

```text
Dummy UI opens
Spotify audio starts quickly
```

---

## Important Logs

Event hook log:

```bash
/home/tvbox/.cache/tvbox-spotify-event.log
```

Mode launcher log:

```bash
/home/tvbox/.cache/tvbox-spotify-mode.log
```

Chromium UI log:

```bash
/home/tvbox/.cache/tvbox-spotify-ui.log
```

Recovery log:

```bash
/home/tvbox/.cache/tvbox-spotify-recover.log
```

Stop script log:

```bash
/tmp/tvbox-stop-spotify.log
```

Combined debug command:

```bash
tail -n 160 /home/tvbox/.cache/tvbox-spotify-event.log
tail -n 160 /home/tvbox/.cache/tvbox-spotify-mode.log
tail -n 160 /home/tvbox/.cache/tvbox-spotify-ui.log
tail -n 160 /home/tvbox/.cache/tvbox-spotify-recover.log 2>/dev/null || true
systemctl --user status tvbox-spotify-mode.service --no-pager
journalctl -u raspotify -n 100 --no-pager
```

---

## Known Failure Modes

### Phone no longer shows TVBox Spotify

Likely cause:

```text
Raspotify crashed repeatedly and hit systemd start-limit, or Avahi/zeroconf still has a stale collision.
```

Logs may show:

```text
Start request repeated too quickly
Failed to start raspotify.service
zeroconf collision for name 'TVBox Spotify'
```

Recovery:

```bash
sudo systemctl stop raspotify
pkill -x librespot 2>/dev/null || true
sudo systemctl reset-failed raspotify
sudo systemctl restart avahi-daemon
sleep 2
sudo systemctl start raspotify
sudo systemctl status raspotify --no-pager
```

Wait 10-20 seconds, then check the Spotify device list again.

---

### Dummy UI opens but audio is delayed

Likely cause:

```text
Kodi/Plex/YouTube still had HDMI audio open when Spotify tried to begin playback.
```

Acceptable behavior:

```text
Current video stops
Dummy UI opens
Spotify audio starts after a short delay
```

Bad behavior:

```text
Raspotify disappears from the phone and does not return
```

If bad behavior occurs, recover Raspotify with the commands above.

---

### Event log shows Spotify events but dummy UI does not open

Check the event log:

```bash
tail -n 160 /home/tvbox/.cache/tvbox-spotify-event.log
```

Expected lines:

```text
Trigger event accepted: playing
Starting tvbox-spotify-mode.service through user systemd
systemctl --user start exit code: 0
```

If missing, inspect the event script:

```bash
cat /usr/local/bin/tvbox-spotify-event
```

---

### User service starts but Chromium does not open

Check Wayland and UI logs:

```bash
ls -l /run/user/$(id -u tvbox)/wayland-* 2>/dev/null || echo "No wayland socket found"
tail -n 160 /home/tvbox/.cache/tvbox-spotify-mode.log
tail -n 160 /home/tvbox/.cache/tvbox-spotify-ui.log
```

Known bad development error:

```text
Failed to connect to Wayland display: No such file or directory
WAYLAND_DISPLAY=wayland-1
```

Fix:

```text
Do not hardcode wayland-1.
Use auto-detection or set the current active socket, usually wayland-0.
```

---

## Current Design Rules

Maintain these rules when editing or extending Spotify mode:

```text
1. Raspotify/librespot handles Spotify Connect and audio playback.
2. The placeholder UI is visual only.
3. The event hook starts the user service; it does not launch Chromium directly.
4. The user service keeps Chromium in the foreground.
5. F12/Home stops Spotify mode through tvbox-stop-spotify.
6. Kodi, YouTube, and future external launchers should stop Spotify mode before taking over audio/video.
7. Do not hardcode WAYLAND_DISPLAY=wayland-1.
8. Detect Wayland from /run/user/1000/wayland-*.
9. Use pgrep -x for Moonlight protection, not broad pgrep -f matching.
10. A short Spotify startup delay from active video playback is acceptable.
11. Reliability after reboot matters more than shaving off every second of handoff delay.
```

---

## Stable State Summary

The TVBox Spotify mode is currently working after reboot with:

```text
Raspotify installed and visible as TVBox Spotify
Raspotify configured for ALSA HDMI output on sysdefault:CARD=vc4hdmi1
Raspotify event hook at /usr/local/bin/tvbox-spotify-event
Raspotify override at /etc/systemd/system/raspotify.service.d/tvbox-user.conf
User service at ~/.config/systemd/user/tvbox-spotify-mode.service
Foreground launcher at /usr/local/bin/tvbox-spotify-mode-foreground
Placeholder page at ~/.local/share/tvbox/spotify.html
Chromium profile at ~/.config/chromium-tvbox-spotify-ui
Stop script at /usr/local/bin/tvbox-stop-spotify
F12/Home integration through /usr/local/bin/tvbox-home
Kodi/YouTube launcher integration through tvbox-stop-spotify
```

Operating principle:

```text
Phone controls Spotify.
TVBox shows Spotify mode visually.
Raspotify plays audio.
F12/Home returns to Kodi.
```
# Spotify Documentation Append: Moonlight Interaction Update

---

## Moonlight Interaction

Spotify mode integrates with the TVBox Moonlight handoff system.

When Spotify playback starts while Moonlight is running, Spotify mode takes over the TVBox display locally without stopping the active Sunshine host app on Obtuse.

Expected behavior:

```text
Spotify playback starts while Moonlight is running.
TVBox disconnects the local Moonlight client.
TVBox does not send Sunshine undo.
Steam/Minecraft remains running and resumable on Obtuse.
tvbox-moonlight is prevented from relaunching Kodi.
Spotify dummy UI opens directly.
Spotify audio plays through Raspotify.
```

Relevant script:

```bash
/usr/local/bin/tvbox-spotify-mode-foreground
```

When `moonlight` or `moonlight-qt` is detected, the Spotify foreground launcher performs the following actions:

```text
1. If /usr/local/bin/tvbox-moonlight is active, write the Kodi-return suppression flag:
   /tmp/tvbox-suppress-kodi-return

2. Disconnect the local Moonlight client through:
   /usr/local/bin/tvbox-stop-moonlight

3. Continue into Spotify mode normally.
```

The suppression flag prevents this unwanted transition:

```text
Spotify starts
-> Moonlight disconnects
-> tvbox-moonlight relaunches Kodi
-> Spotify immediately closes Kodi
-> Spotify dummy UI opens
```

Expected successful log line:

```bash
/home/tvbox/.cache/tvbox-moonlight.log
```

```text
Kodi return suppressed by: spotify-takeover ...
```

### Non-Destructive vs. Destructive Moonlight Behavior

Spotify takeover uses the non-destructive Moonlight disconnect path.

Correct Spotify behavior:

```bash
/usr/local/bin/tvbox-stop-moonlight
```

This closes only the local Moonlight client on TVBox. It does not stop the remote Sunshine app. Steam or Minecraft remains running on Obtuse and can be resumed later.

Spotify mode must not use:

```bash
moonlight-qt quit
```

That command is reserved for destructive Moonlight Exit behavior because it stops the active Sunshine session and triggers the app's undo wrapper.

Dedicated destructive Moonlight Exit script:

```bash
/usr/local/bin/tvbox-quit-moonlight-session
```

### Verification

Start a Moonlight app, then start Spotify playback from a Spotify client.

Expected result:

```text
Moonlight closes locally.
Kodi does not flash open.
Spotify dummy UI opens.
Spotify audio plays.
Steam/Minecraft remains running on Obtuse.
```

Check logs:

```bash
tail -n 160 /home/tvbox/.cache/tvbox-moonlight.log
tail -n 120 /home/tvbox/.cache/tvbox-stop-moonlight.log
tail -n 160 /home/tvbox/.cache/tvbox-spotify-mode.log
```

Expected `tvbox-moonlight.log` indicator:

```text
Kodi return suppressed by: spotify-takeover ...
```

---

## Replace Older Moonlight Protection Wording

Any older Spotify documentation stating that Spotify should refuse to start when Moonlight is running is outdated.

Replace that behavior description with:

```text
Spotify mode may interrupt the local Moonlight client, but it must not stop the remote Sunshine app.
```

Correct behavior summary:

```text
Spotify takeover from Moonlight:
  disconnect local Moonlight client
  suppress Kodi return from tvbox-moonlight
  open Spotify dummy UI
  leave Steam/Minecraft running on Obtuse
```
