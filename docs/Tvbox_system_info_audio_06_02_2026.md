TV Box System Information Append: HDMI and GameSir Audio Output Control

Purpose

This section documents the current TVBox audio-control state after adding support for a GameSir controller that exposes itself as a USB audio device.

The TVBox should continue to behave primarily as a TV appliance:

Normal audio output: TV HDMI
Optional audio output: GameSir controller audio

The GameSir audio device should remain usable, but it should not automatically steal normal TV audio.

---

Current Audio Stack

The TVBox currently uses:

PipeWire 1.4.2
WirePlumber
pipewire-pulse
ALSA

Observed user audio services:

pipewire.service
pipewire-pulse.service
wireplumber.service
filter-chain.service

Firefox, Chromium, and other normal desktop/browser applications use the PipeWire/PulseAudio compatibility path:

App -> pipewire-pulse -> PipeWire/WirePlumber -> ALSA -> HDMI/GameSir

Kodi is intentionally launched through ALSA directly:

Kodi -> ALSA -> HDMI

Spotify/Raspotify is also configured separately to use ALSA direct:

Raspotify/librespot -> ALSA -> vc4-hdmi-1 -> TV

---

Confirmed Audio Devices

HDMI TV Output

Known working ALSA HDMI device:

card 1: vc4-hdmi-1
ALSA card name: vc4hdmi1
Device: MAI PCM

Known working direct ALSA test:

speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2 -t wav -l 2

Known PipeWire/Pulse sink name for HDMI:

alsa_output.platform-107c706400.hdmi.hdmi-stereo

This is the preferred default sink for desktop/browser audio.

---

GameSir Controller Audio

The GameSir-T7 controller appears as an additional USB audio card.

Observed ALSA playback card:

card 2: Xbox [GameSir-T7 Controller for Xbox], device 0: USB Audio

Observed PipeWire sink:

GameSir-T7 Controller for Xbox Analog Stereo

Observed Pulse/PipeWire sink name pattern:

alsa_output.usb-Guangzhou_Chicken_Run_Network_Technology_Co.__Ltd._GameSir-T7_Controller_for_Xbox-00.analog-stereo

The GameSir may also appear as the default input/source:

GameSir-T7 Controller for Xbox Mono

That is acceptable unless microphone/input routing becomes a problem.

---

Confirmed Failure Mode

When the GameSir controller is plugged in, PipeWire/WirePlumber may promote it to the default audio output.

Failure symptoms:

TV HDMI audio stops.
Firefox/Chromium audio routes to the GameSir controller.
Kodi menu sounds may disappear if the active output changes unexpectedly.
Unplugging the GameSir immediately restores TV audio.
Plugging it back in can steal audio again.

This is not an HDMI hardware failure.

The confirmed HDMI path works when tested directly with:

speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2 -t wav -l 2

The correct fix is to enforce audio-output policy, not to remove the GameSir audio device entirely.

---

Current Output Policy

The current intended policy is:

HDMI is the normal/default output.
GameSir remains available as an optional output.
GameSir should only be selected manually or by a deliberate TVBox control action.

Current desired PipeWire/Pulse default sink:

alsa_output.platform-107c706400.hdmi.hdmi-stereo

Verify current default:

pactl info | grep 'Default Sink'
wpctl status

Expected result:

Default Sink: alsa_output.platform-107c706400.hdmi.hdmi-stereo

In "wpctl status", the HDMI sink should have the "*" marker:

* Built-in Audio Digital Stereo (HDMI)

---

ALSA Default Override

The "tvbox" user has an ALSA default override at:

/home/tvbox/.asoundrc

Current intended contents:

pcm.!default {
    type plug
    slave.pcm "hdmi:CARD=vc4hdmi1,DEV=0"
}

ctl.!default {
    type hw
    card vc4hdmi1
}

Purpose:

Make ALSA "default" resolve to the known-good HDMI device.

Important limitation:

This only affects ALSA clients that use ALSA default.
It does not control Firefox, Chromium, or other PipeWire/Pulse applications.

Firefox/Chromium must be controlled through the PipeWire/Pulse default sink.

---

HDMI Audio Recovery Script

A recovery script exists at:

/usr/local/bin/tvbox-audio-hdmi

Purpose:

Set PipeWire/Pulse default output to HDMI.
Unmute HDMI.
Set HDMI volume to 100%.
Move active PipeWire/Pulse audio streams to HDMI.
Set WirePlumber's default sink to HDMI when the HDMI node ID can be detected.

Current intended contents:

#!/bin/bash
set -e

HDMI_SINK="alsa_output.platform-107c706400.hdmi.hdmi-stereo"

pactl set-default-sink "$HDMI_SINK"
pactl set-sink-mute "$HDMI_SINK" 0
pactl set-sink-volume "$HDMI_SINK" 100%

# Move currently playing PipeWire/Pulse streams to HDMI.
for id in $(pactl list sink-inputs short | awk '{print $1}'); do
  pactl move-sink-input "$id" "$HDMI_SINK" || true
done

# Find the WirePlumber numeric sink ID safely.
HDMI_ID="$(wpctl status | awk '
/Built-in Audio Digital Stereo \(HDMI\)/ {
  for (i = 1; i <= NF; i++) {
    if ($i ~ /^[0-9]+\.$/) {
      gsub(/\./, "", $i)
      print $i
      exit
    }
  }
}')"

if [ -n "$HDMI_ID" ]; then
  wpctl set-default "$HDMI_ID" || true
  wpctl set-mute "$HDMI_ID" 0 || true
  wpctl set-volume "$HDMI_ID" 1.0 || true
fi

echo "TVBox audio forced to HDMI."

The file should be executable:

sudo chmod +x /usr/local/bin/tvbox-audio-hdmi

Manual use:

tvbox-audio-hdmi

This is the primary recovery command if GameSir steals browser/desktop audio.

---

GameSir Audio Selection Script

A GameSir audio switch script exists at:

/usr/local/bin/tvbox-audio-gamesir

Purpose:

Set PipeWire/Pulse default output to the GameSir controller.
Unmute GameSir audio.
Set GameSir volume to 100%.
Move active PipeWire/Pulse streams to GameSir.

Current intended contents:

#!/bin/bash
set -e

GS_SINK="$(pactl list sinks short | awk 'tolower($0) ~ /gamesir/ {print $2; exit}')"

if [ -z "$GS_SINK" ]; then
  echo "No GameSir sink found."
  pactl list sinks short
  exit 1
fi

pactl set-default-sink "$GS_SINK"
pactl set-sink-mute "$GS_SINK" 0
pactl set-sink-volume "$GS_SINK" 100%

# Move currently playing PipeWire/Pulse streams to GameSir.
for id in $(pactl list sink-inputs short | awk '{print $1}'); do
  pactl move-sink-input "$id" "$GS_SINK" || true
done

echo "TVBox audio switched to GameSir: $GS_SINK"

The file should be executable:

sudo chmod +x /usr/local/bin/tvbox-audio-gamesir

Manual use:

tvbox-audio-gamesir

This affects PipeWire/Pulse applications such as Firefox and Chromium. It should not be expected to move Kodi when Kodi is running through ALSA direct.

---

Audio Default at Login

A desktop autostart entry exists to enforce HDMI audio after login.

Expected file:

/home/tvbox/.config/autostart/tvbox-audio-hdmi.desktop

Expected contents:

[Desktop Entry]
Type=Application
Name=TVBox Force HDMI Audio
Exec=sh -c 'sleep 5; /usr/local/bin/tvbox-audio-hdmi'
Terminal=false
X-GNOME-Autostart-enabled=true

Purpose:

After desktop login, force PipeWire/Pulse output back to TV HDMI even if the GameSir controller is already plugged in.

Verify:

cat ~/.config/autostart/tvbox-audio-hdmi.desktop

---

Kodi Launcher Integration

The Kodi wrapper now enforces HDMI audio before a fresh Kodi launch.

Kodi wrapper:

/usr/local/bin/tvbox-kodi

Expected line before the fresh Kodi launch log line:

/usr/local/bin/tvbox-audio-hdmi >> "$LOG" 2>&1 || true
log "Launching Kodi with ALSA backend."

Verify:

grep -n -A4 -B4 'tvbox-audio-hdmi\|Launching Kodi' /usr/local/bin/tvbox-kodi

Expected result includes:

/usr/local/bin/tvbox-audio-hdmi >> "$LOG" 2>&1 || true
log "Launching Kodi with ALSA backend."

Important behavior:

Fresh Kodi launch -> HDMI audio is enforced first.
Kodi already running -> wrapper currently opens Favourites and exits without relaunching Kodi.

If future behavior requires HDMI enforcement even when Kodi is already running, add the HDMI enforcement call to the existing-running branch before "open_favourites".

---

PipeWire/Pulse Versus ALSA Scope

Do not confuse the control paths.

Controlled by "tvbox-audio-hdmi" and "tvbox-audio-gamesir"

Firefox
Chromium
YouTube web mode
Most desktop applications using PulseAudio/PipeWire

Controlled separately through ALSA/direct app settings

Kodi
Raspotify/librespot
speaker-test direct ALSA commands

Kodi should remain configured for:

ALSA / vc4-hdmi-1 / MAI PCM
Channels: 2.0
Passthrough: Off

Raspotify should remain configured for:

LIBRESPOT_DEVICE="sysdefault:CARD=vc4hdmi1"

---

Current Audio Test Commands

Check current defaults

pactl info | grep 'Default Sink'
wpctl status | grep -A6 'Sinks:'

Expected normal state:

Default Sink: alsa_output.platform-107c706400.hdmi.hdmi-stereo
Built-in Audio Digital Stereo (HDMI) has the default marker

Force HDMI and verify

tvbox-audio-hdmi
pactl info | grep 'Default Sink'
wpctl status | grep -A6 'Sinks:'

Expected:

Default Sink: alsa_output.platform-107c706400.hdmi.hdmi-stereo

Switch to GameSir and verify

tvbox-audio-gamesir
pactl info | grep 'Default Sink'
wpctl status | grep -A6 'Sinks:'

Expected:

Default Sink contains GameSir

Switch back to HDMI

tvbox-audio-hdmi
pactl info | grep 'Default Sink'

Expected:

Default Sink: alsa_output.platform-107c706400.hdmi.hdmi-stereo

Direct HDMI ALSA hardware test

speaker-test -D hdmi:CARD=vc4hdmi1,DEV=0 -c 2 -t wav -l 2

Expected:

Front Left
Front Right

Audio should be heard through the TV.

---

Planned User-Facing Sound Control

The current likely plan is to add a Kodi-accessible sound-output control.

Possible user flow:

Kodi Favourites
-> TVBox Audio Output
-> choose TV HDMI or GameSir Controller

This would likely be implemented as a small local Kodi Program add-on that calls:

/usr/local/bin/tvbox-audio-hdmi
/usr/local/bin/tvbox-audio-gamesir

This plan is not final.

Acceptable future alternatives include:

A global remote button that toggles HDMI/GameSir.
Separate remote buttons for HDMI and GameSir.
A tvboxctl audio command integrated into the larger TVBox control system.
A lightweight on-screen selector outside Kodi.
A future controller-friendly audio menu in the TVBox home/control layer.

Design requirement:

The final user-facing sound control must be usable with a TV remote or controller and must not require a keyboard or mouse for normal operation.

Do not treat "pavucontrol" as the normal TVBox audio UI.

"pavucontrol" may be installed and used as an administrative troubleshooting tool, but it is not the intended day-to-day interface for a remote-controlled TV appliance.

---

Maintenance Rules

1. Do not disable PipeWire, WirePlumber, or pipewire-pulse just because the GameSir can steal audio.

2. Do not remove the GameSir audio device unless the goal changes and GameSir audio is no longer wanted.

3. HDMI should remain the default output for TVBox appliance behavior.

4. GameSir should remain selectable, but not allowed to silently become the normal output.

5. "tvbox-audio-hdmi" is the recovery command when browser/desktop audio disappears after plugging in the controller.

6. Kodi should continue to launch through "/usr/local/bin/tvbox-kodi".

7. Kodi should continue using ALSA direct unless the overall audio design is intentionally changed.

8. Browser/desktop audio should be controlled through PipeWire/Pulse sink defaults.

9. Spotify/Raspotify audio should remain configured separately through "/etc/raspotify/conf".

10. Future audio UI work should favor remote/controller usability over desktop-style audio control panels.

---

Current Stable Audio State Summary

Current intended state:

PipeWire/WirePlumber remains active.
pipewire-pulse remains active for Firefox/Chromium/desktop apps.
HDMI PipeWire sink is the default output.
GameSir audio sink remains available as an optional output.
GameSir may remain the default input/source unless microphone routing becomes a problem.
ALSA default for the tvbox user points to hdmi:CARD=vc4hdmi1,DEV=0.
Kodi wrapper enforces HDMI before fresh Kodi launch.
Kodi still launches through /usr/local/bin/tvbox-kodi.
Kodi still uses --audio-backend=alsa.
Raspotify remains separately configured for sysdefault:CARD=vc4hdmi1.
A user-facing audio selector is planned but not yet implemented.

Operating principle:

TV audio should work by default.
Controller audio should be available by choice.
Sound recovery should be scriptable.
Normal sound control should eventually be remote/controller friendly.