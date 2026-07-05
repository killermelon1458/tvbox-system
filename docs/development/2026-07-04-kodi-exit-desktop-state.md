# Kodi Exit Desktop State

## Goal

Set the TVBox control state to `desktop` when Kodi is closed from the Kodi GUI and no other TVBox-controlled application is active.

## Current behavior

`tvbox-kodi` launches Kodi in the background, sleeps briefly, and exits. After that, no repo-owned process observes a normal Kodi GUI exit, so `tvboxctl` can keep reporting an old `active-context` such as `kodi`.

## Problem being solved

Closing Kodi from the GUI should leave `tvboxctl status` in a truthful desktop state unless another controlled app, such as Steam Link, Moonlight, Spotify, YouTube, or Mario Kart 64, is running.

The desktop state should also apply the generic controller keyboard/mouse profile so the controller works as a desktop pointer after Kodi exits.

## Files expected to change

```text
bin/tvbox-kodi
bin/tvboxctl
input-profiles/controller_kbm_generic.gamecontroller.amgp
docs/current-system-redeploy.md
docs/development/2026-07-04-kodi-exit-desktop-state.md
```

## Proposed implementation

Keep `tvbox-kodi` as the canonical Kodi launcher, but make its background Kodi child run under a tiny shell supervisor. When Kodi exits, the supervisor waits briefly and asks `tvboxctl reconcile-context` to infer the current state from process/window detection.

Add `tvboxctl reconcile-context`, guarded by the existing lock. If another `tvboxctl` operation is in progress, reconciliation is ignored so a controlled launch that intentionally closed Kodi is not overwritten.

Map known `tvboxctl` contexts to input profiles inside `set_context`, including `desktop -> controller_kbm_generic`.

## Commands used

```text
git status --short
sed -n '1,240p' bin/tvbox-kodi
sed -n '1,620p' bin/tvboxctl
rg -n "set-context|active-context|show_kodi|tvbox-kodi|desktop|launch" bin config kodi-addons docs/current-system-redeploy.md
bash -n bin/tvboxctl bin/tvbox-kodi bin/tvbox-home install.sh
TVBOX_HOME=/tmp/tvbox-reconcile-test HOME=/tmp/tvbox-reconcile-test bin/tvboxctl reconcile-context test-static
TVBOX_HOME=/tmp/tvbox-reconcile-test HOME=/tmp/tvbox-reconcile-test bin/tvboxctl get-context
bash -n bin/tvboxctl bin/tvbox-kodi bin/tvbox-home install.sh
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("input-profiles/controller_kbm_generic.gamecontroller.amgp")'
```

## Validation checklist

Repo validation:

```text
bash -n bin/tvboxctl bin/tvbox-kodi bin/tvbox-home install.sh
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("input-profiles/controller_kbm_generic.gamecontroller.amgp")'
```

Deploy validation:

```text
sudo /opt/tvbox-system/install.sh
Close Kodi from the Kodi GUI.
Run tvboxctl status and confirm active-context is desktop.
Run tvbox-inputctl status and confirm input-profile is controller_kbm_generic and AntiMicroX is running.
Launch Steam Link, Moonlight, YouTube, Spotify mode, and Mario Kart 64 from their normal entrypoints and confirm Kodi-exit reconciliation does not overwrite their active state.
Press Home/F12 from desktop and confirm Kodi returns.
```

## Test results

Repo validation passed:

```text
bash -n bin/tvboxctl bin/tvbox-kodi bin/tvbox-home install.sh
```

After adding context-to-input-profile mapping, repo validation passed again:

```text
bash -n bin/tvboxctl bin/tvbox-kodi bin/tvbox-home install.sh
```

After including the updated generic controller keyboard/mouse profile, XML validation passed:

```text
python3 -c 'import xml.etree.ElementTree as ET; ET.parse("input-profiles/controller_kbm_generic.gamecontroller.amgp")'
```

Attempted non-live runtime validation with:

```text
TVBOX_HOME=/tmp/tvbox-reconcile-test HOME=/tmp/tvbox-reconcile-test bin/tvboxctl reconcile-context test-static
TVBOX_HOME=/tmp/tvbox-reconcile-test HOME=/tmp/tvbox-reconcile-test bin/tvboxctl get-context
```

This did not validate the new behavior because `tvboxctl` currently uses hardcoded defaults for `STATE_DIR` and `LOG_DIR` unless `/etc/tvboxctl.conf` overrides them. Under the sandbox it attempted `/run/user/1000/tvbox/lock` and `/home/tvbox/.cache/tvboxctl.log`, which are not writable here.

Deploy validation was run by the user after installing the repo update. The confirmed working behavior is that leaving Kodi enters desktop context and the controller uses the generic controller keyboard/mouse profile.

## Known risks

This depends on `tvbox-kodi` being the path that launched Kodi. If Kodi is launched directly with `/usr/bin/kodi`, there is no wrapper supervisor to reconcile state after exit.

The reconciliation command infers state from process/window checks. If a process lingers briefly after exit, the context may remain app-specific until the next explicit Home/launch/status workflow changes it.

## Rollback notes

Restore the previous `bin/tvbox-kodi` and `bin/tvboxctl` from git. If deployed, rerun `sudo /opt/tvbox-system/install.sh` so `/usr/local/bin/tvbox-kodi` and `/usr/local/bin/tvboxctl` point back at the prior repo versions.

## Status

validated
