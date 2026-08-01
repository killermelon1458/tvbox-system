# TVBox Canonical Idle-State Engine Plan

**Status:** Implemented and live-validated 2026-07-31; physical keyboard/pointer confirmation pending
**Scope:** Determining whether TVBox is idle and publishing canonical idle state  
**Out of scope:** Screensaver activation, renderer control, scheduling, overlay lifecycle, input-profile changes, loading screens, deep-idle actions

> Downstream automatic reaction was implemented separately on 2026-07-31 in
> `tvbox-screensaverd`. This does not change the canonical idle engine's
> observation-only boundary.

## 1. Purpose

This plan defines a narrow idle-state subsystem whose only responsibility is to answer:

```text
Is TVBox idle right now?
```

The idle subsystem observes reconciled application state, meaningful user activity, and app-specific provider rules. It then publishes one canonical idle-state record.

It does not start or stop screensavers.

A separate screensaver policy service reads canonical idle state and reacts through the already-deployed screensaver and overlay systems.

## 2. Core architecture

```text
tvbox-state
    +
tvbox-activityd
    +
app-specific idle providers
    ↓
tvbox-idled
    ↓
canonical idle-state.json
    ↓
tvbox-screensaverd
    ↓
existing schedule + screensaver + overlay stack
```

Core rule:

```text
tvbox-idled determines idle.
The screensaver system reacts to idle.
```

## 3. Responsibility boundaries

### 3.1 `tvbox-state`

Provides reconciled facts:

- stable foreground application;
- lifecycle request and transition state;
- recovery state;
- display state;
- playback/session evidence where available;
- current input profile as observation;
- source confidence and disagreement.

It does not decide idle policy.

### 3.2 `tvbox-activityd`

Provides:

- last meaningful user activity;
- activity-source health;
- available and missing input sources;
- device identity and activity class.

It does not decide whether the TVBox is idle.

### 3.3 Idle providers

Each provider interprets one application/context and returns:

- whether it applies;
- whether idle determination is currently possible;
- timeout;
- activity basis;
- inhibition reasons;
- confidence.

Providers do not start screensavers, choose black or slideshow, evaluate schedules, mutate application state, or change input profiles.

### 3.4 `tvbox-idled`

Owns:

- provider selection;
- provider-local idle epochs;
- timeout evaluation;
- canonical idle state;
- confidence and inhibition;
- state publication.

It does not request overlays, hold overlay tokens, renew renderer leases, choose a screensaver mode, evaluate wall-clock schedules, dismiss renderers, or perform Home/application recovery.

### 3.5 `tvbox-screensaverd`

A separate downstream service owns automatic screensaver reaction:

- reads canonical idle state;
- creates or releases the automatic screensaver request;
- consumes the existing schedule-selected mode;
- preserves manual override behavior;
- tracks its own overlay request token.

This service is not implemented by this plan unless explicitly scheduled as a later task.

### 3.6 Existing screensaver and overlay systems

Continue to own:

- black/slideshow mode;
- schedule changes;
- live renderer replacement;
- overlay request tokens;
- generations;
- leases;
- renderer supervision;
- visible state.

## 4. Canonical idle state

Suggested path:

```text
$XDG_RUNTIME_DIR/tvbox/idle-state.json
```

This is the canonical answer for idle consumers.

Example:

```json
{
  "schema_version": 1,
  "writer_instance_id": "opaque-id",
  "boot_id": "linux-boot-id",
  "wall_time": "2026-07-31T22:00:00-05:00",
  "state": "idle",
  "idle": true,
  "provider": "desktop",
  "provider_context": "stable-desktop",
  "confidence": "high",
  "epoch_started_monotonic": 12000.0,
  "idle_since_monotonic": 12300.0,
  "timeout_seconds": 300,
  "reasons": [
    "stable-desktop",
    "no-meaningful-input-for-timeout"
  ],
  "inhibit_reasons": [],
  "source_health": {
    "application_state": "healthy",
    "activity": "healthy",
    "provider": "healthy"
  }
}
```

Consumers should treat `state=idle` and `idle=true` as the only positive idle assertion.

Unknown, degraded, inhibited, transitional, or recovering states are not idle.

## 5. Idle state vocabulary

Recommended states:

```text
active
idle-pending
idle
inhibited
unknown
degraded
display-absent
recovering
```

- `active`: idle determination is healthy, but timeout has not elapsed.
- `idle-pending`: timeout elapsed, but a short stability delay is running.
- `idle`: all required evidence is healthy and timeout elapsed.
- `inhibited`: current provider or global state explicitly prevents idle.
- `unknown`: idle cannot be determined confidently.
- `degraded`: required activity or application evidence is incomplete.
- `display-absent`: display is unavailable; do not assert `idle=true`.
- `recovering`: display, focus, or application recovery is active.

## 6. Runtime-state contract

Use the repository’s shared runtime helper:

```text
TVBOX_RUNTIME_ROOT
  tests only

otherwise:
  $XDG_RUNTIME_DIR/tvbox

systemd:
  %t/tvbox
```

Requirements:

- runtime root mode `0700`;
- state file mode `0600`;
- `schema_version`;
- `writer_instance_id`;
- `boot_id`;
- RFC 3339 wall-clock timestamp for diagnostics;
- monotonic time only for same-boot durations;
- atomic temporary-file-plus-rename replacement;
- malformed and unsupported state rejected safely;
- prior-boot monotonic values ignored.

## 7. `tvbox-activityd`

Suggested path:

```text
bin/tvbox-activityd
```

Suggested service:

```text
config/systemd-user/tvbox-activityd.service
```

### V1 sources

Initially observe only:

- FLIRC keyboard;
- physical keyboards;
- physical pointer devices.

Explicitly exclude known AntiMicroX virtual devices.

Do not configure unstable `/dev/input/eventN` paths.

Preferred identity:

1. `/dev/input/by-id`;
2. udev properties;
3. documented device-name fallback.

### Meaningful activity

Count:

- key-down;
- mouse button-down;
- accumulated meaningful pointer motion.

Ignore:

- release-only events;
- attach/detach;
- enumeration;
- pointer jitter;
- synthetic status events;
- AntiMicroX virtual duplicates.

### Health

Publish:

- required sources;
- available sources;
- source errors;
- health state;
- last meaningful event.

If a provider requires a missing source:

```text
activity health degraded
-> tvbox-idled must not assert idle
```

### Controller and CEC scope

V1 does not use:

- raw controller input as a safe wake basis;
- controller axis drift;
- evdev grabs;
- CEC user-control observation.

These may be added later without changing the canonical idle contract.

## 8. Provider contract

Suggested result:

```json
{
  "schema_version": 1,
  "provider": "desktop",
  "applies": true,
  "eligible": true,
  "timeout_seconds": 300,
  "required_activity_sources": [
    "keyboard",
    "pointer"
  ],
  "confidence": "high",
  "inhibit": false,
  "reasons": [
    "stable-desktop"
  ]
}
```

Inhibited example:

```json
{
  "provider": "steamlink",
  "applies": true,
  "eligible": false,
  "timeout_seconds": null,
  "confidence": "high",
  "inhibit": true,
  "reasons": [
    "provider-disabled-v1"
  ]
}
```

Providers define when the TVBox becomes idle for that app/context.

They do not mention black, slideshow, schedules, renderers, overlays, or request tokens.

## 9. Provider selection

Recommended precedence:

1. Display absent or recovering → non-idle canonical state.
2. Recovery active → recovering.
3. Application transition active → inhibited.
4. Reconciled-state disagreement → degraded or unknown.
5. High-confidence concurrent media provider that explicitly owns idle policy.
6. Otherwise high-confidence stable foreground provider.
7. Unsupported or unknown context → inhibited.

A provider change always begins a fresh idle epoch.

The new provider never inherits prior idle duration.

## 10. Idle epochs

`tvbox-idled` owns provider-local, boot-local idle epochs.

Start a fresh epoch when:

- meaningful activity occurs;
- provider changes;
- stable foreground changes;
- transition begins;
- transition ends;
- recovery begins or ends;
- display disappears or returns;
- source health degrades or recovers;
- provider configuration changes;
- daemon starts or restarts.

Do not reset an idle epoch when:

- the screensaver schedule changes;
- black changes to slideshow;
- slideshow changes to black;
- the downstream screensaver service restarts.

Scheduling is not idle determination.

## 11. Stability delay

When timeout is first crossed:

```text
active
-> idle-pending
```

Wait a short configurable delay, initially 2–5 seconds.

Then reread provider, application state, transition state, activity timestamp, and source health.

Only then publish:

```text
state=idle
idle=true
```

## 12. Initial providers

### Desktop

Recommended first provider:

```toml
[providers.desktop]
enabled = true
timeout_seconds = 300
required_sources = ["keyboard", "pointer"]
```

### Kodi

Enable only after reliable menu/playback evidence exists.

Potential eventual policy:

```text
menu/stopped:
  eligible

playing/buffering:
  inhibited

paused:
  configurable

unknown:
  inhibited
```

Kodi process+toplevel readiness alone does not prove menu or playback state.

### Spotify

May be added after authoritative playback state is confirmed.

The provider decides when Spotify is considered idle. It does not decide slideshow versus black.

### YouTube

Initially disabled.

Mapped Chromium or window title alone is not enough to distinguish page loading, menu, and playback.

### Moonlight and Steam Link

Initially disabled.

### Mario Kart and native games

Initially disabled.

### Unknown

Always inhibited.

## 13. Configuration

Suggested file:

```text
config/idle.toml
```

Example:

```toml
[global]
enabled = true
stability_delay_seconds = 3
unknown_policy = "inhibit"
degraded_policy = "not-idle"

[activity]
pointer_distance_px = 12
pointer_window_ms = 500
exclude_virtual_device_names = [
  "antimicrox Keyboard Emulation",
  "antimicrox Mouse Emulation",
  "antimicrox Abs Mouse Emulation"
]

[providers.desktop]
enabled = true
timeout_seconds = 300
required_sources = ["keyboard", "pointer"]

[providers.kodi]
enabled = false
timeout_seconds = 600

[providers.spotify]
enabled = false
timeout_seconds = 120

[providers.youtube]
enabled = false

[providers.moonlight]
enabled = false

[providers.steamlink]
enabled = false

[providers.mariokart64]
enabled = false
```

Provider enablement and timeout changes should be reloadable.

## 14. `tvbox-idled`

Suggested path:

```text
bin/tvbox-idled
```

Suggested service:

```text
config/systemd-user/tvbox-idled.service
```

### Inputs

- normalized `tvbox-state`;
- activity state;
- provider configuration;
- provider observations;
- explicit idle inhibitors, if retained.

### Output

Only:

```text
canonical idle-state.json
```

Optional status interface:

```bash
tvbox-idled status
tvbox-idled status --json
tvbox-idled reload
```

### No action interface

Do not add:

```text
start-screensaver
stop-screensaver
request-overlay
release-overlay
mode-black
mode-slideshow
```

Those belong downstream.

## 15. Optional explicit inhibitors

Prefer deriving inhibition from normalized state.

For operations not represented elsewhere, use tokenized expiring inhibitors:

```text
$XDG_RUNTIME_DIR/tvbox/idle-inhibitors/
```

Each record includes:

- opaque inhibitor ID;
- owner service and instance;
- reason;
- boot ID;
- creation monotonic time;
- expiry;
- persistent flag only for explicitly trusted cases.

Release requires the token.

Indefinite unowned marker files are prohibited.

## 16. Downstream screensaver consumer contract

A future or existing `tvbox-screensaverd` reads canonical idle state.

Expected reaction:

```text
idle=false
-> no automatic screensaver request

idle=true
-> ensure one automatic scheduled-mode screensaver request exists
```

When idle remains true and the schedule changes:

```text
tvbox-idled:
  unchanged

screensaver policy:
  changes effective mode
  existing overlay system replaces renderer
```

When idle becomes false:

```text
screensaver policy:
  release exact automatic request token
```

The screensaver consumer must not recalculate idle from input timestamps or app state.

## 17. Service ordering

Recommended:

```text
tvbox-activityd.service
tvbox-idled.service
```

`tvbox-idled` should start only after required runtime/state dependencies are available.

On startup:

1. create new writer instance;
2. reject old-boot state;
3. read current normalized state;
4. wait for activity health;
5. begin fresh epoch;
6. publish active/inhibited/degraded, never resurrect prior idle.

On shutdown:

- publish stopped or remove current state according to repository convention;
- no overlay cleanup is required because it owns no overlay request.

## 18. Implementation phases

### Phase 0 — API reconciliation

Inspect deployed:

- `tvbox-state`;
- runtime helper;
- atomic JSON utilities;
- current application-state schemas;
- existing systemd and installer conventions;
- physical input identities.

Adjust this plan only for observed API differences.

### Phase 1 — Activity collector

Implement and test:

- stable device identity;
- key-down;
- pointer button;
- pointer movement threshold;
- hotplug;
- virtual-device exclusion;
- health/degradation;
- atomic activity cache.

### Phase 2 — Provider framework

Implement:

- provider interface;
- desktop provider;
- disabled provider stubs;
- provider selection;
- confidence and inhibition reasons.

### Phase 3 — Canonical idle engine in dry-run

Implement:

- provider-local epochs;
- timeout;
- stability delay;
- canonical state;
- status output;
- no screensaver actions.

Live-validate state transitions only.

### Phase 4 — Narrow Kodi provider

Implemented and production-validated 2026-08-01. An observation-only,
current-session Kodi log follower publishes normalized playback state. The V1
provider uses a stopped-anywhere policy: stopped is eligible; starting,
playing, paused, unknown, stale, unhealthy, and session mismatch inhibit.
Playback stop and observer/session recovery begin fresh epochs.

### Phase 5 — Separate screensaver reaction plan

After idle state is proven, produce or implement the small downstream consumer that maps:

```text
idle true/false
-> automatic screensaver request lifecycle
```

Do not merge that consumer back into `tvbox-idled`.

Implemented separately by `tvbox-screensaverd`; the observation-only boundary
above remains unchanged.

## 19. Testing requirements

### Activity

- stable by-id resolution;
- hotplug;
- event-number changes;
- key-down counted;
- release ignored;
- pointer jitter ignored;
- meaningful pointer motion counted;
- AntiMicroX virtual devices excluded;
- source loss degrades;
- atomic writes.

### Providers

- desktop applies correctly;
- unsupported provider inhibits;
- transition prevents provider acceptance;
- disagreement lowers confidence;
- provider change resets epoch;
- provider result contains no renderer/schedule fields.

### Idle engine

- timeout not reached → active;
- timeout reached → idle-pending;
- stability passes → idle;
- late input during pending → active;
- source degradation → degraded;
- transition → inhibited;
- recovery → recovering;
- display absence → display-absent;
- daemon restart → fresh epoch;
- previous-boot monotonic values rejected;
- schedule changes have no effect on idle epoch;
- no overlay/screen action occurs.

### Canonical state

- only `state=idle` yields `idle=true`;
- unknown never yields idle;
- malformed input fails safe;
- reasons and source health present;
- atomic replacement;
- restrictive permissions.

## 20. Live validation

Before testing, confirm TV state if visual context is relevant.

Validate:

1. Keyboard activity updates activity state.
2. FLIRC activity updates activity state.
3. Mouse click and meaningful movement update state.
4. Pointer jitter does not.
5. Desktop provider begins fresh epoch.
6. Accelerated timeout enters idle-pending then idle.
7. Activity returns state to active.
8. App transition produces inhibited.
9. Unsupported app produces inhibited.
10. Source removal produces degraded.
11. Source return begins fresh epoch.
12. Daemon restart begins fresh epoch.
13. No renderer or overlay request is created at any point.
14. Final appliance returns to stable Kodi.

## 21. Documentation

Create:

```text
docs/development/YYYY-MM-DD-canonical-idle-state-implementation.md
```

Document:

- deployed inputs;
- schemas;
- device identities;
- provider contract;
- state machine;
- configuration;
- tests;
- live validation;
- known limitations;
- rollback.

Update the redeploy document.

Mark prior automatic-idle plans superseded by this narrower canonical-idle plan while retaining them as historical design input.

## 22. Done criteria

The canonical idle engine is complete when:

- activity collection is reliable for approved V1 sources;
- source health is explicit;
- provider selection is deterministic;
- provider-local epochs work;
- idle state is versioned and atomic;
- only healthy, confident timeout completion yields `idle=true`;
- transitions, recovery, disagreement, display loss, unsupported apps, and degraded sources never yield idle;
- schedule and renderer concepts do not exist in provider or idle-engine contracts;
- `tvbox-idled` never requests an overlay;
- tests pass;
- live validation proves idle transitions without visual actions;
- downstream consumers can rely on one canonical idle record.

## 23. Final architectural rule

```text
tvbox-state describes the appliance.
tvbox-activityd describes user activity.
Providers define app-specific idle eligibility.
tvbox-idled publishes canonical idle state.
Other systems decide what to do about it.
```
