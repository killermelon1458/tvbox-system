# Canonical Idle-State Implementation

Date: 2026-07-31

Status: validated, including physical FLIRC/keyboard/pointer input

## Goal

Implement observation-only `tvbox-activityd`, an idle-provider framework, and
`tvbox-idled`, publishing one canonical boot-local `idle-state.json`. The idle
engine must never request a screensaver/overlay, evaluate schedules, choose a
renderer, change input profiles, or perform lifecycle/recovery actions.

## Current behavior

TVBox has reconciled application state and a token-safe manual screensaver
stack, but no canonical activity record or idle answer. The live input tree has
FLIRC, physical keyboard/pointer interfaces, controller-derived HID interfaces,
raw gamepads, and AntiMicroX virtual keyboard/mouse interfaces. The desktop
user is in the `input` group; live node access and event behavior still require
validation on the deployed appliance.

## Problem being solved

Downstream policy needs one conservative, healthy, provider-aware idle fact
instead of independently interpreting timestamps and application context.

## Files expected to change

- `lib/tvbox/idle/` configuration, activity, provider, and engine modules
- `bin/tvbox-activityd`
- `bin/tvbox-idled`
- `config/idle.toml`
- `config/systemd-user/tvbox-activityd.service`
- `config/systemd-user/tvbox-idled.service`
- `bin/tvbox-state` read-only aggregation
- `install.sh`
- focused activity/provider/engine tests
- `docs/current-system-redeploy.md`
- canonical/prior idle plan status documentation where required

## Proposed implementation

`tvbox-activityd` passively opens approved evdev nodes without grabs, resolves
stable `/dev/input/by-id` identity where available, counts key/button down and
thresholded relative pointer motion, publishes source health, and rescans for
hotplug. AntiMicroX, controller-derived HID, raw controllers, and non-input
interfaces are excluded.

Providers are pure evaluators. Desktop is enabled. Kodi is implemented as a
conservative provider but inhibited until authoritative menu/playback evidence
exists. All other/unknown contexts inhibit.

`tvbox-idled` reads application and activity state, owns fresh boot-local
provider epochs and stability delay, and atomically publishes only
`idle-state.json`. Only healthy, eligible, stable timeout completion can set
`idle=true`.

## Commands used

```text
git status --short
git log -6 --oneline --decorate
read canonical plan, runtime helper, state CLI, installer, units, and tests
inspect /sys/class/input identities/capabilities and installed dependencies
```

## Validation checklist

### Repository validation

- [x] Stable identity and hotplug/event-number changes.
- [x] Key/button down counts; release ignored.
- [x] Pointer jitter ignored; accumulated movement counts.
- [x] AntiMicroX/controller/raw-gamepad devices excluded.
- [x] Source loss/error and recovery health.
- [x] Desktop provider eligibility and unsupported/Kodi inhibition.
- [x] Provider result contains no action/schedule/renderer concepts.
- [x] Provider/activity/config changes reset epochs.
- [x] Timeout, idle-pending, stability delay, idle, and late activity.
- [x] Transition, recovery, disagreement, degraded source, and display absence fail safe.
- [x] Restart starts a fresh epoch and old-boot state is rejected.
- [x] Schedule/screensaver state changes do not affect epochs.
- [x] Canonical JSON is schema/boot/writer identified, atomic, and mode 0600.
- [x] Static proof and integration test show no screensaver/overlay action.
- [x] Existing tests retained; syntax, compile, unit verify, and diff checks pass.

### Deployment/live validation

- [x] Installer deploys config, binaries, and user units idempotently.
- [x] Approved device inventory and open health recorded.
- [x] Physical keyboard activity updates activity state.
- [x] FLIRC key activity updates activity state (user-assisted).
- [x] Mouse movement updates activity; jitter rejection remains automated-test proven.
- [x] Accelerated isolated desktop timeout reaches pending then idle.
- [x] Activity returns isolated state to active.
- [x] Production stable Kodi remains inhibited without trustworthy playback evidence.
- [x] Source degradation/recovery and daemon restart begin fresh epochs.
- [x] No overlay request, renderer, or screensaver policy mutation occurs.
- [x] Final appliance is stable Kodi with idle inhibited and no overlay.

## Test results

### Repository

```text
python3 -m unittest discover -s tests -v
Ran 117 tests ... OK

bash -n install.sh
python3 -m compileall -q ...
systemd-analyze --user verify ...
git diff --check
```

Focused coverage includes stable by-id identity, event-number changes,
hotplug classification, key/button down, release rejection, pointer threshold,
AntiMicroX/controller exclusion, source loss/recovery, atomic activity state,
provider contracts, provider/config/activity epochs, timeout, stability delay,
late input, transitions, returning recovery, disagreement, display absence,
stale/missing activity, daemon restart, prior boot/malformed input, unrelated
schedule state, canonical permissions, and action-vocabulary exclusion.

### Deployment

`sudo /opt/tvbox-system/install.sh` deployed both repo symlinks, the idle TOML,
and user units. `tvbox-activityd.service` and `tvbox-idled.service` are enabled
and active. The live config was backed up as `idle.toml.bak.20260731-2300` and
the canonical repo config deployed byte-for-byte.

The live inventory opens these approved identities without grabs:

```text
Logitech K360                             keyboard
mini keyboard                            keyboard
mini keyboard Mouse                      pointer
flirc.tv flirc Keyboard                  flirc + keyboard
Logitech Wireless Device PID:4055        pointer
```

AntiMicroX virtual devices, 8BitDo controller keyboard/mouse interfaces, raw
Xbox gamepad, system/consumer/power controls, and HDMI nodes were present but
not opened. Source health is healthy for keyboard, pointer, and FLIRC with no
errors.

Production Kodi publishes `state=inhibited`, `idle=false`, reason
`provider-disabled-v1`. An isolated 10-second desktop-provider test used the
real activity collector: FLIRC and physical keyboard key-down events plus
physical Logitech pointer motion each advanced activity generation, returned
canonical idle to `active`, and caused the downstream automatic policy to
release its exact request.

The deployed binary was run against an isolated two-second desktop timeout:

```text
active false
idle-pending false
idle true
after-input active false (new epoch)
```

Production overlay active request, overlay request list, and screensaver
policy ownership fields were semantically identical before/after that idle
transition. Pausing only the exact activity daemon PID produced
`degraded/activity-state-stale`; resuming it restored healthy input and began a
fresh epoch. No overlay or renderer appeared.

## Final schema and state machine

`activity-state.json` contains writer/boot metadata, approved/excluded device
inventory, available sources, per-source health/errors, last meaningful event,
and activity generation. `idle-state.json` contains writer/boot/wall metadata,
state/idle, provider/context/confidence, epoch and pending timing, reasons,
inhibitors, timeout, activity generation, and nested source health.

Only healthy desktop eligibility can advance:

```text
active -> idle-pending -> idle=true
```

Any meaningful input or provider/context/health/config change starts a fresh
epoch. All uncertain or unsupported cases publish `idle=false`.

## Deferred and uncertain

- Kodi menu/playback eligibility awaits an authoritative state signal.
- Controller-native, CEC, and evdev-grab activity remain excluded.
- Automatic screensaver reaction to `idle=true` is not implemented.
- Mouse-button handling is automated-test proven; live thresholded physical
  pointer motion was user-assisted and passed.

## Known risks

Logind/udev ACLs may not grant the user service access to every physical input
node. Missing required sources must degrade rather than assert idle. FLIRC and
mouse behavior require user-generated physical input for final live proof.

## Rollback notes

Disable and stop `tvbox-idled.service` then `tvbox-activityd.service`; remove
only their deployed unit files/symlinks and boot-local `activity-state.json`
and `idle-state.json`, then run `systemctl --user daemon-reload`. Neither
service owns an overlay or application process, so rollback must not signal
screensaver renderers or controlled applications.
