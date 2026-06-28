# TVBox Moonlight / Sunshine Integration

## 1. Scope

This document defines the current TVBox Moonlight/Sunshine integration and the relevant host-side configuration on Obtuse.

The integration provides three TVBox-facing Moonlight launch targets:

```text
Moonlight
Moonlight - Steam
Moonlight - Minecraft
```

The system is designed so Kodi remains the primary TVBox home environment while Moonlight can temporarily take over the display for game streaming.

---

## 2. System Roles

### 2.1 TVBox

```text
Hostname: tvbox
Platform: Raspberry Pi 5
Role: Kodi/Plex TV appliance and Moonlight client
Primary user: tvbox
Moonlight client: moonlight-qt
Moonlight version observed: 6.1.0-4
```

TVBox is responsible for:

```text
Kodi/Plex UI and playback
Moonlight client launch and local disconnect behavior
Global Home/F12 behavior
Spotify dummy UI takeover behavior
YouTube Chromium mode handoff behavior
Returning the user to Kodi after external apps exit
```

### 2.2 Obtuse

```text
Hostname: obtuse
Current LAN IP used by TVBox: 192.168.1.189
Role: Sunshine host / game-streaming server
GPU: NVIDIA GeForce RTX 2070 Super
Sunshine service type: user systemd service
Sunshine user: obtuse
```

Obtuse is responsible for:

```text
Sunshine GameStream host
Steam Big Picture launch and cleanup
Minecraft Launcher / Minecraft client launch and cleanup
NVENC video encoding
```

---

## 3. Functional Requirements

The integration must satisfy the following behavior:

```text
Kodi remains the default TVBox home interface.
Kodi launches Moonlight targets through Kodi Program add-ons.
Moonlight can stream Minecraft, Steam Big Picture, Desktop, or open the Moonlight GUI.
Home/F12 disconnects the local Moonlight client without stopping the host app.
A separate destructive Exit action can stop the Sunshine session and run the host app cleanup wrapper.
Spotify takeover disconnects local Moonlight without killing the Sunshine host app.
All normal Kodi launches go through /usr/local/bin/tvbox-kodi.
Kodi launch must be idempotent to prevent duplicate Kodi instances.
```

---

## 4. Network Requirements

### 4.1 Required Ethernet State

TVBox must negotiate gigabit Ethernet for reliable 1080p Moonlight streaming.

Required state:

```text
eth0 speed: 1000
eth0 duplex: full
```

Check on TVBox:

```bash
cat /sys/class/net/eth0/speed
cat /sys/class/net/eth0/duplex
ip -s link show eth0
ethtool eth0 | grep -A12 "Link partner advertised"
```

Expected output includes:

```text
1000
full
Link partner advertised link modes: ... 1000baseT/Full
```

### 4.2 Unsupported / Unhealthy Ethernet State

The following state is not acceptable for reliable 1080p Moonlight:

```text
eth0 speed: 100
eth0 duplex: full
RX dropped: increasing or high under stream load
```

A 100 Mbps link can appear functional for buffered media playback but still fail under low-latency Moonlight video transport. If 1080p Moonlight freezes, displays a black stream, or reports unrecoverable/network-dropped frames, verify Ethernet negotiation before changing Moonlight, Sunshine, or application wrapper logic.

### 4.3 Link Troubleshooting Procedure

If TVBox is not negotiating `1000 full`:

```text
1. Check the AP/router/switch port status.
2. Move TVBox to a known gigabit-capable port.
3. Test with a known-good short Cat 5e/Cat 6/Cat 6A cable.
4. Bypass intermediate network hardware for testing when possible.
5. Re-run ethtool and speed checks after each physical change.
```

Renegotiate the link:

```bash
sudo ethtool -r eth0
sleep 5
cat /sys/class/net/eth0/speed
cat /sys/class/net/eth0/duplex
```

Do not force gigabit manually with autonegotiation disabled as a permanent fix. Gigabit Ethernet normally requires autonegotiation.

---

## 5. Moonlight Client Settings

Recommended TVBox Moonlight settings:

```text
Resolution: 1080p
FPS: 60
Codec: HEVC
Bitrate: 20 Mbps
HDR: off
```

Reasonable bitrate ranges for 1080p60 HEVC:

```text
Conservative: 15 Mbps
Recommended: 20 Mbps
High quality: 25 Mbps
Usually unnecessary: 30+ Mbps
Do not use: extreme values such as 500 Mbps
```

A healthy 1080p60 HEVC stream should show approximately:

```text
Incoming frame rate: near 60 FPS
Decoding frame rate: near 60 FPS
Rendering frame rate: near 60 FPS
Frames dropped by network: 0.00%
Frames dropped due to jitter: 0.00%
Average network latency: near 1 ms on wired LAN
Average decoding time: comfortably below the frame budget
```

---

## 6. TVBox Scripts

### 6.1 Canonical Kodi Launcher

Path:

```bash
/usr/local/bin/tvbox-kodi
```

Purpose:

```text
Launch Kodi with the expected TVBox user/session environment.
Prevent duplicate Kodi launches.
Use ALSA audio backend.
Open Kodi Favourites if Kodi is already running.
```

Rules:

```text
All normal Kodi launches must call /usr/local/bin/tvbox-kodi.
Scripts should not call plain kodi or /usr/bin/kodi directly unless intentionally bypassing TVBox behavior.
```

Behavior:

```text
Sets HOME/USER/LOGNAME/XDG_RUNTIME_DIR/DISPLAY.
Auto-detects WAYLAND_DISPLAY from /run/user/1000/wayland-*.
Uses flock on /tmp/tvbox-kodi-launch.lock.
If kodi or kodi.bin already exists, sends ActivateWindow(FavouritesBrowser) and exits.
Otherwise execs /usr/bin/kodi --audio-backend=alsa.
```

Log:

```bash
/home/tvbox/.cache/tvbox-kodi.log
```

Verify:

```bash
bash -n /usr/local/bin/tvbox-kodi
pgrep -a kodi
pgrep -a kodi.bin
tail -n 80 /home/tvbox/.cache/tvbox-kodi.log
```

---

### 6.2 Global Home/F12 Handler

Path:

```bash
/usr/local/bin/tvbox-home
```

Purpose:

```text
Provide global Home/F12 behavior across Kodi, Moonlight, Spotify mode, YouTube mode, and idle desktop states.
```

Moonlight behavior:

```text
If Moonlight is running, disconnect local Moonlight only.
Do not send Sunshine undo.
If Moonlight was launched by tvbox-moonlight, let tvbox-moonlight return to Kodi.
If Moonlight was launched manually, return to Kodi from tvbox-home.
```

Required Moonlight branch:

```bash
if pgrep -x moonlight-qt >/dev/null 2>&1 || pgrep -x moonlight >/dev/null 2>&1; then
  /usr/local/bin/tvbox-stop-moonlight 2>/tmp/tvbox-stop-moonlight.log || true
  sleep 2

  if ! pgrep -f '/usr/local/bin/tvbox-moonlight' >/dev/null 2>&1; then
    /usr/local/bin/tvbox-kodi
  fi

  exit 0
fi
```

General expected behavior:

```text
Home/F12 from Kodi: open Favourites / stop playback as applicable.
Home/F12 from Moonlight: local disconnect only, then Kodi returns.
Home/F12 from Spotify mode: stop Spotify mode and return to Kodi.
Home/F12 from YouTube Chromium mode: close Chromium and return to Kodi.
Home/F12 when nothing relevant is running: launch Kodi.
```

---

### 6.3 Moonlight Wrapper

Path:

```bash
/usr/local/bin/tvbox-moonlight
```

Purpose:

```text
Coordinate Kodi-to-Moonlight handoff and Moonlight-to-Kodi return.
```

Supported targets:

```bash
/usr/local/bin/tvbox-moonlight moonlight
/usr/local/bin/tvbox-moonlight steam
/usr/local/bin/tvbox-moonlight minecraft
/usr/local/bin/tvbox-moonlight desktop
/usr/local/bin/tvbox-moonlight lowres
```

Target mapping:

```text
moonlight -> Moonlight GUI
steam     -> Sunshine app: Steam Big Picture
minecraft -> Sunshine app: Minecraft
desktop   -> Sunshine app: Desktop
lowres    -> Sunshine app: Low Res Desktop
```

Runtime files:

```text
Log: /home/tvbox/.cache/tvbox-moonlight.log
State directory: /tmp/tvbox-moonlight
Last target file: /tmp/tvbox-moonlight/last-target
Kodi return suppression flag: /tmp/tvbox-suppress-kodi-return
```

Startup behavior:

```text
Stops Spotify mode.
Stops Kodi playback.
Closes Kodi.
Closes YouTube Chromium mode if present.
Checks last direct Moonlight target.
If changing direct app targets, runs moonlight-qt quit first so the previous Sunshine app undo wrapper runs.
Launches the requested Moonlight target.
Waits for Moonlight to exit.
Returns to Kodi unless Kodi return is suppressed.
```

Kodi return suppression behavior:

```text
If /tmp/tvbox-suppress-kodi-return exists when Moonlight exits, tvbox-moonlight removes the flag and does not relaunch Kodi.
This is used by Spotify takeover.
```

---

### 6.4 Local Moonlight Disconnect

Path:

```bash
/usr/local/bin/tvbox-stop-moonlight
```

Purpose:

```text
Stop only the local Moonlight client on TVBox.
Leave the Sunshine host app/session resumable.
Do not run Sunshine undo.
```

Used by:

```text
Home/F12 Moonlight behavior
Spotify takeover from Moonlight
Manual non-destructive disconnects
```

Expected implementation behavior:

```text
TERM moonlight-qt/moonlight.
Wait briefly.
KILL only if Moonlight refuses to exit.
```

Log:

```bash
/home/tvbox/.cache/tvbox-stop-moonlight.log
```

---

### 6.5 Destructive Moonlight Session Quit

Path:

```bash
/usr/local/bin/tvbox-quit-moonlight-session
```

Purpose:

```text
Stop the active Sunshine session/app.
Trigger Sunshine undo wrapper.
Close the host app on Obtuse.
Return to Kodi.
```

Intended binding:

```text
Remote Exit button or other explicit destructive stop action.
```

Do not bind this script to Home/F12.

Expected core behavior:

```bash
moonlight-qt quit 192.168.1.189
```

Then close any remaining local Moonlight client and return to Kodi if not inside the normal Moonlight wrapper path.

Log:

```bash
/home/tvbox/.cache/tvbox-quit-moonlight-session.log
```

---

## 7. Kodi Moonlight Add-ons

Kodi Program add-ons provide the visible TV interface buttons.

### 7.1 Moonlight GUI

Directory:

```bash
/home/tvbox/.kodi/addons/plugin.program.tvbox.moonlight
```

Display name:

```text
Moonlight
```

Command:

```bash
/usr/local/bin/tvbox-moonlight moonlight
```

### 7.2 Steam

Directory:

```bash
/home/tvbox/.kodi/addons/plugin.program.tvbox.moonlight.steam
```

Display name:

```text
Moonlight - Steam
```

Command:

```bash
/usr/local/bin/tvbox-moonlight steam
```

### 7.3 Minecraft

Directory:

```bash
/home/tvbox/.kodi/addons/plugin.program.tvbox.moonlight.minecraft
```

Display name:

```text
Moonlight - Minecraft
```

Command:

```bash
/usr/local/bin/tvbox-moonlight minecraft
```

Expected Kodi location:

```text
Kodi -> Add-ons -> Program add-ons
```

These add-ons should be added to Kodi Favourites for normal remote-control use.

---

## 8. Spotify Interaction

Spotify mode is managed by the Raspotify event system and TVBox Spotify foreground launcher.

Relevant script:

```bash
/usr/local/bin/tvbox-spotify-mode-foreground
```

Required Moonlight behavior:

```text
If Moonlight is running, Spotify takeover must disconnect local Moonlight.
Spotify takeover must not send Sunshine undo.
Spotify takeover must prevent tvbox-moonlight from relaunching Kodi before the Spotify dummy UI opens.
```

Required suppression flow:

```text
1. Detect moonlight-qt or moonlight.
2. If /usr/local/bin/tvbox-moonlight is active, write /tmp/tvbox-suppress-kodi-return.
3. Run /usr/local/bin/tvbox-stop-moonlight.
4. Continue Spotify foreground mode.
```

Expected line in `tvbox-moonlight.log`:

```text
Kodi return suppressed by: spotify-takeover ...
```

Spotify return behavior:

```text
Home/F12 from Spotify mode stops Spotify mode, closes dummy UI, restarts/recovers Raspotify, and returns Kodi.
```

---

## 9. YouTube Interaction

YouTube Chromium mode remains separate from Moonlight.

Expected behavior:

```text
Launching YouTube closes Kodi and opens Chromium YouTube TV mode.
Home/F12 closes Chromium and returns to Kodi.
Spotify takeover should interrupt YouTube if Spotify starts.
```

Moonlight wrapper closes YouTube Chromium mode before launching Moonlight if a matching Chromium process is present.

---

# 10. Obtuse Sunshine Host Configuration

## 10.1 Sunshine Service

Sunshine runs as a user service:

```bash
systemctl --user status sunshine --no-pager
systemctl --user restart sunshine
journalctl --user -fu sunshine
```

Expected status:

```text
Active: active (running)
```

Sunshine web UI:

```text
https://192.168.1.189:47990
```

Sunshine must run in the `obtuse` user session so it can access the graphical display and GPU encode path.

---

## 10.2 Sunshine App Config

Config file:

```bash
/home/obtuse/.config/sunshine/apps.json
```

Inspect relevant app entries:

```bash
python3 - <<'EOF'
import json
p="/home/obtuse/.config/sunshine/apps.json"
data=json.load(open(p))
for app in data.get("apps", []):
    if app.get("name") in ("Minecraft", "Steam Big Picture"):
        print("\n---", app.get("name"), "---")
        print(json.dumps(app, indent=2))
EOF
```

Custom app model:

```text
cmd: empty
detached: launch wrapper
prep-cmd undo: stop wrapper
auto-detach: true
wait-all: false
exit-timeout: 10
```

This model allows apps to remain running/resumable after a local TVBox disconnect while still giving Sunshine a controlled cleanup command when the user stops the app or launches a different app.

Do not use long-lived launch wrappers for the current design.

---

## 10.3 Minecraft Sunshine Entry

Expected important fields:

```json
{
  "name": "Minecraft",
  "cmd": [],
  "detached": [
    "/home/obtuse/bin/launch-minecraft-tv.sh"
  ],
  "prep-cmd": [
    {
      "do": "",
      "undo": "/home/obtuse/bin/stop-minecraft-tv.sh"
    }
  ],
  "auto-detach": true,
  "wait-all": false,
  "exit-timeout": 10,
  "output": ""
}
```

Additional Sunshine-managed fields may exist. The fields above define the required behavior.

---

## 10.4 Steam Big Picture Sunshine Entry

Expected important fields:

```json
{
  "name": "Steam Big Picture",
  "cmd": [],
  "detached": [
    "/home/obtuse/bin/launch-steam-tv.sh"
  ],
  "prep-cmd": [
    {
      "do": "",
      "undo": "/home/obtuse/bin/stop-steam-tv.sh"
    }
  ],
  "auto-detach": true,
  "wait-all": false,
  "exit-timeout": 10,
  "output": "",
  "image-path": "steam.png"
}
```

Do not use this older brittle undo command:

```bash
setsid steam steam://close/bigpicture
```

Steam shutdown is handled by `/home/obtuse/bin/stop-steam-tv.sh`.

---

## 11. Obtuse Wrapper Scripts

### 11.1 Minecraft Launch Wrapper

Path:

```bash
/home/obtuse/bin/launch-minecraft-tv.sh
```

Purpose:

```text
Focus the Minecraft game window if present.
Otherwise focus the Minecraft Launcher if present.
Otherwise start /usr/bin/minecraft-launcher and focus/maximize the resulting window.
Exit quickly.
```

Required environment:

```bash
DISPLAY=:0
XDG_RUNTIME_DIR=/run/user/1000
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
```

Window management:

```bash
wmctrl -lx
wmctrl -ir <window> -t <desktop>
wmctrl -ir <window> -b remove,hidden
wmctrl -ir <window> -b add,maximized_vert,maximized_horz
wmctrl -ia <window>
```

Log:

```bash
/home/obtuse/logs/minecraft-tv/launch-minecraft-tv.log
```

---

### 11.2 Minecraft Stop Wrapper

Path:

```bash
/home/obtuse/bin/stop-minecraft-tv.sh
```

Purpose:

```text
Close visible Minecraft windows.
Stop Minecraft Launcher.
Stop the Java Minecraft client.
Escalate only if needed.
Return success even if Minecraft is already stopped.
```

Current Java client pattern:

```text
net.minecraft.client.main.Main
```

If Minecraft does not stop correctly after a launcher/game update, inspect current process names:

```bash
pgrep -af 'java|minecraft|net.minecraft'
```

Log:

```bash
/home/obtuse/logs/minecraft-tv/stop-minecraft-tv.log
```

---

### 11.3 Steam Launch Wrapper

Path:

```bash
/home/obtuse/bin/launch-steam-tv.sh
```

Purpose:

```text
Launch Steam in Gamepad UI / Big Picture mode.
Exit quickly.
```

Steam install type:

```text
Snap
```

Expected Steam executable:

```bash
/snap/bin/steam
```

Expected launch command:

```bash
/snap/bin/steam steam://open/gamepadui
```

Log:

```bash
/home/obtuse/logs/steam-tv/launch-steam-tv.log
```

If Steam launches in desktop mode instead of Gamepad UI, test:

```bash
DISPLAY=:0 \
XDG_RUNTIME_DIR=/run/user/1000 \
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
/snap/bin/steam -tenfoot
```

Only change the wrapper to `-tenfoot` if that proves more reliable.

---

### 11.4 Steam Stop Wrapper

Path:

```bash
/home/obtuse/bin/stop-steam-tv.sh
```

Purpose:

```text
Exit successfully if Steam is already stopped.
Try clean Steam shutdown.
Wait for clean exit.
TERM Steam and steamwebhelper if needed.
KILL fallback only if needed.
```

Expected clean command:

```bash
/snap/bin/steam -shutdown
```

Log:

```bash
/home/obtuse/logs/steam-tv/stop-steam-tv.log
```

---

# 12. Operational Workflows

## 12.1 Minecraft from Kodi

```text
Kodi Favourites -> Moonlight - Minecraft
```

Expected:

```text
Kodi closes.
Moonlight streams the Minecraft Sunshine target.
Minecraft Launcher or game appears.
Home/F12 disconnects local Moonlight and returns Kodi.
Minecraft remains running/resumable on Obtuse.
Exit/Stop closes Minecraft through Sunshine undo.
```

## 12.2 Steam from Kodi

```text
Kodi Favourites -> Moonlight - Steam
```

Expected:

```text
Kodi closes.
Moonlight streams the Steam Big Picture Sunshine target.
Steam Big Picture appears.
Home/F12 disconnects local Moonlight and returns Kodi.
Steam remains running/resumable on Obtuse.
Exit/Stop closes Steam through Sunshine undo.
```

## 12.3 Generic Moonlight GUI from Kodi

```text
Kodi Favourites -> Moonlight
```

Expected:

```text
Kodi closes.
Moonlight GUI opens.
User can manually use Play/Stop in Moonlight.
Closing Moonlight GUI returns Kodi.
```

## 12.4 Direct App Switching

When `tvbox-moonlight` launches a different direct app target than the previous direct app target:

```text
moonlight-qt quit 192.168.1.189 runs first.
Sunshine stops the old app/session.
Sunshine runs the old app undo wrapper.
The new Sunshine app launches.
```

Example:

```text
Minecraft target -> Steam target
stop-minecraft-tv.sh runs
launch-steam-tv.sh runs
```

## 12.5 Spotify During Moonlight

Expected:

```text
Spotify starts.
TVBox detects Moonlight.
TVBox writes Kodi-return suppression flag.
TVBox disconnects local Moonlight.
Host app remains running on Obtuse.
Spotify dummy UI opens.
Kodi does not flash open between Moonlight and Spotify.
```

---

# 13. Testing Procedures

## 13.1 Syntax Test

TVBox:

```bash
bash -n /usr/local/bin/tvbox-kodi
bash -n /usr/local/bin/tvbox-home
bash -n /usr/local/bin/tvbox-moonlight
bash -n /usr/local/bin/tvbox-stop-moonlight
bash -n /usr/local/bin/tvbox-quit-moonlight-session
bash -n /usr/local/bin/tvbox-spotify-mode-foreground
bash -n /usr/local/bin/tvbox-youtube
```

Obtuse:

```bash
bash -n /home/obtuse/bin/launch-minecraft-tv.sh
bash -n /home/obtuse/bin/stop-minecraft-tv.sh
bash -n /home/obtuse/bin/launch-steam-tv.sh
bash -n /home/obtuse/bin/stop-steam-tv.sh
```

## 13.2 Kodi Idempotency Test

TVBox:

```bash
pkill -TERM -x kodi 2>/dev/null || true
pkill -TERM -x kodi.bin 2>/dev/null || true
sleep 3

/usr/local/bin/tvbox-kodi &
sleep 5
/usr/local/bin/tvbox-kodi &
sleep 3

pgrep -a kodi
pgrep -a kodi.bin
tail -n 80 /home/tvbox/.cache/tvbox-kodi.log
```

Expected:

```text
Only one Kodi process tree exists.
Second launch logs that Kodi is already running.
```

## 13.3 Home/F12 from Moonlight

Start:

```bash
/usr/local/bin/tvbox-moonlight minecraft
```

Press Home/F12.

Expected:

```text
Moonlight exits locally.
Kodi returns once.
Minecraft remains running/resumable on Obtuse.
No Minecraft stop wrapper invocation occurs.
```

## 13.4 Destructive Exit from Moonlight

Start:

```bash
/usr/local/bin/tvbox-moonlight minecraft
```

From another TVBox SSH session:

```bash
/usr/local/bin/tvbox-quit-moonlight-session
```

Expected:

```text
Moonlight exits locally.
Kodi returns.
Sunshine undo runs.
Minecraft closes on Obtuse.
```

Repeat equivalent test for Steam.

## 13.5 Spotify Takeover from Moonlight

Start:

```bash
/usr/local/bin/tvbox-moonlight minecraft
```

Start Spotify playback to TVBox from a Spotify client.

Expected:

```text
Moonlight disconnects locally.
Kodi does not relaunch before Spotify UI.
Spotify dummy UI opens.
Minecraft remains running/resumable on Obtuse.
```

Check:

```bash
tail -n 160 /home/tvbox/.cache/tvbox-moonlight.log
```

Expected:

```text
Kodi return suppressed by: spotify-takeover ...
```

---

# 14. Troubleshooting

## 14.1 1080p Stream Freezes or Goes Black

Check TVBox Ethernet first:

```bash
cat /sys/class/net/eth0/speed
cat /sys/class/net/eth0/duplex
ip -s link show eth0
ethtool eth0 | grep -A12 "Link partner advertised"
```

If the link is `100 full`, fix the physical network path before changing Moonlight settings.

Symptoms associated with bad or downgraded link negotiation:

```text
1080p stream starts, then freezes.
Input continues to affect the host.
PiKVM or host monitor shows the game still running.
Moonlight logs show unrecoverable frames or network dropped frames.
```

## 14.2 App Does Not Launch

On Obtuse:

```bash
journalctl --user -u sunshine -b -n 220 --no-pager | grep -Ei 'Minecraft|Steam|Executing|Spawning|Undo|CLIENT|DISCONNECTED|error|warn'
```

Expected for custom apps:

```text
Spawning [/home/obtuse/bin/launch-minecraft-tv.sh]
```

or:

```text
Spawning [/home/obtuse/bin/launch-steam-tv.sh]
```

If no `Spawning` line appears, Sunshine did not run the wrapper.

## 14.3 Minecraft Does Not Stop

On Obtuse:

```bash
pgrep -af 'java|minecraft|net.minecraft'
```

Update `/home/obtuse/bin/stop-minecraft-tv.sh` if the Java client command line no longer matches the configured stop pattern.

## 14.4 Steam Does Not Stop

On Obtuse:

```bash
tail -n 120 /home/obtuse/logs/steam-tv/stop-steam-tv.log
pgrep -af 'steam|steamwebhelper' || true
```

If Steam processes remain after clean shutdown and TERM, verify Snap Steam path:

```bash
ls -l /snap/bin/steam
snap list | grep -i steam
```

## 14.5 Duplicate Kodi

Check:

```bash
pgrep -a kodi
pgrep -a kodi.bin
tail -n 120 /home/tvbox/.cache/tvbox-kodi.log
```

Search for direct Kodi calls:

```bash
grep -RniE '(^|[^a-zA-Z0-9_/])kodi($|[^a-zA-Z0-9_.-])|/usr/bin/kodi|tvbox-kodi' \
  /usr/local/bin ~/.config/autostart ~/.kodi/addons 2>/dev/null
```

Normal scripts should use `/usr/local/bin/tvbox-kodi`.

## 14.6 Spotify Opens Kodi Before Spotify UI

Check suppression behavior:

```bash
tail -n 160 /home/tvbox/.cache/tvbox-moonlight.log
```

Expected:

```text
Kodi return suppressed by: spotify-takeover ...
```

If missing, inspect the Moonlight block in:

```bash
/usr/local/bin/tvbox-spotify-mode-foreground
```

---

# 15. Log Reference

## 15.1 TVBox Logs

```bash
tail -n 160 /home/tvbox/.cache/tvbox-kodi.log
tail -n 160 /home/tvbox/.cache/tvbox-moonlight.log
tail -n 120 /home/tvbox/.cache/tvbox-stop-moonlight.log
tail -n 120 /home/tvbox/.cache/tvbox-quit-moonlight-session.log
tail -n 160 /home/tvbox/.cache/tvbox-spotify-event.log 2>/dev/null || true
tail -n 160 /home/tvbox/.cache/tvbox-spotify-mode.log 2>/dev/null || true
tail -n 160 /home/tvbox/.cache/tvbox-spotify-ui.log 2>/dev/null || true
tail -n 120 /tmp/tvbox-stop-spotify.log 2>/dev/null || true
```

## 15.2 Obtuse Logs

```bash
journalctl --user -u sunshine -b -n 220 --no-pager | grep -Ei 'Minecraft|Steam|Executing|Spawning|Undo|CLIENT|DISCONNECTED|error|warn'
tail -n 120 /home/obtuse/logs/minecraft-tv/launch-minecraft-tv.log
tail -n 120 /home/obtuse/logs/minecraft-tv/stop-minecraft-tv.log
tail -n 120 /home/obtuse/logs/steam-tv/launch-steam-tv.log
tail -n 120 /home/obtuse/logs/steam-tv/stop-steam-tv.log
```

## 15.3 Process and Window Checks

TVBox:

```bash
pgrep -a kodi || true
pgrep -a kodi.bin || true
pgrep -a moonlight-qt || true
pgrep -af 'chromium.*chromium-tvbox' || true
```

Obtuse:

```bash
DISPLAY=:0 wmctrl -lx | grep -Ei 'minecraft|steam' || true
pgrep -af 'minecraft-launcher|net.minecraft.client.main.Main|steam|steamwebhelper' || true
```

---

# 16. Maintenance Rules

1. Use `/usr/local/bin/tvbox-kodi` for normal Kodi launches.

2. Home/F12 must not run `moonlight-qt quit`.

3. Destructive Exit may run `/usr/local/bin/tvbox-quit-moonlight-session`.

4. Spotify takeover must use local Moonlight disconnect, not destructive Sunshine quit.

5. Sunshine Minecraft and Steam entries must use detached launch wrappers plus undo stop wrappers.

6. Do not reintroduce the old Steam Big Picture undo command:

```bash
setsid steam steam://close/bigpicture
```

7. If 1080p streaming fails, verify Ethernet speed and drops first.

8. Keep the desktop/labwc session as the standard TVBox operating mode.

9. Do not use a restart-always Kodi service. External app handoff intentionally closes and relaunches Kodi.

10. Before editing scripts, make timestamped backups:

```bash
sudo cp /path/to/script /path/to/script.bak.$(date +%Y%m%d-%H%M%S)
```

---

# 17. Known Good State

```text
TVBox Ethernet negotiates 1000 full.
Moonlight 1080p60 HEVC works at practical bitrates around 20 Mbps.
Kodi launches through idempotent tvbox-kodi.
Kodi Program add-ons launch Moonlight GUI, Steam, and Minecraft.
Home/F12 disconnects Moonlight locally and returns Kodi.
Destructive Exit can stop Sunshine session and run undo wrappers.
Spotify takeover from Moonlight suppresses Kodi return and opens Spotify UI directly.
Obtuse Sunshine custom apps use detached launch wrappers and undo stop wrappers.
Steam and Minecraft remain resumable after local TVBox disconnect.
Steam and Minecraft close when Sunshine Stop/Exit behavior runs undo wrappers.
```
-2