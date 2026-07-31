# Screensaver, Overlay, and Scheduling Implementation

Date: 2026-07-31

Status: validated

## Goal

Implement the initial manual TVBox screensaver release: a token-safe overlay
manager, black and slideshow GtkLayerShell renderers, schedule/manual policy,
gapless active replacement, and Home/application-transition invalidation.

Automatic idle detection, loading policy, controller interception, CEC/DRM
power actions, video, and application-provider policy remain out of scope.

## Current behavior

GtkLayerShell overlay rendering and F12 routing were proven in discovery, and
application lifecycle state is now reconciled separately. No production overlay
manager, renderer, screensaver facade, or schedule evaluator exists.

## Problem being solved

Provide manual black/slideshow screensavers with time-selected mode switching
while retaining a single renderer lifecycle authority and never exposing the
underlying application during successful replacement.

## Files expected to change

- `lib/tvbox/` runtime, overlay, and screensaver modules
- `bin/tvbox-overlay`
- `bin/tvbox-screensaverd`
- `bin/tvbox-screensaver`
- `bin/tvbox-render-black`
- `bin/tvbox-render-slideshow`
- `bin/tvboxctl`
- `config/screensaver.toml`
- `config/systemd-user/tvbox-overlay.service`
- `config/systemd-user/tvbox-screensaver-policy.service`
- `install.sh`
- tests for manager, renderers, schedule, policy, and integration
- `docs/current-system-redeploy.md`
- screensaver plan status documentation

## Proposed implementation

`tvbox-overlay` is a Unix-socket manager and the only renderer launcher. It
allocates opaque request tokens and generations, validates typed requests,
supervises renderer-owned process groups, waits on an inherited readiness pipe,
enforces leases, publishes an atomic observation cache, and replaces only after
the new opaque renderer reports first-frame readiness.

`tvbox-screensaverd` owns manual override, schedule selection, the current
screensaver request token, renewals, exact-token release, and boundary/config
reevaluation. `tvbox-screensaver` is a thin client.

Renderers use Python 3, GTK 3, and GtkLayerShell overlay surfaces. They only
draw pixels and report first-frame readiness.

## Commands used

```text
git status --short
sed -n ... required plans, lifecycle code, units, installer, and tests
rg --files ...
```

## Validation checklist

### Repo validation

- [x] Exact-token release/renew and stale-token rejection.
- [x] Generations, priority/preemption, and finite lease expiry.
- [x] Readiness timeout, crash cleanup, late readiness/exit isolation.
- [x] Fresh manager restart cache and unrelated-PID safety.
- [x] Gapless successful replacement and old-renderer retention on failure.
- [x] Black renderer layer-shell/readiness/TERM/no-audio contract.
- [x] Slideshow valid/corrupt/missing/empty/EXIF/fit/predecode/fallback behavior.
- [x] Day/overnight/cross-midnight/boundary/DST/clock-jump/config reload schedule.
- [x] Manual black/slideshow/scheduled policy.
- [x] Home and application transitions release by exact saved token first.
- [x] All existing tests retained.
- [x] Shell syntax, Python compilation, unit verification, and diff checks pass.

### Deploy validation

- [x] Dependency and source/live mappings verified.
- [x] Timestamped backups made before live replacement.
- [x] Black covers fullscreen Kodi.
- [x] Slideshow covers fullscreen Kodi.
- [x] Missing-directory slideshow remains opaque black and degraded.
- [x] Manual commands and status work.
- [x] Accelerated active schedule boundary switches both directions.
- [x] Replacement failure retains old renderer.
- [x] F12/Home works from black and slideshow.
- [x] Manager restart and renderer crash reconcile.
- [x] Final renderer absent, manager inactive, Kodi exact process+toplevel,
      lifecycle transition clear, and TV/source confirmed.

## Final component design

`tvbox-overlay` is the sole production renderer owner. `tvbox-screensaverd`
owns schedule/manual policy and a single exact overlay token.
`tvbox-screensaver` is the client facade. `tvbox-state` only aggregates the
two atomic observational caches. Renderers only draw and report first frame.
Home, Exit, and application wrappers invalidate the saver before lifecycle
work; no renderer changes lifecycle context or input profile.

## Protocol and schemas

The version-1 Unix socket protocol validates owner/service identity, overlay
type, renderer, bounded renderer arguments, reserved priority, finite lease,
and optional replacement token. Acceptance returns a random 128-bit token,
manager-local generation, manager instance, and `starting`. Release and renew
require the exact token; owner-name release is unsupported.

## Runtime files

Under `TVBOX_RUNTIME_ROOT` for tests or `$XDG_RUNTIME_DIR/tvbox`:

```text
overlay.sock                 0600 control socket
screensaver.sock             0600 control socket
overlay-state.json           atomic manager observation
screensaver-policy.json      atomic policy/schedule observation
```

The root is `0700`. JSON includes schema version, boot ID, writer instance,
wall timestamp, and monotonic update time. Cached PIDs never grant authority.

## Configuration and schedule semantics

`config/screensaver.toml` selects default mode, IANA timezone, explicit output,
fixed local-time rules, and slideshow settings. Start is inclusive and end is
exclusive; cross-midnight works; later overlapping rules win. Schedule is
recomputed from timezone-aware wall time every policy tick, after restart,
reload, resume/clock jumps, and at boundaries. Leases use monotonic time.
Precedence reserves future recovery/inhibition/provider slots, then uses manual
override, schedule, and default.

## Manager supervision and replacement

The manager launches each renderer in a new process group, waits on an
inherited request/generation readiness pipe, and applies bounded TERM/KILL
cleanup. Systemd `KillMode=control-group` covers manager termination. It starts
a replacement first, promotes only its matching ready generation, then stops
the old renderer. Failure retains the old renderer. Late readiness/exits cannot
mutate newer generations. A restart publishes fresh empty state and never
signals cached or name-matched PIDs; retained policy intent reissues a request.

## Renderer readiness and slideshow behavior

Both GTK 3 renderers use GtkLayerShell overlay, all four anchors, explicit
monitor, on-demand keyboard, and opaque full pointer surfaces. Live validation
found `wf-panel-pi` reserves 36 top pixels: zone `0` exposed that strip, so
production uses zone `-1` to ignore other exclusive zones while reserving no
workspace. A full-frame capture had no non-black pixels.

Readiness is sent after GTK `after-paint`. Black explicitly paints with Cairo
SOURCE. Slideshow scans a bounded extension allowlist, honors EXIF orientation,
supports contain/cover, skips invalid files, and retains only current plus one
predecoded next image. Missing/empty/invalid sources commit opaque black and
report `no-valid-images-black-fallback`.

## Commands

```bash
tvbox-screensaver start
tvbox-screensaver stop
tvbox-screensaver status
tvbox-screensaver mode black
tvbox-screensaver mode slideshow
tvbox-screensaver mode scheduled
tvbox-screensaver reload
```

## Test results

```text
python3 -m unittest discover -s tests -v
Ran 90 tests ... OK
```

The suite covers manager tokens, leases, generations, restart/crash/timeout,
unrelated PID safety, replacement success/failure, renderer contracts,
slideshow scanning/decode/fallback/fit, timezone schedules including DST and
clock jumps, policy restart, and lifecycle invalidation.

## Deployment and live validation

`sudo /opt/tvbox-system/install.sh` was run. It installed repo symlinks,
configuration, and both user units; both services were enabled and active.
The GI GTK 3 and GtkLayerShell dependency check passed.

Live-proven above fullscreen Kodi:

- fully opaque black and valid-image slideshow;
- absent slideshow directory degraded safely to fully black;
- manual black/slideshow/scheduled operations;
- slideshow-to-black and black-to-slideshow generation replacement with zero
  sampled inactive states;
- failed invalid-output replacement retained the old ready slideshow;
- accelerated 07:07 black and 07:08 slideshow boundaries while continuously
  requested;
- manager restart created a fresh instance/token and restored the saver;
- killing the exact supervised renderer PID produced a fresh ready generation;
- Home from black and slideshow released the exact saver then restored Kodi.

The accelerated configuration was restored from
`screensaver.toml.bak.20260731-070625`; its temporary image/directory was
removed. Final state was overlay inactive, transition clear, exact Kodi process
and toplevel ready, TV on, DRM on, and active HDMI source `1.0.0.0`.

## Known limitations

Automatic idle/wake, controller/CEC wake interception, provider policy,
loading policy, playback detection, display power-off, and video renderers are
deferred. Slideshow content changes use a bounded periodic rescan rather than
real-time filesystem watch. Moonlight stream and Steam Link overlay coverage
remain unproven. The shipped image directory is intentionally not populated.
Phone/web hardening is recorded in the v1.1 image-compatibility report.

## Rollback

Restore timestamped user-unit/config backups, stop the two screensaver services,
and remove only their boot-local socket/cache files below `%t/tvbox`. Restore
the prior `tvboxctl` repo revision if transition integration must be removed.
Do not kill renderers by executable name; stop the overlay service so its
owned child process groups receive bounded shutdown.
