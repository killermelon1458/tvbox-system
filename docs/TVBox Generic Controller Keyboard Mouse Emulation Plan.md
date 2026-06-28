TVBox Generic Controller Keyboard/Mouse Emulation and Contextual Home Policy

1. Purpose

This document defines a generic controller-to-keyboard/mouse input profile for TVBox and clarifies how the controller Guide/Home/Xbox button should behave across different app contexts.

The goal is to make a standard game controller usable in local TVBox apps that already work well with keyboard-style remote input, especially Chromium TV/web apps such as YouTube TVBox mode.

This is not a full controller abstraction layer. It is a practical V1 input profile that turns a normal Xbox-style controller layout into:

D-pad / left stick navigation
A / confirm
B / back
basic playback keys
right-stick mouse control
trigger mouse clicks
context-dependent Guide/Home behavior
remote Home/Exit recovery preserved

This profile should be generic enough to reuse in multiple local TVBox contexts. If a specific app needs different behavior later, clone this profile and make an app-specific variant.

---

2. Core Design Decision

Create one generic controller keyboard/mouse emulation profile first.

Recommended profile name:

controller_kbm_generic

Meaning:

controller -> keyboard/mouse generic

This profile replaces the narrower idea of only having "controller_remote_clone".

Older concept:

controller_remote_clone:
  D-pad/stick -> arrows
  A -> Enter
  B -> Backspace

New preferred generic profile:

controller_kbm_generic:
  D-pad / left stick -> arrows
  A -> Enter
  B -> Backspace/browser Back
  X/Y/shoulders -> useful generic keys if needed
  right stick -> mouse movement
  triggers -> mouse clicks
  Guide/Home/Xbox -> context-dependent TVBox Home in local profiles

Rationale:

Many TVBox apps need mostly keyboard-style navigation.
Some apps and desktop fallback states still need mouse control.
One generic keyboard/mouse profile avoids creating one-off profiles too early.
Specific apps can later clone this profile and override only what differs.
Controller Home behavior must be context-dependent because Steam/Moonlight may need the real Guide/Xbox button.

---

3. Scope

This profile is intended for:

YouTube TVBox Chromium mode
Desktop rescue/fallback mode
Generic Chromium TV web apps
Simple web games that need mouse fallback
Emulator launchers or menus that support keyboard navigation
File manager / desktop icon recovery
Local TVBox app menus

This profile is not intended for:

Moonlight game streaming
Steam Link streaming
Native controller games
Any context where the remote host/client needs the real controller

Kodi is a special case. Kodi may use native controller input, but the current observed controller Guide/Home behavior is wrong because it opens Kodi’s main menu instead of TVBox Favourites/Home. Kodi needs either a controller remap, a Kodi keymap fix, or another tested input path so controller Home behaves like TVBox Home in local Kodi/Plex contexts.

For streaming/game contexts, use passthrough unless there is a specific reason to remap input.

---

4. Controller Layout Assumption

V1 should assume an Xbox 360-style logical layout because that is the current practical baseline.

Logical controls:

D-pad
Left stick
Right stick
A / B / X / Y
LB / RB
LT / RT
Start/Menu
Back/View
Guide/Home/Xbox if accessible
Left stick click
Right stick click

The implementation should not hardcode a single physical brand if avoidable. The default layout can be Xbox-style, but the profile should be treated as a logical mapping that can later be duplicated for PlayStation, Switch, or odd controllers.

---

5. Generic Local TVBox Mapping

This section defines the intended mapping for local TVBox contexts where the controller is being used like a remote plus mouse.

Relevant contexts:

youtube
desktop
spotify visual mode
chromium:<app_id>
emulator-launcher
generic local app menu
possibly kodi/plex if Kodi-native behavior is insufficient

5.1 Navigation

D-pad Up       -> Up Arrow
D-pad Down     -> Down Arrow
D-pad Left     -> Left Arrow
D-pad Right    -> Right Arrow

Left stick Up    -> Up Arrow
Left stick Down  -> Down Arrow
Left stick Left  -> Left Arrow
Left stick Right -> Right Arrow

D-pad should be the primary navigation control.

Left stick may duplicate D-pad navigation, but only if it does not create noisy repeated input. If analog drift causes bad navigation, disable left-stick keyboard mapping and keep only D-pad navigation.

5.2 Confirm / Back

A -> Enter
B -> Backspace

Optional alternate for B if Backspace is not enough in Chromium:

B -> Alt+Left

Decision rule:

Use Backspace first because YouTube TV mode and many remote-style apps already handle it.
If Chromium/web apps fail to go back reliably, test Alt+Left as an app-specific clone.

5.3 Playback / Common Media

Recommended V1:

X -> Space
Y -> Escape

Reason:

Space is commonly play/pause in YouTube and media contexts.
Escape is useful for closing menus, overlays, or fullscreen dialogs.

If Y causes bad behavior in a specific app, leave Y unmapped in that app’s cloned profile.

5.4 Page / Scroll Movement

Optional:

LB -> PageUp
RB -> PageDown

This may be useful in desktop/file-manager/web contexts.

Do not make this mandatory for V1. Add only after basic navigation works.

5.5 Mouse Control

Recommended V1:

Right stick -> mouse movement
RT          -> left click
LT          -> right click
Stick clicks unmapped

Possible later mapping:

Right stick click -> middle click
Left stick click  -> left click or no-op

Reason:

Right stick mouse movement is useful as a fallback.
Triggers are natural click controls.
Stick clicks can cause accidental input and should stay unmapped until needed.

5.6 Menu / View Buttons

Initial safest mapping:

Start/Menu -> Escape
Back/View  -> Backspace

If these conflict with global TVBox controls later, remove them from the generic profile and handle them through "labwc", "tvboxctl", or app-specific profiles instead.

---

6. Context-Dependent Guide/Home/Xbox Button Policy

The controller Guide/Home/Xbox button is not globally one thing.

It must be context-dependent.

6.1 Problem

Current observed issue:

Remote Home -> F12 -> global TVBox Home script -> Favourites / return-to-Kodi behavior

Controller Guide/Xbox/Home -> Kodi's internal home behavior
                            -> Kodi main menu
                            -> does not call global TVBox Home script
                            -> does not open TVBox Favourites

This creates an inconsistent control model:

Remote Home means: TVBox Home / recovery / Favourites
Controller Home means: Kodi main menu only

That is wrong in local TVBox contexts.

6.2 Correct Rule

Bad rule:

Never map controller Guide/Home to F12.

Correct rule:

Do not map controller Guide/Home globally in every context.

Do map controller Guide/Home to TVBox Home/F12 in local TVBox UI contexts where the controller is acting as a remote.

Do not map controller Guide/Home to F12 in passthrough/streaming/game contexts where Steam, Moonlight, Steam Link, or the remote host needs the real Guide/Xbox button.

6.3 Local TVBox Contexts

In local TVBox contexts, the controller is acting like a TV remote.

Relevant contexts:

kodi
plex
youtube
spotify
desktop
chromium:<app_id>
emulator-launcher
generic local app menu
unknown/desktop rescue fallback

Expected mapping:

Controller Guide/Home/Xbox -> F12 -> labwc global keybind -> /usr/local/bin/tvbox-home

or an equivalent direct action:

Controller Guide/Home/Xbox -> /usr/local/bin/tvboxctl home

Preferred first implementation:

Controller Guide/Home/Xbox -> F12

Reason:

The existing F12 path already works for the remote and should remain the single normal Home entrypoint.
Do not change /usr/local/bin/tvbox-home unless Home behavior itself is wrong.

Expected behavior in local contexts:

Kodi menu        -> open TVBox Favourites, not Kodi main menu
Plex playback    -> stop playback, then open Favourites
YouTube          -> close YouTube and return Kodi
Spotify mode     -> stop Spotify mode and return Kodi
Desktop          -> launch/focus Kodi
Chromium app     -> close app and return Kodi

6.4 Streaming / Passthrough Contexts

In streaming contexts, the controller should belong to the streaming client or remote host.

Relevant contexts:

moonlight
moonlight:steam
moonlight:minecraft
moonlight:desktop
steamlink
native controller game

Expected mapping:

Controller Guide/Home/Xbox -> passthrough / native controller behavior

Do not remap it to F12 in these contexts.

Reason:

Steam and game-streaming environments may require the Guide/Xbox button for Steam overlay, Steam navigation, controller chord shortcuts, or host-side navigation.

Home/F12 recovery from these contexts should still exist through the TV remote.

A later explicit controller recovery combo may be added, but the normal Guide/Xbox button should not be stolen in passthrough contexts.

---

7. Updated Input Profile Model

7.1 "controller_kbm_generic"

Purpose:

Generic controller-to-keyboard/mouse profile for local TVBox apps.

Used by:

youtube
desktop
generic Chromium apps
local launchers
simple app menus
possibly kodi/plex if Kodi-native behavior is not sufficient

Mapping:

D-pad / left stick -> Arrow keys
A                  -> Enter
B                  -> Backspace or Alt+Left
X                  -> Space
Y                  -> Escape
Right stick        -> Mouse movement
RT                 -> Left click
LT                 -> Right click
Guide/Home/Xbox    -> F12

Important:

Guide/Home/Xbox -> F12 is allowed and desired in this profile because this is a local TVBox control profile.

7.2 "kodi_native"

Purpose:

Kodi-native controller behavior where Kodi handles the controller directly.

Problem:

Kodi may map the controller Guide/Home/Xbox button to Kodi's main menu instead of TVBox Favourites.

Policy:

If Kodi-native controller handling sends Guide/Home/Xbox to Kodi main menu, then Kodi-native is not sufficient for final TVBox controller Home behavior.

Possible fixes:

Option A:
  Add a Kodi controller/keymap override so Guide/Home/Xbox triggers ActivateWindow(FavouritesBrowser) or a TVBox Home action.

Option B:
  Use a remapper profile in Kodi-local context that maps Guide/Home/Xbox to F12 while leaving normal Kodi navigation usable.

Option C:
  Leave Kodi-native for basic navigation, but add a separate tested controller Home remap path.

Preferred final behavior:

Controller Home in Kodi must behave like TVBox Home, not Kodi main menu.

7.3 "passthrough"

Purpose:

Streaming and native game contexts.

Used by:

Moonlight
Steam Link
native controller games

Mapping:

No controller-to-keyboard remapping.
Do not map Guide/Home/Xbox to F12.

Reason:

The stream/game needs the real controller, including the Guide/Xbox button.

7.4 App-Specific Clones

If a local app needs different behavior, clone the generic profile.

Examples:

controller_kbm_youtube
controller_kbm_desktop
controller_kbm_emulator_launcher
controller_kbm_kodi
controller_kbm_fireboy_watergirl
controller_kbm_fixitfelix

Clone rule:

Start with controller_kbm_generic.
Clone only when testing proves the generic profile is wrong for that app.

---

8. tvbox-inputctl Integration

Add the profile to "tvbox-inputctl".

Required command:

tvbox-inputctl set controller_kbm_generic

Required status output should include:

input_profile=controller_kbm_generic
remapper=antimicrox
profile_file=/opt/tvbox-system/input-profiles/antimicrox/controller_kbm_generic.gamecontroller.amgp

Recommended profile path:

/opt/tvbox-system/input-profiles/antimicrox/controller_kbm_generic.gamecontroller.amgp

Possible live/cache/runtime state:

/run/user/1000/tvbox/input-profile

Expected behavior:

1. Stop the currently running remapper profile.
2. Start AntiMicroX with controller_kbm_generic profile.
3. Write input-profile state.
4. Log success/failure.
5. Never block app launch if the remapper fails.
6. Never block TV remote Home/Exit recovery.

Failure rule:

If AntiMicroX fails to start, TVBox should still launch the requested app.
The failure should be logged, not treated as a fatal app-launch failure.

---

9. tvboxctl Context Integration

9.1 YouTube

YouTube currently works well with the remote because it accepts keyboard-style TV navigation.

Set YouTube’s input profile to:

controller_kbm_generic

Recommended Chromium app config:

app_id=youtube
name=YouTube
url=https://www.youtube.com/tv
profile=/home/tvbox/.config/chromium-tvbox-youtube
input_profile=controller_kbm_generic
mode=app

Expected behavior:

Kodi Favourites -> YouTube TVBox
-> tvboxctl launches YouTube Chromium mode
-> tvbox-inputctl set controller_kbm_generic
-> controller D-pad navigates YouTube
-> A selects
-> B backs out
-> X toggles play/pause
-> right stick moves mouse if needed
-> RT clicks if needed
-> controller Guide/Home sends F12 in this context
-> Home/F12 exits YouTube and returns Kodi/Favourites

9.2 Desktop Rescue

Add or reserve context:

context=desktop
input_profile=controller_kbm_generic

Purpose:

If the user is dumped to the desktop, controller navigation remains usable enough to select desktop icons, press Enter, or use right-stick mouse control.

Expected desktop fallback behavior:

D-pad / left stick -> select desktop icons if desktop has focus
A / Enter          -> open selected launcher
B / Backspace      -> back where applicable
Right stick        -> mouse movement
RT                 -> left click
LT                 -> right click
Guide/Home/F12     -> return Kodi/Favourites

The desktop should have launcher icons for important recovery/app paths:

Kodi
YouTube TVBox
Moonlight
Moonlight - Steam
Moonlight - Minecraft
Steam Link
Emulators / emulator frontends

Desktop launcher rule:

Desktop icons must call TVBox wrapper scripts or tvboxctl commands.
Do not point desktop icons directly at raw apps unless intentionally testing.

Examples:

Exec=/usr/local/bin/tvbox-kodi
Exec=/usr/local/bin/tvbox-youtube
Exec=/usr/local/bin/tvboxctl launch moonlight steam
Exec=/usr/local/bin/tvboxctl launch chromium-app youtube

9.3 Generic Chromium Apps

For generic local Chromium apps, default to:

input_profile=controller_kbm_generic

Only create a clone profile if the app needs different controls.

Rule:

Start generic.
Clone only when testing proves the generic profile is wrong.

9.4 Kodi / Plex

Default Kodi input may remain:

kodi_native

But this is acceptable only if Kodi-native input provides the correct TVBox behavior.

Current issue:

Controller Guide/Home opens Kodi main menu.
It does not call TVBox Home/F12.
It does not open TVBox Favourites.

Therefore, Kodi/Plex needs one of the following before controller support is considered complete:

Kodi keymap override for controller Home
A Kodi-local F12 equivalent
A controller remapper profile active in Kodi/Plex
A direct input handler that turns Guide/Home into tvboxctl home in Kodi/Plex contexts

Success condition:

Controller Home from Kodi/Plex reaches TVBox Favourites/Home behavior.

Not sufficient:

Controller Home opens Kodi's plain main menu.

9.5 Moonlight and Steam Link

Moonlight and Steam Link should remain:

input_profile=passthrough

Reason:

Controllers should pass through to the remote host/client.
The Pi should not translate controller input into keyboard/mouse for game streaming unless a specific app requires it.
The Guide/Xbox button may be required for Steam navigation or host-side behavior.

---

10. AntiMicroX First Implementation

Recommended V1 implementation:

Use AntiMicroX to create and run controller_kbm_generic.
Use tvbox-inputctl to manage AntiMicroX lifecycle.
Do not build custom uinput remapping until AntiMicroX proves insufficient.

Repo path:

/opt/tvbox-system/input-profiles/antimicrox/controller_kbm_generic.gamecontroller.amgp

Potential support files:

/opt/tvbox-system/input-profiles/antimicrox/README.md
/opt/tvbox-system/config/tvbox-inputctl.conf.example

Profile README should document:

Which controller was used to create the profile.
Expected logical button layout.
Known drift/deadzone assumptions.
Mouse sensitivity.
Repeat rate assumptions.
Which buttons are intentionally unmapped.
Whether Guide/Home is mapped in that profile.
Whether the profile is local-control or passthrough-oriented.

Do not store user caches or generated runtime files in Git.

---

11. Guide/Home Implementation Notes

11.1 Test Whether the Remapper Sees the Guide Button

Some controllers expose the Guide/Xbox button normally. Others may hide it, reserve it, or report it differently.

Test with:

evtest

and also test inside the selected remapper.

Required finding:

Does the controller Guide/Home/Xbox button produce an event?
What event code/name does it produce?
Can AntiMicroX map it?
Can the chosen remapper send F12 from it?

If AntiMicroX cannot see or map the button, use another remapping approach for that button, likely evdev/uinput or interception-based handling.

11.2 Preferred First Test

In a local profile, map:

Controller Guide/Home/Xbox -> F12

Then test whether labwc receives the generated F12 as a global keybind.

Expected:

Controller Guide/Home/Xbox
-> generated F12
-> labwc global keybind
-> /usr/local/bin/tvbox-home

If labwc does not catch synthetic F12 from the remapper, use a direct action path instead:

Controller Guide/Home/Xbox
-> remapper/direct input handler
-> /usr/local/bin/tvboxctl home

Do not change "/usr/local/bin/tvbox-home" just to solve this.

11.3 Kodi-Specific Caution

Kodi may intercept controller Guide/Home before a remapper or global keybind handles it.

If that happens, Kodi needs one of these:

Kodi controller keymap override
Kodi input setting change
External remapper that grabs the controller before Kodi
Switch Kodi context from pure kodi_native to a controlled local profile

The success condition is not “Kodi sees the button.”

The success condition is:

Controller Home in Kodi reaches TVBox Home behavior.

---

12. Safety Rules

1. The generic controller profile must not be the only recovery path.

2. Remote keyboard mappings should still work independently:

Remote D-pad -> arrow keys
Remote OK    -> Enter
Remote Back  -> Backspace
Remote Home  -> F12/global Home

3. Guide/Home must be context-dependent:

Local TVBox profile:
  Guide/Home/Xbox -> F12 or tvboxctl home

Passthrough/streaming/game profile:
  Guide/Home/Xbox -> native/passthrough behavior

4. Do not map Guide/Home to the normal keyboard "Home" key in the generic profile.

5. Do not use broad process kills to switch profiles.

6. If remapper startup fails, log it and continue.

7. If a profile breaks remote Home/Exit, that profile is defective.

8. If left-stick drift causes navigation problems, disable left-stick arrow mapping and rely on D-pad.

9. Mouse movement should be available but not required for normal YouTube navigation.

10. Use app-specific clone profiles only after generic profile testing proves they are needed.

11. Do not change the F12 Home script unless the Home behavior itself is wrong.

12. Do not let controller Home open Kodi’s plain main menu when the intended TVBox Home is Favourites.

13. Streaming contexts must preserve the Guide/Xbox button unless a specific tested recovery combo is added.

14. App-specific controller Home behavior must be documented in the input profile README.

---

13. Implementation Order

Phase 1 — Create generic profile manually

Create and test:

controller_kbm_generic

Minimum required working controls:

D-pad -> arrows
A -> Enter
B -> Backspace
X -> Space
Right stick -> mouse movement
RT -> left click
LT -> right click

Guide/Home test target:

Guide/Home/Xbox -> F12

Only apply this Guide/Home mapping in local TVBox profiles, not passthrough profiles.

Phase 2 — Test Guide/Home visibility

Use:

evtest

and AntiMicroX.

Find:

Does Guide/Home/Xbox produce an event?
Can AntiMicroX map it?
Can generated F12 reach labwc?
Does Kodi intercept it before the global path?

Phase 3 — Add tvbox-inputctl support

Implement:

tvbox-inputctl set controller_kbm_generic
tvbox-inputctl status
tvbox-inputctl reset

Expected:

Can start the profile.
Can stop/reset it.
Can report active profile.
Does not interfere with TV remote F12/Home.

Phase 4 — Wire YouTube to the generic profile

Update YouTube app config/launcher policy:

context=chromium:youtube
input_profile=controller_kbm_generic

Test controller navigation in YouTube.

Phase 5 — Add desktop rescue context

Add or reserve:

context=desktop
input_profile=controller_kbm_generic

Ensure the desktop has useful launch icons.

Phase 6 — Fix Kodi/Plex controller Home

Test whether Kodi-native can be corrected.

Possible approaches:

Kodi keymap override
Kodi input setting
controller_kbm_kodi clone
direct input handler for Guide/Home in Kodi/Plex context

Required final behavior:

Controller Guide/Home from Kodi/Plex opens TVBox Favourites/Home behavior, not Kodi's plain main menu.

Phase 7 — Preserve passthrough contexts

Verify:

Moonlight -> input_profile=passthrough
Steam Link -> input_profile=passthrough
Native controller games -> input_profile=passthrough

The Guide/Xbox button must remain available to those contexts.

Phase 8 — Clone only when necessary

If YouTube needs different behavior:

clone controller_kbm_generic -> controller_kbm_youtube

If an emulator launcher needs different behavior:

clone controller_kbm_generic -> controller_kbm_emulator_launcher

If Kodi needs controlled local behavior:

clone controller_kbm_generic -> controller_kbm_kodi

If a game needs custom controls:

make a dedicated game profile

Do not pre-create a pile of profiles before testing.

---

14. Testing Matrix

14.1 AntiMicroX profile test

From desktop:

tvbox-inputctl set controller_kbm_generic
tvbox-inputctl status

Expected:

D-pad moves focus/selection where desktop focus allows.
A presses Enter.
B sends Backspace.
Right stick moves cursor.
RT left-clicks.
LT right-clicks.
Guide/Home sends F12 or TVBox Home in local profile.
TV remote F12/Home still works globally.

14.2 YouTube controller test

Start YouTube TVBox mode:

/usr/local/bin/tvbox-youtube

Or later:

tvboxctl launch chromium-app youtube

Expected:

D-pad navigates YouTube tiles/buttons.
A selects video/menu item.
B backs out.
X play/pauses.
Right stick moves mouse cursor if needed.
RT clicks if needed.
Controller Guide/Home closes YouTube and returns Kodi/Favourites.
TV remote Home/F12 still works independently.

Failure cases:

D-pad does nothing:
  profile not active, wrong controller device selected, or Chromium/YouTube lacks focus.

A does nothing:
  Enter mapping wrong or focus not on Chromium.

B does not go back:
  test Alt+Left in a cloned YouTube profile.

Controller Home opens Kodi main menu:
  Kodi-native handling is intercepting it or the wrong profile is active.

Controller Home does nothing:
  Guide button may not be visible to AntiMicroX or generated F12 may not be reaching labwc.

TV remote Home stops working:
  profile or app focus handling has broken recovery and must be fixed before continuing.

14.3 Desktop rescue test

From desktop with Kodi closed:

tvbox-inputctl set controller_kbm_generic

Expected:

Can select Kodi desktop icon with D-pad/arrows if desktop focus supports it.
Can open Kodi with A/Enter.
Can move mouse with right stick.
Can click launcher icons with RT.
Can press controller Guide/Home to launch/focus Kodi through TVBox Home behavior.
Can press TV remote Home/F12 to launch/focus Kodi independently.

14.4 Kodi / Plex controller Home test

Context:

Kodi menu
Plex menu
Plex playback

Press:

Controller Guide/Home/Xbox

Expected:

Kodi menu:
  TVBox Favourites opens.
  Kodi main menu should not be the final result.

Plex menu:
  TVBox Favourites opens.

Plex playback:
  Playback stops.
  TVBox Favourites opens.

Acceptable implementation paths:

tvbox-home
tvboxctl home
Kodi-local Favourites action only if it fully matches desired behavior

Not acceptable:

Controller Home only opens Kodi's plain main menu.

14.5 Kodi protection test

Start Kodi with normal policy:

/usr/local/bin/tvbox-kodi

Expected:

No double input.
No runaway repeated arrows.
Back works normally.
A/Enter works normally.
Controller Home reaches TVBox Home behavior once implemented.
TV remote F12/Home still works.

14.6 Moonlight / Steam Link protection test

Launch Moonlight or Steam Link.

Expected:

input_profile=passthrough
controller reaches stream/client normally
controller_kbm_generic is not active
Guide/Xbox remains available to Steam/Moonlight/Steam Link
TV remote Home/F12 still performs TVBox recovery behavior

Press:

Controller Guide/Home/Xbox

Expected:

The button remains available to the streaming/game environment.
It should not call TVBox F12/Home in passthrough mode.

Recovery in these contexts remains:

TV remote Home/F12

or a later explicitly designed controller recovery combo.

---

15. Done Criteria

This plan is complete when:

controller_kbm_generic exists in the repo.
tvbox-inputctl can start/stop/status the profile.
YouTube TVBox mode is controllable with a game controller.
Desktop fallback is usable with controller mouse/keyboard emulation.
Controller Guide/Home maps to TVBox Home/F12 in local TVBox contexts.
Controller Guide/Home remains passthrough in Steam/Moonlight/Steam Link contexts.
Kodi/Plex controller Home no longer dumps the user at Kodi's plain main menu as the final behavior.
TV remote Home/F12 remains independent and reliable.
Moonlight and Steam Link still use passthrough.
Kodi is not harmed by duplicate remapping.
At least one controller has been tested end-to-end.
The profile can be cloned for app-specific variants later.

---

16. Final Policy

The correct V1 design is:

Use the remote as the primary guaranteed TV control.
Use controller_kbm_generic as a reusable controller fallback/control layer for local TVBox apps.
Use passthrough for real game/streaming contexts.
Map controller Guide/Home to TVBox Home only in local TVBox contexts.
Preserve controller Guide/Home in streaming/game passthrough contexts.
Use app-specific clones only after testing proves they are needed.
Never let input remapping break TV remote Home/Exit recovery.

Controller Guide/Home/Xbox behavior:

Local TVBox UI context:
  Guide/Home/Xbox = TVBox Home

Streaming/game passthrough context:
  Guide/Home/Xbox = native controller Guide/Home

Unknown or desktop rescue context:
  Guide/Home/Xbox = TVBox Home

This makes YouTube usable with controllers now, improves desktop recovery, fixes inconsistent controller Home behavior in local TVBox contexts, and keeps the system extensible without overbuilding controller abstraction too early.