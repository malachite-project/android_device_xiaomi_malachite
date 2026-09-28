"""Offline guards for product wiring and the transitional malachite baseline.

GNU Make evaluation stubs Android inheritance/helpers. It checks this fragment,
not Kati/Soong, image construction, VINTF compatibility, or hardware behavior.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))


def product_copies(local_path: str) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="malachite-make-test-") as temporary:
        work = Path(temporary)
        device = work / "device/xiaomi/malachite"
        device.mkdir(parents=True)
        shutil.copyfile(ROOT / "device.mk", device / "device.mk")
        shutil.copyfile(ROOT / "vendor_logtag.mk", device / "vendor_logtag.mk")
        (work / "harness.mk").write_text(
            "PRODUCT_COPY_FILES :=\n"
            "TARGET_COPY_OUT_PRODUCT := product\n"
            "TARGET_COPY_OUT_VENDOR := vendor\n"
            "TARGET_COPY_OUT_ODM := odm\n"
            f"LOCAL_PATH := {local_path}\n"
            "include device/xiaomi/malachite/device.mk\n"
            ".PHONY: print-copies\n"
            "print-copies:\n\t@printf '%s\\n' '$(PRODUCT_COPY_FILES)'\n"
        )
        run = subprocess.run(["make", "--no-print-directory", "-f", "harness.mk", "print-copies"],
                             cwd=work, check=True, text=True, capture_output=True, timeout=20,
                             env=dict(os.environ, MAKEFLAGS="", MAKEFILES=""))
        return run.stdout.split()


class DeviceContracts(unittest.TestCase):
    def test_primary_skus_define_the_bluetooth_name_property(self):
        primary = list((ROOT / "boardid").glob("*.prop"))
        primary = [path for path in primary if "_" not in path.stem]
        self.assertTrue(primary)
        for path in primary:
            with self.subTest(sku=path.stem):
                text = path.read_text()
                self.assertRegex(text, r"(?m)^bluetooth\.device\.default_name=.+$")
                self.assertNotIn("ubluetooth.device.default_name=", text)
        self.assertIn("bluetooth.device.default_name=POCO X7\n",
                      (ROOT / "boardid/S99016IA1.prop").read_text())

    def test_poco_boards_override_the_marketname_from_product(self):
        product = (ROOT / "product.prop").read_text()
        self.assertIn("ro.product.marketname=Redmi Note 14 Pro 5G\n"
                      "import /product/etc/marketname/${ro.boot.board_id}.prop\n", product)
        self.assertIn("$(DEVICE_PATH)/marketname/,$(TARGET_COPY_OUT_PRODUCT)/etc/marketname",
                      (ROOT / "device.mk").read_text())
        boards = [path for path in (ROOT / "boardid").glob("*.prop") if "_" not in path.stem]
        poco = {path.stem for path in boards if "ro.product.odm.brand=POCO\n" in path.read_text()}
        self.assertEqual(poco, {"S99016IA1", "S99116EA1"})
        overrides = {path.stem: path.read_text() for path in (ROOT / "marketname").glob("*.prop")}
        self.assertEqual(overrides, {sku: "ro.product.marketname=POCO X7\n" for sku in poco})
        # vendor_init loads the odm files and may not set default_prop.
        for path in (ROOT / "boardid").glob("*.prop"):
            with self.subTest(sku=path.stem):
                self.assertNotIn("ro.product.marketname", path.read_text())

    def test_brightness_table_stays_in_the_panel_range(self):
        header = (ROOT / "lights/Light.h").read_text()
        body = header.split("brightness_table[256] = {", 1)[1].split("};", 1)[0]
        # The initializer must close right after the 256th value.
        self.assertRegex(header, r"4095,\s*\n\};")
        table = [int(value) for value in re.findall(r"\d+", body)]
        self.assertEqual(len(table), 256)
        self.assertEqual(table[0], 0)
        # 0x51 holds 12 bits; 4095 is the panel's peak mode.
        self.assertEqual(table[-1], 4095)
        # Linear like stock's composer: level L is float (L - 1) / 254.
        self.assertEqual(table[1], 15)
        self.assertTrue(all(low < high for low, high in zip(table[1:], table[2:])))
        for level in range(2, 256):
            with self.subTest(level=level):
                self.assertLessEqual(abs(table[level] - 4095 * (level - 1) / 254), 1)
        # Float 0.5, the high-brightness transition point, is the normal maximum.
        self.assertEqual(table[128], 2047)
        self.assertGreater(table[129], 2047)
        display = ET.parse(ROOT / "configs/display_id_4627039422300187648.xml").getroot()
        self.assertEqual(display.find("highBrightnessMode/transitionPoint").text, "0.499951")

    def test_lights_hal_keeps_brightness_clone_set(self):
        node = "/sys/devices/virtual/mi_display/disp_feature/disp-DSI-0/brightness_clone"
        light = (ROOT / "lights/Light.cpp").read_text()
        self.assertIn(f'#define BRIGHTNESS_CLONE "{node}"', light)
        self.assertIn("set(BRIGHTNESS_CLONE,", light)
        self.assertIn(f"genfscon sysfs {node.removeprefix('/sys')} u:object_r:sysfs_leds:s0\n",
                      (ROOT / "sepolicy/vendor/genfs_contexts").read_text())
        self.assertIn("allow hal_light_default sysfs_gpu:dir search;",
                      (ROOT / "sepolicy/vendor/hal_light_default.te").read_text())
        init = (ROOT / "init/init.mt6878.rc").read_text()
        self.assertIn("chown system system /sys/class/mi_display/disp-DSI-0/brightness_clone\n", init)

    def test_a2dp_has_a_plain_output_beside_the_spatializer(self):
        module = ET.parse(ROOT / "configs/audio/bluetooth_audio_policy_configuration.xml").getroot()
        flags = {port.get("name"): port.get("flags") for port in module.iter("mixPort")}
        self.assertIsNone(flags["a2dp output"])
        self.assertEqual(flags["a2dp spatializer output"], "AUDIO_OUTPUT_FLAG_SPATIALIZER")
        routes = {route.get("sink"): route.get("sources").split(",") for route in module.iter("route")}
        for sink in ("BT A2DP Out", "BT A2DP Headphones", "BT A2DP Speaker"):
            with self.subTest(sink=sink):
                self.assertEqual(routes[sink], ["a2dp output", "a2dp spatializer output"])

    def test_qr_tile_uses_aperture_without_a_second_camera(self):
        self.assertIn("product/priv-app/MiuiCamera/MiuiCamera.apk\n",
                      (ROOT / "proprietary-files.txt").read_text())
        config = ET.parse(ROOT / "overlay/FrameworkResOverlayMalachite/res/values/config.xml").getroot()
        strings = {node.get("name"): node.text for node in config.iter("string")}
        self.assertEqual(strings["config_defaultQrCodeComponent"],
                         "org.lineageos.aperture/.QrScannerActivity")
        override = ET.parse(ROOT / "configs/sysconfig/aperture-qr-scanner.xml").getroot().find(
            "component-override")
        self.assertEqual(override.get("package"), "org.lineageos.aperture")
        disabled = {node.get("class") for node in override.iter("component")
                    if node.get("enabled") == "false"}
        self.assertEqual(disabled, {".CameraLauncher", ".CameraActivity", ".CaptureActivity",
                                    ".VideoCamera", ".SecureCameraActivity"})
        self.assertIn("configs/sysconfig/aperture-qr-scanner.xml:"
                      "$(TARGET_COPY_OUT_PRODUCT)/etc/sysconfig/aperture-qr-scanner.xml",
                      (ROOT / "device.mk").read_text())

    def test_euicc_permission_has_one_copy(self):
        entries = product_copies("vendor/mediatek/ims")
        destination = "product/etc/permissions/android.hardware.telephony.euicc.xml"
        self.assertEqual(sum(entry.split(":")[-1] == destination for entry in entries), 1)

    def test_hotword_path_is_independent_of_local_path(self):
        expected = "device/xiaomi/malachite/configs/permissions/privapp-permissions-hotword.xml:product/etc/permissions/privapp-permissions-hotword.xml"
        for inherited_path in ("vendor/mediatek/ims", "hardware/xiaomi", "unrelated"):
            with self.subTest(local_path=inherited_path):
                self.assertIn(expected, product_copies(inherited_path))
        self.assertTrue((ROOT / "configs/permissions/privapp-permissions-hotword.xml").is_file())

    def test_literal_device_copy_sources_exist(self):
        copies = product_copies("vendor/mediatek/ims")
        local = [entry.split(":", 1)[0] for entry in copies if entry.startswith("device/xiaomi/malachite/")]
        self.assertTrue(local)
        for source in local:
            with self.subTest(source=source):
                self.assertTrue((ROOT / source.removeprefix("device/xiaomi/malachite/")).is_file())

    def test_device_xml_is_well_formed(self):
        files = list(ROOT.glob("*.xml")) + [path for directory in ("configs", "overlay", "overlay-lineage", "vintf", "lights") for path in (ROOT / directory).rglob("*.xml")]
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=str(path.relative_to(ROOT))):
                ET.parse(path)

    def test_transitional_prebuilt_kernel_is_not_silently_switched(self):
        board = (ROOT / "BoardConfig.mk").read_text()
        self.assertRegex(board, r"(?m)^TARGET_FORCE_PREBUILT_KERNEL\s*:=\s*true\s*$")

    def test_dtbo_and_sensitive_partitions_are_not_added_to_ota(self):
        board = (ROOT / "BoardConfig.mk").read_text()
        self.assertNotRegex(board, r"(?m)^\s*BOARD_PREBUILT_DTBOIMAGE\s*[:+?]?=")
        logical_lines = board.replace("\\\n", " ")
        assignments = re.findall(r"(?m)^AB_OTA_PARTITIONS\s*[:+?]?=\s*([^\n]+)", logical_lines)
        partitions = set(" ".join(assignments).split())
        self.assertTrue({"boot", "init_boot", "vendor_boot"} <= partitions)
        forbidden = {"dtbo", "preloader", "bootloader", "lk", "lk1", "lk2", "gpt", "seccfg", "efuse", "nvram", "nvdata", "nvcfg", "persist", "protect1", "protect2", "modem"}
        self.assertFalse(partitions & forbidden)

    def test_documented_camera_baseline_and_abi_fixups_remain(self):
        blobs = (ROOT / "proprietary-files.txt").read_text()
        fixups = (ROOT / "extract-files.py").read_text()
        self.assertIn("All blobs are from OS2.0.208.0.VOOMIXM unless noted or pinned", blobs)
        self.assertIn(".replace_needed('libtinyxml2.so', 'libtinyxml2-v34.so')", fixups)
        self.assertIn(".call(blob_fixup_graphic_buffer_size)", fixups)


if __name__ == "__main__":
    unittest.main()
