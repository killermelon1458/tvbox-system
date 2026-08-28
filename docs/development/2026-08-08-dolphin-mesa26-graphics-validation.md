# Dolphin / Double Dash Mesa 26 Graphics Validation

Date tested: 2026-08-08  
Document created: 2026-08-28  
Host: `tvbox`  
Purpose: document the Mesa/Dolphin graphics work needed to fix Mario Kart Double Dash!! visual artifacts on Raspberry Pi 5 without breaking Kodi/Plex.

## 1. Summary

Mario Kart Double Dash!! in Dolphin had visual artifacts on the TVBox with the normal Raspberry Pi Mesa stack.

The likely required graphics feature was available in newer Mesa. Debian trixie-backports provided Mesa 26.1.2, and testing confirmed that Mesa 26.1.2 exposes the required V3DV Vulkan capability.

However, installing Debian backports Mesa system-wide caused unacceptable TVBox regressions:

- Kodi/Plex navigation became choppy.
- At least one Plex stream produced audio with black video.
- Another Plex stream played extremely choppily, roughly estimated around 15 FPS.

The system-wide Mesa upgrade was rolled back to Raspberry Pi `+rpt` Mesa. Plex then worked again.

The working solution is:

```text
Keep Raspberry Pi +rpt Mesa as the system Mesa.
Extract Debian backports Mesa 26.1.2 to /opt/mesa-26.1.2-bpo.
Patch a private Broadcom/V3DV Vulkan ICD JSON.
Launch Dolphin only with VK_DRIVER_FILES pointed at that private ICD.
Force Dolphin/Qt through XCB/XWayland.
Force Dolphin backend to Vulkan.
```

This successfully launched Mario Kart Double Dash!! without the observed visual artifacts.

## 2. Tested environment

### OS

Observed earlier in the session:

```text
Debian GNU/Linux 13 (trixie)
Debian version 13.1
```

### Stable system Mesa after rollback

After rollback and reboot:

```text
mesa-vulkan-drivers: 25.0.7-2+rpt4+deb13u1
libgl1-mesa-dri:    25.0.7-2+rpt4+deb13u1
libegl-mesa0:       25.0.7-2+rpt4+deb13u1
libgbm1:            25.0.7-2+rpt4+deb13u1
libglx-mesa0:       25.0.7-2+rpt4+deb13u1
mesa-libgallium:    25.0.7-2+rpt4+deb13u1
```

Backports remained available but lower priority after rollback:

```text
26.1.2-1~bpo13+1 priority 100
25.0.7-2+rpt4+deb13u1 priority 500
```

### Dolphin install

Discovery found:

```text
/usr/games/dolphin-emu
dolphin-emu      2503+dfsg-1+deb13u1 arm64
dolphin-emu-data 2503+dfsg-1+deb13u1 all
```

No Flatpak or Snap Dolphin was present.

### Dolphin user data discovered

Discovery found Dolphin state/config in:

```text
/home/tvbox/.config/dolphin-emu
/home/tvbox/.local/share/dolphin-emu
/home/tvbox/.cache/dolphin-emu
```

A Double Dash save was present at:

```text
/home/tvbox/.local/share/dolphin-emu/GC/USA/Card A/01-GM4E-MarioKart Double Dash!!.gci
```

Initial Dolphin config still said:

```text
/home/tvbox/.config/dolphin-emu/Dolphin.ini:6:GFXBackend = OGL
```

## 3. Backports Mesa system-wide test

Backports was added with:

```deb822
Types: deb
URIs: http://deb.debian.org/debian
Suites: trixie-backports
Components: main
Enabled: yes
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
```

After `sudo apt update`, backports offered Mesa 26.1.2:

```text
mesa-vulkan-drivers 26.1.2-1~bpo13+1
libgl1-mesa-dri     26.1.2-1~bpo13+1
libegl-mesa0        26.1.2-1~bpo13+1
libgbm1             26.1.2-1~bpo13+1
libglx-mesa0        26.1.2-1~bpo13+1
```

The simulation was clean:

```text
Upgrading: 9
Installing: 0
Removing: 0
```

The upgraded packages were:

```text
libegl-mesa0
libgl1-mesa-dev
libglx-mesa0
libgbm-dev
libgl1-mesa-dri
mesa-libgallium
libgbm1
libgles2-mesa-dev
mesa-vulkan-drivers
```

After real install, `vulkaninfo` confirmed Mesa 26.1.2 V3DV:

```text
driverID     = DRIVER_ID_MESA_V3DV
driverName   = V3DV Mesa
driverInfo   = Mesa 26.1.2-1~bpo13+1
dualSrcBlend = true
```

### Result

The feature target was achieved, but TVBox media playback regressed.

Observed regressions:

```text
Kodi/Plex navigation choppy
Plex show: audio with black video
Plex show: video plays but very choppy
```

Conclusion:

```text
Do not use Debian backports Mesa 26 system-wide on this TVBox unless Kodi/Plex are retested and proven stable.
```

## 4. Rollback

System-wide backports Mesa was rolled back with:

```bash
sudo apt install --allow-downgrades \
  mesa-vulkan-drivers=25.0.7-2+rpt4+deb13u1 \
  libgl1-mesa-dri=25.0.7-2+rpt4+deb13u1 \
  libegl-mesa0=25.0.7-2+rpt4+deb13u1 \
  libgbm1=25.0.7-2+rpt4+deb13u1 \
  libglx-mesa0=25.0.7-2+rpt4+deb13u1 \
  mesa-libgallium=25.0.7-2+rpt4+deb13u1 \
  libgbm-dev=25.0.7-2+rpt4+deb13u1 \
  libgl1-mesa-dev=25.0.7-2+rpt4+deb13u1 \
  libgles2-mesa-dev=25.0.7-2+rpt4+deb13u1
```

After reboot, apt policy showed Raspberry Pi `+rpt` Mesa as installed and candidate.

Plex worked again after rollback.

## 5. Private extracted Mesa 26 runtime

Backports packages were downloaded but not installed:

```bash
mkdir -p ~/mesa-26-debs
cd ~/mesa-26-debs

apt download \
  mesa-vulkan-drivers=26.1.2-1~bpo13+1 \
  libgl1-mesa-dri=26.1.2-1~bpo13+1 \
  libegl-mesa0=26.1.2-1~bpo13+1 \
  libgbm1=26.1.2-1~bpo13+1 \
  libglx-mesa0=26.1.2-1~bpo13+1 \
  mesa-libgallium=26.1.2-1~bpo13+1
```

They were extracted to:

```text
/opt/mesa-26.1.2-bpo
```

Extraction command:

```bash
sudo rm -rf /opt/mesa-26.1.2-bpo
sudo mkdir -p /opt/mesa-26.1.2-bpo

for f in *.deb; do
  sudo dpkg-deb -x "$f" /opt/mesa-26.1.2-bpo
done
```

Important extracted files included:

```text
/opt/mesa-26.1.2-bpo/usr/lib/aarch64-linux-gnu/libvulkan_broadcom.so
/opt/mesa-26.1.2-bpo/usr/share/vulkan/icd.d/broadcom_icd.json
```

A private patched ICD file was written:

```text
/opt/mesa-26.1.2-bpo/vulkan-broadcom-mesa26.json
```

The patched ICD points directly to:

```text
/opt/mesa-26.1.2-bpo/usr/lib/aarch64-linux-gnu/libvulkan_broadcom.so
```

Patch command used:

```bash
sudo python3 - <<'PY'
import json
from pathlib import Path

prefix = Path("/opt/mesa-26.1.2-bpo")
icd_dir = prefix / "usr/share/vulkan/icd.d"
lib_dir = prefix / "usr/lib/aarch64-linux-gnu"

jsons = list(icd_dir.glob("*broadcom*.json")) + list(icd_dir.glob("*v3dv*.json"))
libs = list(lib_dir.glob("libvulkan_broadcom.so*"))

if not jsons:
    raise SystemExit(f"No Broadcom/V3DV ICD JSON found under {icd_dir}")
if not libs:
    raise SystemExit(f"No libvulkan_broadcom.so found under {lib_dir}")

src = jsons[0]
lib = libs[0]

data = json.loads(src.read_text())
data["ICD"]["library_path"] = str(lib)

out = prefix / "vulkan-broadcom-mesa26.json"
out.write_text(json.dumps(data, indent=2) + "\n")

print("Wrote:", out)
print("Using driver:", lib)
PY
```

## 6. Private Mesa Vulkan validation

This command confirmed the private Mesa 26 V3DV ICD works:

```bash
PREFIX=/opt/mesa-26.1.2-bpo

VK_DRIVER_FILES="$PREFIX/vulkan-broadcom-mesa26.json" \
vulkaninfo --summary
```

Observed result:

```text
GPU0:
apiVersion         = 1.3.348
driverVersion      = 26.1.2
vendorID           = 0x14e4
deviceID           = 0x55701c33
deviceType         = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU
deviceName         = V3D 7.1.7.0
driverID           = DRIVER_ID_MESA_V3DV
driverName         = V3DV Mesa
driverInfo         = Mesa 26.1.2-1~bpo13+1
conformanceVersion = 1.3.8.3
```

Conclusion:

```text
VK_DRIVER_FILES can point a single process at Mesa 26 V3DV without replacing system Mesa.
```

## 7. Failed Dolphin launch attempts

### Attempt A — broad Mesa environment

A wrapper using broad graphics overrides was tested:

```text
VK_DRIVER_FILES
LD_LIBRARY_PATH
LIBGL_DRIVERS_PATH
MESA_LOADER_DRIVER_OVERRIDE
```

Dolphin launched, but Double Dash failed with:

```text
failed to initialize video backend
```

This approach was considered too invasive because global/broad Mesa replacement had already broken Kodi/Plex.

### Attempt B — native Wayland, Vulkan only

A safer wrapper used only:

```text
QT_QPA_PLATFORM=wayland
VK_DRIVER_FILES=/opt/mesa-26.1.2-bpo/vulkan-broadcom-mesa26.json
/usr/games/dolphin-emu -v Vulkan
```

Dolphin launched, but Double Dash failed with:

```text
failed to create Vulkan surface
```

Conclusion:

```text
Mesa 26 V3DV was loading, and Dolphin was reaching Vulkan, but native Wayland Vulkan surface creation failed.
```

## 8. Working Dolphin launch method

The successful wrapper used XCB/XWayland:

```bash
#!/usr/bin/env bash
set -euo pipefail

PREFIX=/opt/mesa-26.1.2-bpo
LOG="$HOME/dolphin-mesa26-vulkan-xcb.log"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DISPLAY="${DISPLAY:-:0}"

# Force Qt through XCB/XWayland instead of native Wayland.
export QT_QPA_PLATFORM=xcb
unset WAYLAND_DISPLAY

# Only override Vulkan driver selection.
export VK_DRIVER_FILES="$PREFIX/vulkan-broadcom-mesa26.json"

{
  echo "=== $(date -Is) ==="
  echo "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
  echo "DISPLAY=$DISPLAY"
  echo "QT_QPA_PLATFORM=$QT_QPA_PLATFORM"
  echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-}"
  echo "VK_DRIVER_FILES=$VK_DRIVER_FILES"
  echo
  exec /usr/games/dolphin-emu -v Vulkan "$@"
} 2>&1 | tee "$LOG"
```

Observed launch environment:

```text
XDG_RUNTIME_DIR=/run/user/1000
DISPLAY=:0
QT_QPA_PLATFORM=xcb
WAYLAND_DISPLAY=
VK_DRIVER_FILES=/opt/mesa-26.1.2-bpo/vulkan-broadcom-mesa26.json
```

Result:

```text
Mario Kart Double Dash!! launched.
The previous visual artifacts were not present.
```

## 9. Current recommended launcher

Recommended stable helper path:

```text
/usr/local/bin/tvbox-dolphin-mesa26
```

Install from the tested wrapper:

```bash
sudo cp ~/run-dolphin-mesa26-vulkan-xcb /usr/local/bin/tvbox-dolphin-mesa26
sudo chmod +x /usr/local/bin/tvbox-dolphin-mesa26
```

This helper should remain a Dolphin-specific Mesa/Vulkan wrapper only.

It should not:

```text
modify global Mesa
set global LD_LIBRARY_PATH
replace system Vulkan ICDs
own TVBox lifecycle policy
decide Home/Exit behavior
change Kodi state by itself
```

## 10. Optional Dolphin config change

Dolphin initially had:

```text
GFXBackend = OGL
```

Because the working launch uses `-v Vulkan`, this is not strictly required. However, to reduce ambiguity, it is reasonable to update Dolphin config to Vulkan:

```bash
cp ~/.config/dolphin-emu/Dolphin.ini \
  ~/.config/dolphin-emu/Dolphin.ini.bak.$(date +%Y%m%d-%H%M%S)

python3 - <<'PY'
from pathlib import Path

p = Path.home() / ".config/dolphin-emu/Dolphin.ini"
s = p.read_text()

if "GFXBackend =" in s:
    s = "\n".join(
        "GFXBackend = Vulkan" if line.startswith("GFXBackend =") else line
        for line in s.splitlines()
    ) + "\n"
else:
    s += "\nGFXBackend = Vulkan\n"

p.write_text(s)
PY

grep -n 'GFXBackend' ~/.config/dolphin-emu/Dolphin.ini
```

Expected:

```text
GFXBackend = Vulkan
```

## 11. Risk notes

### Do not install Mesa 26 globally

System-wide Debian backports Mesa 26 broke Kodi/Plex behavior. Keep system Mesa on Raspberry Pi `+rpt` packages.

### Do not use broad LD_LIBRARY_PATH unless proven necessary

The working result did not require global-looking library overrides.

Preferred Dolphin-only environment:

```text
QT_QPA_PLATFORM=xcb
DISPLAY=:0
VK_DRIVER_FILES=/opt/mesa-26.1.2-bpo/vulkan-broadcom-mesa26.json
/usr/games/dolphin-emu -v Vulkan
```

Avoid by default:

```text
LD_LIBRARY_PATH=/opt/mesa-26.1.2-bpo/usr/lib/aarch64-linux-gnu
LIBGL_DRIVERS_PATH=/opt/mesa-26.1.2-bpo/usr/lib/aarch64-linux-gnu/dri
MESA_LOADER_DRIVER_OVERRIDE=v3d
```

### Keep /opt/mesa-26.1.2-bpo

The working wrapper depends on:

```text
/opt/mesa-26.1.2-bpo/vulkan-broadcom-mesa26.json
/opt/mesa-26.1.2-bpo/usr/lib/aarch64-linux-gnu/libvulkan_broadcom.so
```

Do not delete `/opt/mesa-26.1.2-bpo` unless the launcher is also removed.

## 12. Still to test

- Confirm Dolphin still launches after a cold reboot.
- Confirm Double Dash remains artifact-free after a cold reboot.
- Confirm Kodi/Plex still work after Dolphin exits.
- Confirm F12/Home can recover while Dolphin is open once integrated through `tvboxctl`.
- Confirm controller mappings for GameCube gameplay.
- Confirm whether Dolphin command-line can boot directly into the Double Dash game path.
- Confirm whether Dolphin exits cleanly when the game window closes.
- Confirm whether `tvbox-state` can detect Dolphin as a new context, or whether detection logic must be added.
