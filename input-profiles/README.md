# TVBox Input Profiles

This directory is reserved for controller/input profile definitions.

Current implementation status:

```text
tvbox-inputctl can start a TVBox-owned AntiMicroX process for local keyboard/mouse profiles and the minimal Kodi profile.
tvbox-inputctl stops the TVBox-owned AntiMicroX process for Kodi-native and passthrough profiles.
controller_kbm_generic exists as the active local keyboard/mouse AntiMicroX profile.
kodi_native_minimal is a minimal AntiMicroX profile that maps controller Home/Guide to F12 and Back/View to F5 while leaving normal Kodi navigation native.
mariokart_n64 is a minimal AntiMicroX profile for Mupen64Plus/Mario Kart 64 that maps only controller Home/Guide to F12 and Back/View to F5.
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
mariokart_n64
```

Current real profile files:

```text
controller_kbm_generic.gamecontroller.amgp
kodi_native_minimal.gamecontroller.amgp
mariokart_n64.gamecontroller.amgp
```

Policy:

```text
tvboxctl owns when profiles change.
tvbox-inputctl owns how profiles are applied.
Global Home/F12 recovery must not depend on an input profile.
Broken app-specific profiles must not trap the user inside an app.
Kodi should use native/minimal behavior: only global recovery buttons are remapped, and normal Kodi navigation stays native.
Streaming contexts should use passthrough unless explicitly approved later.
```

Future backend candidates:

```text
AntiMicroX profiles
evdev/uinput remapper
app-specific native controller modes
```
