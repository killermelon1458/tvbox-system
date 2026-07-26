# Asynchronous TV Activation from Home

## Goal

Have every global Home/F12 request ensure that the TVBox HDMI source is active
without adding CEC or TV-startup latency to normal Home behavior.

## Current behavior

`tvbox-home` preserves an emergency Mupen64Plus exit path, then synchronously
delegates to `tvboxctl home`. The validated `tvbox-tv activate` command can take
27 seconds when waking the Hisense TV, so it must not run synchronously in the
Home path.

## Problem being solved

Home should wake/activate the TV when needed while immediately continuing Kodi
and application policy. Repeated Home presses must not create parallel CEC wake
sequences. Failure of the activation facility must never prevent Home recovery.

## Files expected to change

```text
bin/tvbox-home
config/systemd-user/tvbox-tv-activate.service
docs/development/2026-07-26-home-asynchronous-tv-activation.md
```

The generic installer already installs all repo user units. Current-state
documentation will be updated only after installed validation.

## Proposed implementation

- Add an invoked-only `Type=oneshot` user unit that runs `tvbox-tv activate`.
- Bound the unit to 55 seconds, above the command's 45-second internal limit.
- Give the unit no `[Install]` section; it is neither persistent nor enabled.
- `tvbox-home` requests the unit with `systemctl --user start --no-block`.
- Bound the systemd request itself to one second and ignore request failure.
- Preserve the emergency emulator termination as the first behavioral action.
- Request activation in both the emergency-emulator and normal Home paths.
- Keep `tvboxctl home` synchronous and otherwise unchanged.
- Rely on systemd job state plus the existing `tvbox-tv` lock to coalesce
  repeated requests.

## Commands used

```text
git status --short
sed and rg
bash -n
systemd-analyze --user verify
python3 -m unittest discover -s tests -v
git diff --check
```

## Validation checklist

### Repo validation

- [x] `tvbox-home` shell syntax passes.
- [x] The activation request uses `--no-block` and has a one-second bound.
- [x] Activation request failure cannot change Home's exit path.
- [x] Emergency Mupen64Plus termination remains the first behavioral action.
- [x] The unit is oneshot with a 55-second bound and no `[Install]` section.
- [x] Full automated tests pass.
- [ ] Unit verification passes on the installed appliance.

### Deploy validation

- [ ] Install the unit and reload the user manager.
- [ ] Measure normal Home latency with TV already active.
- [ ] Confirm Home returns without waiting for the activation service.
- [ ] Confirm the oneshot logs `already_active` during normal operation.
- [ ] Turn TV off and confirm one Home press starts activation and immediately
      runs normal Home behavior.
- [ ] Confirm repeated Home presses do not create multiple activation workers.
- [ ] Confirm the TV wakes/activates and Kodi becomes usable.
- [ ] Confirm emulator Home recovery remains safe.

## Test results

Repo validation:

- `bash -n bin/tvbox-home`: passed.
- Static inspection confirmed `timeout 1`, `--no-block`, ignored request failure,
  emulator termination ordering, `Type=oneshot`, `TimeoutStartSec=55`, and no
  `[Install]` section.
- `python3 -m unittest discover -s tests -v`: all 28 tests passed.
- `git diff --check`: passed.
- `systemd-analyze verify` could not run to completion in the restricted
  development shell (`SO_PASSCRED failed: Operation not permitted`). A host
  user-manager attempt emitted no unit error before it was stopped after
  waiting more than 60 seconds. Installed verification remains pending.

Deploy validation has not been run. Current-state documentation was therefore
not changed.

## Known risks

- A broken user D-Bus could consume the one-second request bound; Home still
  continues.
- User unit output is in the system journal on this appliance and must be read
  with `journalctl --user-unit=tvbox-tv-activate.service`.
- Rapid repeated Home presses still reach existing Home/panic policy even
  though TV activation is deduplicated.

## Rollback notes

Restore the prior `/usr/local/bin/tvbox-home` symlink target content and remove:

```text
/home/tvbox/.config/systemd/user/tvbox-tv-activate.service
```

Then run `systemctl --user daemon-reload`. No TV, Kodi, input-profile, or Pi
power setting is changed.

## Status

Status: implemented
