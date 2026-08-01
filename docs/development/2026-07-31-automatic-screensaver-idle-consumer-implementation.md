# Automatic Screensaver Idle Consumer Implementation

Date: 2026-07-31

Status: implemented, deployed, and live-validated

## Goal

Extend the existing `tvbox-screensaverd` policy daemon to consume canonical
`idle-state.json` and own the one automatic screensaver request, without adding
action logic to `tvbox-idled` or duplicating overlay lifecycle authority.

## Current behavior

The canonical idle engine publishes an observation-only boot-local record. The
screensaver policy already owns manual intent, exact overlay request tokens,
leases, schedule evaluation, mode overrides, and gapless renderer replacement,
but it does not consume idle state.

## Problem being solved

Valid canonical idle must activate one scheduled screensaver automatically;
non-idle or invalid input must release only that automatic request. Manual
screensavers must remain independent, and manually stopping an automatic saver
must suppress only the current idle epoch.

## Files expected to change

- `lib/tvbox/screensaver/policy.py`
- `lib/tvbox/screensaver/schedule.py`
- `bin/tvbox-screensaverd`
- `bin/tvbox-screensaver` only if status presentation requires it
- `config/screensaver.toml`
- `config/systemd-user/tvbox-screensaver-policy.service`
- `install.sh` for safe configuration migration
- screensaver policy/integration tests
- current screensaver/redeploy documentation

## Proposed implementation

Validate the canonical record by schema, boot, freshness, state/idle pair, and
health. Use its boot/writer/provider/epoch-start tuple as the idle epoch. Extend
the existing policy state with activation source and persisted current-epoch
suppression. Watch the runtime directory for atomic idle-state replacement and
also reconcile every configured 1–2 seconds. Reuse the existing request,
renewal, replacement, and schedule paths.

## Commands used

```text
git status --short
inspect policy daemon/client, canonical idle engine, runtime helper, overlay
protocol, lifecycle integration, units, config, installer, and tests
```

## Validation checklist

- [x] Every invalid/non-idle canonical state fails safe.
- [x] Valid idle creates exactly one automatic request.
- [x] Same epoch/event/reconciliation does not duplicate it.
- [x] Non-idle releases only the exact automatic token.
- [x] Manual start remains independent and overrides suppression.
- [x] Manual stop suppresses only the current automatic idle epoch.
- [x] A later epoch can activate; schedule changes do not alter idle epoch.
- [x] Mode overrides replace the existing owned request without competing intent.
- [x] Lost token/overlay restart recreates safely when still eligible.
- [x] Policy restart reconciles automatic intent and persisted suppression.
- [x] Directory replacement events and periodic fallback both trigger evaluation.
- [x] Status separates idle input, policy intent, and overlay observation.
- [x] `tvbox-idled` remains observation-only; policy has no provider/activity logic.
- [x] Full test/static/unit suite passes.
- [x] Installer migration preserves existing schedule/slideshow configuration.
- [x] Isolated and live validation finish at stable Kodi with no test overlay.

## Test results

### Repository

```text
python3 -m unittest discover -s tests -v
Ran 134 tests ... OK

bash -n install.sh
python3 -m compileall -q lib/tvbox/screensaver bin/tvbox-screensaverd
systemd-analyze --user verify ...
git diff --check
```

Focused coverage includes all canonical non-idle/failure states, schema/boot/
freshness/health validation, exact-token release, duplicate reconciliation,
epoch suppression and restart persistence, manual independence, schedule
replacement, lost request recreation, bounded failure retry, inotify directory
replacement, structured status, and static responsibility boundaries.

### Deployment and live validation

`sudo /opt/tvbox-system/install.sh` was run twice to prove idempotence. It
preserved the existing schedule/slideshow settings and appended the automatic
section after backing up the live file as
`screensaver.toml.bak.20260731-232437`. The changed user unit was backed up as
`tvbox-screensaver-policy.service.bak.20260731-232437`. All four relevant user
services are enabled and active.

An isolated runtime used the real policy, overlay manager, and renderers with a
synthetic healthy desktop idle record. It proved automatic slideshow readiness,
scheduled black readiness, black-to-slideshow replacement with the same epoch,
same-epoch manual-stop suppression, later-epoch reactivation, policy restart,
overlay-manager restart, stale-record release, and manual activation while idle
input was stale. No production provider was enabled.

A subsequent user-assisted run used the real passive activity collector, a
10-second timeout, and one-second stability delay. The user visually confirmed
that the slideshow correctly covered Kodi and disappeared for every tested
input. FLIRC key-down, physical keyboard key-down, and physical pointer motion
were each independently observed; every event returned canonical idle to
`active` and released the exact automatic overlay request.

The first isolated slideshow launch exposed a logger initialization-order bug
introduced during recursive-discovery work. It was fixed and retested; failed
renderer requests now also use a five-second retry backoff rather than creating
a request every reconciliation pass.

Final production state is stable Kodi, canonical idle is
`inhibited/idle=false`, automatic policy is enabled but ineligible, overlay is
inactive, no renderer remains, and the TV is on at active source `1.0.0.0`.

## Final architecture and semantics

The policy watches the runtime directory with inotify because idle state is
atomically renamed, with a configurable periodic fallback. Validation accepts
only supported-schema, current-boot, fresh, healthy canonical `idle=true`.
Epoch identity is boot ID, idle-writer instance, provider, and epoch start.

`activation_source` is `inactive`, `manual`, or `automatic`. Manual start
converts ownership to manual and clears suppression. Manual mode black or
slideshow changes the effective renderer of the existing request; scheduled
clears the override. Manual screensavers are not released by non-idle input.
Stopping an automatic saver records the current epoch and prevents immediate
reactivation until a non-idle record or different epoch arrives.

Overlay manager state remains authoritative for readiness, renderer,
generation, lease, and process. Policy state records only intent, its exact
token, canonical idle observation, activation source, and suppression.

## Known risks

Production Kodi remains intentionally inhibited, so automatic visual validation
must use an isolated runtime/config rather than enabling Kodi eligibility.

FLIRC, physical keyboard, and physical pointer transition behavior is now
user-assisted live-proven. Production Kodi inhibition still means no production
automatic saver is expected.

## Rollback notes

Set `[screensaver.automatic] enabled = false`, reload the screensaver policy,
and verify its exact automatic token is released. This leaves manual start,
scheduling, both renderers, the overlay manager, and canonical idle engine
installed and available.
