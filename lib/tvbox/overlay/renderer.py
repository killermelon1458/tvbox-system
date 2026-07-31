"""Shared GtkLayerShell renderer setup and readiness."""

import json
import os


def configure_opaque_overlay_window(window):
    """Apply properties owned by a single overlay window, including cursor."""
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk

    window.set_decorated(False)
    window.set_app_paintable(True)
    window.set_opacity(1.0)

    def hide_cursor(widget):
        surface = widget.get_window()
        display = widget.get_display()
        cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.BLANK_CURSOR)
        surface.set_cursor(cursor)

    window.connect("realize", hide_cursor)


def readiness_payload(degradation=None):
    return {
        "event": "first-frame-ready",
        "request_id": os.environ["TVBOX_OVERLAY_REQUEST_ID"],
        "generation": int(os.environ["TVBOX_OVERLAY_GENERATION"]),
        "degradation": degradation,
    }


def signal_ready(degradation=None):
    fd = int(os.environ["TVBOX_OVERLAY_READY_FD"])
    os.write(fd, json.dumps(readiness_payload(degradation)).encode() + b"\n")
    os.close(fd)


def configure_layer_surface(window, namespace, output):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, GtkLayerShell

    GtkLayerShell.init_for_window(window)
    GtkLayerShell.set_layer(window, GtkLayerShell.Layer.OVERLAY)
    for edge in (
        GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
        GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT,
    ):
        GtkLayerShell.set_anchor(window, edge, True)
    # The live Raspberry Pi desktop's wf-panel-pi reserves a 36px top zone.
    # A zone of -1 makes this full-output overlay ignore other exclusive zones
    # while still reserving no workspace itself.  Discovery's zone=0 probe
    # predated this observed panel interaction and left that strip uncovered.
    GtkLayerShell.set_exclusive_zone(window, -1)
    for edge in (
        GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
        GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT,
    ):
        GtkLayerShell.set_margin(window, edge, 0)
    GtkLayerShell.set_keyboard_mode(
        window, GtkLayerShell.KeyboardMode.ON_DEMAND)
    GtkLayerShell.set_namespace(window, namespace)
    display = Gdk.Display.get_default()
    monitors = [display.get_monitor(index)
                for index in range(display.get_n_monitors())]
    if not monitors:
        raise RuntimeError("no GDK monitor available")
    selected = None
    if output:
        if str(output).isdigit():
            index = int(output)
            if 0 <= index < len(monitors):
                selected = monitors[index]
        else:
            wanted = str(output).lower()
            for monitor in monitors:
                description = " ".join(filter(None, [
                    monitor.get_manufacturer(), monitor.get_model(),
                ])).lower()
                if wanted in description:
                    selected = monitor
                    break
    elif len(monitors) == 1:
        selected = monitors[0]
    if selected is None:
        raise RuntimeError(f"configured output not found: {output!r}")
    GtkLayerShell.set_monitor(window, selected)


def report_after_first_paint(window, degradation=None):
    sent = {"value": False}

    def realized(widget):
        clock = widget.get_frame_clock()

        def after_paint(_clock):
            if sent["value"]:
                return
            sent["value"] = True
            signal_ready(degradation)
            clock.disconnect(handler)

        handler = clock.connect("after-paint", after_paint)
        widget.queue_draw()

    window.connect("realize", realized)
