# TVBox Focus, CEC, Display, and Input Diagnostic Discovery

Discovery date: 2026-07-25 (America/Chicago)

This is a record of observed capability, not a recovery design. Commands were
read-only. No Kodi action, focus request, input profile change, CEC control
message, display change, service restart, or TV power action was performed.

## Session limitation

The inspection ran as `tvbox` over a TTY/SSH-style execution context:

```text
uid=1000(tvbox) gid=1000(tvbox) groups=1000(tvbox),65534(nogroup)
XDG_RUNTIME_DIR=/run/user/1000
WAYLAND_DISPLAY=
DISPLAY=
XDG_SESSION_TYPE=tty
```

`/run/user/1000/wayland-0` existed, but no labwc or Kodi process was running and
both `wlrctl` and `wlr-randr` failed to connect. The socket timestamps predated
this inspection. Live app IDs/titles, activated toplevel, JSON-RPC state, CEC
coexistence, raw FLIRC observation, and a controlled TV cycle therefore remain
deploy-validation work. They are not guessed below.

## OS and installed tooling

Commands:

```bash
uname -a
cat /etc/os-release
labwc --version
kodi --version
wlrctl --version
wlr-randr --version
cec-ctl --version
cec-client --version
dpkg-query -W
```

Relevant exact output:

```text
Linux tvbox 6.12.47+rpt-rpi-2712 #1 SMP PREEMPT Debian 1:6.12.47-1+rpt1 (2025-09-16) aarch64 GNU/Linux
Debian GNU/Linux 13 (trixie), VERSION_ID=13, DEBIAN_VERSION_FULL=13.1
labwc 0.8.4
Kodi 21.3, Debian package 3:21.3+dfsg-1+rpt2
wlrctl v0.2.2 (package 0.2.2-2)
wlr-randr package 0.4.1-1
cec-ctl 1.30.1 (v4l-utils 1.30.1-1)
cec-client: command not found
libcec7 7.0.0-1+rpt1
antimicrox executable present at /usr/bin/antimicrox; no owning dpkg package reported
evtest 1.35-1+b1
libinput 1.28.1-1
udev 257.13-1~deb13u1
python3 3.13.5-1
```

## Wayland and focus capability

Exact `wlrctl --help`:

```text
Usage: wlrctl [options] [keyboard|pointer|toplevel] <action>

  -h, --help     Show a help message and quit
  -v, --version  Show a version number and quit
```

The installed syntax is `wlrctl toplevel list`; `window` is not shown as a
supported object. The output format observed in prior repo evidence is one
`app_id: title` line per toplevel. Version 0.2.2 has no documented field for
activated/focused state. It can request `toplevel focus <selector>`, but a
passive diagnostic must not use that to discover focus.

Attempting the passive list in this inspection produced:

```text
wlrctl: ../main.c:177: main: Assertion `state.display' failed.
failed to connect to display
```

`labwc --help` exposes configuration, exit, reconfigure, startup/session, and
logging switches. It does not expose a passive focus query. No other supported
labwc focus interface was found in the current repo/session. X11 active-window
tools are therefore not used.

Repo implementation comments state Kodi's observed labwc app ID is `Kodi`.
Historical Steam Link lines are `shell: SteamLink`, `shell: Streaming Client`,
or `shell: <title> [Streaming]`. These must be re-recorded from a live graphical
session before being treated as current discovery output. Other current app
IDs/titles were unavailable.

Conclusion: list app IDs/titles where `wlrctl toplevel list` works; report focus
as `unknown`. Do not label a confirmed focus mismatch on this installation
without a new activation-capable interface.

## Kodi introspection

The repo configures:

```text
http://127.0.0.1:8080/jsonrpc
```

Existing `tvboxctl` already uses `GUI.GetProperties(currentwindow)`. Historical
Kodi log evidence says:

```text
JSONRPC v13.5.0: Successfully initialized
JSONRPC Server: Successfully initialized
```

During this inspection Kodi was absent and all `curl` queries failed with:

```text
curl: (7) Failed to connect to 127.0.0.1 port 8080
```

The diagnostic tool queries, with a two-second bound:

```text
JSONRPC.Ping
GUI.GetProperties(currentwindow,currentcontrol)
Player.GetActivePlayers
Player.GetProperties(speed,percentage,time,totaltime,position)
Player.GetItem(title,file,type,label)
```

It marks Plex only when returned Kodi strings contain `plex`,
`script.plexmod`, or `plugin://script.plexmod`. Historical logs confirm
`script.plexmod v1.0.6` was installed and ran, but live differentiation remains
untested. JSON-RPC failure does not fail a snapshot.

## TVBox runtime state and locks

Canonical defaults in repo code:

```text
/run/user/1000/tvbox/active-context       one line, logical context
/run/user/1000/tvbox/input-profile        one line, selected profile
/run/user/1000/tvbox/lock                 flock(2) transition lock
/run/user/1000/tvbox/inputctl.lock        flock(2) input-profile lock
/run/user/1000/tvbox/antimicrox.pid       decimal PID
/run/user/1000/tvbox/button-home-state    "<epoch-seconds> <count>"
/run/user/1000/tvbox/button-exit-state    "<epoch-seconds> <count>"
/run/user/1000/tvbox/last-panic           ISO-8601 timestamp
/run/user/1000/tvbox/kodi-favourites-hint epoch seconds
```

Observed:

```text
active-context=kodi
input-profile=kodi_native_minimal
tvboxctl: Kodi not running; all controlled external apps not running
tvbox-inputctl: AntiMicroX not running; controller-target=all
```

Both zero-length lock files existed but nonblocking `flock -n <path> true`
succeeded: neither lock was held. File presence or mtime is not lock ownership.
The passive test is to attempt a nonblocking exclusive flock and immediately
release it. `lslocks` may identify an owner only while the lock is held. A file
age is not a reliable held duration; the observer times continuous held
observations from its own monotonic clock.

## CEC

`cec-ctl` supports `--monitor`, `--monitor-all`, `--show-raw`,
`--show-topology`, and power-status messages. `cec-client` is unavailable.

No `/dev/cec*` or `/sys/class/cec/cec*` was visible in this execution context.
Consequently adapter-to-HDMI mapping, permissions/group, topology, TV
power-status query, coexistence with Kodi/libCEC, and off/on broadcasts could
not be tested. No CEC message was transmitted.

The separate `tvbox-diag cec-watch` uses passive `cec-ctl --monitor` only.
Periodic power queries default off (`CEC_QUERY_ENABLED=0`) and remain
unimplemented until a controlled coexistence test proves the exact query safe.
It does not claim to intercept CEC.

## HDMI, DRM, and Wayland output

Observed connectors:

```text
card1-HDMI-A-1: status=disconnected enabled=disabled dpms=On
  modes: none; EDID empty
card1-HDMI-A-2: status=connected enabled=enabled dpms=On
  modes include 1920x1080, 1920x1080i, 1280x1024, 1280x960,
  1360x768, 1280x720, 1024x768, 800x600, 720x480,
  720x480i, and 640x480
  EDID SHA-256=74b048f04f96da551b871a2d6b2362be9f7aaa825c84ba091b0e62b19f66a3c5
```

Kodi's prior log identified:

```text
Hisense Electric Co., Ltd. HDMI
1920x1080 @ 60.00Hz
```

This maps the used display to the second vc4 HDMI connector/HDMI-A-2. DRM
connected is not treated as proof that the TV is on because a TV may retain HPD
and EDID in standby.

`udevadm monitor --udev --property` is available and can passively report DRM
and input events. `wlr-randr` could not connect during this inspection. A
controlled TV-off/on cycle was not performed.

## Input and controllers

Sysfs/udev identified:

```text
FLIRC
  USB path 3-2
  VID:PID 20a0:0006
  serial 0BCB17BE50584832322E3120FF022B15
  event node in sysfs: event8

8BitDo receiver at 1-1.1.2
  VID:PID 2dc8:310a
  product 8BitDo Ultimate 2C Wireless Controller
  serial E438326060
  event10/event16/event17 and js0 in sysfs

8BitDo receiver at 1-1.3
  VID:PID 2dc8:301c
  product IDLE
  serial 8FCA7505C6

8BitDo receiver at 1-1.4
  VID:PID 2dc8:301c
  product IDLE
  serial E5245226B5
```

The execution sandbox did not expose `/dev/input`, so permissions, by-id/by-path
links, safe passive event duplication, and current Kodi file descriptors could
not be tested. The coordinator observes lifecycle through udev/sysfs and never
opens/grabs event devices. It does not record general keyboard text. Direct
observation of which Wayland client received a key is unavailable; raw arrival
(only after explicit FLIRC validation), activated toplevel when available, and
Kodi state are the intended proxy.

Historical evidence from the required incident report and Kodi log includes:

```text
ScanEvents: failed to read joystick "Generic X-Box pad" on /dev/input/js1 - 19 (No such device)
ScanForJoysticks: can't open /dev/input/js1 (errno=13)
```

At 01:53:35 path `1-1.3` disconnected and returned as `2dc8:301c IDLE`.
Kodi later unregistered a joystick. Node indices are not stable identities.

## Conclusions and unavailable capabilities

- The evidence supports at least two distinct incident classes: controller-only
  reacquisition failure and possible focus/display failure.
- HDMI-A-2 is the active connector in the captured state.
- `wlrctl` can list toplevel app IDs/titles when connected, but no installed
  supported interface exposes activated/focused state.
- Kodi JSON-RPC is configured and historically initialized, but was unavailable
  with Kodi stopped.
- `flock`, not lock-file presence, identifies an active transition.
- Stable controller identity must combine USB serial/path and VID/PID.
- CEC, direct input-node access, live Wayland state, and all controlled power
  cycles remain explicitly unvalidated.
