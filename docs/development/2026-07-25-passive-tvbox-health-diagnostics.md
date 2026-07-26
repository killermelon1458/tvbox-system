# Passive TVBox Health Diagnostics

## Goal

Implement Phase 0 capability discovery and a Phase 1 passive diagnostic
coordinator that can distinguish focus/toplevel, input profile, controller
reconnect/Kodi acquisition, and HDMI/Wayland failures without applying repairs.

## Current behavior

`tvboxctl` owns application policy and stores runtime state below
`/run/user/1000/tvbox`. Its panic path captures a small text snapshot immediately
before recovery. There is no long-running passive observer, correlated display
and input-device timeline, or bounded diagnostic bundle command.

The required incident report
`docs/development/2026-07-25-8bitdo-kodi-input-reconnect-bug.md` establishes that
an apparent Kodi input failure can be isolated to an 8BitDo controller: FLIRC
still worked while an 8BitDo receiver changed USB identity, input nodes were
recreated, and Kodi reported a stale `/dev/input/js1`.

## Problem being solved

Recovery currently destroys some of the best evidence. The system needs a
passive, degraded-safe timeline before any Phase 2 recovery policy is designed.
It must not equate a visible but unresponsive Kodi window with focus theft.

## Files expected to change

```text
bin/tvbox-diag
config/tvbox-diag.conf.example
config/systemd-user/tvbox-healthd.service
config/systemd-user/tvbox-healthd-cec.service
install.sh
docs/tvbox-focus-cec-diagnostic-discovery.md
docs/tvbox-focus-cec-diagnostic-tests.md
docs/tvbox-future-recovery-design.md
docs/current-system-redeploy.md (only repo-owned validated facts)
tests/test_tvbox_diag.py
docs/development/2026-07-25-passive-tvbox-health-diagnostics.md
```

## Proposed implementation

- One `tvbox-diag` CLI provides `status`, `snapshot`, `watch`, `cec-watch`,
  `test focus`, `test cec`, and `bundle`.
- `watch` is the `tvbox-healthd` coordinator. It samples health and consumes
  passive DRM/USB/input udev events. It emits JSON Lines to stdout/journald,
  records transitions rather than repeating full snapshots, and rate-limits
  larger anomaly snapshots.
- `cec-watch` is a separate optional service so a busy, missing, or
  permission-denied adapter cannot stop the coordinator.
- Device identity uses USB serial and physical path plus VID/PID, never a
  joystick/event index alone.
- Focus remains `unknown` unless a supported tool explicitly exposes activated
  state. A different toplevel is not promoted to confirmed focus failure
  without activation evidence.
- Kodi controller reacquisition failure requires Kodi log/open-error evidence
  and safe `/proc/<pid>/fd` inspection; node renumbering alone is insufficient.
- Logs use journald. Rate-limited snapshots use a bounded cache directory.
- Bundle creation uses an explicit allowlist and excludes profiles, credentials,
  arbitrary input text, and unbounded logs.

## Commands used

Phase 0 read-only commands include:

```text
git status --short
rg, sed, find, stat, sha256sum
uname -a; cat /etc/os-release; dpkg-query
labwc --version; kodi --version; wlrctl --version
wlrctl --help and supported subcommands
wlr-randr
tvboxctl status; tvbox-inputctl status
flock -n <lock> true
curl to Kodi localhost JSON-RPC
udevadm info
lsusb
cec-ctl --help/--version
journalctl and Kodi log filtering
```

No application, service, input profile, display mode, CEC control state, or
live configuration was changed.

## Validation checklist

### Repo validation

- [x] `python3 -m py_compile bin/tvbox-diag`
- [x] `python3 -m unittest discover -s tests`
- [x] `bin/tvbox-diag --help`
- [x] Snapshot succeeds when Wayland, Kodi JSON-RPC, CEC, journald, or devices
      are unavailable.
- [x] Every JSONL record has timestamp, monotonic timestamp, source, event type,
      severity, active context, input profile, and details.
- [x] Anomaly fixture tests cover context/process, profile, toplevel/focus
      uncertainty, display, and controller/Kodi evidence rules.
- [x] Bundle content uses an allowlist and contains no browser/auth/profile data.
- [ ] `systemd-analyze --user verify` both user units when possible (sandbox
      returned `SO_PASSCRED failed: Operation not permitted`).
- [x] Installer changes are scoped and do not enable either service.
- [x] Static review confirms no focus, Kodi action, application restart,
      display reset, CEC power/source, input grab, profile change, or transition
      lock acquisition.

### Deploy validation

- [ ] Install with timestamped backups.
- [ ] Start (do not enable) `tvbox-healthd.service`.
- [ ] Start the optional CEC unit only after adapter access/coexistence is
      confirmed.
- [ ] Confirm heartbeat and transition-only logging.
- [ ] Confirm udev observation does not grab FLIRC or controllers.
- [ ] Confirm CPU/memory and bounded journal/snapshot retention.
- [ ] Run baseline, focus-theft, context mismatch, profile mismatch, one/multiple
      receiver, controller sleep/wake, Kodi reacquisition, remote-vs-controller,
      and three-cycle TV tests.
- [ ] Confirm Home/F12, Exit/F5, Kodi CEC, Moonlight, Spotify, YouTube, Steam
      Link, and controllers remain behaviorally unchanged.

## Test results

Repo validation:

```text
python3 -m py_compile bin/tvbox-diag
  passed
python3 -m unittest discover -s tests -v
  9 tests passed
python3 -m mypy --ignore-missing-imports bin/tvbox-diag
  Success: no issues found in 1 source file
bash -n install.sh bin/tvboxctl bin/tvbox-inputctl
  passed
git diff --check
  passed
tvbox-diag status/snapshot/bundle with cache below /tmp
  passed in degraded TTY state
tvbox-diag watch --diagnostic (five-second foreground smoke test)
  emitted valid JSONL; udev monitor permission failure was isolated and logged
systemd-analyze verify
  not completed: SO_PASSCRED is blocked by the execution sandbox
```

Deploy validation was not run. No installer, systemd start/enable, reboot,
application restart, TV cycle, controller sleep/wake, CEC query, or CEC monitor
coexistence test was performed.

## Known risks

- `wlrctl` 0.2.2 lists toplevels but does not expose activation state, so focus
  may remain unknown.
- CEC and input device nodes were unavailable in the current execution context;
  live coexistence and permissions require a graphical/appliance test.
- Some TVs retain HPD/EDID in standby, so DRM connected is not proof of power-on.
- `/proc/<kodi-pid>/fd` proves an open node, not that Kodi is processing events.
- Kodi log pattern matching is evidence, not a substitute for a controlled
  navigation test.

## Rollback notes

The installer deploys:

```text
/usr/local/bin/tvbox-diag -> /opt/tvbox-system/bin/tvbox-diag
/home/tvbox/.config/tvbox/tvbox-diag.conf
/home/tvbox/.config/systemd/user/tvbox-healthd.service
/home/tvbox/.config/systemd/user/tvbox-healthd-cec.service
```

Exact rollback is:

```bash
systemctl --user disable --now tvbox-healthd.service tvbox-healthd-cec.service
rm /home/tvbox/.config/systemd/user/tvbox-healthd.service
rm /home/tvbox/.config/systemd/user/tvbox-healthd-cec.service
rm /home/tvbox/.config/tvbox/tvbox-diag.conf
rm /usr/local/bin/tvbox-diag
systemctl --user daemon-reload
```

If an installer-created `.bak.YYYYMMDD-HHMMSS` exists for any destination,
restore that exact backup instead of removing the destination.

## Status

Status: implemented
