from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class RendererContractTests(unittest.TestCase):
    def test_layer_shell_contract(self):
        source = (ROOT / "lib/tvbox/overlay/renderer.py").read_text()
        for contract in (
            "Layer.OVERLAY", "Edge.TOP", "Edge.BOTTOM", "Edge.LEFT",
            "Edge.RIGHT", "set_exclusive_zone(window, -1)",
            "KeyboardMode.ON_DEMAND", "set_monitor", "after-paint",
        ):
            self.assertIn(contract, source)

    def test_black_is_opaque_and_has_no_audio_or_lifecycle_calls(self):
        source = (ROOT / "bin/tvbox-render-black").read_text()
        self.assertIn("set_source_rgba(0.0, 0.0, 0.0, 1.0)", source)
        self.assertIn("context.paint()", source)
        for forbidden in ("alsa", "pactl", "tvboxctl", "tvbox-inputctl", "cec"):
            self.assertNotIn(forbidden, source.lower())

    def test_renderers_use_term_and_first_frame_readiness(self):
        for name in ("tvbox-render-black", "tvbox-render-slideshow"):
            source = (ROOT / f"bin/{name}").read_text()
            self.assertIn("SIGTERM", source)
            self.assertIn("report_after_first_paint", source)

    def test_every_overlay_uses_surface_owned_blank_cursor(self):
        shared = (ROOT / "lib/tvbox/overlay/renderer.py").read_text()
        self.assertIn("Gdk.CursorType.BLANK_CURSOR", shared)
        self.assertIn("surface.set_cursor(cursor)", shared)
        for name in ("tvbox-render-black", "tvbox-render-slideshow"):
            source = (ROOT / f"bin/{name}").read_text()
            self.assertIn("configure_opaque_overlay_window", source)

    def test_slideshow_always_paints_black_and_flattens_alpha(self):
        renderer = (ROOT / "bin/tvbox-render-slideshow").read_text()
        loader = (ROOT / "lib/tvbox/screensaver/slideshow.py").read_text()
        self.assertIn("set_source_rgba(0.0, 0.0, 0.0, 1.0)", renderer)
        self.assertIn("context.paint()", renderer)
        self.assertIn("flatten_alpha_over_black", loader)


if __name__ == "__main__":
    unittest.main()
