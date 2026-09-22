"""Static checks that the face unlock pieces are wired together."""
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))


def device_mk():
    return (ROOT / "device.mk").read_text().replace("\\\n", " ")


def manifest_projects():
    root = ET.parse(ROOT / "manifests/malachite.xml").getroot()
    return {p.get("path"): p for p in root.findall("project")}


class FaceUnlockTests(unittest.TestCase):
    def test_app_and_provider_switch_ship_together(self):
        # frameworks/base only registers SenseProvider when this is true, and
        # SenseProvider binds co.aospa.sense, so one without the other is dead.
        mk = device_mk()
        self.assertRegex(mk, r"PRODUCT_PACKAGES \+=\s+ParanoidSense\b")
        self.assertRegex(mk, r"PRODUCT_SYSTEM_EXT_PROPERTIES \+=\s+ro\.face\.sense_service=true")

    def test_face_feature_is_declared(self):
        self.assertIn("android.hardware.biometrics.face.xml:", device_mk())

    def test_manifest_provides_both_halves(self):
        projects = manifest_projects()
        base = projects["frameworks/base"]
        self.assertEqual(base.get("name"), "android_frameworks_base")
        self.assertEqual(base.get("revision"), "noam/lineage-23.2")
        sense = projects["packages/apps/ParanoidSense"]
        self.assertEqual(sense.get("remote"), "malachite-project")
        self.assertEqual(sense.get("revision"), "sixteen-qpr2")

    def test_replaced_paths_are_removed_first(self):
        root = ET.parse(ROOT / "manifests/malachite.xml").getroot()
        removed = {p.get("path") for p in root.findall("remove-project")}
        self.assertIn("frameworks/base", removed)
        self.assertNotIn("packages/apps/ParanoidSense", removed)


if __name__ == "__main__":
    unittest.main()
