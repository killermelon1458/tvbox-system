TVBox Input Architecture Plan

Core Decision

TVBox input should be built around a two-layer architecture, but implemented in stages.

The first working version should focus only on context-dependent input profiles. These profiles will assume a standard Xbox 360 / XInput-style controller layout. This matches the majority of currently tested usable controllers and gives TVBox a practical baseline without delaying the project for a full controller-normalization system.

A later version can add a controller-remapping or normalization layer underneath the context profiles. That layer will translate unusual physical controllers into the same standard logical layout used by the existing profiles. The goal is for future controller support to expand TVBox without requiring a complete rebuild of the context-profile system.

V1: Context-Dependent Input Profiles

V1 should use context-dependent input profiles directly against controllers that already expose a normal Xbox 360-style layout.

The V1 input standard is:

tvbox_xinput_core_v1

This logical layout includes:

A
B
X
Y
LB
RB
LT
RT
Left Stick X/Y
Right Stick X/Y
Left Stick Click
Right Stick Click
D-pad Up/Down/Left/Right
View / Back / Select
Menu / Start
Guide / Xbox / Home, if exposed

V1 profiles are not controller-specific in concept. They are context profiles written against the expected Xbox-style logical layout.

Examples:

kodi_native
controller_remote_clone
youtube_remote
browser_remote
fireboy_watergirl
fixitfelix
passthrough

In V1, controllers that already behave like Xbox 360/XInput-style controllers can use these profiles directly.

This currently appears reasonable because several tested controllers expose a mostly standard 360-style layout, including the wired Xbox 360-style controller, Voye wired 360 controller, 8BitDo controller, GameSir Xbox-style controller, real Xbox One controller, and at least some PowerA-style controllers when functioning correctly.

V1 Scope

V1 should prioritize working behavior over perfect abstraction.

V1 should provide:

1. Context switching.
2. Per-context controller-to-keyboard/mouse mappings where needed.
3. Passthrough mode for Moonlight, Steam Link, and anything that should receive the controller directly.
4. A clean standard layout document.
5. A clean profile directory structure that will survive later abstraction.

V1 should not attempt to solve every controller quirk. Controllers that already match the expected layout are supported first. Weird controllers can be documented and either handled with temporary profile variants or deferred until the normalization layer exists.

V2: Controller Normalization Layer

V2 adds a layer below the context profiles.

The long-term input path becomes:

Physical Controller
    ↓
Controller-specific normalization/remapping layer
    ↓
tvbox_xinput_core_v1 logical controller
    ↓
Context-dependent input profile
    ↓
Kodi / Browser / YouTube / Moonlight / Steam Link / Game

This means that a weird controller only needs one device-specific mapping into the TVBox standard. After that, it can reuse the same context profiles as every other controller.

The normalization layer may eventually be implemented with a custom evdev/uinput daemon, input-remapper, MoltenGamepad, or another suitable Linux input tool. The specific implementation does not need to be chosen for V1, but the V1 directory structure and profile naming should leave room for it.

Global Controls Stay Separate

Global recovery controls should remain outside the context-profile system.

Examples:

Home
Exit
Menu
App / Plex
YouTube
Steam / Moonlight shortcut

These should continue to be handled by the remote/global hotkey layer where possible, such as FLIRC plus labwc keybindings or other system-level bindings.

Context profiles must not be able to trap the user inside a broken app state. Home/Exit-style recovery should remain available even if an app profile or controller mapping is wrong.

Recommended Directory Structure

/opt/tvbox-system/input-profiles/
  standards/
    tvbox_xinput_core_v1.md
    tvbox_xinput_plus_v1.md

  antimicrox/
    tvbox_xinput_core_v1/
      kodi_native.gamecontroller.amgp
      controller_remote_clone.gamecontroller.amgp
      youtube_remote.gamecontroller.amgp
      browser_remote.gamecontroller.amgp
      fireboy_watergirl.gamecontroller.amgp
      fixitfelix.gamecontroller.amgp

  devices/
    xbox_360_wired.md
    voye_wired_360.md
    xbox_one_usb.md
    xbox_one_dongle.md
    8bitdo_ultimate_2c.md
    gamesir_xbox.md
    powera_model_a.md
    powera_model_b.md
    rii_rk707.md

  normalization/
    README.md

The purpose of each section is:

standards/
  Defines what TVBox expects logically.

antimicrox/
  Stores V1 context profiles built against the standard layout.

devices/
  Documents how each physical controller actually reports buttons and axes.

normalization/
  Reserved for the later V2 controller-remapping layer.

Controller Classification

Controllers should be classified by how well they fit the V1 standard.

Class A: Standard / Preferred
  Works like an Xbox 360/XInput controller.
  Safe for V1 context profiles and passthrough.

Class B: Usable With Mapping
  Inputs work, but layout is unusual.
  Usable for context profiles, but may need a device-specific profile or future normalization.

Class C: Menu-Only / Limited
  Enough inputs work for Kodi/browser navigation, but analog sticks/triggers or buttons are unreliable.
  Not trusted for passthrough gaming.

Class D: Problem / Do Not Rely On
  Enumerates but does not send usable input, disconnects, or has major missing controls.

Practical Implementation Rule

V1 should be built around the Xbox 360-style layout because that is the lowest-friction common denominator among the current usable controllers.

However, the implementation should avoid hardcoding assumptions in a way that prevents future abstraction. Context profiles should be named and organized around the logical TVBox standard, not around one specific physical controller.

Correct framing:

Good:
  tvbox_xinput_core_v1

Avoid:
  8bitdo_standard
  powera_standard
  gamesir_standard

The physical controller used to create or test a profile is only a reference device. It should not define the TVBox input architecture by itself.

Summary

V1 gets TVBox working with the controllers that already behave normally.

V2 makes weird controllers behave normally.

The important design boundary is that context profiles should target the TVBox standard layout from the beginning. That way, adding controller normalization later expands compatibility instead of forcing the project to rebuild its input system.