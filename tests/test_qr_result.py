"""The Xiaomi camera's QR hand-off to MalachiteQrResult (package com.xiaomi.scanner).

Checks the names the camera uses and runs the plain-Java parser test when a JDK
is available. It does not build the app or test it on a device.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
APP = ROOT / "camera/qr-result"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class QrResultContract(unittest.TestCase):
    def test_manifest_matches_what_the_camera_sends(self):
        manifest = ET.parse(APP / "AndroidManifest.xml").getroot()
        # MiuiCamera b1.r.a: explicit broadcast to this component, extra "result",
        # and it holds com.xiaomi.scanner.receiver.RECEIVER.
        self.assertEqual(manifest.get("package"), "com.xiaomi.scanner")
        permission = manifest.find("permission")
        self.assertEqual(permission.get(ANDROID + "name"), "com.xiaomi.scanner.receiver.RECEIVER")
        self.assertEqual(permission.get(ANDROID + "protectionLevel"), "signature")
        receiver = manifest.find("application/receiver")
        self.assertEqual(receiver.get(ANDROID + "name"), ".module.code.app.BarCodeScannerReceiver")
        self.assertEqual(receiver.get(ANDROID + "permission"), "com.xiaomi.scanner.receiver.RECEIVER")
        self.assertEqual(receiver.find("intent-filter/action").get(ANDROID + "name"),
                         "com.xiaomi.scanner.receiver.senderbarcodescanner")
        activities = manifest.findall("application/activity")
        self.assertTrue(all(a.get(ANDROID + "exported") == "false" for a in activities))
        self.assertIsNone(manifest.find(".//category[@" + ANDROID + "name='android.intent.category.LAUNCHER']"))
        receiver_source = (APP / "src/com/xiaomi/scanner/module/code/app/BarCodeScannerReceiver.java").read_text()
        self.assertIn('EXTRA_RESULT = "result"', receiver_source)

    def test_signed_like_the_camera_and_installed(self):
        blueprint = (APP / "Android.bp").read_text()
        self.assertIn('name: "MalachiteQrResult"', blueprint)
        self.assertIn('certificate: "platform"', blueprint)
        self.assertIn("    MalachiteQrResult \\\n", (ROOT / "device.mk").read_text())

    @unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "no JDK")
    def test_parser(self):
        sources = [APP / "src/com/xiaomi/scanner/module/code/app/QrContent.java",
                   ROOT / "tests/java/com/xiaomi/scanner/module/code/app/QrContentTest.java"]
        with tempfile.TemporaryDirectory() as out:
            subprocess.run(["javac", "-d", out, *map(str, sources)], check=True,
                           capture_output=True, text=True, timeout=120)
            run = subprocess.run(["java", "-cp", out, "com.xiaomi.scanner.module.code.app.QrContentTest"],
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
