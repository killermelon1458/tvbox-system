from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class LifecycleIntegrationTests(unittest.TestCase):
    def test_home_stops_screensaver_before_lifecycle(self):
        source = (ROOT / "bin/tvbox-home").read_text()
        self.assertLess(source.index("tvbox-screensaver stop"),
                        source.index("request_tv_activation"))

    def test_tvboxctl_home_and_exit_invalidate(self):
        source = (ROOT / "bin/tvboxctl").read_text()
        for function in ("do_home()", "do_exit()"):
            section = source.split(function, 1)[1].split("\n}", 1)[0]
            self.assertIn("invalidate_screensaver", section)

    def test_application_wrappers_stop_before_launch(self):
        checks = {
            "tvbox-moonlight": "moonlight-qt",
            "tvbox-youtube": '"$CHROME"',
            "tvbox-mariokart64": "/usr/local/bin/mupen64plus",
            "tvbox-spotify-mode": "pkill -x kodi",
        }
        for name, launch in checks.items():
            source = (ROOT / f"bin/{name}").read_text()
            self.assertLess(source.index("tvbox-screensaver stop"),
                            source.rindex(launch), name)


if __name__ == "__main__":
    unittest.main()
