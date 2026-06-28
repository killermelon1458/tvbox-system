# Current TVBox Redeploy Baseline

This repo now aims to capture the TVBox system that exists today, before the larger control-layer plans are implemented.

The goal is reproducibility, not perfection: a new Raspberry Pi should be able to clone this repo, run the installer, complete local setup, and get close to the current appliance behavior without guessing which files were hand-edited under `/usr/local/bin` or `~/.config`.

## Ownership Model

Repo-owned deployable files:

```text
bin/                         current TVBox scripts installed as /usr/local/bin/tvbox-*
config/tvboxctl.conf.example default tvboxctl config
config/labwc/                canonical labwc recovery config
config/autostart/            desktop autostart entries
config/systemd-user/         tvbox user services
config/systemd-system/       system systemd drop-ins
kodi-addons/                 TVBox Kodi launcher/startup addons
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
local network addresses, especially MOONLIGHT_HOST
audio device names if the HDMI sink changes
```

## Current Entrypoints

The important live commands after install are:

```text
/usr/local/bin/tvboxctl
/usr/local/bin/tvbox-home
/usr/local/bin/tvbox-kodi
/usr/local/bin/tvbox-youtube
/usr/local/bin/tvbox-moonlight
/usr/local/bin/tvbox-steamlink
/usr/local/bin/tvbox-spotify-mode
/usr/local/bin/tvbox-stop-spotify
/usr/local/bin/tvbox-audio-hdmi
/usr/local/bin/tvbox-audio-gamesir
/usr/local/bin/tvbox-mariokart64
```

`tvbox-home` is the global F12 target. It handles the current emergency Mupen64Plus exit path first, then delegates to `tvboxctl home`.

## Validation

After install/reboot:

```bash
readlink -f /usr/local/bin/tvboxctl
readlink -f /usr/local/bin/tvbox-home
readlink -f /usr/local/bin/tvbox-kodi
tvboxctl status
grep -n -A4 -B2 -E 'key="F12"|tvbox-home' /home/tvbox/.config/labwc/rc.xml
systemctl cat raspotify
```

Also test from the TV:

```text
Kodi autostarts.
F12/Home returns to Kodi Favourites.
YouTube addon launches Chromium TV mode and returns to Kodi.
Moonlight addons launch and Home soft-disconnects locally.
Steam Link addon launches through tvboxctl and Home closes local Steam Link.
Spotify connect starts the visible Spotify mode and Home returns to Kodi.
```

## Known Gaps

The future plan docs are not implemented yet. In particular:

```text
tvboxctl exit and menu are placeholders.
Most tvboxctl launch subcommands are placeholders except steamlink.
tvbox-inputctl does not exist yet.
Controller profile ownership is not implemented.
The installer does not install OS packages or configure external accounts.
```
