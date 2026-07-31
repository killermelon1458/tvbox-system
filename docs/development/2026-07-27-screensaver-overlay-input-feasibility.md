# Screensaver Overlay and Input Feasibility

## Goal

Determine, with evidence from this Raspberry Pi 5 TVBox, which Wayland overlay,
input-routing, activity-observation, lifecycle, runtime-state, and provider-state
designs are reliable enough to support a replacement screensaver implementation
plan.

The existing `docs/tvbox-screensaver-idle-architecture-plan.md` is treated as a
statement of desired behavior and architectural spirit, not as an approved
implementation specification.

## Current behavior

- Raspberry Pi OS runs a `labwc` Wayland desktop session.
- Kodi is the normal foreground application and is launched fullscreen.
- `tvboxctl` owns application lifecycle, Home/F12, Exit/F5, context, recovery,
  and input-profile transitions.
- `tvbox-inputctl` starts or stops AntiMicroX according to the active profile.
- No production TVBox screensaver or overlay manager exists.

## Problem being solved

Generic Wayland assumptions are not sufficient to decide whether a surface can
reliably cover fullscreen TVBox applications or whether the first wake input can
be consumed without breaking global recovery controls. The risky mechanisms
must be tested on the deployed compositor, applications, and input hardware
before implementation architecture is approved.

## Files expected to change

- `docs/development/2026-07-27-screensaver-overlay-input-feasibility.md`

Disposable probes, if needed, belong under:

```text
/tmp/tvbox-overlay-discovery/
```

The existing architecture plan and production code/configuration are not to be
changed during discovery.

## Proposed implementation

This is a discovery-only change:

1. Inventory repository and deployed session behavior.
2. Test minimal disposable normal-toplevel and layer-shell overlay candidates.
3. Test routing and observation for available input sources without broad grabs.
4. Define evidence-backed lifecycle, runtime/schema, and state-precedence
   contracts.
5. Recommend the smallest safe V1 and enumerate required changes for a future
   replacement plan.

## Environment and dependency inventory

Baseline observed 2026-07-27:

- Session: local seat0, Wayland, desktop `rpd-labwc`.
- Compositor: `labwc 0.8.4`.
- wlroots: `libwlroots-0.18 0.18.2-3+rpt4+b1`.
- Wayland client library: `libwayland-client0 1.24.0`.
- `wlrctl 0.2.2`.
- Kodi: running as `/usr/lib/aarch64-linux-gnu/kodi/kodi.bin -fs
  --audio-backend=alsa`; toplevel reported as `Kodi: Kodi from Debian`.
- TV state before visual testing: `standby`; DRM connected/enabled/DPMS On,
  CEC power standby, physical address `1.0.0.0`, logical address 4.
- User `tvbox` is a member of `input`; event nodes are `root:input 0660`.
- AntiMicroX is launched by `tvbox-inputctl` with the selected repo profile.
  At baseline it used `kodi_native_minimal.gamecontroller.amgp` and exposed
  separate virtual keyboard, relative mouse, and absolute mouse devices.
- Installed graphics/runtime candidates include GTK 3/4, Qt Wayland 5/6,
  SDL 2.32.4, `libgtk-layer-shell0 0.9.0`, and `swaylock`.
- GTK 3 Python GI is available.
- GtkLayerShell GI, Python evdev, PyWayland, `wayland-info`, and the
  `libgtk-layer-shell-dev` headers/pkg-config file are not installed.
- SDL exposes no discovered layer-shell API or hint on this installation.
- `swaylock` is not used as the probe because a real session lock introduces
  authentication and recovery risk.

Candidate probe dependency, not yet installed:

- `gir1.2-gtklayershell-0.1` allows a small Python/GTK probe without
  introducing production files or a compiler-built retained binary.
- It was installed with approval for discovery. `wtype` and `wev` were also
  installed with approval for non-grabbing Wayland input tests.
- `libgtk-layer-shell-dev`, Python evdev, PyWayland, and `wayland-utils` were
  not installed.

## Commands used

```bash
git status --short
bin/tvbox-tv status
bin/tvbox-tv status --json
tvbox-tv status
tvbox-tv status --json
systemctl --user --no-pager --type=service
systemctl --user status tvbox-focus-recovery.service --no-pager
tvboxctl status
wlrctl toplevel list
loginctl session-status --no-pager
env | grep -E '^(WAYLAND|DISPLAY|XDG_RUNTIME)'
labwc --version
dpkg-query -W
pkg-config --list-all
ls -l /dev/input /dev/input/by-id /dev/input/by-path
getfacl -p /dev/input/event*
libinput list-devices
tvbox-inputctl status
sudo apt-get install -y gir1.2-gtklayershell-0.1
sudo apt-get install -y wtype wev
tvbox-tv activate --json
grim /tmp/tvbox-overlay-discovery/<probe-result>.png
wtype -k Left
wtype -k F12
timeout 2 evtest <stable-by-id-path>
python3 -m unittest discover -s tests -v
git diff --check
git status --short
git diff --stat
```

The first live-session command attempt ran inside the workspace sandbox. It
could not reach the host user bus, compositor socket, or `/dev/input`, so those
failures were discarded as sandbox artifacts. The inventory above comes from a
subsequent approved read-only host inspection.

## Overlay mechanism results

### TV activation and output

Visual tests began only after:

```bash
tvbox-tv activate --json
tvbox-tv status --json
```

The canonical command reported `wake_sent`, then `active_source_sent`, then
`activated`. The final state was CEC power `on`, physical address `1.0.0.0`,
logical address 4, active source `1.0.0.0`, and `active=true`.

The Wayland session exposes one monitor:

```text
0: Hisense Electric Co., Ltd. HDMI
geometry: 1920x1080 at 0,0
scale: 1
DRM: card1-HDMI-A-2 connected
```

GtkLayerShell can explicitly bind a surface to a `GdkMonitor`. The probe used
the compositor default, which was unambiguous with one output. Production must
select the configured/connected TV output and must not depend on list order if
more than one output appears.

### Normal Wayland fullscreen/toplevel

Probe: normal GTK 3 window, fullscreen plus keep-above.

Observed:

- Initially covered fullscreen Kodi at 1920x1080.
- Appeared in `wlrctl toplevel list` as an ordinary toplevel.
- After `wlrctl toplevel focus app_id:Kodi`, Kodi immediately covered the probe.

Conclusion: **not reliable**. A labwc rule or keep-above normal toplevel is not a
sufficient V1 foundation because focus/fullscreen transitions can restack it.

### Layer-shell

Probe: GTK 3 plus GtkLayerShell 0.9.0, all four anchors, exclusive zone 0,
namespace `tvbox-overlay-discovery`.

Layer results over fullscreen Kodi:

| Layer | Above fullscreen Kodi | Result |
|---|---:|---|
| background | not separately tested | reject by protocol purpose |
| bottom | not separately tested | reject by protocol purpose |
| top | no | Kodi completely covered the probe |
| overlay | yes | retained visibility after Kodi was explicitly focused |

The overlay-layer surface did not appear in the ordinary toplevel list. It
covered the full output, did not reserve workspace area, and remained above
Kodi after an explicit Kodi focus request.

`overlay` also covered fullscreen Chromium/YouTube. A local Moonlight GUI
window was covered, but an actual fullscreen Moonlight stream was not started,
so fullscreen/direct-scanout Moonlight remains unproven. Steam Link did not
start successfully on this machine during the bounded test, so it remains
unproven.

Layer-shell settings supported by the evidence:

```text
layer: overlay
anchors: top + bottom + left + right
exclusive zone: 0
keyboard mode: on-demand for a dismissible screensaver
namespace: stable TVBox-specific identity
output: explicit GdkMonitor selection when possible
```

`keyboard=exclusive` was not needed to prove normal input consumption and could
unnecessarily interfere with another trusted layer-shell client. It should not
be the V1 default.

The probe logged a mapped event immediately after GTK mapping. Production
readiness must be stronger: send readiness only after the first frame has been
committed/configured, ideally after a frame callback, with a startup timeout.

TERM/INT caused the layer-shell probe to leave cleanly and expose the underlying
application. No audio API was opened.

### Existing wlroots-compatible tools

- `swaylock` is installed and uses Wayland, but was rejected as a discovery
  overlay because authentication/locking creates an unsafe recovery dependency.
- No suitable installed `swaybg`, `wbg`, `waylock`, `foot`, or layer-shell demo
  was found.
- SDL 2.32.4 is installed, but no installed SDL layer-shell API/hint was found.
  SDL fullscreen is therefore only a normal toplevel candidate here.
- GtkLayerShell is the smallest proven mechanism on this image.

## Input-source results

### Wayland keyboard routing

With the overlay-layer surface using `keyboard=on-demand`:

- A compositor-injected Left key was delivered to the overlay as press and
  release.
- The overlay handler returned handled/true.
- F12 was not delivered to the overlay.
- Labwc matched the repo `F12` binding and executed `tvbox-home`.
- `tvbox-recovery.log` gained exactly one `button=home ... action=home` record.
- Kodi remained running and context remained `kodi`.

This proves that on labwc 0.8.4 the compositor global keybind is evaluated
before normal focused-client delivery. It also proves that ordinary compositor
keyboard input can be consumed by the focused overlay while F12 remains global.

F5/Exit was not injected because it can be destructive by design. The binding
uses the same labwc mechanism as F12, so it is expected to remain global, but
that expectation is not promoted to a live-tested fact.

### Pointer routing

With the full-output layer-shell surface active, `wlrctl pointer move` and
`wlrctl pointer click left` produced motion, button press, and button release
only in the overlay log. Thus a full input region can consume pointer input
before it reaches the underlying client.

### Physical and synthetic sources

- FLIRC is a USB HID keyboard (`20a0:0006`) and exposes F12 plus ordinary keys.
  It was opened passively by stable by-id path while Kodi continued running.
  A timed physical remote press was not captured during this run, so physical
  FLIRC routing should receive a final acceptance test even though compositor
  routing is the same keyboard path tested with `wtype`.
- The mini keyboard and Logitech keyboard/mouse are normal libinput
  keyboard/pointer devices. Passive access was proven. Direct physical key and
  click timing was not captured; compositor-level keyboard and pointer delivery
  were proven.
- The 8BitDo exposes a physical joystick plus keyboard/mouse HID interfaces.
  The physical joystick has buttons and absolute axes. It can be passively
  observed concurrently with Kodi and AntiMicroX.
- Kodi directly held `/dev/input/js1`; AntiMicroX directly held the physical
  joystick event node.
- Layer-shell has no joystick/gamepad input protocol. Raw controller events are
  therefore not intercepted by the overlay and can still reach Kodi, Moonlight,
  Steam Link, or another direct consumer.
- In `kodi_native_minimal`, AntiMicroX maps only controller Home/Guide to F12 and
  Back/View to F5. Those generated keyboard events enter the compositor path;
  F12 follows the proven global route. Ordinary controller buttons remain raw.
- In generic controller-to-keyboard/mouse profiles, mapped synthetic events can
  reach the focused overlay. Observing both physical and AntiMicroX virtual
  devices would duplicate activity. The activity collector should observe
  physical devices as the primary source and ignore known AntiMicroX virtual
  devices by name/udev identity.
- Axis metadata reports `flat=128` and `fuzz=16`, but that kernel deadzone is too
  small to constitute a TVBox meaningful-activity policy. No long drift sample
  was collected. Axis wake is not safe for V1 until per-device hysteresis and
  dwell behavior are measured.

### First-event consumption conclusion

Reliable first-event consumption is proven for compositor-delivered keyboard
and pointer events when the overlay is keyboard-interactive and covers the
pointer input region. Global F12 is deliberately consumed by labwc instead and
executes Home.

It is **not** available for raw joystick/controller events. A passive evdev
observer sees the event after it has also been delivered to other readers. An
`EVIOCGRAB` design could intercept it but would break direct passthrough and
possibly AntiMicroX/global recovery; no broad grab was attempted.

Practical V1 policy:

1. Enable automatic screensavers only in contexts whose accepted wake devices
   route as keyboard/pointer through the compositor.
2. Let the overlay consume the first ordinary keyboard/pointer wake event.
3. Let F12 continue through labwc to normal Home semantics.
4. Inhibit automatic screensavers in Moonlight, Steam Link, native games, and
   controller-native Kodi operation until raw-controller wake behavior is
   intentionally accepted or safely mediated.
5. Do not use a post-dismiss guard as a substitute for interception: once a raw
   event reaches an underlying direct reader, a later guard cannot retract it.

## Capability matrix

`proven` means directly exercised on this machine. `expected` is an inference
from an exercised equivalent path and still needs an acceptance test.

| Mechanism/input | Observed | Intercepted | Global Home works | Safe for V1 |
|---|---:|---:|---:|---:|
| FLIRC keyboard | passive open proven | expected via keyboard focus | expected; F12 HID present | yes after physical acceptance |
| Physical keyboard | passive open + injected route proven | proven equivalent route | proven with injected F12 | yes |
| Mouse | passive open + injected route proven | proven equivalent route | n/a | yes |
| 8BitDo buttons | passive physical observation proven | no for raw buttons | mapped Guide→F12 expected | no |
| Controller axes | capabilities proven; drift unmeasured | no | n/a | no |
| AntiMicroX synthetic | virtual devices observed | expected for mapped keys/pointer | F12 mapping and global route expected | only mapped profiles after acceptance |
| CEC user control | not safely observed | no | not tested | no |
| Kodi fullscreen | n/a | n/a | proven | yes |
| Chromium fullscreen | n/a | n/a | proven | yes |
| Moonlight fullscreen | GUI only | n/a | not tested in stream | no |
| Steam Link fullscreen | launch failed | n/a | not tested | no |

## Exact Home/F12 behavior

The repo labwc configuration binds F12 to `/usr/local/bin/tvbox-home`.

With an input-interactive overlay-layer surface focused:

```text
F12
-> labwc consumes the global binding
-> overlay receives no F12 event
-> tvbox-home requests bounded TV activation
-> tvboxctl home runs existing context-specific non-destructive Home behavior
```

During the Kodi test, one injected F12 stopped playback/opened Favourites
through existing Home behavior and left Kodi running.

During the YouTube test, F12 closed the TVBox Chromium profile and set context
back to Kodi. Kodi did not relaunch automatically in that particular transition
and had to be restored through `/usr/local/bin/tvbox-kodi`. This existing race
is not caused by layer-shell stacking, but it proves that future overlay policy
must inhibit during transitions and reconcile facts after them rather than
trusting context alone.

Home must not be reimplemented inside the renderer. A future manager or
`tvboxctl` integration should synchronously invalidate the overlay request at
the beginning of Home, while the existing Home action remains authoritative.

## Activity-device permissions and hotplug findings

- Stable by-id links exist for the FLIRC keyboard, 8BitDo controller interfaces,
  mini keyboard interfaces, and Logitech keyboard/mouse devices.
- The current `tvbox` account can read event devices through membership in the
  `input` group. The 8BitDo joystick event also has a seat ACL.
- Group membership grants broad persistent access beyond the active login
  session; this is functional but less restrictive than logind-only ACL access.
- Event numbers are not stable and must not be configured directly.
- Passive `evtest` opens by stable path succeeded for FLIRC, the mini keyboard,
  and the physical 8BitDo joystick while Kodi and AntiMicroX remained running.
- `/dev/input/by-id` is preferred when present. A udev monitor must discover
  additions/removals and use properties plus device name/vendor/product/path
  when no by-id link exists.
- AntiMicroX virtual event numbers changed after Home restarted its process.
  They have no useful by-id link and are identifiable by device names
  `antimicrox Keyboard Emulation`, `antimicrox Mouse Emulation`, and
  `antimicrox Abs Mouse Emulation`.
- Failure to open any configured required activity source should set health to
  degraded and inhibit automatic screensaving for affected providers. It must
  not silently calculate idle from an incomplete device set.
- Python evdev is not installed. A future collector can use Python evdev after
  dependency approval or a small libevdev/epoll implementation; dependency
  choice is not needed for the overlay V1 proof.

### CEC

Kodi held both `/dev/cec0` and `/dev/cec1` during inspection. The optional
`tvbox-healthd-cec.service` is inactive and static by design pending coexistence
testing. No second persistent CEC client was started.

CEC user-control activity is therefore **unsupported for V1**. Status and
bounded activation continue through `tvbox-tv`; that does not establish a safe
passive user-control stream. A future test must prove that monitoring does not
steal or destabilize Kodi/libCEC before CEC can become an activity source.

## Overlay lifecycle contract recommendation

Use one manager process as the sole launcher/supervisor of overlay renderers.
The manager's in-memory process table is authoritative. JSON is a cache for
observation only.

### Request contract

```text
request:
  schema_version
  owner_service
  owner_instance_id
  owner_pid (diagnostic hint only)
  overlay_type
  renderer
  priority
  arguments validated against renderer allowlist
  lease_policy

response:
  request_id: random 128-bit opaque token
  generation: manager-local increasing integer
  state: starting
```

`owner_pid` must never be used alone for authority because PIDs are reusable.
The request ID is the capability required for renewal or release.

```text
request accepted
-> manager allocates request_id and generation
-> manager starts renderer in its own process group/cgroup
-> renderer creates overlay-layer surface
-> renderer reports first-frame readiness over inherited pipe/socket
-> manager marks request active and atomically publishes status
```

Release requires the exact `request_id`. An old release from the same owner
cannot affect a later request. A trusted administrative `release-all` may exist
behind a separate privileged interface; ordinary clients cannot release by
owner name.

### Lease policy

- Automatic/screensaver requests: finite lease, renewed by policy owner.
- Loading/recovery requests: finite startup deadline plus explicit renewal or
  trusted bounded persistence.
- Manual blank: trusted persistent request, explicitly released.
- Ordinary requests do not disappear merely because a short CLI connection
  closes; they are tied to the lease and token.
- Owner service restart loses its old token intentionally; the old finite lease
  expires, or a trusted manager API can enumerate only that authenticated
  service instance's requests.

### Arbitration and preemption

- Highest priority eligible request is active; equal priority uses newest
  generation.
- Preempted requests remain pending only if their declared policy permits it;
  otherwise they are cancelled.
- Notification is best-effort over a subscribed Unix socket/D-Bus signal.
  Correctness must not require receipt; status polling and lease expiry remain.
- A newly active request gets a new renderer generation. Late readiness/exit
  messages must include matching request ID and generation.

### Failure and reconciliation

- Startup timeout: terminate renderer process group, then bounded KILL fallback,
  publish `failed`, and do not claim active.
- Renderer crash: clear active state atomically, record exit status, and select
  the next eligible request. Restart only under a bounded per-request policy.
- Manager shutdown: TERM supervised groups, wait bounded time, KILL remaining
  groups, remove socket, atomically publish stopped status.
- Manager startup: ignore cached active/PID claims; create a fresh manager
  instance ID; terminate only processes carrying a manager-owned cgroup/unit or
  unforgeable launch marker; do not kill by executable name; do not adopt
  unknown renderers in V1; publish a fresh empty state before accepting work.
- Use pidfd/systemd scope identity where practical so PID reuse cannot cause an
  unrelated process to be signalled.
- Client restart does not resurrect cached requests. Only explicit fresh
  requests are accepted.

## Runtime path and JSON schema recommendations

### Runtime root

One helper must resolve:

```text
TVBOX_RUNTIME_ROOT override (tests only)
otherwise $XDG_RUNTIME_DIR/tvbox
systemd units use %t/tvbox
```

A user-session service should fail closed if `XDG_RUNTIME_DIR`/`%t` is missing
or not owned by the current UID. New services must not silently fall back to
`/tmp/tvbox`. Compatibility readers may inspect the existing `/tmp/tvbox`
fallback during migration, but must not mix writes across roots.

Create the directory mode 0700. Unix sockets and mutable state should be 0600;
read-only status may be 0640 only if a deliberate TVBox group consumer exists.

### Common JSON rules

Every document includes:

```text
schema_version
writer_instance_id
wall_time: RFC 3339 with offset, diagnostics only
boot_id: /proc/sys/kernel/random/boot_id
monotonic_seconds: boot-local ordering/duration only
```

Writers serialize to a same-directory temporary file, `fsync` when durability
of the observation matters, `rename` atomically, and ensure restrictive mode.
Readers reject unsupported schemas, malformed files, mismatched boot IDs for
monotonic calculations, and impossible field combinations.

Minimum schema payloads:

```text
overlay-status v1:
  manager_instance_id, state, active_request_id, generation, owner_service,
  overlay_type, renderer, priority, renderer_pid (diagnostic), ready,
  created_monotonic, lease_expires_monotonic, failure

activity-observation v1:
  collector_instance_id, health, required_sources, available_sources,
  last_activity_class, last_device_id, last_event_monotonic,
  ignored_reason, source_errors

idle-decision v1:
  policy_instance_id, state, provider, reason, inhibit_reasons,
  epoch_started_monotonic, deadline_monotonic, overlay_request_id

normalized-state v1:
  foreground_context, foreground_subcontext, context_confidence,
  concurrent_media_sessions, display, input_activity, idle_provider,
  overlay, transition, recovery, source_health

inhibitor-record v1:
  inhibitor_id, owner_service, owner_instance_id, reason, created_monotonic,
  expires_monotonic, persistent, generation
```

Inhibitor creation returns an opaque token. Release requires the token.
Non-persistent inhibitors require expiry. Cached files never grant authority.

## Foreground and concurrent-provider precedence recommendation

Do not overload `active-context`. Keep it as `tvboxctl` lifecycle intent and
expose reconciled foreground facts separately:

```text
lifecycle_context
foreground_context
foreground_subcontext
foreground_confidence
concurrent_media_sessions[]
transition_state
recovery_state
active_idle_provider
```

Deterministic selection:

1. Display absent or recovery active: inhibit; no visual provider.
2. Transition lock/inhibitor active: inhibit and release any old automatic
   overlay; never select from transient process combinations.
3. A high-confidence concurrent audio session whose policy intentionally owns
   visuals, such as Spotify playing: select Spotify while retaining the visible
   foreground separately.
4. Otherwise select a high-confidence reconciled foreground application.
5. If lifecycle context and process/toplevel evidence disagree, report the
   disagreement and inhibit until stable.
6. Unknown or unhealthy playback/activity evidence inhibits.

Required cases:

| Evidence | Foreground | Concurrent media | Idle result |
|---|---|---|---|
| Kodi visible, Spotify playing | Kodi | Spotify playing | Spotify provider after fresh epoch |
| Spotify begins under old saver | unchanged | Spotify playing | release old request, inhibit transition, then fresh Spotify epoch |
| Moonlight exits, Kodi relaunches | transitioning until Kodi toplevel stable | preserve separately | inhibit; then Kodi fresh epoch |
| YouTube process/toplevel, stale context Kodi | YouTube if stable and uniquely identified | as observed | report mismatch and inhibit until reconciled |
| Kodi process, no Kodi toplevel | unknown/degraded | as observed | inhibit |
| transition lock active | retain last known as diagnostic | retain facts | inhibit |
| display absent/recovering | retain underlying facts | retain facts | stop visual overlay and inhibit |

Provider selection must not mutate lifecycle context.

## Known limitations

- TV-visible results cannot be claimed until the TV is activated and the panel
  is confirmed visually.
- Moonlight and Steam Link tests may require deliberate application transitions;
  only the local Moonlight GUI was tested. No remote stream was started.
- No broad evdev grab will be tested during discovery.
- A Steam Link launch attempt produced no process/window but set lifecycle
  context to `steamlink`; Home restored Kodi.
- The normal YouTube Home transition set context to Kodi but did not relaunch
  Kodi in that run; the canonical Kodi wrapper restored it.
- Kodi JSON-RPC returned HTTP 401 during the probe, so playback/UI comparisons
  could not use unauthenticated JSON-RPC.
- Physical FLIRC, keyboard, mouse, and controller button presses were not
  captured interactively. Equivalent compositor routes and passive opens were
  tested, but device-specific acceptance remains.

## Recommended minimal implementation scope

### Milestone 0: retained feasibility test

Before a daemon, retain a small test-only GtkLayerShell overlay harness and
automated manager-contract tests. Add a manual acceptance checklist for:

- overlay layer above Kodi and Chromium,
- physical FLIRC/keyboard first-key consumption,
- physical mouse consumption,
- F12 global Home,
- TERM/crash cleanup,
- HDMI loss/reconnect.

### V1

Implement only:

1. A single manager with token-safe request/release, finite leases, renderer
   supervision, first-frame readiness, and startup reconciliation.
2. One solid black GtkLayerShell renderer using overlay layer, four anchors,
   exclusive zone 0, explicit output, on-demand keyboard, full pointer region,
   and no audio.
3. Manual request/release/status plus tests; no automatic idle policy initially.
4. Narrow passive physical keyboard/pointer activity health/observation,
   excluding known AntiMicroX virtual devices.
5. Integration at the beginning of Home/app transitions to invalidate an
   overlay token without changing underlying context.
6. Automatic policy only after manual lifecycle tests, initially for Kodi menu,
   desktop, and Spotify visual mode where playback evidence is high-confidence.

Exclude from V1:

- slideshow, bouncer, and video renderers,
- Moonlight and Steam Link automatic screensavers,
- native game/controller wake,
- controller axes,
- CEC user-control wake,
- DRM disable, picture-off, standby, and deep idle,
- loading-screen policy.

The same low-level manager can later accept loading-overlay requests with
different owner, priority, lease, and dismissal semantics. No second rendering
stack is needed.

## Specific required changes to the existing plan

A replacement implementation plan should:

1. Mandate GtkLayerShell/wlr-layer-shell overlay layer for the first renderer;
   reject normal fullscreen, top layer, and unspecified “Wayland-compatible”
   surfaces.
2. Define anchors, exclusive zone 0, output selection, namespace, keyboard
   on-demand, pointer region, and first-frame readiness.
3. Limit first-event consumption claims to compositor keyboard/pointer input.
   Explicitly state raw controller and CEC limitations.
4. Keep F12 in labwc and make renderers unaware of Home semantics.
5. Replace owner-name release with opaque request tokens and generations.
6. Add leases, manager instance IDs, process-group/pidfd supervision, failure
   backoff, and fresh-start reconciliation. Do not adopt arbitrary stale PIDs.
7. Make runtime JSON observational cache only and use
   `$XDG_RUNTIME_DIR/tvbox`/`%t/tvbox`, not UID 1000.
8. Add versioned schemas, boot ID, atomic replacement, ownership/mode rules,
   and monotonic reboot boundaries.
9. Split lifecycle context, reconciled foreground, concurrent media, transition,
   recovery, provider, and overlay facts.
10. Define conservative deterministic provider precedence and inhibit on
    disagreement or source-health loss.
11. Reduce the first milestone to one black renderer and manual lifecycle
    proof. Defer provider breadth and decorative renderers.
12. Add the observed YouTube/Steam Link transition inconsistencies to
    integration prerequisites; automatic idle must not rely on context alone.
13. Mark fullscreen Moonlight, Steam Link, physical FLIRC acceptance,
    controller drift, and CEC observation as unresolved gates rather than
    assumed support.

## Validation checklist

- [x] Repository and deployed-session baseline collected.
- [x] TV state checked before activation.
- [x] TV activated through canonical command for visual tests.
- [x] Normal fullscreen/toplevel candidate tested.
- [x] Layer-shell candidate tested.
- [x] Input routing and global key behavior tested with compositor injection.
- [x] Passive activity observation tested without an evdev grab.
- [x] Lifecycle and reconciliation contract documented.
- [x] Runtime and schema contract documented.
- [x] Foreground/concurrent provider precedence documented.
- [x] Capability matrix completed.
- [x] Repository validation completed.
- [x] Deploy validation status stated.

## Test results

### Proven

- Overlay layer covers and remains above fullscreen Kodi.
- Overlay layer covers fullscreen Chromium/YouTube.
- Top layer does not cover fullscreen Kodi.
- Normal fullscreen loses to Kodi when Kodi is focused.
- On-demand keyboard mode receives normal keys.
- Labwc F12 remains global and bypasses the overlay.
- Full-output layer surface receives pointer motion/click.
- Passive evdev opens coexist with Kodi and AntiMicroX for selected devices.
- Local Moonlight GUI is covered; no stream was started.
- Canonical TV activation works and confirms active source.

### Failed

- Steam Link did not create a process/window in the bounded launch test.
- The tested YouTube Home return did not automatically relaunch Kodi.
- Unauthenticated Kodi JSON-RPC returned HTTP 401.

### Uncertain

- Fullscreen Moonlight stream and Steam Link overlay behavior.
- Direct physical-device acceptance for FLIRC/keyboard/mouse.
- Raw controller wake side effects and axis drift thresholds.
- CEC user-control coexistence.
- Multi-output hotplug/output migration.

### Repository validation

```text
python3 -m unittest discover -s tests -v
28 tests passed

git diff --check
passed
```

`git diff --stat` is empty because both documents are currently untracked; Git
does not include untracked files in a normal diff. Final `git status --short`:

```text
?? docs/development/2026-07-27-screensaver-overlay-input-feasibility.md
?? docs/tvbox-screensaver-idle-architecture-plan.md
```

### Deploy/live validation

No production subsystem was installed, no repo installer was run, no service
was restarted, and no system or labwc configuration was changed.

Live discovery validation was run against the deployed labwc session, Kodi,
Chromium/YouTube, local Moonlight GUI, input devices, and canonical TV
activation. Kodi was restored at the end. Final state was:

```text
active-context: kodi
kodi-running: yes
other controlled apps: no
TV: on and active source
visible toplevel: Kodi
disposable overlay probes: none running
```

The approved discovery packages remain installed:

```text
gir1.2-gtklayershell-0.1
wtype
wev
```

They are tooling/dependency inventory changes on the live OS, not repo
deployment or production configuration.

## Known risks

- A keyboard-interactive layer-shell surface may alter global key routing.
- Input tests can activate the underlying UI if interception assumptions are
  wrong.
- Application transitions for Moonlight or Steam Link can affect the active
  foreground session even when their remote-host state is preserved.
- Starting another persistent CEC client may interfere with Kodi/libCEC.

## Rollback notes

No production files or services were changed. Disposable probe processes were
terminated. `/tmp/tvbox-overlay-discovery/` contains only disposable scripts and
screenshots and can be removed without affecting the appliance. No rollback of
`/usr/local/bin`, systemd, labwc, Kodi, or input-profile files is necessary.

If the discovery-only packages are no longer wanted, the exact removal command
is:

```bash
sudo apt-get remove gir1.2-gtklayershell-0.1 wtype wev
```

Do not remove `libgtk-layer-shell0`; it predated discovery and is used by
existing desktop components.

## Status

Status: validated
