# TVBox Screensaver, Scheduling, and Overlay Implementation Plan

**Status:** Implemented and live-validated 2026-07-31
**Scope:** Screensaver policy, scheduling, overlay lifecycle, black renderer, slideshow renderer
**Out of scope:** Loading-screen policy, deep-idle/CEC standby, controller interception, broad provider rollout

## 1. Purpose

This document replaces the earlier assumption-heavy screensaver plan with an implementation plan grounded in completed live discovery and the deployed application-state reconciliation system.

The first user-facing screensaver modes are:

1. **Black / blank**
2. **Picture slideshow**

The system must also support time-based scheduling so the preferred screensaver mode can change while a screensaver is already active.

Primary example:

```text
Daytime:
  slideshow

Midnight through configured morning time:
  black
```

At a schedule boundary, the active screensaver must switch modes without dismissing the screensaver, resetting idle time, changing the underlying application context, or briefly exposing the application underneath.

## 2. Proven foundation

Live discovery established:

- GtkLayerShell using the `overlay` layer stays above fullscreen Kodi.
- The same mechanism covers fullscreen Chromium/YouTube and the local Moonlight GUI.
- Four anchors plus exclusive zone `0` cover the TV output without reserving workspace space.
- A normal fullscreen/keep-above GTK window is not reliable.
- Layer-shell `top` is insufficient; `overlay` is required.
- Keyboard mode `on-demand` permits normal keyboard input to reach the overlay.
- F12 remains a labwc global binding and bypasses the overlay.
- A full-output layer surface receives pointer motion and clicks.
- Raw controller events cannot be intercepted by layer-shell.
- Passive evdev observation can coexist with Kodi and AntiMicroX for selected physical devices.

The deployed application-state refactor now separates lifecycle request, active transition, observed facts, stable reconciled state, and retained failure. `active-context` now represents stable accepted context rather than launch intent.

Implementation validation found that the current `wf-panel-pi` reserves a
36-pixel top zone. With zone `0`, the production surface was moved below that
zone and exposed a strip of Kodi. Production therefore uses layer-shell
exclusive zone `-1`: it ignores other clients' reserved zones while reserving
none itself. A `grim` capture verified an all-black 1920x1080 frame. The
overlay layer, four anchors, explicit output, on-demand keyboard mode, and
full pointer region remain unchanged.

## 3. Architectural boundaries

### 3.1 `tvboxctl`

Owns application lifecycle, Home/F12, Exit/F5, recovery, application transitions, and explicit global actions.

It does not own idle timers, screensaver scheduling, overlay rendering, image slideshow behavior, or schedule evaluation.

### 3.2 `tvbox-state`

Owns no mutable policy. It exposes a versioned normalized snapshot built from existing source facts, including stable foreground, lifecycle request and transition, display state, current input profile as observation, playback/session facts where available, overlay state, idle-policy state, and source health.

### 3.3 Idle policy

A future `tvbox-idled` component decides whether an automatic screensaver is allowed, whether inactivity crossed a timeout, whether state disagreement or unhealthy observation requires inhibition, and which provider policy applies.

Idle duration uses a monotonic clock.

### 3.4 Schedule policy

A schedule evaluator decides which screensaver mode is preferred at the current local wall-clock time, when the next boundary occurs, whether an already-active screensaver must switch renderers, and whether a manual override supersedes the schedule.

Scheduling is separate from idle detection.

### 3.5 Overlay manager

`tvbox-overlay` owns visible-overlay arbitration, renderer supervision, request tokens, generations, leases, preemption, readiness, crash cleanup, and safe live renderer replacement.

It is general-purpose infrastructure. Initial use is screensaver overlays. Future-compatible uses include loading, recovery, and manual blank overlays. No loading-screen policy is implemented by this plan.

### 3.6 Screensaver facade

A thin screensaver-specific client may request a typed `screensaver` overlay, select black or slideshow, expose manual commands, and derive status from the overlay manager.

It must not own a second mutable renderer lifecycle.

### 3.7 Renderers

Renderers only draw pixels. They do not choose policy, evaluate schedules, modify app context, change input profiles, launch or close applications, claim audio, or send CEC commands.

## 4. Initial component layout

```text
bin/
  tvbox-overlay
  tvbox-screensaver
  tvbox-render-black
  tvbox-render-slideshow

lib/tvbox/
  runtime.py
  atomic_json.py
  overlay/
    protocol.py
    manager.py
    supervision.py
  screensaver/
    schedule.py
    policy.py
    config.py

config/
  screensaver.toml
  systemd-user/
    tvbox-overlay.service

tests/
  test_overlay_protocol.py
  test_overlay_manager.py
  test_overlay_reconciliation.py
  test_screensaver_schedule.py
  test_black_renderer_contract.py
  test_slideshow_config.py
```

Exact names may vary if the repository already has stronger conventions.

## 5. Runtime path contract

Use one shared helper:

```text
TVBOX_RUNTIME_ROOT
  test override only

otherwise:
  $XDG_RUNTIME_DIR/tvbox

systemd:
  %t/tvbox
```

Do not hard-code `/run/user/1000/tvbox`.

Requirements:

- runtime root mode `0700`
- sockets and mutable control state mode `0600`
- versioned JSON
- atomic temporary-file-plus-rename replacement
- boot ID on boot-local state
- monotonic timestamps only for same-boot durations
- wall-clock timestamps only for diagnostics and schedule interpretation
- cached JSON never grants lifecycle authority

## 6. Overlay request contract

Every accepted request receives:

- opaque random 128-bit `request_id`
- manager-local `generation`
- manager instance ID
- owner service and owner instance ID
- overlay type and renderer
- validated renderer arguments
- priority
- lease policy
- creation time and lease expiry

Release and renewal require the exact request token. Owner-name-only release is not allowed. An old release must not stop a newer request from the same owner.

```text
request
-> validate
-> allocate request ID and generation
-> start renderer in owned process group/scope
-> await first-frame readiness
-> promote request active
-> publish status atomically
```

## 7. Lease and ownership model

Automatic screensaver requests use finite leases renewed by policy. Manual requests are finite by default, with optional trusted persistence. A short CLI disconnect does not cancel a request.

On manager restart:

- ignore cached PID claims
- create a new manager instance ID
- reconcile only manager-owned process groups/scopes
- terminate orphaned manager-owned renderers
- do not adopt unknown processes in V1
- publish a fresh empty state before accepting requests

## 8. Overlay arbitration

Initial priority order:

```text
recovery / panic
loading
manual blank
screensaver
notification
```

Loading remains future policy but is reserved in the generic type/priority design.

For equal priority, newest eligible generation wins unless request policy states otherwise. Preempted requests must explicitly declare whether they remain pending or are cancelled.

## 9. Renderer mechanism

Both V1 renderers must use:

```text
GtkLayerShell
layer = overlay
anchors = top + bottom + left + right
exclusive zone = 0
keyboard mode = on-demand
full pointer input region
stable TVBox namespace
explicit output selection
```

A renderer reports readiness only after a visible first frame has been committed. A mapped GTK window alone is insufficient.

Startup has a bounded timeout. Shutdown uses TERM, bounded wait, process-group/scope KILL fallback, and state updates only for matching request ID and generation.

## 10. Black renderer

Requirements:

- fully opaque black surface
- no audio
- no animation
- clean TERM
- first-frame readiness
- explicit output
- full keyboard/pointer coverage
- no app-context mutation
- no DRM disable
- no CEC standby

A black overlay is not equivalent to powering off the TV. Deep power-saving actions remain separate future policy.

## 11. Slideshow renderer

Slideshow is a V1 priority.

Required configuration:

- image root directory
- recursive or non-recursive scan
- image duration
- fit mode: contain or cover
- optional crop behavior
- optional shuffle
- supported extension allowlist
- transition behavior
- black background

Required behavior:

- validate image files
- respect EXIF orientation
- predecode the next image
- bound memory usage
- avoid audio
- skip unreadable/corrupt files
- report useful diagnostics
- first-frame readiness only after an image is visible or black fallback is committed

If no valid image is available:

```text
slideshow renderer
-> display black fallback
-> report degraded status
-> remain safely opaque
```

The underlying application must never be exposed because an image directory is empty or unavailable.

## 12. Schedule model

Scheduling chooses the preferred screensaver mode. It does not decide whether the system is idle.

Use a timezone-aware wall clock.

```toml
[screensaver]
default_mode = "slideshow"
timezone = "America/Chicago"

[[screensaver.schedule]]
start = "00:00"
end = "08:00"
mode = "black"
```

V1 requirements:

- fixed local-time ranges
- ranges crossing midnight
- deterministic precedence
- overlap validation
- calculate next boundary
- reevaluate at boundary
- reevaluate after restart, clock correction, resume, and config reload
- handle DST with timezone-aware local-time evaluation

Future-compatible but not required: weekday/weekend rules, sunrise/sunset, holidays, and temporary exceptions.

## 13. Active renderer switching at schedule boundaries

A currently active screensaver must switch immediately when the schedule-selected mode changes.

```text
23:59
  active renderer = slideshow

00:00
  schedule result = black
```

Required behavior:

```text
screensaver remains active
-> start replacement black renderer
-> wait for first-frame readiness
-> promote black generation
-> stop old slideshow renderer
```

Do not dismiss the saver, reset idle time, expose the underlying app, change context, record fake activity, restart the app, or require user input.

## 14. Gapless replacement contract

Incorrect:

```text
stop slideshow
-> expose underlying app
-> start black
```

Correct:

```text
start replacement
-> replacement commits opaque first frame
-> promote replacement generation
-> stop previous renderer
```

Two opaque overlay surfaces may briefly coexist. The new renderer must be fully opaque before the old renderer exits. Late readiness or exit events from the old generation must not affect the new state.

## 15. Manual mode control

Suggested commands:

```bash
tvbox-screensaver start
tvbox-screensaver stop
tvbox-screensaver status
tvbox-screensaver mode black
tvbox-screensaver mode slideshow
tvbox-screensaver mode scheduled
```

Semantics:

- `black`: force black while a screensaver is active
- `slideshow`: force slideshow while active
- `scheduled`: return to schedule selection
- `start`: activate using current effective mode
- `stop`: release caller's request
- `status`: derive typed status from overlay-manager state

Manual overrides are policy state, not renderer configuration.

## 16. Policy precedence

Recommended precedence:

```text
1. recovery/panic preemption
2. provider/screensaver inhibit
3. explicit provider forced mode
4. manual screensaver mode override
5. schedule-selected mode
6. configured default mode
```

Safety-oriented inhibition always wins.

## 17. Screensaver state versus overlay state

The overlay manager is authoritative for active renderer, request ID, generation, readiness, failure, and lease.

Screensaver status is derived from typed overlay requests plus policy facts:

- desired mode
- effective mode
- schedule result
- manual override
- idle reason
- provider reason

`tvbox-state` aggregates these into a read-only snapshot.

## 18. Home and input behavior

V1 behavior:

```text
ordinary keyboard/pointer wake
-> overlay consumes event
-> screensaver policy releases request
-> underlying app does not receive wake action
```

```text
F12/Home
-> labwc global binding
-> existing Home lifecycle
-> current screensaver request invalidated at transition start
-> canonical Kodi recovery as required
```

Renderers do not implement Home semantics.

Raw controller input is not interceptable through layer-shell. Automatic screensavers remain inhibited in controller-native contexts until deliberately accepted.

## 19. Automatic idle scope

Initial candidates:

- stable Kodi menu, after playback detection is trustworthy
- stable desktop
- Spotify visual mode, after its state source is integrated

Initially inhibit lifecycle transitions, recovery, state disagreement, unhealthy activity observation, Moonlight, Steam Link, Mario Kart/native games, unknown foreground, raw-controller-dependent contexts, and uncertain playback.

Manual black/slideshow operation does not require automatic provider support.

## 20. Implementation phases

### Phase 0 — Replace and approve plan

- mark the previous plan superseded
- retain both discovery reports
- reference the deployed application-state implementation

### Phase 1 — Overlay protocol and manager tests

Implement tests first for tokens, generations, leases, preemption, restart reconciliation, readiness timeout, crash handling, and replacement handoff.

No automatic idle policy.

### Phase 2 — Black renderer and manual lifecycle

Implement GtkLayerShell black renderer, readiness, manual request/release/status, Home/app-transition invalidation, and crash cleanup.

### Phase 3 — Slideshow renderer

Implement image loading, EXIF orientation, contain/cover, duration, predecode, black fallback, bounded memory, and diagnostics.

### Phase 4 — Schedule policy

Implement local-time parsing, next-boundary calculation, fixed ranges, effective mode, manual override, config reload, and restart/time-change reevaluation.

### Phase 5 — Gapless live replacement

Validate slideshow→black, black→slideshow, replacement failure, stale generation events, active/inactive schedule boundaries, and config changes while active.

### Phase 6 — Physical input acceptance

Test FLIRC ordinary wake, physical keyboard/mouse wake, F12/Home, input leakage, and degraded observation.

### Phase 7 — Narrow automatic idle policy

Enable only proven providers and contexts.

### Later phases

Broader providers, YouTube page/playback source, controller policy, Moonlight/Steam Link policy, Mario Kart readiness, loading overlays, picture-off/CEC standby/deep idle, video, and additional renderers.

## 21. Required tests

### Overlay manager

- exact-token release
- stale token cannot release newer request
- late readiness/exit ignored
- lease expiry
- startup timeout
- crash handling
- manager restart ignores stale cache
- unrelated PID never signalled

### Black renderer

- overlay layer
- full anchors
- exclusive zone zero
- readiness after first frame
- TERM cleanup
- no audio access

### Slideshow renderer

- valid image
- corrupt image skipped
- no valid images produces black
- EXIF orientation
- contain/cover
- predecode failure
- missing directory
- bounded scan
- readiness semantics

### Schedule

- daytime slideshow
- overnight black
- crossing-midnight range
- exact boundary
- overlap handling
- DST
- restart mid-range
- wall-clock jump
- config reload
- manual override and return to scheduled

### Replacement

- slideshow→black with no inactive gap
- black→slideshow with no inactive gap
- replacement failure leaves old renderer active
- successful replacement ends old generation
- no idle reset
- no context change

## 22. Deployment dependencies

Expected production dependency:

```text
gir1.2-gtk-3.0
gir1.2-gtklayershell-0.1
libgdk-pixbuf2.0-bin
heif-gdk-pixbuf
```

The installer ensures these packages and verifies JPEG, PNG, WebP, HEIC/HEIF,
and AVIF loader registration. Production remains Python + GTK 3 + GI +
GtkLayerShell.

Screensaver v1.1 accepts JPEG, PNG, WebP, HEIC/HEIF, and AVIF, plus static
GIF-first-frame, TIFF, and BMP where registered. It ignores videos (including
Live Photo `.mov`), SVG, DNG/RAW, and animation playback. Slideshow scanning
is Syncthing-safe, decoding is per-file and asynchronous, alpha is flattened
over black, and `contain` remains the default fit.

Activity-observation dependency selection is deferred until automatic idle work.

## 23. Initial-release done criteria

The initial release is complete when:

- black and slideshow work above fullscreen Kodi
- manual start/stop/status works
- requests use opaque tokens and generations
- automatic requests use finite leases
- readiness is first-frame based
- crashes and manager restart reconcile safely
- slideshow falls back to black
- schedule selects black/slideshow by local time
- active saver changes mode at boundaries
- mode changes do not reset idle or expose the app
- F12/Home remains global
- keyboard/pointer wake is accepted
- app context remains unchanged
- runtime paths use `$XDG_RUNTIME_DIR/tvbox`
- tests and live validation pass
- loading policy, controller interception, and deep idle remain out of scope

## 24. Final architectural rule

```text
Application state describes reality.
Idle policy decides whether a screensaver may be active.
Schedule policy chooses the preferred allowed mode.
The overlay manager owns visible lifecycle and safe replacement.
Renderers only draw black or slideshow content.
```
