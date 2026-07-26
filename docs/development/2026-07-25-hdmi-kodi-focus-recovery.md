# HDMI Kodi Focus Recovery

## Goal

Restore Kodi focus quickly after HDMI output reconnection when Kodi remains the
intended TVBox application.

## Current behavior

Two controlled TV off/on incidents left Kodi visible but transferred input to
the PCManFM desktop. A manual:

```text
wlrctl toplevel focus app_id:Kodi
```

immediately restored both FLIRC and controller input without restarting Kodi.

## Problem being solved

HDMI hotplug churn can leave the compositor focused on PCManFM while
`active-context` remains `kodi`. Desktop icons then receive remote activation
and can open Mousepad or Trash over the still-visible Kodi surface.

Post-reboot validation found the initially deployed unit enabled but inactive.
The LightDM/Labwc user session does not activate `graphical-session.target`, so
a unit wanted only by that target is not started automatically. Manual service
starts had hidden this deployment defect.

## Files expected to change

```text
bin/tvbox-focusd
config/systemd-user/tvbox-focus-recovery.service
tests/test_tvbox_focusd.py
docs/development/2026-07-25-hdmi-kodi-focus-recovery.md
```

Current-state documentation will not be updated until deploy validation passes.

## Proposed implementation

Add a separate recovery daemon; keep `tvbox-healthd` observation-only.

The daemon will:

- observe DRM hotplug events without grabbing input or CEC;
- debounce until one second after the final event;
- require the configured HDMI connector to be connected;
- require context `kodi` or `plex`;
- require Kodi to be running and listed as a Wayland toplevel;
- refuse recovery while another controlled application is running;
- focus exact app ID `Kodi`;
- rate-limit assertions and log every decision to journald;
- retry once after an additional second if the output/toplevel is not ready.

The user unit must be wanted by `default.target`, which this session actually
starts. Recovery remains safe before Wayland/Kodi readiness because service
startup itself never focuses anything and every hotplug recovery is gated.

## Commands used

```text
git status --short
rg and sed
bash -n
python3 -m py_compile
python3 -m unittest discover -s tests -v
systemd-analyze --user verify
git diff --check
```

## Validation checklist

### Repo validation

- [x] Python syntax passes.
- [x] Unit tests cover context, connector, Kodi, and external-app gates.
- [x] Static review confirms one-second debounce, one bounded retry, and
      three-second rate limiting.
- [x] Repeat systemd verification after installation creates the expected
      `/usr/local/bin/tvbox-focusd` link.
- [x] Observer and recovery services remain separate.
- [x] Exact Kodi selector matches the successful live manual test.
- [ ] Confirm the deployed enablement symlink targets `default.target.wants`.

### Deploy validation

- [x] Install the new script and unit.
- [x] Start the recovery service explicitly.
- [x] Confirm no assertion occurs merely at service start.
- [x] Confirm TV off/on restores input after approximately one stable second.
- [x] Confirm Kodi is not restarted.
- [ ] Confirm the service is active automatically after reboot.
- [ ] Confirm YouTube, Spotify, Moonlight, Steam Link, Mario Kart, and desktop
      contexts are not overridden.
- [ ] Confirm Home/F12 and Exit/F5 remain safe.

## Test results

Repo validation:

```text
python3 -m py_compile bin/tvbox-focusd
  passed

python3 -m unittest discover -s tests -v
  17 tests passed

python3 -m mypy --ignore-missing-imports bin/tvbox-focusd
  passed with no issues

bash -n install.sh bin/tvboxctl bin/tvbox-inputctl
  passed

git diff --check
  passed
```

Pre-install `systemd-analyze --user verify` parsed the unit and reported only
that `/usr/local/bin/tvbox-focusd` did not exist yet. After installation,
verification of the deployed unit passed with no output.

Deploy validation on 2026-07-25:

```text
tvbox-focus-recovery.service
  active with tvbox-focusd plus its passive udevadm DRM monitor

service startup
  emitted only started; did not assert focus before a hotplug

repeated TV off/on cycles
  input failure did not recur

HDMI reconnect events
  focus_asserted was emitted approximately one second after the final event

HDMI disconnect events
  connector_not_connected was safely skipped with one bounded retry

additional hotplug inside the three-second window
  focus assertion was rate-limited

Kodi process
  remained running; no recovery restart occurred
```

This host stores user-unit output in the system journal. The working query is:

```text
journalctl --user-unit=tvbox-focus-recovery.service -f
```

`journalctl --user -u ...` reports `No journal files were found` because there
is no separate per-user journal namespace on this installation.

## Known risks

- One second may be too short on a slower TV/output negotiation; one bounded
  retry handles delayed readiness.
- Incorrect context state could focus Kodi over an intentional application, so
  process exclusion is required in addition to context.
- Repeated DRM events could cause a focus loop; debounce and rate limiting are
  required.
- PCManFM is intentionally not closed. Recovery only changes focus.

## Rollback notes

Stop and remove only:

```text
/home/tvbox/.config/systemd/user/tvbox-focus-recovery.service
/usr/local/bin/tvbox-focusd
```

Then run `systemctl --user daemon-reload`. Restore timestamped installer backups
if present.

## Status

Status: implemented

Repo implementation and the Kodi/HDMI deploy path are validated. External-app
exclusion and Home/Exit regression checks remain pending.
