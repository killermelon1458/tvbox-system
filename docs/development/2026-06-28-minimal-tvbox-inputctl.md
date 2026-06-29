# Minimal tvbox-inputctl

## Goal

Add a minimal `tvbox-inputctl` command that gives TVBox a repo-owned control surface for context-dependent controller/input profiles.

This first version should be safe and state-only. It should not start, stop, or configure a real remapper process yet.

## Current behavior

TVBox has app/session control through `tvboxctl`, but no implemented `tvbox-inputctl`.

The future plan docs describe context-dependent input profiles, but there is no current repo-owned command for recording or switching the intended input profile.

## Problem being solved

Before wiring controller profiles into app transitions, TVBox needs a small, testable command that can:

```text
report the current intended input profile
set the intended profile
reset to Kodi-native input
stop/remap to no active profile
log profile changes
avoid touching global Home/F12 recovery
```

## Files expected to change

```text
bin/tvbox-inputctl
input-profiles/README.md
docs/development/2026-06-28-minimal-tvbox-inputctl.md
docs/current-system-redeploy.md
```

## Proposed implementation

Add `bin/tvbox-inputctl` with commands:

```text
status
get-profile
set-profile <profile>
reset
stop
list-profiles
```

Use runtime state:

```text
/run/user/1000/tvbox/input-profile
/run/user/1000/tvbox/inputctl.lock
```

Fallback state:

```text
/tmp/tvbox/input-profile
/tmp/tvbox/inputctl.lock
```

Use log file:

```text
/home/tvbox/.cache/tvbox-inputctl.log
```

Support environment overrides for repo validation without writing live runtime state:

```text
TVBOX_INPUTCTL_STATE_DIR
TVBOX_INPUTCTL_LOG_DIR
```

Initial profiles are names only:

```text
none
kodi_native
passthrough
youtube_remote
spotify_ui
desktop_mouse
```

No backend remapper will run yet. `tvbox-inputctl` will explicitly report `backend: state-only`.

## Commands used

```bash
git status --short
bash -n bin/tvbox-inputctl
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test-state TVBOX_INPUTCTL_LOG_DIR=/tmp/tvbox-inputctl-test-log bin/tvbox-inputctl status
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test-state TVBOX_INPUTCTL_LOG_DIR=/tmp/tvbox-inputctl-test-log bin/tvbox-inputctl list-profiles
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test-state TVBOX_INPUTCTL_LOG_DIR=/tmp/tvbox-inputctl-test-log bin/tvbox-inputctl set-profile youtube_remote
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test-state TVBOX_INPUTCTL_LOG_DIR=/tmp/tvbox-inputctl-test-log bin/tvbox-inputctl get-profile
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test-state TVBOX_INPUTCTL_LOG_DIR=/tmp/tvbox-inputctl-test-log bin/tvbox-inputctl reset
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test-state TVBOX_INPUTCTL_LOG_DIR=/tmp/tvbox-inputctl-test-log bin/tvbox-inputctl stop
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test-state TVBOX_INPUTCTL_LOG_DIR=/tmp/tvbox-inputctl-test-log bin/tvbox-inputctl set-profile bad/profile
TVBOX_INPUTCTL_STATE_DIR=/tmp/tvbox-inputctl-test-state TVBOX_INPUTCTL_LOG_DIR=/tmp/tvbox-inputctl-test-log bin/tvbox-inputctl set-profile unknown_profile
```

## Validation checklist

```text
bash -n bin/tvbox-inputctl
Run state-only smoke tests with TVBOX_INPUTCTL_STATE_DIR and TVBOX_INPUTCTL_LOG_DIR pointed at /tmp
Confirm invalid profile names are rejected
Confirm current-state docs only claim repo-owned/state-only behavior
Show git status --short and git diff --stat
```

## Test results

```text
bash -n bin/tvbox-inputctl: passed
status with /tmp state/log overrides: passed, reported backend=state-only and input-profile=unknown
list-profiles: passed
set-profile youtube_remote: passed
get-profile after set-profile: passed, returned youtube_remote
reset: passed, profile became kodi_native
stop: passed, profile became none
invalid profile name bad/profile: passed, rejected with exit code 2
unknown valid-looking profile unknown_profile: passed, rejected with exit code 2
```

Deploy validation was not run. `install.sh` was not run and no live `/usr/local/bin` symlink was changed.

## Known risks

This does not actually change controller behavior yet. It only records intended profile state.

Future wiring into `tvboxctl` and app wrappers must preserve global Home/F12 recovery even if a profile is broken.

## Rollback notes

Before deployment, rollback is removing the repo files:

```text
bin/tvbox-inputctl
input-profiles/README.md
docs/development/2026-06-28-minimal-tvbox-inputctl.md
```

After deployment through `install.sh`, rollback is:

```bash
sudo rm -f /usr/local/bin/tvbox-inputctl
rm -f /run/user/1000/tvbox/input-profile /run/user/1000/tvbox/inputctl.lock
rm -f /tmp/tvbox/input-profile /tmp/tvbox/inputctl.lock
```

## Status

validated
