# Custom Exit Button

## Goal

Implement the repo-owned custom Exit button path planned in `docs/tvbox_home_exit_panic_recovery_plan.md`.

## Current behavior

`tvboxctl exit` is a placeholder. The repo labwc config binds F12/Home only.

## Problem being solved

The remote needs a global Exit button that closes the current TVBox mode without using SSH or a keyboard. Repeated Exit presses should also provide a local panic recovery path for wedged Kodi or stale state.

## Files expected to change

```text
bin/tvboxctl
bin/tvbox-exit
bin/tvbox-inputctl
config/labwc/rc.xml
input-profiles/kodi_native_minimal.gamecontroller.amgp
input-profiles/mariokart_n64.gamecontroller.amgp
docs/development/2026-07-04-custom-exit-button.md
docs/current-system-redeploy.md
```

## Proposed implementation

Add a thin `tvbox-exit` wrapper that delegates to `tvboxctl exit`.

Bind F5 in the repo labwc config to `/usr/local/bin/tvbox-exit`.

Implement `tvboxctl exit` with context-aware V1 behavior:

```text
Moonlight -> hard/destructive Moonlight quit path, then Kodi
Spotify -> stop Spotify mode, then Kodi
Steam Link -> close local Steam Link, then Kodi
YouTube -> close TVBox YouTube Chromium profile, then Kodi
Mario Kart 64 -> close Mupen64Plus, then Kodi
Kodi -> if away from Favourites, open Favourites; if already at Favourites, close Kodi to desktop
Unknown/desktop -> show Kodi
Exit x5 -> exit panic cleanup and leave desktop
Home x5 -> home panic cleanup and hard Kodi restart
```

Add repo-side recovery logging and panic snapshot support. Keep panic local and avoid broad Chromium or desktop-session restarts. Home panic and Exit panic are intentionally different: Home panic returns to Kodi; Exit panic closes everything in TVBox scope and does not relaunch Kodi.

Make `kodi_native_minimal` an active minimal AntiMicroX profile so Kodi mode can emit global recovery keys. Map controller Home/Guide to F12 and Back/View to F5, leaving normal Kodi navigation native.

Make `mariokart_n64` an active minimal AntiMicroX profile and map the `mariokart64` tvboxctl context to it. This keeps Mario Kart gameplay input native while still exposing controller Home/Guide as F12 and Back/View as F5.

## Commands used

```bash
git status --short
rg -n "exit button|custom exit|Exit button|exit" docs -S
rg --files docs
ls
sed -n '1,220p' docs/tvbox_home_exit_panic_recovery_plan.md
sed -n '220,520p' docs/tvbox_home_exit_panic_recovery_plan.md
sed -n '520,820p' docs/tvbox_home_exit_panic_recovery_plan.md
rg --files bin lib config kodi-addons input-profiles install.sh
sed -n '1,260p' bin/tvboxctl
sed -n '260,620p' bin/tvboxctl
sed -n '620,980p' bin/tvboxctl
sed -n '1,120p' bin/tvbox-home
rg -n "tvbox-exit|F5|tvbox-home|F12|keybind|Execute" config install.sh bin docs/current-system-redeploy.md -S
sed -n '1,220p' install.sh
sed -n '1,80p' config/labwc/rc.xml
sed -n '1,190p' docs/current-system-redeploy.md
sed -n '1,120p' config/tvboxctl.conf.example
bash -n bin/tvboxctl bin/tvbox-home bin/tvbox-exit install.sh
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("config/labwc/rc.xml")'
rg -n 'key="F5"|tvbox-exit' config/labwc/rc.xml bin/tvbox-exit install.sh docs/current-system-redeploy.md
find kodi-addons -type d -name __pycache__ -print
rg -n 'panic-home|panic-exit|recover_exit_panic_local|kodi_at_favourites|KODI_JSONRPC_URL' bin/tvboxctl config/tvboxctl.conf.example docs/current-system-redeploy.md
bash -n bin/tvboxctl bin/tvbox-home bin/tvbox-exit bin/tvbox-inputctl install.sh
python3 -c 'import xml.etree.ElementTree as ET; [ET.parse(p) for p in ["config/labwc/rc.xml", "input-profiles/kodi_native_minimal.gamecontroller.amgp", "input-profiles/controller_kbm_generic.gamecontroller.amgp"]]'
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test TVBOX_INPUTCTL_LOG_DIR=/tmp TVBOX_INPUTCTL_DRY_RUN=1 TVBOX_ANTIMICROX_BIN=/bin/true bin/tvbox-inputctl set-profile kodi_native_minimal
rg -n 'kodi_native_minimal|0x1000034|0x100003b|button index="5"|button index="6"' bin/tvbox-inputctl input-profiles/kodi_native_minimal.gamecontroller.amgp docs/current-system-redeploy.md input-profiles/README.md
bash -n bin/tvboxctl bin/tvbox-inputctl
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("input-profiles/mariokart_n64.gamecontroller.amgp")'
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test TVBOX_INPUTCTL_LOG_DIR=/tmp TVBOX_INPUTCTL_DRY_RUN=1 TVBOX_ANTIMICROX_BIN=/bin/true bin/tvbox-inputctl set-profile mariokart_n64
rg -n 'mariokart64\)|mariokart_n64|KNOWN_PROFILES|profile_file|apply_profile' bin/tvboxctl bin/tvbox-inputctl input-profiles/README.md docs/current-system-redeploy.md
```

## Validation checklist

Repo validation:

```text
bash -n bin/tvboxctl bin/tvbox-home bin/tvbox-exit install.sh
Parse config/labwc/rc.xml with an XML parser.
Confirm F5 maps to /usr/local/bin/tvbox-exit.
Confirm installer will symlink bin/tvbox-exit through the existing tvbox* loop.
Confirm Exit x5 maps to close-only panic and Home x5 maps to hard-restart-home panic.
Confirm `kodi_native_minimal` maps Home/Guide to F12 and Back/View to F5.
Confirm `tvbox-inputctl` dry-run resolves `kodi_native_minimal` to the repo profile file.
Confirm `mariokart64` context maps to `mariokart_n64`.
Confirm `tvbox-inputctl` dry-run resolves `mariokart_n64` to the repo profile file.
```

Deploy validation:

```text
Not run unless explicitly requested.
Install repo changes with sudo /opt/tvbox-system/install.sh.
Restart labwc session or reboot.
From the TV, test F5 in Kodi, YouTube, Spotify, Steam Link, Moonlight, Mario Kart 64, and desktop/unknown contexts.
Confirm Exit x5 writes a panic snapshot, closes TVBox-controlled apps, closes Kodi, and leaves desktop.
Confirm Home x5 writes a panic snapshot and hard-restarts Kodi to Favourites.
```

## Test results

Repo validation:

```text
bash -n bin/tvboxctl bin/tvbox-home bin/tvbox-exit install.sh: passed
XML parse config/labwc/rc.xml: passed
F5/tvbox-exit lookup: passed
installer coverage: passed by existing install.sh bin/tvbox* symlink loop
generated __pycache__ cleanup check: passed
Exit/Home panic split static check: passed
Kodi minimal profile XML parse: passed
tvbox-inputctl kodi_native_minimal dry-run with /tmp state/log dirs: passed
mariokart_n64 profile XML parse: passed
tvbox-inputctl mariokart_n64 dry-run with /tmp state/log dirs: passed
mariokart64 context to mariokart_n64 static check: passed
```

Deploy validation:

```text
Not run. No install, labwc restart, service restart, or reboot was performed.
```

Repository pre-commit validation repeated on 2026-07-20:

```text
bash -n bin/tvboxctl bin/tvbox-home bin/tvbox-exit bin/tvbox-inputctl install.sh: passed
XML parsing for labwc and all three changed AntiMicroX profiles: passed
tvbox-inputctl dry-run for kodi_native_minimal and mariokart_n64: passed
F12/Home and F5/Exit labwc binding lookup: passed
Home/Exit panic threshold and pre-cleanup snapshot static lookup: passed
Executable-bit checks for tvboxctl, tvbox-inputctl, and tvbox-exit: passed
git diff --check: passed
Deploy validation: not run
```

## Known risks

Kodi Favourites detection uses Kodi JSON-RPC at `KODI_JSONRPC_URL` and a short-lived local hint when `tvboxctl` just opened Favourites. If Kodi JSON-RPC is unavailable and the hint is absent, Exit will conservatively open Favourites instead of closing Kodi.

Plex UI/playback is still treated as Kodi because this V1 does not add Plex-specific Kodi JSON-RPC window/add-on detection.

Panic snapshot commands depend on optional tools such as `wlrctl` and `journalctl`; missing tools are tolerated.

The F5 labwc binding requires deployment and labwc reload/restart or reboot before it works live.

## Duplicate press definition

Home and Exit use separate counters.

```text
Home duplicate window: 10 seconds
Exit duplicate window: 8 seconds
Panic threshold: 5 presses
```

The timer resets on each press that still falls inside the window. Practically, this means you can spam the button; there is no required delay between presses. For Exit, five presses in roughly eight seconds counts as Exit panic. For Home, five presses in roughly ten seconds counts as Home panic. If the gap between two presses exceeds that button's window, the count starts over at 1.

## Rollback notes

Remove or revert the F5 keybind in:

```text
/home/tvbox/.config/labwc/rc.xml
```

Restore or remove the wrapper symlink:

```text
/usr/local/bin/tvbox-exit
```

Restore the previous repo `bin/tvboxctl` behavior or redeploy the previous commit. If Kodi was closed by Exit, run:

```bash
/usr/local/bin/tvbox-kodi
```

## Status: implemented and repo-validated; deploy validation pending
