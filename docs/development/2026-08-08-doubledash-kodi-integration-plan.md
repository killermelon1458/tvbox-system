# TVBox Double Dash Kodi Integration Plan

Date tested: 2026-08-08  
Document created: 2026-08-28  
Target game: Mario Kart Double Dash!!  
Target emulator: Dolphin  
Target launcher goal: Kodi Program add-on that launches directly into Double Dash if feasible.

## 1. Goal

Add Mario Kart Double Dash!! as a first-class TVBox app, similar in spirit to the existing Mario Kart 64 launcher, but using Dolphin instead of Mupen64Plus.

Desired user flow:

```text
Kodi Favourites
-> Mario Kart Double Dash
-> TVBox transition starts
-> Kodi closes or yields foreground
-> Dolphin launches directly into Double Dash
-> Game runs with Mesa 26 V3DV Vulkan via private ICD
-> Home/Exit returns to Kodi
```

Preferred final command shape:

```bash
tvboxctl launch doubledash
```

Preferred final wrapper paths:

```text
/opt/tvbox-system/bin/tvbox-doubledash
/usr/local/bin/tvbox-doubledash -> /opt/tvbox-system/bin/tvbox-doubledash
```

Preferred Kodi add-on:

```text
/opt/tvbox-system/kodi-addons/plugin.program.tvbox.doubledash/
```

## 2. Current state

### Dolphin

Installed Dolphin:

```text
/usr/games/dolphin-emu
dolphin-emu 2503+dfsg-1+deb13u1 arm64
```

Working graphics helper:

```text
/usr/local/bin/tvbox-dolphin-mesa26
```

This helper uses:

```text
QT_QPA_PLATFORM=xcb
DISPLAY=:0
VK_DRIVER_FILES=/opt/mesa-26.1.2-bpo/vulkan-broadcom-mesa26.json
/usr/games/dolphin-emu -v Vulkan
```

This launches Dolphin with the private Mesa 26 V3DV Vulkan driver while leaving system Mesa on Raspberry Pi `+rpt`.

### Existing TVBox game integration

Existing repo/live wiring is for Mario Kart 64:

```text
/usr/local/bin/tvbox-mariokart64
/opt/tvbox-system/bin/tvbox-mariokart64
/opt/tvbox-system/kodi-addons/plugin.program.tvbox.mariokart64/
tvboxctl launch mariokart64
input profile: mariokart_n64
emulator: Mupen64Plus
```

No existing Double Dash / Dolphin Kodi launcher was discovered.

### Current TVBox architecture rule

`tvboxctl` owns global lifecycle policy:

```text
Home
Exit
app transitions
state
locking
input profile changes
recovery
```

Small wrappers may start/stop/focus one app, but wrappers should not implement global Home/Exit policy.

## 3. Required runtime assets

Need to identify and document the Double Dash game path.

Likely discovery command:

```bash
find "$HOME/Games" "$HOME/ROMs" "$HOME" \
  -type f \
  \( -iname '*double*dash*' -o -iname '*mario*kart*double*' -o -iname '*.iso' -o -iname '*.rvz' -o -iname '*.gcm' -o -iname '*.wbfs' \) \
  2>/dev/null | sort
```

Once found, define a stable path in the wrapper, for example:

```text
/home/tvbox/Games/ROMs/GameCube/Mario Kart Double Dash!!.rvz
```

The final wrapper should fail clearly if the game file is missing.

## 4. Direct-to-game launch feasibility

Dolphin normally supports opening a game path from the command line.

The target wrapper should attempt:

```bash
/usr/local/bin/tvbox-dolphin-mesa26 "/path/to/Mario Kart Double Dash!!.rvz"
```

or, if using the Dolphin binary directly inside the wrapper:

```bash
/usr/games/dolphin-emu -v Vulkan "/path/to/Mario Kart Double Dash!!.rvz"
```

with the proven environment:

```bash
export QT_QPA_PLATFORM=xcb
export DISPLAY="${DISPLAY:-:0}"
unset WAYLAND_DISPLAY
export VK_DRIVER_FILES=/opt/mesa-26.1.2-bpo/vulkan-broadcom-mesa26.json
```

If direct game path launch fails, fallback is to launch Dolphin normally and rely on Dolphin's GUI/game list.

Desired final state is direct game boot.

## 5. Proposed app identity

Use a new distinct context, not `mariokart64`.

Recommended context:

```text
doubledash
```

Alternative if a generic emulator framework is created later:

```text
dolphin:doubledash
game:doubledash
```

For the current TVBox architecture, `doubledash` is simpler.

Recommended process detection:

```text
process: dolphin-emu
context: doubledash
```

Potential issue:

```text
Dolphin could later be used for other games.
```

For now, because only Double Dash is being added, Dolphin process detection may be acceptable. If more Dolphin games are added later, use wrapper-owned state files or command-line tags if available.

## 6. Proposed input profile

Do not reuse `mariokart_n64` blindly.

### Option A — passthrough/native controller

Recommended first test:

```text
input_profile=passthrough
```

Reason:

```text
Dolphin can usually handle controllers directly.
AntiMicroX keyboard emulation may interfere with native gamepad input.
```

### Option B — dedicated GameCube/Dolphin minimal profile

If global Home/Exit require AntiMicroX assistance, create:

```text
dolphin_gamecube
```

or:

```text
doubledash_gamecube
```

Behavior:

```text
Gameplay buttons remain native if possible.
Only controller Home/Guide and Back/View map to global TVBox controls if needed.
```

Do not use a keyboard/mouse profile unless Dolphin cannot see the controller directly.

## 7. Proposed wrapper: bin/tvbox-doubledash

Initial repo-owned wrapper should do only app-specific launch work.

Suggested behavior:

```text
1. Set display/session environment.
2. Set Dolphin/Mesa private Vulkan environment.
3. Verify private Mesa ICD exists.
4. Verify Double Dash game file exists.
5. Launch Dolphin directly into the game using Vulkan.
6. Log to ~/.cache/tvbox-doubledash.log.
7. Return Dolphin's exit code.
```

Draft wrapper:

```bash
#!/usr/bin/env bash
set -euo pipefail

LOG="$HOME/.cache/tvbox-doubledash.log"
MESA_PREFIX="/opt/mesa-26.1.2-bpo"
ICD="$MESA_PREFIX/vulkan-broadcom-mesa26.json"

# TODO: replace with confirmed path.
GAME="/home/tvbox/Games/ROMs/GameCube/Mario Kart Double Dash!!.rvz"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DISPLAY="${DISPLAY:-:0}"

# Proven working path for Dolphin on labwc/Wayland:
# Qt via XCB/XWayland, Vulkan via private Mesa 26 V3DV ICD.
export QT_QPA_PLATFORM=xcb
unset WAYLAND_DISPLAY
export VK_DRIVER_FILES="$ICD"

{
  echo "=== $(date -Is) tvbox-doubledash ==="
  echo "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
  echo "DISPLAY=$DISPLAY"
  echo "QT_QPA_PLATFORM=$QT_QPA_PLATFORM"
  echo "VK_DRIVER_FILES=$VK_DRIVER_FILES"
  echo "GAME=$GAME"

  if [ ! -f "$ICD" ]; then
    echo "ERROR: private Mesa 26 ICD is missing: $ICD" >&2
    exit 20
  fi

  if [ ! -f "$GAME" ]; then
    echo "ERROR: Double Dash game file is missing: $GAME" >&2
    exit 21
  fi

  exec /usr/games/dolphin-emu -v Vulkan "$GAME"
} 2>&1 | tee -a "$LOG"
```

## 8. Proposed tvboxctl integration

Add `doubledash` as a launch target.

Expected behavior:

```text
tvboxctl launch doubledash
```

Should:

```text
1. acquire tvboxctl lock;
2. request state transition for doubledash;
3. stop/close conflicting local apps;
4. stop Kodi playback if needed;
5. close Kodi before launching Dolphin, unless testing proves Dolphin can reliably overlay/focus above Kodi;
6. set active context to doubledash;
7. set input profile to passthrough or a new doubledash profile;
8. start /usr/local/bin/tvbox-doubledash without inheriting the tvboxctl lock FD;
9. reconcile process/toplevel state;
10. on failure, return to Kodi.
```

Home behavior:

```text
If doubledash/Dolphin is running:
  close Dolphin locally
  return to Kodi
  set Kodi input profile
```

Exit behavior:

```text
If doubledash/Dolphin is running:
  close Dolphin locally
  return to Kodi
  set Kodi input profile
```

There is no remote host state to preserve or hard-close.

## 9. Kodi add-on plan

Create:

```text
/opt/tvbox-system/kodi-addons/plugin.program.tvbox.doubledash/
```

Files:

```text
addon.xml
default.py
icon.png
fanart.png optional
```

`default.py` should call:

```python
subprocess.Popen(["/usr/local/bin/tvboxctl", "launch", "doubledash"])
```

The add-on should not launch Dolphin directly. It should always route through `tvboxctl` so locking, cleanup, state, input profile, and recovery stay centralized.

Suggested `addon.xml` identity:

```xml
<addon id="plugin.program.tvbox.doubledash"
       name="Mario Kart Double Dash"
       version="1.0.0"
       provider-name="TVBox">
```

Suggested summary:

```text
Launch Mario Kart Double Dash through TVBox.
```

## 10. Kodi Favourites

After installing the add-on, add it to Kodi Favourites.

Manual first test path:

```text
Kodi -> Add-ons -> Program add-ons -> Mario Kart Double Dash
```

Then add to Favourites once launch/recovery works.

## 11. Testing plan

### Graphics regression tests

Before integration:

```text
/usr/local/bin/tvbox-dolphin-mesa26 launches Dolphin
Double Dash launches
visual artifacts absent
Dolphin exits cleanly
Kodi/Plex still work after Dolphin exits
```

### Direct game boot tests

```text
/usr/local/bin/tvbox-doubledash launches directly into Double Dash
missing ROM path fails clearly
wrong ROM path fails clearly
Vulkan backend remains active
native Wayland is not used
XCB/XWayland path remains active
```

### tvboxctl launch tests

```text
Kodi menu -> tvboxctl launch doubledash
Plex playback -> tvboxctl launch doubledash
YouTube active -> tvboxctl launch doubledash
Moonlight active -> tvboxctl launch doubledash
Spotify active -> tvboxctl launch doubledash
Desktop/unknown -> tvboxctl launch doubledash
```

Expected:

```text
Only Dolphin/Double Dash owns the foreground.
Other local TVBox apps are closed or yielded according to existing policy.
Kodi does not remain fighting for focus.
State reports doubledash.
Input profile is correct.
```

### Home tests

```text
Double Dash running -> F12/Home closes Dolphin and returns Kodi
Double Dash loading -> F12/Home still returns Kodi
Dolphin error dialog -> F12/Home returns Kodi
Dolphin GUI open without game -> F12/Home returns Kodi
```

### Exit tests

```text
Double Dash running -> Exit closes Dolphin and returns Kodi
Dolphin GUI open -> Exit closes Dolphin and returns Kodi
```

### Kodi add-on tests

```text
Program add-on launches through tvboxctl.
Favourite launches through tvboxctl.
Repeated selection does not create duplicate Dolphin instances.
Launch failure returns Kodi.
```

### Reboot tests

```text
Cold reboot.
Kodi starts normally.
Plex works.
Double Dash launches from wrapper.
Double Dash launches from Kodi add-on.
Home returns Kodi.
```

## 12. Open questions

- What is the final stable ROM path?
- Does Dolphin command-line direct game launch work reliably with this Debian package?
- Does Dolphin expose a predictable Wayland/XCB window title or app_id for reconciliation?
- Should context be `doubledash`, `dolphin`, or `dolphin:doubledash`?
- Should input profile be `passthrough` or a new minimal Dolphin/GameCube profile?
- Should Kodi be closed before Dolphin launch every time, or only if focus/audio conflict is observed?
- Should the current `mariokart64` code be generalized to support multiple local game launchers?
- Should `/usr/local/bin/tvbox-dolphin-mesa26` remain a live-only helper, or be moved into `/opt/tvbox-system/bin/` as repo-owned code?

## 13. Recommended implementation phases

### Phase 1 — Preserve working helper

- Copy the proven XCB/Vulkan/Mesa26 Dolphin helper to a stable path.
- Confirm it still works after reboot.
- Confirm Kodi/Plex remain healthy after using it.

### Phase 2 — Direct Double Dash wrapper

- Find the ROM path.
- Create `/opt/tvbox-system/bin/tvbox-doubledash`.
- Symlink `/usr/local/bin/tvbox-doubledash`.
- Test direct game boot from SSH while the TV display is active.

### Phase 3 — tvboxctl target

- Add `doubledash` context.
- Add process detection for `dolphin-emu`.
- Add launch logic.
- Add Home/Exit close logic.
- Add status reporting.
- Add input profile choice.

### Phase 4 — Kodi add-on

- Create `plugin.program.tvbox.doubledash`.
- Install add-on into Kodi.
- Add to Favourites after direct add-on launch works.

### Phase 5 — Hardening

- Prevent duplicate Dolphin launches.
- Ensure transition lock is not inherited by Dolphin.
- Ensure launch failures recover to Kodi.
- Ensure F12/Home works in loading, gameplay, GUI, and error-dialog states.
- Add repo docs and redeploy notes.
