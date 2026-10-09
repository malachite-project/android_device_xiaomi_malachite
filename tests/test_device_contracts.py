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


A2DP_SINKS = ("BT A2DP Out", "BT A2DP Headphones", "BT A2DP Speaker")
XINCLUDE = "{http://www.w3.org/2001/XInclude}include"


def primary_module(config):
    modules = [module for module in config.iter("module") if module.get("name") == "primary"]
    assert len(modules) == 1, modules
    return modules[0]


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
        # Zero HBM time makes the controller reschedule itself continuously in sunlight.
        timing = display.find("highBrightnessMode/timing")
        self.assertGreater(int(timing.find("timeMaxSecs").text), 0)
        self.assertGreater(int(timing.find("timeMinSecs").text), 0)
        self.assertLessEqual(int(timing.find("timeMinSecs").text),
                             int(timing.find("timeMaxSecs").text))

    def test_colour_mode_lists_agree(self):
        def arrays(path, kind):
            root = ET.parse(ROOT / path).getroot()
            return {node.get("name"): [item.text.strip() for item in node.iter("item")]
                    for node in root.iter(kind)}
        framework = arrays("overlay/FrameworkResOverlayMalachite/res/values/config.xml",
                           "integer-array")
        settings = arrays("overlay/SettingsResOverlayMalachite/res/values/config.xml",
                          "integer-array")
        names = arrays("overlay/SettingsResOverlayMalachite/res/values/config.xml",
                       "string-array")["config_color_mode_options_strings"]
        modes = framework["config_availableColorModes"]
        # Native D65 is the default; Natural (0) shows the pink MediaTek template modes.
        self.assertEqual(modes[0], "273")
        self.assertTrue(all(256 <= int(mode) <= 511 for mode in modes))
        self.assertEqual(len(set(modes)), len(modes))
        self.assertEqual(framework["config_displayCompositionColorModes"], modes)
        self.assertEqual(framework["config_displayCompositionColorSpaces"], ["0"] * len(modes))
        self.assertEqual(settings["config_color_mode_options_values"], modes)
        self.assertEqual(len(names), len(modes))
        self.assertEqual(names[0], "Xiaomi native D65")
        # 0x10d, expert wide colour, shows only a faint red without Xiaomi's display service.
        self.assertNotIn("269", modes)

    def test_hdr_has_headroom_for_full_screen_hdr_only(self):
        hbm = ET.parse(ROOT / "configs/display_id_4627039422300187648.xml").getroot().find(
            "highBrightnessMode")
        self.assertEqual(hbm.find("minimumHdrPercentOfScreen").text, "0.5")
        ratios = [float(p.find("hdrRatio").text) for p in hbm.find("sdrHdrRatioMap").iter("point")]
        # The whole screen is boosted here, so stay within the normal range (<= 500 nits).
        self.assertLessEqual(max(ratios), 2.0)
        self.assertEqual(ratios[-1], 1.0)

    def test_auto_brightness_ramps_slowly(self):
        display = ET.parse(ROOT / "configs/display_id_4627039422300187648.xml").getroot()
        ramp = {name: float(display.find("screenBrightnessRamp" + name).text)
                for name in ("FastDecrease", "FastIncrease", "SlowDecrease", "SlowIncrease",
                             "IncreaseMaxMillis", "DecreaseMaxMillis")}
        # The framework ignores the rates unless all four are present.
        self.assertLess(ramp["SlowIncrease"], ramp["FastIncrease"])
        self.assertLess(ramp["SlowDecrease"], ramp["FastDecrease"])
        self.assertLessEqual(ramp["SlowDecrease"], ramp["SlowIncrease"])
        # config.xml's default slow rate (0.232) finished a change in about half a second.
        self.assertLessEqual(ramp["SlowIncrease"], 0.1)
        # Stepping into sunlight must still brighten within a few seconds.
        self.assertLessEqual(ramp["IncreaseMaxMillis"], 4000)
        self.assertGreaterEqual(ramp["DecreaseMaxMillis"], ramp["IncreaseMaxMillis"])

    def test_light_debounce_fits_in_the_sensor_history(self):
        # AutomaticBrightnessController prunes its lux ring buffer to ambientLightHorizonLong
        # and needs debounce-long runs of samples past the threshold inside it. With 4000 ms
        # darkening and a 3000 ms horizon the screen never dimmed again (2026-09-30 report).
        display = ET.parse(ROOT / "configs/display_id_4627039422300187648.xml").getroot()
        horizon = int(display.find("ambientLightHorizonLong").text)
        overlay = ET.parse(ROOT / "overlay/FrameworkResOverlayMalachite/res/values/config.xml")
        debounce = {node.get("name"): int(node.text) for node in overlay.getroot().iter("integer")
                    if node.get("name", "").startswith("config_autoBrightness")
                    and node.get("name", "").endswith(("LightDebounce", "LightDebounceIdle"))}
        self.assertIn("config_autoBrightnessDarkeningLightDebounce", debounce)
        self.assertIn("config_autoBrightnessBrighteningLightDebounce", debounce)
        # The display config's own values, if any, take precedence over config.xml.
        auto = display.find("autoBrightness")
        if auto is not None:
            for node in auto:
                if node.tag.endswith("LightDebounceMillis") or node.tag.endswith("LightDebounceIdleMillis"):
                    debounce[node.tag] = int(node.text)
        for name, millis in debounce.items():
            with self.subTest(name=name):
                self.assertLess(millis, horizon)

    def test_ambient_thresholds_live_in_the_display_config(self):
        display = ET.parse(ROOT / "configs/display_id_4627039422300187648.xml").getroot()
        for side in ("brighteningThresholds", "darkeningThresholds"):
            with self.subTest(side=side):
                node = display.find(f"ambientBrightnessChangeThresholds/{side}")
                self.assertGreater(float(node.find("minimum").text), 0)
                points = [(float(point.find("threshold").text),
                           float(point.find("percentage").text))
                          for point in node.iter("brightnessThresholdPoint")]
                # Below the first level the framework uses 0 %, so start at 0 lux.
                self.assertEqual(points[0][0], 0)
                self.assertTrue(all(a[0] < b[0] for a, b in zip(points, points[1:])))
                # Percent, not the permille config.xml uses.
                self.assertTrue(all(10 <= percentage <= 100 for _, percentage in points))
        overlay = (ROOT / "overlay/FrameworkResOverlayMalachite/res/values/config.xml").read_text()
        for name in ("config_ambientThresholdLevels", "config_ambientBrighteningThresholds",
                     "config_ambientDarkeningThresholds"):
            self.assertNotIn(f'name="{name}"', overlay)

    def test_auto_brightness_curve_has_no_steps(self):
        root = ET.parse(ROOT / "overlay/FrameworkResOverlayMalachite/res/values/config.xml").getroot()
        levels = [float(item.text) for item in
                  root.find("integer-array[@name='config_autoBrightnessLevels']").iter("item")]
        nits = [float(item.text) for item in
                root.find("array[@name='config_autoBrightnessDisplayValuesNits']").iter("item")]
        self.assertEqual(len(nits), len(levels) + 1)
        self.assertTrue(all(a < b for a, b in zip(levels, levels[1:])))
        self.assertTrue(all(a <= b for a, b in zip(nits, nits[1:])))
        lux = [0.0] + levels
        for i in range(1, len(lux)):
            if lux[i] > 30:
                break
            with self.subTest(lux=lux[i]):
                # A dim room's sensor noise must not switch between distant levels.
                self.assertLessEqual((nits[i] - nits[i - 1]) / (lux[i] - lux[i - 1]), 7)

    def test_lights_hal_reads_the_unrounded_level(self):
        overlay = ET.parse(ROOT / "overlay/FrameworkResOverlayMalachite/res/values/config.xml")
        flag = overlay.getroot().find("bool[@name='config_backlightHighPrecision']")
        self.assertEqual(flag.text, "true")
        light = (ROOT / "lights/Light.cpp").read_text()
        self.assertIn("state.flashMode == FlashMode::NONE && state.flashOnMs > 0", light)
        self.assertIn("#define PRECISE_LEVEL_MAX 65535", light)
        self.assertIn("#define PANEL_LEVEL_MAX 4095", light)
        header = (ROOT / "lights/Light.h").read_text()
        body = header.split("brightness_table[256] = {", 1)[1].split("};", 1)[0]
        table = [int(value) for value in re.findall(r"\d+", body)]
        # The unrounded path (LightsService: round(float * 65535)) lands on the table's
        # line, so an 8-bit and an unrounded value never disagree by more than a level.
        for level in range(1, 256):
            brightness = (level - 1) / 254
            precise = max(1, round(brightness * 65535))
            panel = max((precise * 4095 + 65535 // 2) // 65535, table[1])
            with self.subTest(level=level):
                self.assertLessEqual(abs(panel - table[level]), 1)

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

    def test_charging_control_can_reach_its_node(self):
        # The battery supply directory is sysfs_batteryinfo; without access the Lineage
        # health HAL failed every call ("Failed to read current charging enabled value").
        device = (ROOT / "device.mk").read_text()
        self.assertIn("charging_control_charging_path,/sys/class/power_supply/battery/", device)
        policy = (ROOT / "sepolicy/vendor/hal_lineage_health_default.te").read_text()
        self.assertIn("r_dir_file(hal_lineage_health_default, sysfs_batteryinfo)", policy)
        self.assertIn("allow hal_lineage_health_default sysfs_batteryinfo:file rw_file_perms;",
                      policy)

    def test_a2dp_runs_on_the_spatializer_output_only(self):
        # A plain A2DP output gets a FastMixer, which puts normal tracks behind a
        # 40-75 ms MonoPipe; the spatializer thread mixes in the HAL's 10 ms periods.
        # Applies to software A2DP in both the offload and the fallback configuration.
        for name in ("bluetooth_audio_policy_configuration.xml",
                     "bluetooth_offload_audio_policy_configuration.xml"):
            module = ET.parse(ROOT / "configs/audio" / name).getroot()
            flags = {port.get("name"): port.get("flags") for port in module.iter("mixPort")}
            self.assertEqual(flags["a2dp output"], "AUDIO_OUTPUT_FLAG_SPATIALIZER", name)
            self.assertNotIn("a2dp spatializer output", flags)
            routes = {route.get("sink"): route.get("sources").split(",")
                      for route in module.iter("route")}
            for sink in A2DP_SINKS:
                with self.subTest(file=name, sink=sink):
                    self.assertEqual(routes[sink], ["a2dp output"])

    def test_a2dp_offload_is_the_default_with_a_software_fallback(self):
        # system/media audio_config.h: with ro.bluetooth.a2dp_offload.supported=true,
        # persist.bluetooth.a2dp_offload.disabled=true selects
        # audio_policy_configuration_a2dp_offload_disabled.xml; otherwise (no
        # le_offload_disabled file here) audio_policy_configuration.xml. The Bluetooth
        # stack reads the same two properties to choose the offload session.
        props = (ROOT / "vendor.prop").read_text()
        for line in ("ro.bluetooth.a2dp_offload.supported=true",
                     "persist.bluetooth.a2dp_offload.disabled=false",
                     "persist.bluetooth.a2dp_offload.cap=sbc-aac"):
            with self.subTest(prop=line):
                self.assertRegex(props, rf"(?m)^{re.escape(line)}$")
        self.assertNotIn("persist.bluetooth.bluetooth_audio_hal.disabled", props)
        audio = ROOT / "configs/audio"
        self.assertFalse((audio / "audio_policy_configuration_le_offload_disabled.xml").exists())
        self.assertFalse((audio / "audio_policy_configuration_bluetooth_legacy_hal.xml").exists())
        cases = {"audio_policy_configuration.xml":
                     ("bluetooth_offload_audio_policy_configuration.xml", True),
                 "audio_policy_configuration_a2dp_offload_disabled.xml":
                     ("bluetooth_audio_policy_configuration.xml", False)}
        for name, (include, offloaded) in cases.items():
            with self.subTest(file=name):
                config = ET.parse(audio / name).getroot()
                includes = [node.get("href") for node in config.iter(XINCLUDE)]
                self.assertIn(include, includes)
                self.assertTrue((audio / include).exists())
                primary = primary_module(config)
                ports = {port.get("tagName"): port for port in primary.iter("devicePort")}
                routes = {route.get("sink"): route.get("sources").split(",")
                          for route in primary.iter("route")}
                for sink in A2DP_SINKS:
                    if offloaded:
                        self.assertEqual(ports[sink].get("encodedFormats"),
                                         "AUDIO_FORMAT_SBC AUDIO_FORMAT_AAC")
                        self.assertEqual(routes[sink], ["primary output", "deep_buffer", "fast",
                                                        "immersive_out"])
                    else:
                        self.assertNotIn(sink, ports)
                        self.assertNotIn(sink, routes)

    def test_offload_and_fallback_primary_modules_differ_only_in_a2dp(self):
        def shape(node):
            children = [shape(child) for child in node
                        if child.get("tagName") not in A2DP_SINKS
                        and child.get("sink") not in A2DP_SINKS]
            return node.tag, sorted(node.attrib.items()), (node.text or "").strip(), children

        def stripped(name):
            return shape(primary_module(ET.parse(ROOT / "configs/audio" / name).getroot()))
        self.assertEqual(stripped("audio_policy_configuration.xml"),
                         stripped("audio_policy_configuration_a2dp_offload_disabled.xml"))

    def test_offloaded_bluetooth_module_has_software_a2dp_and_no_le_audio(self):
        # PCM-only A2DP ports catch codecs the DSP does not encode (empty encodedFormats
        # matches any codec in DeviceDescriptorBase::supportsFormat). LE Audio stays off.
        module = ET.parse(ROOT / "configs/audio/bluetooth_offload_audio_policy_configuration.xml"
                          ).getroot()
        ports = {port.get("tagName"): port for port in module.iter("devicePort")}
        for sink in A2DP_SINKS:
            with self.subTest(sink=sink):
                self.assertEqual(ports[sink].get("encodedFormats"), "")
        self.assertIn("BT Hearing Aid Out", ports)
        self.assertFalse([port for port in ports.values() if "BLE" in port.get("type")])

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

    def test_touch_hal_offers_high_polling_rate(self):
        node = "/sys/devices/platform/goodix_ts.0/goodix_ts_report_rate"
        self.assertIn("vendor.lineage.touch-service.malachite", (ROOT / "device.mk").read_text())
        self.assertIn(node, (ROOT / "touch/HighTouchPollingRate.cpp").read_text())
        rc = (ROOT / "touch/vendor.lineage.touch-service.malachite.rc").read_text()
        self.assertIn("chown system system " + node, rc)
        self.assertIn("genfscon sysfs " + node[len("/sys"):] +
                      " u:object_r:vendor_sysfs_touch_report_rate:s0",
                      (ROOT / "sepolicy/vendor/genfs_contexts").read_text())
        self.assertIn(r"vendor\.lineage\.touch-service\.malachite "
                      "u:object_r:hal_lineage_touch_default_exec:s0",
                      (ROOT / "sepolicy/vendor/file_contexts").read_text())
        manifest = ET.parse(ROOT / "touch/vendor.lineage.touch-service.malachite.xml").getroot()
        self.assertEqual([i.text for i in manifest.iter("name")],
                         ["vendor.lineage.touch", "IHighTouchPollingRate"])

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
