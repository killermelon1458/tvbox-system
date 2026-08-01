# TVBox Screensaver and Idle Architecture Plan

> **Status: superseded for overlay/screensaver implementation.**
>
> This historical plan is retained for its broader idle-policy goals. The
> discovery-backed replacement is
> `docs/tvbox-screensaver-overlay-scheduling-implementation-plan.md`. Do not use
> this document as the implementation contract for the overlay manager,
> renderers, manual screensaver, or scheduling.
>
> Automatic idle determination is now governed by the narrower canonical plan
> `docs/tvbox-canonical-idle-state-engine-plan.md`. Provider/action coupling in
> this historical document is not the deployed idle-state contract.

## 1. Purpose

This document defines the planned architecture for TVBox idle detection, screensaver policy, overlay rendering, and application-specific idle providers.

The goal is to add configurable screensavers without turning idle handling into a monolithic feature or duplicating application lifecycle logic already owned by `tvboxctl`.

The design must support:

- Black-screen overlays
- TV/display-off actions
- Custom real-time renderers
- Picture slideshows
- Future video screensavers
- Application-specific idle policies
- Playback-aware idle detection
- Input-aware idle detection
- Future loading-screen overlays

This plan focuses on screensavers and idle behavior.

It does **not** define or implement a loading-screen policy engine. However, the overlay and renderer infrastructure created for screensavers must be general-purpose so future loading screens can use the same display layer without requiring a second competing fullscreen-overlay implementation.

## 2. Core Design Principles

### 2.1 Idle detection is its own policy subsystem

Idle detection must not be embedded inside `tvboxctl`, `tvbox-focusd`, application launch wrappers, screensaver renderers, or individual app processes.

The idle subsystem should consume normalized state, evaluate application-specific policy, and request an overlay or system action.

```text
state providers
    ↓
normalized TVBox state
    ↓
idle policy engine
    ↓
screensaver / standby decision
    ↓
overlay manager or tvboxctl action
```

### 2.2 `tvboxctl` remains the global command authority

`tvboxctl` remains responsible for application lifecycle, global Home/Exit/recovery behavior, application transitions, explicit standby or wake actions, stopping screensavers during context transitions, and delegating screensaver commands to the screensaver subsystem.

`tvboxctl` should not directly implement idle timers, input classification, playback detection, screensaver rendering, screensaver process supervision, or provider-specific idle policy.

Recommended authority model:

```text
tvboxctl
  Global command and lifecycle authority

tvbox-state
  Global read-only state authority

tvbox-idled
  Idle-policy decision authority

tvbox-overlay
  Visible-overlay arbitration and lifecycle authority

providers
  App-specific observation authority

renderers
  Pixel-output processes only
```

### 2.3 Screensaver state is separate from application context

A screensaver must not replace the current app context.

Correct:

```text
context=kodi
screensaver.state=active
screensaver.mode=slideshow
```

Incorrect:

```text
context=screensaver
```

The underlying context must remain available because other systems still need to know which application is underneath the overlay, which input profile is active, how Home and Exit should behave, which application should regain focus, whether playback is active or paused, whether Spotify or another app takeover is occurring, and whether HDMI recovery should target Kodi or another application.

### 2.4 Overlay policy and overlay rendering are separate

The idle engine decides **why and when** a screensaver should appear.

The overlay manager decides **which overlay is allowed to be visible**.

The renderer decides **what pixels are drawn**.

```text
tvbox-idled
  Why and when to show a screensaver

tvbox-overlay
  Which overlay owns the screen

tvbox-render-*
  How the overlay looks
```

### 2.5 Every supported app gets a provider contract

Every supported TVBox app or context should have an idle provider from the beginning, even when the initial provider only reports:

```text
enabled=false
inhibit=true
reason=not-yet-tuned
```

Initial providers should include Kodi, Plex through Kodi, YouTube, Spotify, Moonlight, Steam Link, Mario Kart 64, Desktop/unknown, and a future Bluetooth or network-audio receiver.

A provider existing does not mean sophisticated detection must be implemented immediately.

## 3. Existing Infrastructure to Reuse

The current repository already provides useful foundations:

- `tvbox-tv`: DRM/HDMI/CEC state observation, TV activation, and cached JSON state
- `tvboxctl`: active context, input profile, application lifecycle, Home/Exit/panic recovery, and locking
- `tvbox-diag`: Kodi JSON-RPC playback and GUI state plus process/display diagnostics
- `tvbox-focusd`: DRM hotplug observation and HDMI reconnect focus recovery
- systemd user services: established user-session supervision pattern
- tests: Python coverage for TV state, focus recovery, and diagnostics

The screensaver subsystem should extend these components rather than duplicate them.

## 4. Proposed Components

### 4.1 `tvbox-state`

Suggested path:

```bash
/opt/tvbox-system/bin/tvbox-state
```

Purpose:

- Collect and normalize read-only TVBox state
- Expose one structured JSON snapshot
- Avoid duplicated detection logic across policy engines

It should aggregate application context, application subcontext, input profile, actual running process reconciliation, playback state, display/HDMI/CEC state, Wayland readiness, last meaningful user activity, idle duration, transition/recovery state, screensaver state, overlay state, and temporary inhibitors.

Suggested interface:

```bash
tvbox-state status
tvbox-state status --json
```

`tvbox-state` must remain observation-only.

### 4.2 `tvbox-activityd`

Suggested path:

```bash
/opt/tvbox-system/bin/tvbox-activityd
```

Suggested service:

```bash
/opt/tvbox-system/config/systemd-user/tvbox-activityd.service
```

Purpose:

- Observe local input
- Classify meaningful user activity
- Update last-activity state
- Avoid treating device noise as user interaction

Suggested runtime state:

```text
/run/user/1000/tvbox/last-user-activity.json
```

Use monotonic time for idle calculations.

Meaningful activity should normally include keyboard key-down, FLIRC remote key-down, controller button-down, mouse button, significant mouse movement, controller axis movement crossing a configured threshold, touch input, and CEC user-control commands.

Normally ignore key release by itself, controller connection/disconnection, device enumeration, small analog drift, tiny pointer movement, repeated unchanged axis values, CEC power/status chatter, and synthetic status events.

A universal classifier should provide defaults, while the current input profile may refine behavior through files such as:

```text
config/idle/input-profiles/
├── defaults.toml
├── kodi_native_minimal.toml
├── controller_kbm_generic.toml
├── mariokart_n64.toml
└── passthrough.toml
```

The classifier should account for duplicate physical and synthetic AntiMicroX events where practical.

### 4.3 Idle providers

Suggested layout:

```text
lib/tvbox/idle/providers/
├── base.py
├── kodi.py
├── youtube.py
├── spotify.py
├── moonlight.py
├── steamlink.py
├── mariokart64.py
├── desktop.py
└── bluetooth_audio.py
```

Provider responsibilities:

- Determine whether the provider applies
- Observe app-specific activity or playback
- Normalize app-specific facts
- Report confidence
- Report whether idle policy should be inhibited
- Never directly start or stop overlays
- Never directly kill or launch applications

Providers should normalize into activity classes:

```text
media
audio
interactive
passive-ui
unknown
```

Media states:

```text
playing
paused
buffering
stopped
unknown
```

Confidence:

```text
high
medium
low
unknown
```

Unknown playback must not be treated as stopped. The safe default is to inhibit.

### 4.4 `tvbox-idled`

Suggested path:

```bash
/opt/tvbox-system/bin/tvbox-idled
```

Suggested service:

```bash
/opt/tvbox-system/config/systemd-user/tvbox-idled.service
```

Purpose:

- Read normalized state
- Select the active provider
- Track provider-local idle epochs and timers
- Evaluate declarative policy
- Request or release screensaver overlays
- Request explicit deep-idle actions through `tvboxctl` when configured

It must not render graphics, directly kill applications, directly manipulate focus, directly send broad CEC commands, or own application context.

Suggested idle states:

```text
ACTIVE
IDLE_PENDING
IDLE
INHIBITED
DISPLAY_ABSENT
RECOVERING
```

When a provider changes:

1. Release any screensaver owned by the previous provider.
2. Reset provider-local idle timers.
3. Evaluate immediate policy for the new provider.
4. Start a new idle epoch.
5. Allow the new provider to start its own screensaver later.

This prevents a newly activated app from inheriting stale idle time.

### 4.5 `tvbox-overlay`

Suggested path:

```bash
/opt/tvbox-system/bin/tvbox-overlay
```

Suggested service:

```bash
/opt/tvbox-system/config/systemd-user/tvbox-overlay.service
```

Purpose:

- Own the fullscreen overlay lifecycle
- Allow only one visible overlay at a time
- Arbitrate requests by owner, type, priority, and generation
- Supervise renderer startup and shutdown
- Expose current overlay state

This component must be general-purpose.

Initial use:

```text
screensaver overlays
```

Future use:

```text
loading overlays
recovery overlays
manual blank overlays
temporary informational overlays
```

Overlay types:

```text
screensaver
loading
recovery
blank
notification
```

Suggested priority order:

```text
recovery / panic
loading
manual blank
screensaver
notification
```

Suggested interface:

```bash
tvbox-overlay request   --owner tvbox-idled   --type screensaver   --renderer slideshow   --priority 20   --reason input-idle

tvbox-overlay release --owner tvbox-idled

tvbox-overlay status
tvbox-overlay status --json
```

Suggested runtime state:

```text
/run/user/1000/tvbox/overlay-state.json
/run/user/1000/tvbox/overlay.lock
```

Overlay lifecycle:

```text
inactive
starting
active
stopping
failed
```

Do not report an overlay as active until the renderer confirms successful startup. Generation IDs should prevent stale stop or exit events from modifying a newer overlay instance.

### 4.6 `tvbox-screensaver`

Suggested path:

```bash
/opt/tvbox-system/bin/tvbox-screensaver
```

Purpose:

- Provide screensaver-specific commands
- Translate screensaver requests into generic overlay requests
- Expose screensaver-specific state
- Keep policy separate from rendering

Suggested interface:

```bash
tvbox-screensaver start black
tvbox-screensaver start slideshow
tvbox-screensaver start bouncer
tvbox-screensaver start video --asset <path>
tvbox-screensaver stop
tvbox-screensaver status
```

`tvboxctl` may expose delegating compatibility commands:

```bash
tvboxctl screensaver start black
tvboxctl screensaver stop
tvboxctl screensaver status
```

### 4.7 Renderers

Suggested paths:

```text
bin/tvbox-render-black
bin/tvbox-render-slideshow
bin/tvbox-render-bouncer
bin/tvbox-render-video
```

Renderers should create a fullscreen Wayland-compatible surface, draw only assigned content, avoid audio unless explicitly required, handle TERM cleanly, report readiness, exit meaningfully, and avoid all global policy.

The first implementation should prioritize black, bouncer, and slideshow. Video remains an explicitly supported future renderer.

## 5. Screensaver State

Screensaver state remains separate from app context and generic overlay state.

Suggested runtime state:

```text
/run/user/1000/tvbox/screensaver-state.json
```

Track at least:

```text
state
mode
reason
provider
underlying context
start time
generation
```

The generic overlay state remains authoritative for whether a renderer is actually active.

## 6. Dismissal and Invalidation Policy

Button presses are the primary user-facing way to dismiss a screensaver.

System events may also invalidate the current saver.

### User activity

Examples:

- Remote button press
- Keyboard key-down
- Controller button-down
- Meaningful controller axis movement
- Mouse button
- Significant mouse movement
- CEC user-control command

Flow:

```text
meaningful activity
-> update activity timestamp
-> request saver stop
-> optionally consume wake event
```

The wake event should normally be consumed so it does not accidentally activate the app underneath. Home/F12 remains special and should continue its normal global behavior.

### System invalidation

Examples:

- Spotify playback activates
- Bluetooth audio activates
- YouTube playback starts
- Application context changes
- TV/HDMI becomes unavailable
- Recovery begins
- Explicit app launch begins
- Provider policy changes to inhibit

These events stop the old saver without recording fake user input.

Suggested stop reasons:

```text
user-input
context-change
playback-started
display-lost
manual
recovery
provider-inhibit
overlay-preempted
```

### Spotify behavior

Spotify activation normally invalidates a saver owned by the previous provider.

Then:

```text
Spotify provider becomes active
Spotify idle epoch resets
Spotify policy starts fresh
Spotify may later enable slideshow, bouncer, black, or another saver
Spotify audio remains active when configured
```

A future Bluetooth or network-audio provider should follow the same pattern.

## 7. Provider Configuration

Suggested layout:

```text
config/idle/
├── defaults.toml
├── providers/
│   ├── kodi.toml
│   ├── youtube.toml
│   ├── spotify.toml
│   ├── moonlight.toml
│   ├── steamlink.toml
│   ├── mariokart64.toml
│   ├── desktop.toml
│   └── bluetooth_audio.toml
└── input-profiles/
    ├── defaults.toml
    ├── kodi_native_minimal.toml
    ├── controller_kbm_generic.toml
    ├── mariokart_n64.toml
    └── passthrough.toml
```

Example conservative policies:

```text
Kodi/Plex playing:
  inhibit

Kodi/Plex paused:
  black after 15 minutes

Kodi/Plex menu:
  slideshow after 10 minutes

YouTube playing:
  inhibit

YouTube paused:
  black after 15 minutes

YouTube menu:
  slideshow after 10 minutes

Spotify playing:
  slideshow after 2–5 minutes
  preserve audio

Moonlight:
  provider exists
  disabled / inhibit initially

Steam Link:
  provider exists
  disabled / inhibit initially

Mario Kart 64:
  provider exists
  disabled initially or black after 15 minutes

Desktop:
  black after 5 minutes

Unknown:
  inhibit
```

## 8. Playback Detection

### Kodi and Plex

Use Kodi JSON-RPC. Plex remains a Kodi subcontext rather than a separate process.

### YouTube

Preferred long-term order:

1. Browser extension or page helper reporting HTML media state
2. Chrome DevTools Protocol
3. Media Session/MPRIS if available
4. Narrow playback heuristics
5. Unknown and inhibit

Chromium process existence is insufficient.

### Spotify

Use Raspotify/librespot events as the playback authority. Do not infer playback from the visual placeholder.

### Moonlight and Steam Link

Initial providers may remain disabled or inhibited but should still exist and report session state where possible.

### Native games

Initial providers may use meaningful input as primary evidence. Unknown activity should fail safely.

## 9. Idle Inhibitors

Suggested runtime directory:

```text
/run/user/1000/tvbox/idle-inhibitors/
```

Examples:

- Application transition in progress
- HDMI recovery in progress
- Diagnostic collection running
- Renderer starting or stopping
- TV activation in progress
- Manual screensaver disable
- Software update or maintenance

Temporary inhibitors should expire automatically unless explicitly persistent.

## 10. Application Transition Integration

Before launching or switching apps, `tvboxctl` should request the current screensaver overlay to stop.

```text
tvboxctl launch youtube
-> release screensaver with reason=context-change
-> continue normal YouTube transition
```

Panic recovery should also release or preempt the saver before local cleanup.

A saver must not survive an app transition unexpectedly, change input profile, close the underlying app, claim ALSA, replace active context, or trigger remote Sunshine cleanup.

## 11. Display and Standby Policy

Keep these distinct:

```text
black overlay
TV picture-off
HDMI output disable
TV standby/off
```

Initial work should prioritize rendered black because it preserves HDMI stability.

Do not initially implement screen-off by disabling the DRM output.

When display becomes unavailable:

```text
stop active visual renderer
do not record fake user activity
preserve provider state as policy requires
enter DISPLAY_ABSENT
```

When display returns:

```text
enter RECOVERING
allow existing HDMI/focus recovery to complete
re-evaluate provider and idle state
do not restore a stale overlay without reevaluation
```

## 12. Future Loading-Screen Compatibility

This plan does not implement a loading-screen engine.

However, `tvbox-overlay` and renderer interfaces must support future loading overlays.

Screensaver:

```text
Triggered by idle policy
Usually dismissed by meaningful input or context invalidation
```

Loading overlay:

```text
Triggered by an application transition
Dismissed by readiness, completion, cancellation, timeout, or failure
```

The shared overlay manager must support multiple owners, overlay type, priority, generation, explicit release, preemption, underlying context, and renderer readiness.

Do not hard-code screensaver-only assumptions into the overlay manager or renderer protocol.

## 13. Repository Layout

Suggested additions:

```text
tvbox-system/
├── bin/
│   ├── tvbox-state
│   ├── tvbox-activityd
│   ├── tvbox-idled
│   ├── tvbox-overlay
│   ├── tvbox-screensaver
│   ├── tvbox-render-black
│   ├── tvbox-render-bouncer
│   └── tvbox-render-slideshow
├── lib/
│   └── tvbox/
│       ├── state/
│       ├── idle/
│       │   └── providers/
│       └── overlay/
├── config/
│   ├── idle/
│   │   ├── defaults.toml
│   │   ├── providers/
│   │   └── input-profiles/
│   └── systemd-user/
│       ├── tvbox-activityd.service
│       ├── tvbox-idled.service
│       └── tvbox-overlay.service
├── assets/
│   └── screensaver/
├── tests/
│   ├── test_tvbox_state.py
│   ├── test_tvbox_activityd.py
│   ├── test_tvbox_idled.py
│   ├── test_tvbox_overlay.py
│   └── test_idle_providers.py
└── docs/
    └── tvbox-screensaver-idle-architecture-plan.md
```

## 14. Implementation Phases

### Phase 1 — Normalize state

Implement `tvbox-state`, provider base contract, Kodi provider, Spotify provider, provider stubs for other supported apps, structured context/subcontext, confidence fields, JSON output, and tests.

### Phase 2 — Meaningful activity collection

Implement `tvbox-activityd`, default classifier, input-profile overrides, monotonic timestamps, noise rejection, and basic deduplication.

### Phase 3 — Generic overlay manager

Implement `tvbox-overlay`, request/release/status, single visible overlay, priority, generation handling, renderer readiness, and clean shutdown. It must remain suitable for future loading overlays.

### Phase 4 — Screensaver lifecycle wrapper

Implement `tvbox-screensaver`, screensaver state, overlay integration, manual start/stop/status, and `tvboxctl` delegation. No automatic idle behavior yet.

### Phase 5 — Initial renderers

Implement and manually test black, bouncer, and slideshow.

### Phase 6 — Idle policy daemon

Implement `tvbox-idled`, provider selection, provider-local timers, idle state machine, stability delay, inhibitors, screensaver requests, and context-change invalidation.

### Phase 7 — Provider expansion and tuning

Tune Kodi/Plex, YouTube, Spotify, Mario Kart, Moonlight, Steam Link, desktop, and future Bluetooth/network audio.

### Phase 8 — Display-off and deep-idle actions

Only after overlay screensavers and HDMI recovery are proven stable, add TV standby, picture-off if supported, long-idle cleanup, and deep-idle policy.

## 15. Testing Requirements

### State tests

- Correct provider selected for every supported context
- Structured context retained while saver is active
- Unknown playback never becomes falsely stopped
- Provider activation resets provider-local timer
- Spotify activation invalidates previous saver
- Display loss stops renderer without fake activity

### Activity tests

- Button-down counts
- Release-only does not count
- Axis drift does not count
- Threshold crossing counts
- Pointer jitter does not count
- Meaningful pointer movement counts
- Controller reconnect does not count
- Profile overrides apply

### Overlay tests

- Only one overlay is active
- Higher priority preempts lower priority
- Stale generation cannot stop newer overlay
- Renderer startup failure reports failed
- Renderer crash clears active state
- Release by owner works
- Screensaver does not replace application context

### Policy tests

- Playback inhibits saver
- Paused timeout differs from menu timeout
- Spotify may preserve audio under slideshow
- Disabled provider inhibits
- Context change releases previous saver
- Unknown state fails safely
- Temporary inhibitor expires

### Integration tests

- Home/F12 works through active saver
- Wake input does not accidentally activate underlying UI
- Spotify activation stops old saver
- Spotify provider can start its own saver later
- App launch stops saver before transition
- Panic recovery preempts or releases saver
- HDMI reconnect recovery does not fight overlay manager

## 16. Safety Rules

- Do not replace active context with screensaver.
- Do not let providers perform actions.
- Do not let renderers perform policy.
- Do not let `tvbox-idled` kill or launch apps directly.
- Do not broad-kill Chromium.
- Do not interfere with Moonlight remote host state.
- Do not claim ALSA from visual renderers.
- Do not disable DRM output in the first implementation.
- Do not treat unknown playback as stopped.
- Do not allow stale inhibitors or generations to persist indefinitely.
- Do not allow multiple fullscreen overlay processes to compete.
- Do not let wake input leak through by default.
- Do not build a separate future loading-screen rendering stack.

## 17. Done Criteria

The initial architecture is complete when:

- Every supported app has an idle provider and config.
- `tvbox-state` exposes normalized structured state.
- `tvbox-activityd` records meaningful input reliably.
- `tvbox-idled` evaluates provider-specific policy.
- `tvbox-overlay` owns one visible overlay at a time.
- Screensaver state remains separate from app context.
- Black, bouncer, and slideshow work manually.
- Automatic policy works in at least Kodi menu and Spotify.
- Playback prevents saver activation where configured.
- Spotify activation stops a previous saver and starts a fresh provider epoch.
- Home/F12 reliably dismisses or supersedes the saver.
- App transitions release active savers.
- Unknown state fails safely.
- The overlay manager remains suitable for future loading screens.
- All components are deployed from the repo and covered by tests.

## 18. Final Design Decision

The TVBox screensaver system will use:

```text
App-specific providers
Input-profile-aware activity classification
A dedicated idle policy engine
A separate structured screensaver state
A general-purpose overlay manager
Dumb reusable renderers
tvboxctl as the global command authority
tvbox-state as the global read-only state authority
```

The application context remains unchanged while a screensaver is active.

Button presses are the primary user-facing dismissal mechanism, while context changes, playback activation, display loss, recovery, and explicit subsystem takeovers may also invalidate the current saver.

Spotify and future audio-receiver providers may intentionally allow screensaver overlays while audio continues.

Future loading screens will use the same overlay manager and renderer contract, but remain a separate policy feature with different triggers and dismissal conditions.
