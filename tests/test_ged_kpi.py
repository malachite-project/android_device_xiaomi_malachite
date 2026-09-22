"""Static checks for libgui's MediaTek GED KPI support (off for the first build)."""
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))


class GedKpiTests(unittest.TestCase):
    def test_libgui_flag_is_off_for_the_first_build(self):
        # frameworks/native compiles the GED KPI code only under this flag. It
        # stays off until a build without it has booted on the phone.
        mk = (ROOT / "device.mk").read_text()
        self.assertIn("$(call soong_config_set_bool,libgui,support_mtk_ged_kpi,false)", mk)

    def test_manifest_takes_patched_native(self):
        root = ET.parse(ROOT / "manifests/malachite.xml").getroot()
        native = {p.get("path"): p for p in root.findall("project")}["frameworks/native"]
        self.assertEqual(native.get("remote"), "malachite-project")
        self.assertEqual(native.get("revision"), "noam/lineage-23.2")

    def test_apps_may_use_proc_ged(self):
        # MediaTek's common policy already grants what libgui needs: every app
        # and surfaceflinger opens /proc/ged and issues GED_BRIDGE_IO_GPU_TIMESTAMP.
        policy = ROOT.parent / "device_mediatek_sepolicy_vndr" / "base" / "vendor"
        if not policy.is_dir():
            self.skipTest("device_mediatek_sepolicy_vndr is not checked out beside the tree")
        app = (policy / "app.te").read_text()
        self.assertIn("allow appdomain proc_ged:file rw_file_perms;", app)
        self.assertIn("allowxperm appdomain proc_ged:file ioctl { proc_ged_ioctls };", app)
        self.assertIn("GED_BRIDGE_IO_GPU_TIMESTAMP", (policy / "ioctl_macros").read_text())


if __name__ == "__main__":
    unittest.main()
