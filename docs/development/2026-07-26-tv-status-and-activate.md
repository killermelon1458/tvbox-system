# TV Status and Activate Command

## Goal

Provide one reusable TV capability with two commands:

```text
tvbox-tv status
tvbox-tv activate
```

`activate` must safely wake the Hisense TV when necessary, wait through its
measured HDMI startup, and make the TVBox HDMI source active. Other input and
policy components can call it later.

## Current behavior

Raw CEC testing confirmed:

- TV logical address 0 answers power queries in about 60-100 ms.
- TVBox is Playback Device 1 at logical address 4 and physical address
  `1.0.0.0`.
- `IMAGE_VIEW_ON` is acknowledged and wakes the TV.
- HDMI and the TVBox CEC address temporarily disappear during wake.
- A manually timed TV power-on took 32 seconds before visible HDMI output.
- Sending `ACTIVE_SOURCE` too early occurs from the unregistered address and is
  not reliable.
- Kodi is configured to ignore TV standby; the Pi must never suspend or shut
  down as part of this feature.

## Problem being solved

Callers should not need to know CEC addresses, HDMI paths, wake timing, or
reallocation behavior. Repeated calls must not send duplicate wake sequences,
and calling activate while the TVBox is already active must be a no-op.

## Files expected to change

```text
bin/tvbox-tv
tests/test_tvbox_tv.py
docs/development/2026-07-26-tv-status-and-activate.md
```

The generic installer already links every `bin/tvbox*` executable.
Current-state documentation will be updated only after live validation.

## Proposed implementation

- `status` performs live bounded DRM and CEC checks and returns human-readable
  output or JSON.
- State values are `on`, `standby`, `transitioning`, `unavailable`, and
  `unknown`.
- Status records DRM connection/enabled/DPMS, CEC power state, physical and
  logical addresses, active-source physical address, evidence, and timestamp.
- The latest observation is cached below `/run/user/1000/tvbox` for diagnostics;
  policy decisions use fresh checks.
- `activate` uses a nonblocking lock to coalesce repeated calls.
- Already on and active at `1.0.0.0` is a strict no-op.
- Otherwise send `IMAGE_VIEW_ON`, poll for up to 45 seconds, require connected
  HDMI plus physical address `1.0.0.0`, logical address 4, and TV power on,
  then broadcast `ACTIVE_SOURCE`.
- The Hisense stops answering active-source queries after accepting the Pi's
  broadcast. A volatile local marker records the successful broadcast only
  while DRM, CEC power, physical address, and Playback address remain ready.
  Standby/disconnect or a reported different source clears the marker.
- Activation never restarts/focuses Kodi, changes input profiles, sends standby,
  or changes Pi power state.

## Commands used

```text
git status --short
cec-ctl topology, power, logical-address, and active-source queries
python3 -m py_compile
python3 -m unittest discover -s tests -v
python3 -m mypy
git diff --check
```

## Validation checklist

### Repo validation

- [x] Python syntax and typing pass.
- [x] Parsing tests cover all CEC power states and missing responses.
- [x] Classification tests cover connected/on, standby, transitioning,
      unavailable, and unknown.
- [x] Already-active activation is a no-op.
- [x] Repeated activation is coalesced by a lock.
- [x] Wake waits up to 45 seconds for delayed HDMI/CEC readiness.
- [x] Active source is not sent before Playback address 4 returns.
- [x] JSON output is stable and timestamped.
- [x] No standby, suspend, shutdown, Kodi action, or focus action exists.

### Deploy validation

- [x] Install `/usr/local/bin/tvbox-tv`.
- [x] Confirm status works without sudo.
- [x] Confirm activate is a no-op while already active.
- [x] Turn TV off and confirm activate wakes it after the observed long startup.
- [x] Confirm active source is sent only after address 4 returns.
- [x] Confirm repeated activate calls do not duplicate wake commands.
- [x] Confirm Pi, Kodi, SSH, controller, and FLIRC remain available.

## Test results

Repo validation:

```text
python3 -m py_compile bin/tvbox-tv
  passed

python3 -m unittest discover -s tests
  28 tests passed

python3 -m mypy --ignore-missing-imports bin/tvbox-tv
  passed with no issues

git diff --check
  passed
```

Live read-only `status` as the desktop user correctly reported:

```text
state: on
drm: connected
cec-power: on
physical-address: 1.0.0.0
logical-address: 4
active-source: 0.0.0.0
active: no
```

A live activation with the TV on transmitted wake and active-source, retained
full DRM/CEC readiness, and recorded volatile local active-source evidence.
The immediately repeated call returned `already_active` without transmitting
another wake.

The installed 45-second TV-off activation path was validated on 2026-07-26:

```text
wake_sent ok=True returncode=0
active_source_sent ok=True returncode=0
  physical_address=1.0.0.0 logical_address=4
activated state=on active_source=1.0.0.0

elapsed: 27.285 seconds
```

Final live status was:

```text
state: on
drm: connected
drm-enabled: enabled
drm-dpms: On
cec-power: on
physical-address: 1.0.0.0
logical-address: 4
active-source: 1.0.0.0
active: yes
evidence: drm_connected,cec_power_on,cec_playback_ready,local_active_source_sent
```

The Pi, SSH session, Kodi, controller, and FLIRC remained available.

## Known risks

- The TV may report CEC power `on` before visible HDMI is ready.
- HDMI may reconnect multiple times during the 45-second window.
- Active-source replies may be absent even when the TV accepted the broadcast.
- User access to `/dev/cec1` depends on the active-seat ACL.
- An input policy could call activate unintentionally; binding decisions remain
  outside this feature.

## Rollback notes

Remove `/usr/local/bin/tvbox-tv` or restore its timestamped installer backup.
No service, Kodi setting, Labwc binding, or live power policy is installed by
this change.

## Status

Status: validated

Repo validation, installation, idempotent on-state behavior, and the real
TV-off long-wake path are complete.
