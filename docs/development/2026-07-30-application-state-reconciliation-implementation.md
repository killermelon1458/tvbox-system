# Application State Reconciliation Implementation

Date: 2026-07-30

Status: validated

## Goal

Separate lifecycle requests, active transitions, direct observations, stable
accepted application state, and failures. Keep `active-context` as a temporary
compatibility view of stable state only.

## Current behavior

`tvboxctl` and several wrappers write `active-context` during launch or return,
before application readiness has been established. Process-only checks can
therefore leave false Kodi, Steam Link, YouTube, Moonlight, or Mario Kart state.

## Problem being solved

Implement the state foundation established by the completed 2026-07-27 and
2026-07-28 discovery notes without adding screensavers, overlays, loading
screens, or a new automatic input-profile policy.

## Files expected to change

- `bin/tvbox-state`
- `bin/tvboxctl`
- application wrappers under `bin/` where lifecycle evidence must be recorded
- `config/tvboxctl.conf.example`
- `tests/test_tvbox_state.py`
- existing focused tests where compatibility behavior changes
- `docs/development/2026-07-30-application-state-reconciliation-implementation.md`
- `docs/current-system-redeploy.md` only after repo and deploy validation

## Proposed implementation

Use a short-lived Python reconciler invoked by lifecycle wrappers and
`tvboxctl`. Store four distinct versioned JSON files below a shared runtime
root, atomically replace each file, verify boot identity, observe exact
owned-process claims and Wayland toplevels, and commit compatibility
`active-context` only after an application predicate succeeds.

Home records `returning`, invalidates the current request acceptance, performs
the existing app-specific local close, invokes the canonical Kodi wrapper, and
waits for the Kodi process plus toplevel before committing Kodi. Failures remain
visible in transition state and can invoke bounded recovery through `tvboxctl`.

Existing profile switching remains in lifecycle code. State records the current
profile and whether it changed during a transition but does not select profiles.

## Commands used

```text
git status --short
sed -n ... discovery documents and repository files
rg ... lifecycle, wrappers, runtime paths, and tests
bash -n bin/tvboxctl bin/tvbox-kodi bin/tvbox-moonlight \
  bin/tvbox-youtube bin/tvbox-mariokart64 bin/tvbox-inputctl
python3 -m unittest discover -s tests -v
systemd-analyze verify config/systemd-user/tvbox-focus-recovery.service
git diff --check
```

## Validation checklist

### Repo validation

- [x] Runtime root uses `TVBOX_RUNTIME_ROOT`, otherwise
      `$XDG_RUNTIME_DIR/tvbox`, with mode 0700.
- [x] JSON includes schema, writer, timestamps, boot ID, and atomic replacement.
- [x] Malformed, unsupported, and previous-boot state is ignored safely.
- [x] Steam Link needs exact owned process plus toplevel and stability interval.
- [x] Steam Link early exit fails without stale stable state.
- [x] Moonlight menu can supersede prior stable Kodi after acceptance.
- [x] Focus recovery cannot overwrite observed Moonlight with Kodi.
- [x] YouTube mapping is not page readiness and return waits for Kodi readiness.
- [x] Mario Kart process/splash remains content-loading, never invented ready.
- [x] Kodi requires exact process plus matching toplevel.
- [x] Home records returning before close and commits Kodi only after readiness.
- [x] Input profile is observation only; existing profile behavior remains.
- [x] Shell syntax checks pass.
- [x] `python3 -m unittest discover -s tests -v` passes.
- [x] `git diff --check` passes.

### Deploy validation

- [x] Timestamped backups/source-to-live ownership verified by installer.
- [x] Kodi readiness detected.
- [x] Generic Moonlight menu launch and one-press Home return validated.
- [x] Steam Link early-exit cleanup validated. Menu acceptance remained
      unavailable because this host's client exited before acceptance.
- [x] YouTube launch and one-press Home return validated.
- [x] Mario Kart loading and Home cleanup validated.
- [x] Final Kodi process+toplevel, clear transition, stable Kodi,
      input-profile observation, TV power/source, and no external app confirmed.

## Final state model

`tvbox-state` is a short-lived reconciler plus an accepted-application monitor.
It separates:

- `lifecycle-request.json`: latest requested application/target and request ID.
- `transition-state.json`: the active/failed phase and boot-local deadline.
- `observed-state.json`: direct process, PID claim, toplevel, and input facts.
- `stable-state.json`: only an application accepted by its predicate.
- `failure-state.json`: the latest failure, retained when recovery creates a
  new returning transition.

`active-context` is atomically generated only when stable state is committed.
The lifecycle request never changes it.

## Runtime files and schemas

The root is `TVBOX_RUNTIME_ROOT` when set, otherwise
`$XDG_RUNTIME_DIR/tvbox`; the user unit supplies `%t/tvbox`. The directory is
0700 and JSON/context files are 0600. JSON files use schema version 1 and carry
writer identity, RFC3339-like wall time, monotonic update time, and boot ID.
Temporary files are flushed and atomically renamed. Unsupported, malformed,
and prior-boot JSON is ignored.

The transition log is `~/.cache/tvbox-transition.log`, mode 0600, and contains
request, phase, acceptance/failure, stable state, recovery-related reasons, and
observed input profile without browser credentials.

## Acceptance predicates and deadlines

- Kodi: exact Kodi executable plus matching toplevel and no conflicting
  controlled-app toplevel; 15 seconds.
- Moonlight menu: exact client plus matching toplevel stable for 0.5 seconds;
  15 seconds.
- Steam Link menu: exact client plus matching toplevel stable for 0.75 seconds;
  20 seconds. A post-acceptance monitor records exit and asks `tvboxctl` for
  bounded Home recovery.
- YouTube: exact Chromium executable with the dedicated profile plus matching
  toplevel stable for 0.75 seconds; 20 seconds. This is medium-confidence
  mapped/menu acceptance, not proof of DOM or playback readiness.
- Mario Kart: exact Mupen process and toplevel reaches `content-loading` only;
  12 seconds. No stable ready state is invented.

## App-specific reconciliation behavior

Generic Moonlight accepts its local menu. Direct Moonlight targets remain
`stream-connecting`; process existence never becomes `streaming`. The wrapper
does not accept remote quit/failure dialogs.

Steam Link is launched as a request, accepted only at menu, and monitored for
the discovered immediate-exit failure. YouTube and Mario Kart wrappers capture
owned child PID/start time and exit status. YouTube close enumerates exact
Chromium executables using the dedicated profile, so diagnostic shells merely
containing the profile string are not targets.

## Home/Kodi recovery contract

Home first creates a Kodi request and records `returning`, then performs the
existing app-specific local close. Moonlight remains non-destructive. The
canonical Kodi wrapper is invoked and Kodi is committed only after exact
process plus toplevel readiness. One bounded retry is made. Failure records
`kodi-recovery-failed` and leaves panic/recovery controls available.

## Input-profile separation

No profile selection exists in `tvbox-state`. The current wrappers and
`tvboxctl` retain their existing profile calls, including passthrough during
Moonlight and Steam Link startup. Observed profile, source, change time, and
whether it changed during a transition are recorded. Automatic failure
recovery is configured by
`INPUT_RECOVERY_ON_TRANSITION_FAILURE=restore-kodi-after-kodi-ready`; `none`
disables it. The Kodi profile is restored only after Kodi readiness.

## Known unresolved readiness signals

- No authoritative current-run Moonlight streaming/video signal.
- No automatic handling of the remote Moonlight “quit Desktop” confirmation.
- Chromium toplevel mapping does not prove page/DOM readiness or playback.
- Mario Kart has no authoritative title/menu/input-ready event and therefore
  remains `content-loading`.

## Migration and active-context compatibility

Existing readers may continue reading `active-context`, but it now mirrors
stable accepted state. `tvboxctl set-context` reconciles current observations
and refuses a requested controlled context that is not actually accepted.
Startup reconciliation ignores cached PID/transition claims from another boot
and rebuilds stable Kodi, Moonlight, Steam Link, or YouTube state from direct
facts; otherwise it reports desktop/unknown with low confidence.

## Test results

Repo validation on 2026-07-30:

- Shell syntax: passed for all six changed shell programs.
- Unit/integration-style suite: 47 tests passed, including all new
  application-state and race tests; all 28 existing tests retained.
- `git diff --check`: passed.
- `systemd-analyze verify`: passed on the host. Its first sandboxed attempt was
  discarded after `SO_PASSCRED failed: Operation not permitted`.

## Deployment steps

Run the repository installer as root after inspecting source/live mappings.
It creates the new `/usr/local/bin/tvbox-state` link and updates the changed
user unit with a timestamped backup. Existing correct `/usr/local/bin` links
already point into the repository. The existing local `/etc/tvboxctl.conf` may
retain machine-specific settings; remove its hard-coded `STATE_DIR` or set it
empty on future config maintenance so runtime derivation is used.

## Deploy validation results

Deployed 2026-07-30 with the repository installer. Backups:

- `/etc/tvboxctl.conf.bak.20260730-225523`
- `/home/tvbox/.config/systemd/user/tvbox-focus-recovery.service.bak.20260730-225625`

Live results:

- Baseline and final Kodi exact process plus `Kodi: Kodi from Debian` toplevel
  were accepted; stable/request IDs matched and transition was clear.
- Generic Moonlight exact owned PID plus toplevel committed stable Moonlight
  even though focus recovery restored the existing Kodi input profile. One
  Home closed only the local client and returned Kodi.
- Steam Link exited before its acceptance predicate. It never committed stable
  Steam Link, recorded `required-process-exited-before-acceptance`, cleaned up,
  and returned Kodi. This validates failure cleanup, not menu acceptance.
- YouTube exact dedicated-profile Chromium plus toplevel committed
  medium-confidence browser-window. One Home returned ready Kodi.
- Mario Kart exact Mupen process plus toplevel remained `content-loading`;
  stable context remained prior Kodi rather than inventing game readiness.
  Home closed Mupen and returned Kodi.
- A final audit exposed a later Kodi exit. Accepted-state liveness monitoring
  was added; Home then restored exact Kodi process+toplevel. Final state had no
  controlled external app, transition clear, stable/active Kodi, observed
  `kodi_native_minimal`, and TV on at active HDMI source `1.0.0.0`.
- Kodi JSON-RPC port 8080 was unavailable during the final audit. Home sent the
  Favourites action, but the current-window label was not independently queried
  or visually asserted in the final command.

## Known risks

- Wayland toplevel output is compositor/version specific.
- Moonlight streaming and Mario Kart true-ready signals remain incomplete.
- Wrapper exit races require request-ID and owned-PID checks.

## Rollback notes

Restore the timestamped `/usr/local/bin/tvbox-state`,
`/usr/local/bin/tvboxctl`, and wrapper symlinks/files created by the installer,
then restore the prior `/etc/tvboxctl.conf` if changed. Runtime files below
`%t/tvbox` are non-durable and may be removed after all TVBox lifecycle
commands are stopped. Relaunch Kodi only through `/usr/local/bin/tvbox-kodi`.
