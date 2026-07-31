# Streaming, Chromium, and game state feasibility

Date: 2026-07-28

Status: validated discovery; no production implementation

## Goal

Establish observable application phases for Moonlight, Steam Link, Chromium/YouTube,
Mario Kart 64, and Kodi returns before designing phase-aware input, screensavers, or
loading overlays. This note does not implement those systems or revise the main
screensaver architecture plan.

## 1. Environment and baseline

At `2026-07-28T09:10:35-05:00`, after canonical `tvbox-tv activate --json`:

- TV state was `on`, CEC power `on`, DRM connected/enabled/DPMS On.
- TVBox was active HDMI source `1.0.0.0`.
- Kodi process and `Kodi: Kodi from Debian` toplevel existed.
- `active-context=kodi`; profile `kodi_native_minimal`.
- No Moonlight, Steam Link, YouTube Chromium, or Mupen64Plus process existed.
- User services were healthy; uptime began `2026-07-25 23:56:22`.
- The first sandboxed baseline briefly observed `context=kodi` with no Kodi process;
  canonical TV activation/focus recovery then started Kodi. This alone proves context
  is not a readiness assertion.

The YouTube profile contained stale-looking `SingletonCookie`, `SingletonLock`
(`tvbox-51131`), and `SingletonSocket` links dated July 27. They did not prevent the
tested launch.

## 2. Observation method

Inspected repo wrappers, add-ons, current input profiles, `tvboxctl` and
`tvbox-inputctl`. A disposable observer at
`/tmp/tvbox-app-state-discovery/observe.sh` sampled nominally every 200 ms and wrote
change records containing context, input profile, lifecycle lock, narrow process
matches, `wlrctl` toplevels, relevant TCP sockets, and log fingerprints. Screenshots
were taken only after TV/source confirmation. Inputs were individual `wtype` keys.

The observer's TERM trap removed its PID file without exiting the loop; `timeout`
parents consequently left sampling children. All exact observer and timeout processes
were force-stopped at the end. The captures remain disposable under `/tmp`; no
observer remains running.

Relevant evidence sources:

- `/home/tvbox/.cache/tvboxctl.log`
- `/home/tvbox/.cache/tvbox-moonlight.log`
- `/home/tvbox/.cache/tvbox-steamlink.log`
- `/tmp/tvbox-youtube.log` and per-run wrapper captures
- process command lines, `wlrctl toplevel list`, screenshots, input-profile state

Absolute 200 ms precision is not claimed: process enumeration, sockets, and
screenshots add sampling latency. Timings below are wall-clock bounds.

## 3. Generic Moonlight menu timeline

| Time | Observed phase | Evidence |
|---|---|---|
| 09:13:43 | launch requested | Kodi Favourites visually confirmed; add-on action issued |
| 09:13:44.448 | client-starting | profile changed to `passthrough`; Kodi still present |
| about 09:13:45-09:14 | menu-loading | Kodi closed; wrapper and then `moonlight-qt` appeared |
| 09:14 screenshot | menu-ready | `com.moonlight_stream.Moonlight: Moonlight`; Computers view showed known host `obtuse` |
| 09:15:40 | inconsistent stable state | Moonlight menu ready, but context still `kodi` and profile had reverted to `kodi_native_minimal` |
| 09:15:40-09:15:46 | returning | one F12; local Moonlight exited; wrapper cleanup launched canonical Kodi |
| 09:15:46 | Kodi ready | Kodi process and toplevel both present |

Keyboard navigation was accepted (Right did not open an unknown dialog). Current
passthrough is not useful for controller menu navigation, and focus recovery can
overwrite it with the Kodi profile. F12 from menu was proven non-destructive locally.

## 4. Direct Moonlight Steam timeline

| Time | Observed phase | Evidence |
|---|---|---|
| 09:16:09 | launch requested | direct Steam add-on invoked |
| 09:16:10.122 | client-starting | profile `passthrough`; Kodi still present |
| by 09:16:19 | stream-requested/preflight | wrapper `tvbox-moonlight steam`; `moonlight-qt stream 192.168.1.189 Steam Big Picture`; Moonlight toplevel |
| 09:16:19 | blocked/failed branch | visual dialog: “Are you sure you want to quit Desktop?” |
| 09:16:39-09:16:44 | returning | F12 closed local client; wrapper cleanup returned Kodi |

The direct wrapper detected a target change and ran `moonlight-qt quit` before the
stream request. The unexpected prompt was not answered. No streaming claim can be
made. Moonlight logs prove host discovery and request traffic but not a new video
session. F12 was safe locally. Remote Steam persistence was not directly provable in
this branch; no Sunshine quit confirmation or undo was sent by the F12 path.

## 5. Steam Link menu and stream timeline

| Time | Observed phase | Evidence |
|---|---|---|
| 09:17:05.580 | launch-requested | lifecycle lock held |
| 09:17:05.852 | client-starting | profile changed to `passthrough` while Kodi remained |
| by 09:17:11 | menu-ready | process accepted launch; `shell: SteamLink`; context committed `steamlink` |
| 09:17:16 | menu-ready, high confidence | visual `Start Playing`, selected `obtuse`, controller green, connection green |
| 09:17:38 | stream-requested | one Enter on the identified target |
| 09:17:39-09:17:47 | failed | window and process disappeared; no stream toplevel/socket; desktop exposed |
| 09:17:47 | stale failure state | context `steamlink`, profile `passthrough`, but no process/window |
| 09:18:07-09:18:12 | returning/ready | F12 fallback launched Kodi; process+toplevel confirmed |

The prior “context but no process” problem was not a missing executable or Wayland
environment in this run: `/usr/bin/steamlink` successfully produced the menu.
Starting the identified host caused immediate client exit. Existing log history
contains past `Session state Streaming` and decoder evidence, but that predates this
test and is not proof of this run. No menu-loading, connecting, or streaming Home test
was possible beyond menu-ready and the failed desktop state.

## 6. Chromium/YouTube cold and warm timelines

No reboot was approved or performed. “Cold” means first tested launch in the current
multi-day boot, not reboot-cold.

### First-in-session launch

| Time | Observed phase | Evidence |
|---|---|---|
| 09:18:54.554 | launch-requested | canonical wrapper started; Kodi present |
| 09:18:55.916 | desktop-gap/client-starting | profile `controller_kbm_generic`; Kodi teardown in progress |
| by 09:18:58 | window/page-loading | Chromium tree with dedicated profile; `www.youtube.com__tv: YouTube on TV`; Kodi absent |
| 09:19:05 | menu-ready, high visual confidence | fullscreen YouTube account/guest chooser was usable-looking |
| 09:19:41 | returning failure | F12 closed Chromium and wrote context/profile for Kodi |
| 09:19:55 | failed return | `context=kodi`, `kodi_native_minimal`, but no Kodi process/toplevel |
| 09:20:10-09:20:15 | recovery | second F12 fallback produced Kodi process+toplevel |

Chromium used the expected dedicated profile, `--app=https://www.youtube.com/tv`,
`--start-fullscreen`, and X11/Ozone under Wayland. Errors included VSync parameter
failures and a deprecated GCM endpoint, but the page became visually ready.

The exact close matcher is also hazardous to observations: `pkill -f
"chromium.*chromium-tvbox-youtube"` matched the diagnostic shell whose command line
contained that pattern and terminated it. This is narrow relative to all Chromium,
but not ownership-safe.

### Warm launch

| Time | Observed phase | Evidence |
|---|---|---|
| 09:20:56.262 | launch-requested | Kodi present |
| 09:20:57.674 | desktop-gap | generic browser profile active during Kodi teardown |
| about 09:21:00 | window/page-loading | Chromium process tree appeared |
| 09:21:04 | menu-ready | same YouTube title and ready screen |
| 09:21:31-09:21:34 | returning/ready | separately issued F12; Kodi process+toplevel present after 3 s |

Both launches mapped a useful page in roughly 4-10 seconds. The reboot-adjacent
first-launch failure remains unresolved. Browser mapped versus page ready is
distinguishable by process/toplevel plus visual/DOM-specific future evidence;
playback was not tested and cannot be inferred from the title.

## 7. Mario Kart 64 timeline

| Time | Observed phase | Evidence |
|---|---|---|
| 09:21:50.648 | launch-requested | lifecycle lock held |
| 09:21:50.949 | emulator-starting | profile prematurely `passthrough`; Kodi still present |
| by 09:21:55 | window-loading/game-loading | Mupen process detected; context `mariokart64`; Kodi briefly still present |
| 09:21:59 | game-loading | `mupen64plus` toplevel; visual “Mupen64Plus Started...” Nintendo splash; profile `mariokart_n64` |
| before 09:23:00 | failed | emulator and window disappeared; desktop exposed |
| 09:23:21 | stale failure state | context `mariokart64`, profile file `mariokart_n64`, no emulator/Kodi/toplevel |
| 09:23:21-09:24:14 | returning/ready | one F12 fallback; Kodi process+toplevel confirmed |

The game never reached a proven title/menu/input-ready state. Process presence and
even mapped splash are insufficient. Future readiness needs an emulator/wrapper event
or conservative bounded delay followed by window liveness; delay alone is only
medium-confidence inference.

## 8-11. Evidence, Home results, profiles, and failures

| App/path | Phase | Detectable | Evidence | Confidence | Home tested | Recommended input profile | Saver safe |
|---|---|---|---|---|---|---|---|
| Moonlight menu | client-starting | yes | wrapper/process/profile/Kodi teardown | high | no | `streaming_client_menu` | no |
| Moonlight menu | menu-ready | yes | Moonlight toplevel + Computers screenshot | high | yes, passed | `streaming_client_menu` | no |
| Moonlight Steam | stream-connecting | partial | target command + remote quit dialog; no session evidence | low | F12 from blocked preflight passed | `streaming_client_menu` | no |
| Moonlight Steam | streaming | not this run | only historical decoder/session logs | none | no | `passthrough` | no |
| Steam Link | menu-loading | weak | process before stable screenshot | medium | no | `streaming_client_menu` | no |
| Steam Link | menu-ready | yes | `shell: SteamLink` + selected-host green checks | high | indirect after failure | `streaming_client_menu` | no |
| Steam Link | stream-connecting | partial | Enter then rapid exit | low | failed-state Home passed | `streaming_client_menu` | no |
| Steam Link | streaming | no | no current-run stream window/session | none | no | `passthrough` | no |
| YouTube | desktop-gap | yes | Kodi gone/no app window; browser profile active | high | not isolated | `controller_kbm_generic` | no |
| YouTube | page-loading | partial | Chromium tree + mapped titled window | medium | no | `controller_kbm_generic` | no |
| YouTube | menu-ready | yes | fullscreen usable account/guest chooser | high | cold failed once; warm passed | `controller_kbm_generic` | policy-dependent; initially no |
| Mario Kart 64 | emulator-starting | yes | wrapper/process/profile/Kodi overlap | high | no | transitional navigation/global Home | no |
| Mario Kart 64 | ready | no | only emulator splash observed | none | failed-state Home passed | `mariokart_n64` only after ready | no |

Proven failures:

- Moonlight lifecycle context remained `kodi` throughout client foreground use.
- A focus/recovery path restored Kodi profile while Moonlight menu was foreground.
- Direct Moonlight target switching exposed a remote “quit Desktop” confirmation.
- Steam Link exited after Start Playing, leaving context/profile stale on desktop.
- Cold YouTube Home committed Kodi before Kodi existed; second Home recovered.
- YouTube `pkill -f` can match unrelated command lines containing the profile pattern.
- Mario Kart exited during splash and left stale game context/profile.
- Launch paths overlap old and new applications briefly; process alone is not readiness.

## 12. Proposed normalized state schema

```json
{
  "schema_version": 1,
  "lifecycle_context": "application",
  "requested_target": "steam",
  "transition": {
    "state": "active",
    "phase": "stream-connecting",
    "started_at": "RFC3339 timestamp"
  },
  "foreground": {
    "application": "moonlight",
    "view": "stream",
    "process_observed": true,
    "toplevel_observed": true
  },
  "client": {
    "name": "moonlight",
    "phase": "stream-connecting"
  },
  "connection_state": "connecting",
  "content_readiness": "not-ready",
  "concurrent_remote_session": {
    "kind": "steam",
    "state": "possibly-running"
  },
  "input_profile": "streaming_client_menu",
  "confidence": "medium",
  "failure_reason": null
}
```

Use phase vocabulary: `absent`, `launch-requested`, `client-starting`,
`menu-loading`, `menu-ready`, `content-loading`, `stream-requested`,
`stream-connecting`, `streaming`, `disconnecting`, `returning`, `ready`, `failed`,
`unknown`. Add observed `desktop-gap` as a foreground view, not a client phase.

Wrapper facts are intent: requested target, command accepted, wrapper alive.
Direct observations are PID identity, exit code, toplevel/app-ID/title, explicit
client log state, and Kodi process+toplevel. Inferences combine multiple direct facts.
Confidence: high for authoritative log or process+toplevel+visual agreement; medium
for two independent indirect signals; low for intent/process alone; none when absent.

## 13. Reconciliation and precedence rules

1. Explicit failure/exit and fresh direct observations outrank stored context.
2. Stable context is committed only after launch acceptance appropriate to the app:
   menu-ready/ready/streaming, never merely after writing intent.
3. Keep requested, transitioning, and stable-reconciled state separately.
4. Steam Link context with no exact process and no matching toplevel becomes `failed`;
   change passthrough to transitional navigation and start bounded Kodi recovery.
5. Moonlight wrapper active with exited client becomes `returning`; never streaming.
6. Client process with ambiguous menu/stream is `client_phase=unknown`,
   `connection_state=unknown`, saver inhibited, menu-safe input.
7. YouTube intent with failed Chromium becomes `failed`; do not commit YouTube.
8. Kodi is stable only when both exact Kodi process and Kodi toplevel exist. Process
   without toplevel is `returning` until a deadline, then `failed`.
9. Mario Kart process without window remains `emulator-starting`; deadline expiry or
   process exit is `failed`.
10. Passthrough without a validated streaming foreground is immediately replaced by
    an inhibited/transitional Home-capable profile.
11. Home in every phase atomically records `returning`, inhibits saver, installs a
    Home-capable transitional profile, performs app-specific non-destructive close,
    invokes canonical Kodi, then commits Kodi only after process+toplevel readiness.
12. Disagreement never upgrades readiness; it lowers confidence and inhibits
    screensaver/phase-sensitive input until reconciled.

## 14. Screensaver implications

Initial safe policy: inhibit during all launch, startup, loading, connecting,
streaming, failure-dialog, disconnecting, and returning phases. Also inhibit whenever
foreground, context, and profile disagree. Kodi stable policy remains separate.
YouTube menu-ready could eventually permit a long timeout only with reliable page
readiness and safe input-source ownership. Streaming and game phases should remain
inhibited initially.

## 15. Future loading-overlay readiness implications

- Moonlight menu: dismiss on Moonlight toplevel plus Computers view evidence.
- Moonlight stream: dismiss only on explicit session/decoder/video evidence, not PID.
- Steam Link menu: dismiss on `shell: SteamLink` plus ready UI signal.
- Steam Link stream: dismiss on streaming title/window plus current-run session/video.
- YouTube: keep overlay through desktop gap; dismiss on page-specific ready signal,
  not Chromium mapping.
- Mario Kart: keep overlay through splash; dismiss on wrapper/emulator readiness event.
- Kodi return: dismiss only after exact process+toplevel and transition completion.

## 16. Minimal implementation prerequisites

1. Versioned structured state written atomically with timestamps and evidence source.
2. Requested/transition/stable separation and bounded reconciler.
3. Exact PID ownership or cgroup tracking for wrappers; avoid pattern-only closes.
4. Toplevel observation helper with Kodi readiness predicate.
5. Per-client log adapters for explicit session states where available.
6. Home-capable `streaming_client_menu` and transitional/inhibited policy, created
   only in a later implementation task through `tvbox-inputctl`.
7. Wrapper exit-code/failure capture, especially Steam Link and Mupen64Plus.
8. Tests that stale passthrough and false Kodi success cannot persist.

## 17. Known limitations and unresolved gates

- No reboot-cold YouTube test; first-after-reboot failure remains open.
- Moonlight Steam streaming was blocked by an unexpected remote quit confirmation.
- Remote Steam persistence on Obtuse was not authoritatively observable.
- Steam Link streaming failed before a current-run session could be proven.
- Mario Kart never reached game-ready.
- YouTube playback was not tested.
- Home was not tested independently in every loading/connecting phase because those
  phases were too brief, unsafe, or not reached.
- Screenshots are visual evidence only; no OCR/DOM/client accessibility API was used.
- Historical Steam Link streaming logs prove capability, not current-run state.

## Commands used

Representative commands:

```text
git status --short
tvbox-tv status
tvbox-tv status --json
tvbox-tv activate --json
tvboxctl status
tvbox-inputctl status
wlrctl toplevel list
pgrep -af ...
systemctl --user --no-pager --type=service
kodi-send --action=RunAddon(...)
/usr/local/bin/tvboxctl launch steamlink
/usr/local/bin/tvboxctl launch mariokart64
/usr/local/bin/tvbox-youtube
wtype -k F12
wtype -k Return
grim /tmp/tvbox-app-state-discovery/*.png
```

## Validation checklist and test results

- [x] Repo wrapper/add-on/profile inspection
- [x] TV on and TVBox active source before screenshots
- [x] Generic Moonlight menu and Home
- [x] Direct Moonlight bounded safely at unexpected dialog
- [x] Steam Link menu; one identified-host Enter; failure recovery
- [x] First-in-session and warm YouTube; Home return race characterized
- [x] Mario Kart startup/splash/failure recovery
- [x] Kodi restored with process and toplevel
- [x] Local Moonlight disconnected
- [x] Disposable observer stopped
- [ ] Reboot-cold YouTube (not approved/run)
- [ ] Current-run Moonlight/Steam Link streaming (not reached)
- [ ] Mario Kart ready (not reached)

Repo validation and final appliance checks are recorded in the final validation
section below after they are run.

Final validation results:

- `python3 -m pytest -q`: unavailable because the system Python has no `pytest`
  module.
- `python3 -m unittest discover -s tests -v`: 28 tests passed.
- `git diff --check`: passed.
- Final screenshot visually confirmed Kodi Favourites.
- Final `tvboxctl status`: Kodi running; all four tested external clients absent.
- Final `wlrctl`: only intended local foreground toplevel was Kodi.
- Final observer query: no disposable observer process.
- Final TV state: on and active, source `1.0.0.0`, DRM connected/enabled/On.
- No deploy validation, reboot, service restart, installer, or production edit was
  performed.

## Known risks

The current coarse context can select unsafe passthrough during failure/desktop gaps,
claim Kodi before recovery, and hide launcher failures. Direct Moonlight target
switching may affect an existing remote Sunshine session before the requested stream
is established.

## Rollback notes

Documentation-only change: remove this note. No production file, service, wrapper,
symlink, input profile, or live configuration was changed.
