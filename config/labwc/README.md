# labwc TVBox Config

This folder contains the canonical labwc config for TVBox global recovery buttons.

## Live config

Path:

    /home/tvbox/.config/labwc/rc.xml

## Canonical repo config

Path:

    /opt/tvbox-system/config/labwc/rc.xml

The repo version is the source of truth. The live config can be overwritten by desktop GUI settings tools.

## Critical F12/Home binding

Required binding:

    <keybind key="F12">
      <action name="Execute" command="/usr/local/bin/tvbox-home" />
    </keybind>

F12/Home must be global so it works from Kodi, Plex playback, Steam Link, Moonlight, Spotify mode, Chromium apps, Firefox, terminals, and the desktop.

Kodi may also have a Kodi-local F12 keymap fallback, but that only works inside Kodi and is not enough for global recovery.

## Restore global controls

Run:

    /usr/local/bin/tvbox-restore-labwc-config
    sudo reboot

## Verify after GUI settings changes

After using GUI tools that change pointer, keyboard, desktop, or window-manager settings, verify F12 is still present:

    grep -n -A4 -B2 -E 'key="F12"|tvbox-home' ~/.config/labwc/rc.xml

If F12 is missing, restore the repo copy.

## Current pointer setting

Current tracked pointer setting:

    <pointerSpeed>0.400000</pointerSpeed>

## Policy

The live labwc config is not trusted as permanent truth. The repo copy is canonical.

GUI settings tools may rewrite ~/.config/labwc/rc.xml and remove custom keybinds. If that happens, restore from the repo with tvbox-restore-labwc-config.

Do not store app-specific controller mappings in labwc. Input profiles belong under /opt/tvbox-system/input-profiles/.
