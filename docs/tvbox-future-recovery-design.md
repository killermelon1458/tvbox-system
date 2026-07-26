# Proposed TVBox Recovery Phases 2–4

This is design only. Phase 1 implements observation and evidence capture; none
of the commands below are implemented.

## Ownership and policy

Recovery stays centered in `tvboxctl`:

```text
tvboxctl refocus
tvboxctl recover focus
tvboxctl recover input
tvboxctl recover display-soft
tvboxctl recover kodi-hard
tvboxctl display-event standby|on|unknown
tvboxctl input-event removed|added <stable-device-id>
tvboxctl recover input-profile
tvboxctl recover kodi-controller <stable-device-id>
```

Proposed configuration:

```text
TV_OFF_ACTION=observe|ignore|pause|home|shutdown
TV_ON_ACTION=observe|refocus|display-soft|kodi-hard
```

Both defaults are `observe`.

## Display state and staged TV-on handling

Track `on`, `standby`, `unavailable`, `transitioning`, or `unknown`, always with
evidence such as `cec_broadcast`, `cec_power_query`, `drm_disconnect`,
`drm_reconnect`, `wayland_output_removed`, `wayland_output_added`, or
`polling_timeout`. CEC and DRM are complementary; connected DRM is not proof of
TV power and a TV need not broadcast power-on.

Future TV-on recovery:

1. Capture the pre-recovery passive snapshot.
2. Wait until DRM/Wayland state is stable for a configurable interval.
3. Validate expected active context.
4. Repair input profile only if wrong.
5. Refocus the expected application.
6. Re-check process, surface, input, and JSON-RPC health.
7. Hard-restart Kodi only if lower-impact recovery failed with supporting evidence.

Never restart Kodi unconditionally on TV power-on. Shutting down the Pi on TV
standby removes its userspace CEC listener; `TV_OFF_ACTION=shutdown` must not be
enabled until an independent, proven wake mechanism exists.

## Controller recovery

Use serial/USB path/VID:PID and stable udev links, not `jsN`/`eventN`.
Track `absent`, `idle`, `reconnecting`, `present_unstable`, `present_stable`,
`kodi_acquired`, `kodi_acquisition_failed`, or `unknown`. Require stable event
and joystick nodes for a configurable settling interval.

Future controller re-add flow:

1. Wait for stable nodes.
2. Capture a pre-recovery snapshot.
3. Verify current context.
4. Verify whether Kodi opened/reacquired the recreated device.
5. Refresh AntiMicroX only if the remapper itself is stale.
6. Attempt a narrowly scoped Kodi peripheral refresh only if Kodi exposes a
   supported, tested method.
7. Re-check navigation and acquisition evidence.
8. Restart Kodi only after confirmed failure.

Do not restart Kodi for every normal sleep/wake and do not assume restarting
AntiMicroX repairs Kodi's native joystick handle. Evaluate targeting one stable
controller instead of `all` only after physical identification and one-receiver
tests.

## Home/Exit debounce

Future event accounting should use stable source device plus EV_KEY value and
monotonic time. Count a distinct physical press only on an accepted
release-to-press transition. Ignore value `2` key repeat and collapse duplicate
synthetic paths within a conservative window while still logging every raw
observation and decision (`accepted`, `debounced`, `ignored`). Preserve the
current global recovery path and do not weaken panic access without controlled
remote/controller tests.
