from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.screensaver.schedule import (
    ConfigError, load_config, next_boundary, scheduled_mode,
)


CONFIG = """
[screensaver]
default_mode = "slideshow"
timezone = "America/Chicago"
output = "0"

[[screensaver.schedule]]
start = "00:00"
end = "08:00"
mode = "black"

[slideshow]
image_directory = "/tmp/images"
fit_mode = "contain"
"""


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "screensaver.toml"
        self.path.write_text(CONFIG)
        self.config = load_config(self.path)
        self.zone = ZoneInfo("America/Chicago")

    def tearDown(self):
        self.tmp.cleanup()

    def moment(self, hour, minute=0, day=15, month=7):
        return datetime(2026, month, day, hour, minute, tzinfo=self.zone)

    def test_daytime_and_overnight(self):
        self.assertEqual(scheduled_mode(self.config, self.moment(12)), "slideshow")
        self.assertEqual(scheduled_mode(self.config, self.moment(0)), "black")
        self.assertEqual(scheduled_mode(self.config, self.moment(7, 59)), "black")
        self.assertEqual(scheduled_mode(self.config, self.moment(8)), "slideshow")

    def test_cross_midnight_rule(self):
        self.path.write_text(CONFIG.replace(
            'start = "00:00"\nend = "08:00"',
            'start = "22:00"\nend = "06:00"'))
        config = load_config(self.path)
        self.assertEqual(scheduled_mode(config, self.moment(23)), "black")
        self.assertEqual(scheduled_mode(config, self.moment(2)), "black")
        self.assertEqual(scheduled_mode(config, self.moment(12)), "slideshow")

    def test_exact_next_boundary(self):
        boundary = next_boundary(self.config, self.moment(7, 30))
        self.assertEqual((boundary.hour, boundary.minute), (8, 0))
        boundary = next_boundary(self.config, self.moment(8))
        self.assertEqual((boundary.day, boundary.hour), (16, 0))

    def test_later_overlap_rule_wins(self):
        self.path.write_text(CONFIG.replace(
            "[slideshow]", """
[[screensaver.schedule]]
start = "07:00"
end = "09:00"
mode = "slideshow"

[slideshow]"""))
        config = load_config(self.path)
        self.assertEqual(scheduled_mode(config, self.moment(7, 30)), "slideshow")

    def test_restart_and_clock_jump_are_fresh_evaluations(self):
        self.assertEqual(scheduled_mode(self.config, self.moment(23)), "slideshow")
        self.assertEqual(scheduled_mode(self.config, self.moment(1)), "black")

    def test_dst_spring_and_fall_use_local_wall_clock(self):
        spring = datetime(2026, 3, 8, 3, 30, tzinfo=self.zone)
        fall = datetime(2026, 11, 1, 1, 30, tzinfo=self.zone, fold=1)
        self.assertEqual(scheduled_mode(self.config, spring), "black")
        self.assertEqual(scheduled_mode(self.config, fall), "black")

    def test_config_reload_and_validation(self):
        self.path.write_text(CONFIG.replace('default_mode = "slideshow"',
                                            'default_mode = "black"'))
        self.assertEqual(load_config(self.path).default_mode, "black")
        self.path.write_text(CONFIG.replace('timezone = "America/Chicago"',
                                            'timezone = "Mars/Olympus"'))
        with self.assertRaises(ConfigError):
            load_config(self.path)

    def test_recursive_discovery_is_mandatory(self):
        self.assertTrue(self.config.recursive)
        self.path.write_text(CONFIG.replace(
            'image_directory = "/tmp/images"',
            'image_directory = "/tmp/images"\nrecursive = false'))
        with self.assertRaisesRegex(ConfigError, "cannot be disabled"):
            load_config(self.path)


if __name__ == "__main__":
    unittest.main()
