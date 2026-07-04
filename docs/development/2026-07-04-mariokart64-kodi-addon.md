# Mario Kart 64 Kodi Addon

## Goal

Add a repo-owned Kodi launcher for Mario Kart 64 and route it through the TVBox control layer.

## Current behavior

`/usr/local/bin/tvbox-mariokart64` launches Mupen64Plus directly after stopping Spotify and Kodi. The repo already contains `bin/tvbox-mariokart64`, matching the live wrapper, but there is no current Kodi add-on for launching it.

## Problem being solved

Mario Kart 64 is currently reachable as a live wrapper but is not exposed through the repo-owned Kodi add-on deployment model. The repo should own the launcher surface and install it through the same installer path as the other TVBox launchers.

## Files expected to change

```text
bin/tvboxctl
kodi-addons/plugin.program.tvbox.mariokart64/
docs/current-system-redeploy.md
docs/development/2026-07-04-mariokart64-kodi-addon.md
```

## Proposed implementation

Create `plugin.program.tvbox.mariokart64` with the provided Mario Kart icon and a small Python entrypoint that calls `tvboxctl launch mariokart64`.

Teach `tvboxctl` about the `mariokart64` launch target so the add-on uses the same locking, context, and Home recovery model as the rest of the appliance. Keep `bin/tvbox-mariokart64` as the emulator-specific wrapper.

Do not install Mupen64Plus or ROM content in this change. Document those as external/manual runtime dependencies.

## Commands used

```text
git status --short
rg --files
sed -n '1,220p' /usr/local/bin/tvbox-mariokart64
sed -n '1,220p' bin/tvbox-mariokart64
sed -n '1,260p' install.sh
sed -n '1,620p' bin/tvboxctl
file icons/mariokart_64.png icons/mariokart_64.jpeg
mkdir -p kodi-addons/plugin.program.tvbox.mariokart64
cp icons/mariokart_64.png kodi-addons/plugin.program.tvbox.mariokart64/icon.png
bash -n install.sh bin/tvboxctl bin/tvbox-mariokart64 bin/tvbox-home
python3 -m py_compile kodi-addons/plugin.program.tvbox.mariokart64/default.py
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("kodi-addons/plugin.program.tvbox.mariokart64/addon.xml")'
test -s kodi-addons/plugin.program.tvbox.mariokart64/icon.png
rm -rf kodi-addons/plugin.program.tvbox.mariokart64/__pycache__
```

## Validation checklist

Repo validation:

```text
bash -n install.sh bin/tvboxctl bin/tvbox-mariokart64 bin/tvbox-home
python3 -m py_compile kodi-addons/plugin.program.tvbox.mariokart64/default.py
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("kodi-addons/plugin.program.tvbox.mariokart64/addon.xml")'
test -s kodi-addons/plugin.program.tvbox.mariokart64/icon.png
```

Deploy validation:

```text
sudo /opt/tvbox-system/install.sh
Launch Mario Kart 64 from Kodi.
Press Home/F12 while Mupen64Plus is active and confirm Kodi returns.
Confirm `/home/tvbox/Games/ROMs/N64/Mario Kart 64 (USA).z64` exists and Mupen64Plus plugins are installed.
```

## Test results

Repo validation passed:

```text
bash -n install.sh bin/tvboxctl bin/tvbox-mariokart64 bin/tvbox-home
python3 -m py_compile kodi-addons/plugin.program.tvbox.mariokart64/default.py
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("kodi-addons/plugin.program.tvbox.mariokart64/addon.xml")'
test -s kodi-addons/plugin.program.tvbox.mariokart64/icon.png
```

Deploy validation was not run. The installer was not executed, Kodi was not restarted, and the live Mario Kart launch/Home path was not tested.

## Known risks

Mupen64Plus, its plugin paths, and the Mario Kart 64 ROM are not repo-owned. A redeployed system still needs those runtime dependencies installed separately.

The current wrapper hardcodes `/usr/local/bin/mupen64plus`, `/usr/local/lib/libmupen64plus.so.2`, `/usr/local/lib/mupen64plus`, and `/home/tvbox/Games/ROMs/N64/Mario Kart 64 (USA).z64`.

## Rollback notes

Remove `/home/tvbox/.kodi/addons/plugin.program.tvbox.mariokart64` after deploy to remove the Kodi entry.

Restore the prior `bin/tvboxctl` from git if the `launch mariokart64` control path needs to be removed.

If `/usr/local/bin/tvbox-mariokart64` was replaced by the installer, restore the timestamped `/usr/local/bin/tvbox-mariokart64.bak.*` file or relink to the desired wrapper.

## Status

validated for repo syntax/static checks; deploy validation pending
