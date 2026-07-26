# Kodi Desktop Focus-Loss Incident

## Goal

Document the 2026-07-25 incident in which Kodi Favourites remained visible but
neither the FLIRC remote nor the controllers produced a visible response in
Kodi, and preserve the live evidence gathered before recovery or restart.

This is an incident report and diagnostic record. It does not implement a fix.

## Current behavior

TVBox runs Kodi fullscreen as a Wayland client under Labwc. PCManFM also runs
with `--desktop`, providing the desktop beneath Kodi.

The active TVBox context was `kodi` and the selected input profile was
`kodi_native_minimal`:

- Kodi handles normal controller navigation through its native joystick
  peripheral.
- AntiMicroX maps only the controller recovery buttons and targets all
  controllers.
- FLIRC presents as a USB keyboard and is handled by Labwc through the Wayland
  keyboard path.
- Home/F12 is a global Labwc binding intended to assert Kodi and return to
  Favourites.

## Problem being solved

At approximately 21:50 local time on 2026-07-25, the user observed:

- Kodi Favourites was visible.
- Controller input produced no visible Kodi response.
- FLIRC remote input produced no visible Kodi response.
- The failure therefore appeared broader than the earlier controller-only
  reconnect incident.

During a controlled diagnostic test, repeated FLIRC Left and OK presses opened
`/home/tvbox/Desktop/test.txt` in Mousepad. The same FLIRC arrows then navigated
inside Mousepad.

This demonstrated that FLIRC events were reaching the graphical session but
were not being delivered to Kodi.

## Diagnostic findings

### Graphical session and process state

Kodi and the desktop session remained running:

```text
/usr/bin/labwc -m
/usr/bin/pcmanfm --desktop
/usr/local/bin/tvbox-kodi
/usr/lib/aarch64-linux-gnu/kodi/kodi.bin -fs --audio-backend=alsa
/usr/bin/antimicrox --hidden --profile \
  /opt/tvbox-system/input-profiles/kodi_native_minimal.gamecontroller.amgp
```

Kodi had been running since `01:33:11`. Labwc and PCManFM had been running
since the July 5 desktop-session start. There was no Kodi restart during this
incident capture.

Before the FLIRC test, `wlrctl toplevel list` reported only:

```text
Kodi: Kodi from Debian
```

The installed Wayland tooling can list toplevels but cannot report the
activated/focused surface. PCManFM's desktop surface is not represented as a
normal toplevel in this output. The single listed Kodi toplevel therefore did
not prove that Kodi had keyboard focus.

After the FLIRC Left/OK test, the toplevel list reported:

```text
mousepad: *~/Desktop/test.txt - Mousepad
Kodi: Kodi from Debian
```

Mousepad started at `21:54:25` with this ancestry:

```text
pcmanfm --desktop
└─ mousepad file:///home/tvbox/Desktop/test.txt
```

The direct PCManFM parent proves that the desktop opened the file. There was no
Labwc key binding for Mousepad or `test.txt`. The evidence supports this
sequence:

1. Kodi remained visible but did not own keyboard focus.
2. PCManFM's desktop owned keyboard focus.
3. FLIRC Left navigated desktop selection.
4. FLIRC OK, emitted as Enter, activated the selected `test.txt` desktop item.
5. PCManFM launched Mousepad, which then received the FLIRC arrow events.

This is strong evidence of desktop focus loss/focus theft rather than FLIRC
hardware failure.

### TVBox state

Live TVBox state was internally consistent:

```text
active-context:       kodi
input-profile:        kodi_native_minimal
antimicrox-running:   yes
antimicrox-pid:       198106
controller-target:    all
```

No YouTube, Spotify, Moonlight, Steam Link, or Mario Kart process was detected.
The runtime context did not notice that input focus had moved to the desktop.

The passive diagnostic systemd user services were not installed/enabled in the
live session at the time of the incident. The repo-owned `tvbox-diag status`
command was run directly.

### Input-device state

Linux exposed the following stable input identities during the failure:

```text
FLIRC
  serial:    0BCB17BE50584832322E3120FF022B15
  USB path:  3-2
  event:     /dev/input/event8

8BitDo Ultimate 2C
  serial:    E438326060
  USB path:  1-1.1.2
  joystick:  /dev/input/js0
  event:     /dev/input/event10

8BitDo Ultimate 2C
  serial:    8FCA7505C6
  USB path:  1-1.3
  joystick:  /dev/input/js1
  event:     /dev/input/event18

8BitDo IDLE
  serial:    E5245226B5
  USB path:  1-1.4
```

Open-node ownership was:

```text
/dev/input/event8   labwc       FLIRC keyboard
/dev/input/event10  antimicrox  first controller event node
/dev/input/event18  antimicrox  second controller event node
/dev/input/js0      kodi.bin    first native joystick
/dev/input/js1      kodi.bin    second native joystick
```

Therefore:

- FLIRC was present and open by Labwc.
- Both active controllers were present.
- Kodi held both joystick nodes open.
- AntiMicroX held both controller event nodes open.
- The failure was not explained by absent nodes or simple node permissions.

The FLIRC test behavior independently confirmed raw input delivery through
Labwc. A simultaneous `evtest` capture was started but interrupted before its
output could be collected; no raw event transcript is claimed.

### Controller reconnect immediately before the report

The receiver at USB path `1-1.3`, serial `8FCA7505C6`, transitioned at:

```text
21:50:44.840  USB disconnect, device number 115
21:50:45.096  new USB device number 116
21:50:45.220  Ultimate 2C identified
21:50:45.384  Generic X-Box pad input created
21:50:45.392  controller keyboard input created
21:50:45.524  controller mouse input created
21:50:47.204  Kodi initialized joystick 0
21:50:47.224  Kodi registered the joystick
```

Kodi successfully logged joystick registration after this reconnect. This
differs from the earlier confirmed stale-joystick failure, although the
controller transition may have contributed to session churn.

### HDMI/Wayland transitions

Kodi recorded several output changes shortly before the failure:

```text
21:49:35  Hisense output changed to Unknown Unknown, 1920x1080 @0 Hz
21:49:44  Hisense output returned, 1920x1080 @60 Hz
21:50:03  output changed again to Unknown Unknown, 1920x1080 @0 Hz
21:50:04  Hisense output returned, 1920x1080 @60 Hz
```

Kodi remained running and continued rendering after the output returned.

The temporal relationship makes HDMI/Wayland reconfiguration a plausible
trigger for the desktop receiving focus, but the available logs do not expose
an activated-surface transition and do not prove causality. Controller
reconnect and HDMI churn occurred in the same short interval and must not be
treated as causal without a controlled reproduction.

### Kodi state and logs

Kodi's log showed:

- normal Wayland initialization;
- both joysticks initialized at Kodi startup;
- an earlier `js1` removal at `01:53`;
- successful registration of the reconnected joystick at `21:50:47`;
- no Kodi crash, shutdown, or restart during the focus-loss capture.

Kodi's HTTP JSON-RPC endpoint responded with HTTP 401 to the unauthenticated
manual GUI query. This prevented that query from recording the current Kodi
control, but it does not indicate Kodi process failure.

The Favourites view remained visible. Visible fullscreen content is therefore
not sufficient evidence that Kodi owns keyboard focus.

## Confirmed incident timeline

Times are local (`America/Chicago`) on 2026-07-25:

```text
21:49:35        Kodi sees HDMI output become Unknown/0 Hz.
21:49:44        Hisense HDMI output returns at 1920x1080/60 Hz.
21:50:03        Kodi sees a second Unknown/0 Hz transition.
21:50:04        Hisense HDMI output returns again.
21:50:44.840    8BitDo receiver 8FCA7505C6 disconnects.
21:50:45-45.524 Receiver and all input interfaces are recreated.
21:50:47.204    Kodi initializes the recreated joystick.
21:50:47.224    Kodi registers the recreated joystick.
~21:52          User reports visible Kodi Favourites with no controller or
                FLIRC response in Kodi.
21:53           Diagnostics show Kodi as the only listed Wayland toplevel,
                correct context/profile, stable devices, and expected open
                node ownership.
21:54:25        During FLIRC Left/OK testing, PCManFM launches Mousepad for
                /home/tvbox/Desktop/test.txt.
21:55+          FLIRC arrow presses visibly navigate Mousepad.
```

## Failure classification

Confirmed:

- FLIRC hardware and kernel enumeration were healthy.
- FLIRC input reached Labwc and the graphical session.
- PCManFM desktop handled the FLIRC activation and launched Mousepad.
- Kodi remained running and visible but did not receive the FLIRC navigation.
- Both controllers were present and open by Kodi/AntiMicroX.
- The TVBox runtime context and input profile remained set to Kodi.

Strongly supported:

- Kodi lost effective input focus to the PCManFM desktop.
- The desktop focus state was invisible to the existing passive toplevel probe.

Not yet confirmed:

- The exact event that transferred focus from Kodi to PCManFM.
- Whether HDMI reconnection, controller reconnection, a pointer event, or
  another Labwc/PCManFM interaction caused the focus transfer.
- Whether controller input was also being delivered to the desktop or was
  independently affected by native Kodi joystick handling.
- Whether Home/F12 would have restored Kodi focus without a Kodi restart.

## Controlled reproduction after diagnostic deployment

After running `install.sh`, rebooting, and starting
`tvbox-healthd.service`, the TV was turned off and back on. The same failure
recurred: Kodi remained visible but controller and FLIRC input did not navigate
Kodi.

The observer recorded:

```text
22:07:45  vc4 HDMI infoframe warning; Kodi reports Hisense at 1080p60
22:07:52  Kodi output becomes Unknown/0 Hz
22:08:02  Hisense output returns at 1080p60
22:08:20  output becomes Unknown/0 Hz and returns within about 0.3 seconds
22:08:35  health observer confirms HDMI-A-2 connected with the expected EDID
22:08:50  a new pcmanfm trash:/// toplevel appears
```

The runtime context/profile remained `kodi`/`kodi_native_minimal`, Kodi remained
running, and Kodi held both joystick nodes open. The new Trash window showed
that desktop activation again received input after HDMI churn.

The user then ran:

```text
XDG_RUNTIME_DIR=/run/user/1000
WAYLAND_DISPLAY=wayland-0
wlrctl toplevel focus app_id:Kodi
```

Both FLIRC and controller input recovered immediately without restarting Kodi.
This confirms compositor focus assertion as a sufficient recovery for this
failure class.

The bounded diagnostic bundle is:

```text
/home/tvbox/.cache/tvbox-diag/tvbox-diagnostics-20260725T221234-0500.tar.gz
```

CEC inspection confirmed `/dev/cec1` on HDMI-A-2 with physical address
`1.0.0.0`, logical address Recording Device 1, and transmit/passthrough/remote
control capabilities. A root monitor observed Kodi repeatedly transmitting
`GIVE_DEVICE_POWER_STATUS` to TV address 0 without acknowledgement. The user
observed the TV remote Back button acting as Back in Kodi, while navigation and
OK were not interpreted by Kodi. TV-side addressing and button mapping remain
incomplete and are separate from the confirmed focus recovery.

## Files expected to change

For this incident report:

```text
docs/development/2026-07-25-kodi-desktop-focus-loss-incident.md
```

Possible future implementation files require a separate approved change:

```text
bin/tvboxctl
bin/tvbox-diag
config/labwc/rc.xml
config/systemd-user/tvbox-healthd.service
install.sh
docs/current-system-redeploy.md
```

## Proposed implementation

No behavior change is implemented by this report.

Recommended diagnostic and recovery work:

1. Install the already prepared passive diagnostic tooling only after its repo
   validation passes.
2. Restart the desktop session or appliance as planned so the diagnostic user
   services start from a clean boot.
3. On the next visible-but-unresponsive Kodi incident, do not restart
   immediately. First capture `tvbox-diag status` and a diagnostic bundle.
4. Test FLIRC arrows and OK separately from each controller, avoiding activation
   of desktop files where practical.
5. Press Home/F12 once and record whether it restores Kodi focus without
   restarting Kodi.
6. Record Wayland toplevels, PCManFM/Mousepad processes, HDMI state, input-node
   ownership, controller USB transitions, Kodi log changes, and Home recovery
   logs before any panic recovery.
7. Evaluate a narrowly scoped focus assertion after HDMI output restoration,
   but only after controlled reproduction proves the relationship.
8. Extend passive diagnostics to flag the combination of Kodi context, Kodi
   process/toplevel present, and a newly launched desktop child application.
9. Do not automatically restart Kodi solely because a controller or HDMI
   device reconnects.

## Commands used

Read-only diagnostics included:

```text
git status --short
uname -a
id
ps
loginctl
systemctl --user status
journalctl
journalctl -k
cat and sed against /proc/bus/input/devices and sysfs input names
ls -la /dev/input and stable by-id/by-path links
fuser against FLIRC/controller input nodes
tail of /home/tvbox/.kodi/temp/kodi.log
tvboxctl status
tvbox-inputctl status
wlrctl toplevel list
tvbox-diag status
curl to Kodi JSON-RPC
pstree
stat /home/tvbox/Desktop/test.txt
rg against repo and live Labwc/PCManFM configuration
```

A bounded passive `evtest` command was started against FLIRC and both
controllers, then deliberately interrupted by the user. It did not grab the
devices and did not produce retained event evidence.

No installer, service restart, reboot, focus request, input-profile change,
application close, or live configuration edit was performed.

## Validation checklist

### Repo validation

- [x] Distinguish confirmed evidence from hypotheses.
- [x] Record the complete visible failure and controlled FLIRC observation.
- [x] Record the process and toplevel state.
- [x] Record context, profile, controller targeting, and input-node ownership.
- [x] Record stable FLIRC and controller identities.
- [x] Record the HDMI and controller reconnect timeline.
- [x] Explain why a single listed Kodi toplevel did not prove focus.
- [x] Record the diagnostic tooling limitations and interrupted event capture.
- [x] Preserve Home/F12 safety and avoid claiming an automatic repair.
- [x] Confirm this report does not change live behavior.

### Deploy validation

- [ ] Run the installer only after repo syntax/tests pass.
- [ ] Restart or reboot and confirm passive diagnostic services are active.
- [ ] Confirm normal Kodi, FLIRC, controller, Home/F12, and Exit/F5 behavior.
- [ ] Reproduce an HDMI off/on cycle while Kodi remains running.
- [ ] Capture whether PCManFM receives focus after HDMI restoration.
- [ ] Reproduce controller sleep/wake independently of HDMI cycling.
- [ ] Test one Home/F12 press during a confirmed desktop-focus incident.
- [ ] Confirm whether Kodi is refocused without process restart.
- [ ] Confirm diagnostic observation does not grab or delay input.

## Test results

### Repo validation

The incident report was compared with the live process list, kernel input
inventory, device-node ownership, Kodi log, Wayland toplevel list, TVBox runtime
state, PCManFM/Mousepad ancestry, and the user's direct FLIRC observation.

The evidence supports desktop focus loss. It does not establish the trigger.

The prepared installer and passive diagnostic implementation were checked
before recommending deployment:

```text
bash -n install.sh bin/tvboxctl bin/tvbox-inputctl
  passed

python3 -m py_compile bin/tvbox-diag
  passed

python3 -m unittest discover -s tests -v
  9 tests passed

python3 -m mypy --ignore-missing-imports bin/tvbox-diag
  passed with no issues

XML parse of config/labwc/rc.xml
  passed

git diff --check
  passed
```

Pre-install `systemd-analyze --user verify` resolved both units but reported
that `/usr/local/bin/tvbox-diag` did not yet exist. This is expected before
`install.sh`: the installer first creates `/usr/local/bin/tvbox-diag` as a link
to the repo script, then installs the user units. Unit verification must be
repeated after installation.

### Deploy validation

Not run for this incident report. The diagnostic services were not installed
or enabled in the current live session, and the appliance was not restarted.

## Known risks

- Treating Kodi's visible fullscreen surface as proof of focus will miss this
  failure class.
- `wlrctl toplevel list` does not expose activation and omits PCManFM's desktop
  surface, so passive focus classification remains incomplete.
- Automatically asserting focus after every HDMI event could interrupt another
  intentionally active application.
- Automatically restarting Kodi could destroy useful evidence and interrupt
  playback without repairing a compositor-focus problem.
- Controller and HDMI transitions happened close together; conflating them
  could lead to an incorrect repair.
- PCManFM desktop items allow an unfocused-looking appliance state to launch
  arbitrary desktop applications when remote arrows/OK are delivered there.
- Installing unvalidated diagnostic services could introduce observer load or
  unexpected permissions behavior; repo validation and post-install smoke tests
  are required.

## Rollback notes

This report is documentation-only. Rollback consists of removing:

```text
docs/development/2026-07-25-kodi-desktop-focus-loss-incident.md
```

No live file, service, symlink, Kodi configuration, Labwc configuration, or
input profile was changed by this report.

If a future focus fix changes Labwc, restore:

```text
/home/tvbox/.config/labwc/rc.xml
```

from the validated repo copy and restart the desktop session. If future
installer work adds diagnostic user-service symlinks, restore or remove only
the exact symlinks documented by that implementation.

## Status

Status: implemented

The incident is captured with live evidence. Root-cause reproduction and deploy
validation remain pending.
