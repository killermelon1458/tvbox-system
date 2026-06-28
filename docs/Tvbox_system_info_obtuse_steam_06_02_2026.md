TVBox / Obtuse Integration Amendment — Steam Link, Debian Steam, and TVBox Control Updates

Date

2026-05-31

Purpose

This amendment records the current TVBox-relevant changes made on Obtuse and the related TVBox-side control changes. It supersedes older documentation that refers to Snap Steam, "/snap/bin/steam", or Steam game storage under the Snap Steam directory.

This amendment is not a full recap. It documents the current operating state and the specific old assumptions that are no longer valid.

---

1. Obtuse Steam Installation Changed

Steam on Obtuse is no longer Snap Steam.

Current Steam launcher:

/usr/games/steam

Current Steam runtime/profile path:

/home/obtuse/.steam/debian-installation

Expected running Steam processes should include paths under:

/home/obtuse/.steam/debian-installation

Snap Steam was removed:

sudo snap remove steam --purge

Old Snap Steam paths are no longer active:

/snap/bin/steam
/home/obtuse/snap/steam

Older documentation that states Steam is installed through Snap or should be launched with "/snap/bin/steam" is outdated.

Operational rule:

Do not use Snap Steam for Steam Link / Remote Play on Obtuse.
Use Debian/apt Steam through /usr/games/steam.

---

2. Reason for Steam Migration

Steam Link from TVBox was failing because Snap Steam on Obtuse crashed during Remote Play video capture.

Observed failure pattern:

TVBox Steam Link connected to Obtuse.
Remote Play session began.
Audio/input initialized.
No usable video frames arrived at TVBox.
TVBox Steam Link timed out with 100% frame loss.
Host Steam crashed and restarted.

Host crash signature:

PipeWire: Initializing streaming
can't make support.system handle: No such file or directory
Segmentation fault (core dumped)

After installing and using Debian/apt Steam, Steam Link streaming worked.

---

3. Steam Link Pairing Changed

Because Debian Steam is a separate Steam installation/profile from Snap Steam, TVBox Steam Link had to be paired again with Steam on Obtuse.

Expected behavior after Steam reinstall or migration:

Steam Link may show Obtuse as offline.
Re-pair/link Steam Link with Steam on Obtuse.
After pairing, Steam Link should connect normally.

This is expected and should not be treated as a TVBox network failure by itself.

---

4. Obtuse Steam Autostart Updated

Obtuse still starts Steam automatically for Steam Link / Remote Play availability.

Autostart desktop entry:

/home/obtuse/.config/autostart/steam-background.desktop

Startup wrapper:

/home/obtuse/bin/start-steam-background.sh

The wrapper now explicitly uses Debian Steam:

STEAM_BIN="/usr/games/steam"

Expected launch behavior:

/usr/games/steam -silent

Old behavior using Snap Steam or "command -v steam" is no longer preferred.

Verification:

grep -nE 'snap|/usr/games/steam|command -v steam|STEAM_BIN' /home/obtuse/bin/start-steam-background.sh
pgrep -af 'steam|steamwebhelper|steam_monitor' | head -80
pgrep -af 'snap/steam|/snap/bin/steam' || echo "No Snap Steam processes"

Expected:

/usr/games/steam is present.
No /snap/bin/steam reference.
No Snap Steam processes.
Running Steam paths are under /home/obtuse/.steam/debian-installation.

---

5. Obtuse Sunshine Steam Wrappers Updated

The Sunshine Steam Big Picture app now uses Debian Steam.

Launch wrapper:

/home/obtuse/bin/launch-steam-tv.sh

Stop wrapper:

/home/obtuse/bin/stop-steam-tv.sh

Both wrappers should use:

STEAM="/usr/games/steam"

Expected launch command:

/usr/games/steam steam://open/gamepadui

Expected stop command:

/usr/games/steam -shutdown

Old Snap-based commands are outdated:

/snap/bin/steam steam://open/gamepadui
/snap/bin/steam -shutdown

Verification:

grep -nE 'snap|/usr/games/steam|STEAM=|gamepad|shutdown' \
  /home/obtuse/bin/launch-steam-tv.sh \
  /home/obtuse/bin/stop-steam-tv.sh

Expected:

/usr/games/steam present.
No /snap/bin/steam references.

---

6. Active Steam Game Library Moved to NVMe SSD

Steam games are now stored on the NVMe SSD under a dedicated Steam library folder.

Active Steam library:

/mnt/docker/steam-library

Convenience symlink:

/home/obtuse/SteamLibrary-ssd -> /mnt/docker/steam-library

Steam library structure:

/mnt/docker/steam-library/steamapps
/mnt/docker/steam-library/steamapps/common
/mnt/docker/steam-library/steamapps/appmanifest_*.acf

The Steam GUI should use the symlink path when adding the library:

/home/obtuse/SteamLibrary-ssd

Reason:

The Steam file picker may not conveniently browse /mnt/docker directly.

---

7. "/mnt/docker" Safety Rule Still Applies

"/mnt/docker" is still Docker’s data root and also contains other service data.

Important rule:

Do not recursively chown, chmod, delete, move, or broadly modify /mnt/docker.

Steam was added as a service-specific sibling directory only:

/mnt/docker/steam-library

Do not touch these paths during Steam maintenance:

/mnt/docker/containers
/mnt/docker/overlay2
/mnt/docker/volumes
/mnt/docker/image
/mnt/docker/network
/mnt/docker/buildkit
/mnt/docker/plex
/mnt/docker/portainer
/mnt/docker/cloudflared
/mnt/docker/libvirt

The virt-manager/libvirt pool exists separately under:

/mnt/docker/libvirt

Steam maintenance must not modify "/mnt/docker/libvirt".

---

8. Copied Snap Runtime / Compatibility Tools Were Removed

During migration, actual game folders and game manifests were copied from the old Snap Steam library to the SSD Steam library.

Copied Snap-era Steam runtime and Proton compatibility-tool state was removed because it caused compatibility-tool failures under Debian Steam.

Removed runtime/tool manifests included:

Steam Linux Runtime 1.0
Steam Linux Runtime 2.0
Steam Linux Runtime 3.0
Steam Linux Runtime 4.0
Proton Experimental
Proton Hotfix
Proton EasyAntiCheat Runtime
Steamworks Common Redistributables

Removed copied runtime/tool folders included:

SteamLinuxRuntime
SteamLinuxRuntime_soldier
SteamLinuxRuntime_sniper
SteamLinuxRuntime_4
Proton - Experimental
Proton Hotfix
Proton EasyAntiCheat Runtime
Steamworks Shared
Steam Controller Configs
Steam.dll

Reason:

Copied Snap-era runtime/tool state contained broken or Snap-specific symlink/runtime data.
Debian Steam should redownload Proton, Steam Linux Runtime, and redistributables cleanly.

After cleanup, launching PICO PARK caused Debian Steam to install the needed compatibility/runtime components again, and the game worked.

---

9. Current Games Discovered in Debian Steam Library

The active SSD Steam library retained the actual game manifests and game data.

Expected game manifests:

11020   TrackMania Nations Forever
1509960 PICO PARK
905340  Heave Ho
976730  Halo: The Master Chief Collection

Expected folders:

/mnt/docker/steam-library/steamapps/common/TrackMania Nations Forever
/mnt/docker/steam-library/steamapps/common/PICO_PARK_ONLINE
/mnt/docker/steam-library/steamapps/common/Heave Ho
/mnt/docker/steam-library/steamapps/common/Halo The Master Chief Collection

Verification:

cd /mnt/docker/steam-library/steamapps

for f in appmanifest_*.acf; do
  echo "=== $f ==="
  grep -E '"appid"|"name"|"installdir"' "$f"
done

---

10. TVBox Steam Link Integration State

TVBox now has Steam Link integrated into "tvboxctl".

Current Steam Link binary on TVBox:

/usr/bin/steamlink

"tvboxctl status" reports Steam Link state and configured path.

Expected status fields include:

steamlink-running: yes/no
steamlink-bin:     /usr/bin/steamlink

TVBox Steam Link lifecycle policy:

Launching Steam Link closes/conflicts with other local TVBox apps as needed.
Steam Link is treated as a local streaming client.
Home/F12 closes the local Steam Link client/stream and returns to Kodi.
Steam Link does not remain preserved behind Kodi.

Current preservation policy:

MAX_PRESERVED_APPS=0

The live config and repo example should both use:

MAX_PRESERVED_APPS=0

Relevant config paths:

/etc/tvboxctl.conf
/opt/tvbox-system/config/tvboxctl.conf.example

Verification:

grep -n 'MAX_PRESERVED_APPS' /etc/tvboxctl.conf
grep -n 'MAX_PRESERVED_APPS' /opt/tvbox-system/config/tvboxctl.conf.example
tvboxctl status

Expected:

MAX_PRESERVED_APPS=0

---

11. TVBox Steam Link Window Detection Updated

Steam Link window detection must handle multiple observed local window states.

Observed Steam Link windows include:

shell: SteamLink
shell: Streaming Client
shell: <game title> [Streaming]

"tvboxctl" should treat all of these as Steam Link.

The "Streaming Client" window state was observed during Steam Link failure/retry behavior and must remain included in detection/cleanup logic.

Operational rule:

Do not broad-kill unrelated shell windows.
Only close shell windows when the window list confirms they are Steam Link / Streaming Client / [Streaming] windows.

---

12. TVBox labwc Global F12 / Home Config Is Repo-Managed

The global F12/Home keybind is now managed from the TVBox system repo because GUI settings tools can rewrite labwc config and remove custom keybinds.

Canonical repo config:

/opt/tvbox-system/config/labwc/rc.xml

Live config:

/home/tvbox/.config/labwc/rc.xml

Restore script:

/usr/local/bin/tvbox-restore-labwc-config

Source path:

/opt/tvbox-system/bin/tvbox-restore-labwc-config

Required global binding:

<keybind key="F12">
  <action name="Execute" command="/usr/local/bin/tvbox-home" />
</keybind>

Expected repair flow:

/usr/local/bin/tvbox-restore-labwc-config
sudo reboot

Important behavior:

F12/Home must work globally from Kodi, Steam Link, Moonlight, Spotify mode, YouTube/Chromium apps, Firefox, terminal, and desktop.
Kodi-local F12 fallback is not enough.

Verification:

grep -n -A8 -B2 -E 'keyboard|F12|tvbox-home|pointerSpeed' ~/.config/labwc/rc.xml
tail -n 40 /home/tvbox/.cache/tvboxctl.log

A successful global F12 press outside Kodi should create a fresh "tvboxctl" log line similar to:

home requested; context=...

---

13. TVBox Repository State

TVBox control files are backed by the Git repo:

/opt/tvbox-system

Current important repo-backed pieces include:

/opt/tvbox-system/bin/tvboxctl
/opt/tvbox-system/bin/tvbox-restore-labwc-config
/opt/tvbox-system/config/tvboxctl.conf.example
/opt/tvbox-system/config/labwc/rc.xml
/opt/tvbox-system/config/labwc/README.md

Live path expectations:

/usr/local/bin/tvboxctl -> /opt/tvbox-system/bin/tvboxctl
/usr/local/bin/tvbox-restore-labwc-config -> /opt/tvbox-system/bin/tvbox-restore-labwc-config

Verification:

ls -l /usr/local/bin/tvboxctl
readlink -f /usr/local/bin/tvboxctl

ls -l /usr/local/bin/tvbox-restore-labwc-config
readlink -f /usr/local/bin/tvbox-restore-labwc-config

cd /opt/tvbox-system
git status --short

---

14. Current Working User-Facing Behavior

Current expected working state:

TVBox -> Steam Link -> connects to Debian Steam on Obtuse.
Steam Link streams video correctly after pairing with the Debian Steam instance.
PICO PARK appears in Debian Steam from /mnt/docker/steam-library.
PICO PARK launches after Debian Steam installs clean compatibility/runtime components.
Moonlight -> Steam Big Picture launches Debian Steam through Sunshine wrapper.
Home/F12 from Steam Link closes the local Steam Link client/stream and returns Kodi.
Home/F12 from Moonlight soft-disconnects local Moonlight and returns Kodi.

Steam Link is currently preferred for games where it handles more controllers better, such as PICO PARK.

Moonlight/Sunshine remains useful for other streaming targets and as a separate tested streaming path.

---

15. Post-Reboot / Post-Maintenance Checks

On Obtuse:

which -a steam
ls -l /usr/games/steam /snap/bin/steam 2>/dev/null || true

pgrep -af 'steam|steamwebhelper|steam_monitor' | head -80
pgrep -af 'snap/steam|/snap/bin/steam' || echo "No Snap Steam processes"

grep -nE 'snap|/usr/games/steam|command -v steam|STEAM_BIN|STEAM=' \
  /home/obtuse/bin/start-steam-background.sh \
  /home/obtuse/bin/launch-steam-tv.sh \
  /home/obtuse/bin/stop-steam-tv.sh

df -h / /mnt/docker
ls -ld /mnt/docker/steam-library /home/obtuse/SteamLibrary-ssd

On TVBox:

tvboxctl status
grep -n 'MAX_PRESERVED_APPS' /etc/tvboxctl.conf
grep -n 'MAX_PRESERVED_APPS' /opt/tvbox-system/config/tvboxctl.conf.example
wlrctl window list
grep -n -A8 -B2 -E 'keyboard|F12|tvbox-home|pointerSpeed' ~/.config/labwc/rc.xml

Expected healthy state:

Obtuse uses /usr/games/steam.
No Snap Steam processes exist.
Obtuse Steam processes run from /home/obtuse/.steam/debian-installation.
Sunshine Steam wrappers use /usr/games/steam.
Steam library exists at /mnt/docker/steam-library.
TVBox tvboxctl reports MAX_PRESERVED_APPS=0.
TVBox global F12/Home binding exists in labwc config.

---

16. Superseded Statements

Any older documentation containing the following should be considered outdated:

Steam install type: Snap
Steam executable: /snap/bin/steam
Steam launch command: /snap/bin/steam steam://open/gamepadui
Steam stop command: /snap/bin/steam -shutdown
Steam games live under /home/obtuse/snap/steam
Steam Link failure is likely a TVBox launch/wrapper issue
Steam Link host is valid without re-pairing after Steam migration
MAX_PRESERVED_APPS=1
F12/Home is only a Kodi-local keymap
labwc live config is safe to edit only through GUI tools

Current replacement assumptions:

Steam install type: Debian/apt Steam
Steam executable: /usr/games/steam
Steam runtime/profile: /home/obtuse/.steam/debian-installation
Steam game library: /mnt/docker/steam-library
Steam Link must be paired with the current Debian Steam instance
TVBox Steam Link is managed by tvboxctl
MAX_PRESERVED_APPS=0
F12/Home is a labwc global binding restored from /opt/tvbox-system