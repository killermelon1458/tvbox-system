from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from tvbox.overlay.protocol import ProtocolError, validate_request


class ProtocolTests(unittest.TestCase):
    def base(self):
        return {
            "schema_version": 1, "owner_service": "screensaver",
            "owner_instance_id": "one", "owner_pid": 1,
            "overlay_type": "screensaver", "renderer": "black",
            "arguments": {"output": "0"}, "priority": 20,
            "lease_seconds": 60, "preemption_policy": "cancel",
        }

    def test_validated_request(self):
        self.assertEqual(validate_request(self.base()).renderer, "black")

    def test_rejects_unknown_arguments_and_priority_spoofing(self):
        value = self.base()
        value["arguments"]["command"] = "bad"
        with self.assertRaises(ProtocolError):
            validate_request(value)
        value = self.base()
        value["priority"] = 50
        with self.assertRaises(ProtocolError):
            validate_request(value)

    def test_rejects_bad_schema_and_lease(self):
        value = self.base()
        value["schema_version"] = 2
        with self.assertRaises(ProtocolError):
            validate_request(value)

    def test_rejects_unbounded_slideshow_arguments(self):
        value = self.base()
        value["renderer"] = "slideshow"
        value["arguments"] = {
            "output": "0", "image_directory": "/tmp",
            "image_duration": -1, "max_files": 5000,
            "extensions": ["jpg"],
        }
        with self.assertRaises(ProtocolError):
            validate_request(value)
        value = self.base()
        value["lease_seconds"] = 0
        with self.assertRaises(ProtocolError):
            validate_request(value)


if __name__ == "__main__":
    unittest.main()
