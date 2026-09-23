"""SystemUI must not use the ultrasound proximity sensor while dozing."""
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))


def systemui_bools() -> dict:
    values = {}
    for path in (ROOT / "overlay" / "SystemUIOverlayMalachite").rglob("*.xml"):
        if path.name == "AndroidManifest.xml":
            continue
        for item in ET.parse(path).getroot().iter("bool"):
            values[item.get("name")] = item.text.strip()
    return values


class DozeProximityTests(unittest.TestCase):
    def test_doze_does_not_use_proximity(self):
        # Ultrasound proximity reads "near" when flat or while the speaker
        # plays; DozeTriggers then ignores touches on a pulsing call.
        self.assertEqual(systemui_bools().get("doze_proximity_sensor_supported"), "false")


if __name__ == "__main__":
    unittest.main()
