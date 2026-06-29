# TVBox Input Profiles

This directory is reserved for controller/input profile definitions.

Current implementation status:

```text
tvbox-inputctl can start a TVBox-owned AntiMicroX process for local keyboard/mouse profiles.
tvbox-inputctl stops the TVBox-owned AntiMicroX process for Kodi-native and passthrough profiles.
controller_kbm_generic exists as the active local keyboard/mouse AntiMicroX profile.
kodi_native_minimal exists as a captured AntiMicroX profile but Kodi currently uses native Kodi keymaps instead of running AntiMicroX.
```

Initial profile names:

```text
none
kodi_native
kodi_native_minimal
passthrough
controller_kbm_generic
youtube_remote
spotify_ui
desktop_mouse
```

Current real profile files:

```text
controller_kbm_generic.gamecontroller.amgp
kodi_native_minimal.gamecontroller.amgp
```

Policy:

```text
tvboxctl owns when profiles change.
tvbox-inputctl owns how profiles are applied.
Global Home/F12 recovery must not depend on an input profile.
Broken app-specific profiles must not trap the user inside an app.
Kodi should use native/minimal behavior unless testing proves a remapper is needed.
Streaming contexts should use passthrough unless explicitly approved later.
```

Future backend candidates:

```text
AntiMicroX profiles
evdev/uinput remapper
app-specific native controller modes
```
