# Current TVBox Redeploy Baseline

This repo now aims to capture the TVBox system that exists today, before the larger control-layer plans are implemented.

The goal is reproducibility, not perfection: a new Raspberry Pi should be able to clone this repo, run the installer, complete local setup, and get close to the current appliance behavior without guessing which files were hand-edited under `/usr/local/bin` or `~/.config`.

## Ownership Model

Repo-owned deployable files:

```text
bin/                         current TVBox scripts installed as /usr/local/bin/tvbox-*
config/tvboxctl.conf.example default tvboxctl config
config/labwc/                canonical labwc recovery config
config/kodi/                 Kodi user config deployed by the installer
config/autostart/            desktop autostart entries
config/systemd-user/         tvbox user services
config/systemd-system/       system systemd drop-ins
kodi-addons/                 TVBox Kodi launcher/startup addons
input-profiles/              input profile names and future backend definitions
```

Historical snapshots and older backups stay under `legacy/`. They are useful references, but they are not the current deploy target.

## Install

From a fresh clone at `/opt/tvbox-system`:

```bash
sudo /opt/tvbox-system/install.sh
sudo reboot
```

The installer:

```text
1. Symlinks current repo scripts into /usr/local/bin.
2. Installs /etc/tvboxctl.conf if it does not already exist.
3. Installs labwc config into /home/tvbox/.config/labwc.
4. Installs desktop autostart entries.
5. Installs tvbox user systemd units.
6. Installs systemd drop-ins for raspotify and logind.
7. Copies TVBox Kodi addons into /home/tvbox/.kodi/addons.
8. Copies repo-owned Kodi keymaps into /home/tvbox/.kodi/userdata/keymaps.
```

Existing `/usr/local/bin/tvbox-*` files are backed up before they are replaced with symlinks.

## Required Manual Setup

The repo does not currently install OS packages. A new Pi still needs the runtime stack installed first:

```text
labwc desktop session
Kodi and kodi-send
Chromium
wlrctl
PipeWire/PulseAudio tools: pactl, wpctl
Raspotify
Moonlight Qt
Steam Link
Mupen64Plus, if using the Mario Kart launcher
```

Machine-specific setup still lives outside the repo:

```text
Spotify credentials/auth state
Moonlight pairing state
Sunshine host apps and undo scripts
Steam Link pairing/auth state
Kodi/Plex account setup
ROM files under /home/tvbox/Games
Mario Kart 64 ROM at /home/tvbox/Games/ROMs/N64/Mario Kart 64 (USA).z64, if using the Mario Kart launcher
local network addresses, especially MOONLIGHT_HOST
audio device names if the HDMI sink changes
```

## Current Entrypoints

The important live commands after install are:

```text
/usr/local/bin/tvboxctl
/usr/local/bin/tvbox-home
/usr/local/bin/tvbox-exit
/usr/local/bin/tvbox-kodi
/usr/local/bin/tvbox-youtube
/usr/local/bin/tvbox-moonlight
/usr/local/bin/tvbox-steamlink
/usr/local/bin/tvbox-spotify-mode
/usr/local/bin/tvbox-stop-spotify
/usr/local/bin/tvbox-audio-hdmi
/usr/local/bin/tvbox-audio-gamesir
/usr/local/bin/tvbox-mariokart64
/usr/local/bin/tvbox-inputctl
/usr/local/bin/tvbox-diag
```

`tvbox-home` is the global F12 target. It handles the current emergency Mupen64Plus exit path first, then delegates to `tvboxctl home`.

`tvbox-exit` is the global F5 target. It delegates to `tvboxctl exit`, which closes the current TVBox mode. In Kodi, Exit only opens Favourites when Kodi is not already at Favourites. If Kodi is already at Favourites, Exit closes Kodi to the desktop. Five repeated Exit presses run exit panic recovery: close TVBox-controlled apps, close Kodi, and leave the desktop. Five repeated Home presses run home panic recovery: clean up local foreground apps, hard-restart Kodi, and return to Favourites.

`tvbox-inputctl` records the intended input profile in TVBox runtime state and can control a TVBox-owned AntiMicroX process. `kodi_native_minimal` starts the minimal Kodi profile, mapping controller Home/Guide to F12 and Back/View to F5. `mariokart_n64` starts the minimal Mario Kart 64 profile, mapping only controller Home/Guide to F12 and Back/View to F5. `controller_kbm_generic`, `youtube_remote`, `spotify_ui`, and `desktop_mouse` start the generic keyboard/mouse profile. `kodi_native`, `passthrough`, and `none` stop the TVBox-owned AntiMicroX process.

Repo-owned Kodi keymaps live under `config/kodi/userdata/keymaps/`. The installer deploys them to `/home/tvbox/.kodi/userdata/keymaps/`. `tvbox-controller-guide.xml` maps the Kodi native controller Guide/Xbox logical button to `ActivateWindow(FavouritesBrowser)` as a Kodi-local fallback.

Repo-owned Kodi launcher add-ons include YouTube, Moonlight, Steam Link, and Mario Kart 64. The Mario Kart 64 add-on runs `tvboxctl launch mariokart64`, which starts `/usr/local/bin/tvbox-mariokart64`; the wrapper expects the Mupen64Plus binary/plugins and ROM path listed above to exist outside the repo.

Kodi mode also applies `kodi_native_minimal.gamecontroller.amgp` through `tvbox-inputctl`. That minimal AntiMicroX profile maps controller Home/Guide to F12 and Back/View to F5 so the labwc global Home and Exit bindings work from Kodi.

Current repo context wiring:

```text
Kodi/Home recovery -> kodi_native_minimal
Kodi GUI close with no controlled app active -> desktop + controller_kbm_generic
YouTube Chromium mode -> controller_kbm_generic
Steam Link -> passthrough
Moonlight -> passthrough
Mario Kart 64 -> mariokart_n64
```

## Passive Diagnostics (Installed, Not Automatically Enabled)

The repo contains the observation-only `tvbox-diag` CLI and two user units:

```text
tvbox-healthd.service       periodic coordinator plus passive DRM/input udev source
tvbox-healthd-cec.service   separate passive CEC monitor
```

The installer deploys the CLI, example-derived user configuration, and units,
but does not enable or start either observer. The CEC unit intentionally has no
`[Install]` section until adapter coexistence is validated.

Start a temporary session:

```bash
systemctl --user start tvbox-healthd.service
journalctl --user-unit=tvbox-healthd.service -f
```

Or run the faster foreground diagnostic mode:

```bash
tvbox-diag watch --diagnostic
```

Create a passive snapshot or bounded allowlisted bundle:

```bash
tvbox-diag snapshot
tvbox-diag bundle
```

Stop all observers:

```bash
systemctl --user disable --now tvbox-healthd.service tvbox-healthd-cec.service
```

Discovery limitations and manual tests are recorded in
`docs/tvbox-focus-cec-diagnostic-discovery.md` and
`docs/tvbox-focus-cec-diagnostic-tests.md`.

## HDMI Kodi Focus Recovery

The installer deploys:

```text
/usr/local/bin/tvbox-focusd
/home/tvbox/.config/systemd/user/tvbox-focus-recovery.service
```

The recovery service watches DRM hotplug events separately from the passive
diagnostic service. After the final event is stable for one second, it asserts
focus on exact Wayland app ID `Kodi` only when:

- HDMI-A-2 is connected;
- active context is Kodi or Plex;
- Kodi is running and listed as a Wayland toplevel; and
- no controlled YouTube, Spotify, Moonlight, Steam Link, or Mario Kart process
  is running.

It retries once when the connector/toplevel is not ready and rate-limits focus
assertions to one per three seconds. It does not restart Kodi, close PCManFM,
change input profiles, or send CEC commands.

The unit is installed but is not automatically enabled. Start it for testing:

```bash
systemctl --user daemon-reload
systemctl --user start tvbox-focus-recovery.service
systemctl --user status tvbox-focus-recovery.service
journalctl --user-unit=tvbox-focus-recovery.service -f
```

After validated TV off/on testing, enable it across login/reboot:

```bash
systemctl --user enable tvbox-focus-recovery.service
```

On this installation, user-unit output is stored in the system journal.
`journalctl --user -u ...` reports that no per-user journal files exist; use
`journalctl --user-unit=...` instead.

## TV Status and Activation

The installer links:

```text
/usr/local/bin/tvbox-tv -> /opt/tvbox-system/bin/tvbox-tv
```

Available commands:

```bash
tvbox-tv status
tvbox-tv status --json
tvbox-tv activate
```

`status` performs fresh bounded DRM and CEC checks. It reports TV state, HDMI
connection/enabled/DPMS state, CEC power, physical and logical addresses, active
source, evidence, and timestamp. Its state values are:

```text
on
standby
transitioning
unavailable
unknown
```

`activate` is an idempotent ensure-active operation:

1. Coalesce concurrent calls with a runtime lock.
2. Return immediately if the TVBox is already on and active.
3. Otherwise send CEC `IMAGE_VIEW_ON`.
4. Wait up to 45 seconds for HDMI-A-2, CEC power on, physical address
   `1.0.0.0`, and Playback logical address 4.
5. Broadcast `ACTIVE_SOURCE` only after CEC readiness returns.

The command does not focus or restart Kodi, change input profiles, power off the
TV, or suspend/shut down the Pi. Kodi's CEC action for TV switch-off must remain
`Ignore`.

The Hisense TV took 27.285 seconds in the validated TV-off activation test.
Activation completed with connected HDMI, CEC power on, Playback address 4, and
active source `1.0.0.0`, inside the 45-second limit.

## Validation

After install/reboot:

```bash
readlink -f /usr/local/bin/tvboxctl
readlink -f /usr/local/bin/tvbox-home
readlink -f /usr/local/bin/tvbox-exit
readlink -f /usr/local/bin/tvbox-kodi
tvboxctl status
grep -n -A4 -B2 -E 'key="F12"|key="F5"|tvbox-home|tvbox-exit' /home/tvbox/.config/labwc/rc.xml
systemctl cat raspotify
```

Also test from the TV:

```text
Kodi autostarts.
F12/Home returns to Kodi Favourites.
F5/Exit closes the current TVBox mode; in Kodi, it opens Favourites when away from Favourites and closes Kodi when already at Favourites.
F5/Exit pressed five times runs exit panic recovery and leaves the desktop.
F12/Home pressed five times runs home panic recovery and hard-restarts Kodi back to Favourites.
Xbox/Guide in Kodi emits F12 through `kodi_native_minimal`, reaching the global Home binding.
Controller Back/View in Kodi emits F5 through `kodi_native_minimal` and reaches the global Exit binding.
YouTube addon launches Chromium TV mode and returns to Kodi.
Moonlight addons launch and Home soft-disconnects locally.
Steam Link addon launches through tvboxctl and Home closes local Steam Link.
Mario Kart 64 addon launches through tvboxctl and Home/F12 closes Mupen64Plus.
Mario Kart 64 applies `mariokart_n64`, so controller Home/Guide emits F12 and Back/View emits F5 while gameplay controls otherwise remain native.
Spotify connect starts the visible Spotify mode and Home returns to Kodi.
Closing Kodi from the Kodi GUI updates `tvboxctl status` to `active-context: desktop` and applies the generic controller keyboard/mouse input profile.
```

## Known Gaps

The future plan docs are not implemented yet. In particular:

```text
tvboxctl menu is a placeholder.
Most tvboxctl launch subcommands are placeholders except steamlink and mariokart64.
Only kodi_native_minimal and controller_kbm_generic are currently used as active AntiMicroX remapping profiles.
Controller-specific profile organization is not implemented yet.
The installer does not install OS packages or configure external accounts.
```
