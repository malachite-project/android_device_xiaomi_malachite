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
# Stock's MediaTek LE Audio offload ports in the primary module.
BLE_OFFLOAD_PORTS = {"BLE Headset Out": ("AUDIO_DEVICE_OUT_BLE_HEADSET", "sink"),
                     "BLE Speaker Out": ("AUDIO_DEVICE_OUT_BLE_SPEAKER", "sink"),
                     "BLE BlueTooth In": ("AUDIO_DEVICE_IN_BLUETOOTH_BLE", "source"),
                     "BLE Headset In": ("AUDIO_DEVICE_IN_BLE_HEADSET", "source"),
                     "BLE Broadcast": ("AUDIO_DEVICE_OUT_BLE_BROADCAST", "sink")}


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

    def test_headset_detection_uses_input_events(self):
        config = ET.parse(ROOT / "overlay/FrameworkResOverlayMalachite/res/values/config.xml")
        bools = {node.get("name"): node.text for node in config.getroot().iter("bool")}
        self.assertEqual(bools["config_useDevInputEventForAudioJack"], "true")

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

    def test_policy_file_follows_the_offload_switches(self):
        # system/media audio_config.h, with ro.bluetooth.a2dp_offload.supported=true:
        # persist.bluetooth.a2dp_offload.disabled=true selects
        # audio_policy_configuration_a2dp_offload_disabled.xml; otherwise LE offload
        # unsupported or persist.bluetooth.leaudio_offload.disabled=true selects
        # audio_policy_configuration_le_offload_disabled.xml; otherwise
        # audio_policy_configuration.xml. The Bluetooth stack reads the same properties
        # (codec_manager.cc defaults leaudio_offload.disabled to true).
        props = (ROOT / "vendor.prop").read_text()
        for line in ("ro.bluetooth.a2dp_offload.supported=true",
                     "persist.bluetooth.a2dp_offload.disabled=false",
                     "persist.bluetooth.a2dp_offload.cap=sbc-aac",
                     "ro.bluetooth.leaudio_offload.supported=true",
                     "persist.bluetooth.leaudio_offload.disabled=false"):
            with self.subTest(prop=line):
                self.assertRegex(props, rf"(?m)^{re.escape(line)}$")
        self.assertNotIn("persist.bluetooth.bluetooth_audio_hal.disabled", props)
        audio = ROOT / "configs/audio"
        self.assertFalse((audio / "audio_policy_configuration_bluetooth_legacy_hal.xml").exists())
        # file: (bluetooth module, A2DP offloaded, LE Audio offloaded)
        cases = {"audio_policy_configuration.xml":
                     ("bluetooth_le_offload_audio_policy_configuration.xml", True, True),
                 "audio_policy_configuration_le_offload_disabled.xml":
                     ("bluetooth_offload_audio_policy_configuration.xml", True, False),
                 "audio_policy_configuration_a2dp_offload_disabled.xml":
                     ("bluetooth_audio_policy_configuration.xml", False, False)}
        for name, (include, a2dp_offloaded, le_offloaded) in cases.items():
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
                    if a2dp_offloaded:
                        self.assertEqual(ports[sink].get("encodedFormats"),
                                         "AUDIO_FORMAT_SBC AUDIO_FORMAT_AAC")
                        self.assertEqual(routes[sink], ["primary output", "deep_buffer", "fast",
                                                        "immersive_out"])
                    else:
                        self.assertNotIn(sink, ports)
                        self.assertNotIn(sink, routes)
                primary_ble = [port for port in primary.iter("devicePort")
                               if "BLE" in port.get("type")]
                module = ET.parse(audio / include).getroot()
                module_ble = [port for port in module.iter("devicePort")
                              if "BLE" in port.get("type")]
                # LE Audio devices in exactly one module: primary when offloaded.
                self.assertEqual(bool(primary_ble), le_offloaded)
                self.assertEqual(bool(module_ble), not le_offloaded)

    def test_policy_primary_modules_differ_only_in_offload_ports(self):
        ble_tags = set(BLE_OFFLOAD_PORTS)

        def shape(node):
            children = [shape(child) for child in node
                        if child.get("tagName") not in A2DP_SINKS + tuple(ble_tags)
                        and child.get("sink") not in A2DP_SINKS + tuple(ble_tags)]
            attrib = dict(node.attrib)
            if node.tag == "route":
                attrib["sources"] = ",".join(source for source in attrib["sources"].split(",")
                                             if source not in ble_tags)
            return node.tag, sorted(attrib.items()), (node.text or "").strip(), children

        def stripped(name):
            return shape(primary_module(ET.parse(ROOT / "configs/audio" / name).getroot()))
        reference = stripped("audio_policy_configuration_a2dp_offload_disabled.xml")
        for name in ("audio_policy_configuration.xml",
                     "audio_policy_configuration_le_offload_disabled.xml"):
            with self.subTest(file=name):
                self.assertEqual(stripped(name), reference)

    def test_a2dp_offload_reserves_coex_buffers(self):
        # bta_av_aact.cc reads persist.bluetooth.a2dp_offload.coex_buf_count (default 0)
        # on each offload start. bluetooth_prop: vendor_init may not set it.
        self.assertRegex((ROOT / "system.prop").read_text(),
                         r"(?m)^persist\.bluetooth\.a2dp_offload\.coex_buf_count=3$")
        self.assertNotIn("coex_buf_count", (ROOT / "vendor.prop").read_text())

    def test_stock_bluetooth_hal_links_stock_session_libraries(self):
        # audio.bluetooth.mt6878 needs libbluetooth_audio_session(.so), which pulls
        # libbluetooth_audio_session_aidl. The AOSP modules of those names build against
        # bluetooth.audio V5 / audio.common V4; Soong refuses them beside the stock HAL's
        # V3 / audio.common V2. Stock's own copies ship renamed instead.
        files = (ROOT / "proprietary-files.txt").read_text()
        for line in ("vendor/lib64/libbluetooth_audio_session.so:"
                     "vendor/lib64/libbluetooth_audio_session_stock.so;FIX_SONAME",
                     "vendor/lib64/libbluetooth_audio_session_aidl.so:"
                     "vendor/lib64/libbluetooth_audio_session_aidl_stock.so;FIX_SONAME"):
            with self.subTest(line=line):
                self.assertRegex(files, rf"(?m)^{re.escape(line)}$")
        fixups = (ROOT / "extract-files.py").read_text()
        self.assertIn("'vendor/lib64/hw/audio.bluetooth.mt6878.so': blob_fixup()\n"
                      "        .replace_needed('libbluetooth_audio_session.so', "
                      "'libbluetooth_audio_session_stock.so')", fixups)
        self.assertIn("'vendor/lib64/libbluetooth_audio_session_stock.so': blob_fixup()\n"
                      "        .replace_needed('libbluetooth_audio_session_aidl.so', "
                      "'libbluetooth_audio_session_aidl_stock.so')", fixups)

    def test_audio_tuning_is_stocks_global_set(self):
        # The parser reads the plain folder (no ro.miui.build.region on LineageOS), so it
        # carries every file stock's global folder overrides. Stock's global folder links
        # SmartPa and AudioParamOptions back to the plain files.
        lines = [l for l in (ROOT / "proprietary-files.txt").read_text().splitlines()
                 if "etc/audio_param" in l and not l.startswith("#")]
        global_prefix = "vendor/etc/audio_param_cust/audio_param_global/"
        mapped = {l.split(":")[1].rsplit("/", 1)[1] for l in lines if l.startswith(global_prefix)}
        for l in lines:
            if l.startswith(global_prefix):
                name = l[len(global_prefix):].split(":")[0]
                self.assertEqual(l.split(":")[1], f"vendor/etc/audio_param/{name}")
        self.assertEqual(len(lines), 123)
        self.assertEqual(len(mapped), 62)
        for name in ("PlaybackVolDigi_AudioParam.xml", "PlaybackDRC_AudioParam.xml",
                     "Speech_AudioParam.xml", "Speech_ParamUnitDesc.xml",
                     "Record_AudioParam.xml", "VoIPv2_AudioParam.xml"):
            self.assertIn(name, mapped)
        for name in ("SmartPa_AudioParam.xml", "SmartPa_ParamUnitDesc.xml",
                     "AudioParamOptions_mgvi.xml", "AudioParamOptions_vext.xml"):
            self.assertNotIn(name, mapped)
            self.assertIn(f"vendor/etc/audio_param/{name}", lines)

    def test_manifest_takes_the_bluetooth_stack_with_the_coex_fix(self):
        # LineageOS 507009 fixes the coex window wrap-around that can hold the A2DP
        # offload start; until it is merged in lineage-23.2 the fork carries it.
        root = ET.parse(ROOT / "manifests/malachite.xml").getroot()
        removed = {node.get("path") for node in root.findall("remove-project")}
        bluetooth = {p.get("path"): p for p in root.findall("project")}["packages/modules/Bluetooth"]
        self.assertIn("packages/modules/Bluetooth", removed)
        self.assertEqual(bluetooth.get("name"), "android_packages_modules_Bluetooth")
        self.assertEqual(bluetooth.get("remote"), "malachite-project")
        self.assertEqual(bluetooth.get("revision"), "lineage-23.2")

    def test_offloaded_bluetooth_modules_have_software_a2dp(self):
        # PCM-only A2DP ports catch codecs the DSP does not encode (empty encodedFormats
        # matches any codec in DeviceDescriptorBase::supportsFormat).
        for name in ("bluetooth_offload_audio_policy_configuration.xml",
                     "bluetooth_le_offload_audio_policy_configuration.xml"):
            module = ET.parse(ROOT / "configs/audio" / name).getroot()
            ports = {port.get("tagName"): port for port in module.iter("devicePort")}
            for sink in A2DP_SINKS:
                with self.subTest(file=name, sink=sink):
                    self.assertEqual(ports[sink].get("encodedFormats"), "")
            self.assertIn("BT Hearing Aid Out", ports)

    def test_le_audio_offload_ports_are_stocks(self):
        # Stock's MediaTek LE Audio offload ports and routes
        # (audio_policy_configuration_a2dp_offload_enable_cg_enable.xml), plus
        # immersive_out to the BLE outputs as for A2DP. The full-offload bluetooth module
        # is stock's no-LE module (bluetooth_a2dp_offload_ums_offload_...).
        primary = primary_module(ET.parse(ROOT / "configs/audio/audio_policy_configuration.xml"
                                          ).getroot())
        ports = {port.get("tagName"): port for port in primary.iter("devicePort")
                 if "BLE" in port.get("type")}
        self.assertEqual({tag: (port.get("type"), port.get("role"))
                          for tag, port in ports.items()}, BLE_OFFLOAD_PORTS)
        for tag, port in ports.items():
            mask = "AUDIO_CHANNEL_IN_MONO" if port.get("role") == "source" \
                else "AUDIO_CHANNEL_OUT_MONO"
            with self.subTest(port=tag):
                self.assertEqual([profile.attrib for profile in port.iter("profile")],
                                 [{"name": "", "format": fmt, "samplingRates": "44100 48000",
                                   "channelMasks": mask}
                                  for fmt in ("AUDIO_FORMAT_PCM_32_BIT",
                                              "AUDIO_FORMAT_PCM_16_BIT")])
        routes = {route.get("sink"): route.get("sources").split(",")
                  for route in primary.iter("route")}
        for sink in ("BLE Headset Out", "BLE Speaker Out"):
            self.assertEqual(routes[sink], ["primary output", "deep_buffer", "fast", "voip_rx",
                                            "Voice Call In", "immersive_out"])
        self.assertEqual(routes["BLE Broadcast"], ["primary output", "deep_buffer", "fast"])
        for sink in ("Telephony Tx", "primary input", "voip_tx", "fast input"):
            with self.subTest(sink=sink):
                self.assertEqual(routes[sink][-2:], ["BLE BlueTooth In", "BLE Headset In"])
        for sink in ("mmap_no_irq_in", "hotword_input", "voice tx", "hifi_input"):
            self.assertFalse(set(routes[sink]) & set(BLE_OFFLOAD_PORTS))

    def test_le_audio_software_fallback_uses_stocks_ports(self):
        # With LE offload or A2DP offload disabled, the stack opens LE_AUDIO_SOFTWARE_*
        # sessions; stock's LE Audio ports in the bluetooth module carry them.
        le_devices = {"BT Le Audio Out HS": ("AUDIO_DEVICE_OUT_BLE_HEADSET", "sink"),
                      "BT Le Audio Out SPK": ("AUDIO_DEVICE_OUT_BLE_SPEAKER", "sink"),
                      "BT Le Audio In COMMON": ("AUDIO_DEVICE_IN_BLUETOOTH_BLE", "source"),
                      "BT Le Audio In HS": ("AUDIO_DEVICE_IN_BLE_HEADSET", "source")}
        for name in ("bluetooth_audio_policy_configuration.xml",
                     "bluetooth_offload_audio_policy_configuration.xml"):
            with self.subTest(file=name):
                module = ET.parse(ROOT / "configs/audio" / name).getroot()
                mixes = {port.get("name"): port for port in module.iter("mixPort")}
                self.assertEqual(mixes["le audio output"].get("role"), "source")
                self.assertIsNone(mixes["le audio output"].get("flags"))
                profiles = [profile.attrib for profile in mixes["le audio input"].iter("profile")]
                self.assertEqual(profiles, [{"name": "", "format": "AUDIO_FORMAT_PCM_16_BIT",
                                             "samplingRates": "16000",
                                             "channelMasks": "AUDIO_CHANNEL_IN_MONO"}])
                ports = {port.get("tagName"): (port.get("type"), port.get("role"))
                         for port in module.iter("devicePort") if "BLE" in port.get("type")}
                self.assertEqual(ports, le_devices)
                routes = {route.get("sink"): route.get("sources").split(",")
                          for route in module.iter("route")}
                self.assertEqual(routes["BT Le Audio Out HS"], ["le audio output"])
                self.assertEqual(routes["BT Le Audio Out SPK"], ["le audio output"])
                self.assertEqual(routes["le audio input"],
                                 ["BT Le Audio In COMMON", "BT Le Audio In HS"])
        module = ET.parse(ROOT / "configs/audio/bluetooth_le_offload_audio_policy_configuration.xml"
                          ).getroot()
        self.assertFalse([port for port in module.iter("mixPort")
                          if port.get("name").startswith("le audio")])

    def test_le_audio_unicast_profiles_are_on_with_a_switch(self):
        # Profile names from BluetoothProperties.sysprop. Broadcast stays off; with it
        # off, Settings shows "Disable Bluetooth LE audio" (leaudio_switcher), which
        # the Bluetooth app's Config reads at start. ro.bluetooth.leaudio_switcher.*
        # is default_prop, which vendor_init may not set, so it lives in system.prop.
        props = (ROOT / "vendor.prop").read_text()
        for profile, enabled in (("bap.unicast.client", "true"),
                                 ("csip.set_coordinator", "true"),
                                 ("vcp.controller", "true"),
                                 ("mcp.server", "true"),
                                 ("ccp.server", "true"),
                                 ("hap.client", "true"),
                                 ("bap.broadcast.source", "false"),
                                 ("bap.broadcast.assist", "false")):
            with self.subTest(profile=profile):
                self.assertRegex(
                    props, rf"(?m)^bluetooth\.profile\.{re.escape(profile)}\.enabled={enabled}$")
        for stale in ("bap.unicast.server", "tbs.server", "vc.server"):
            self.assertNotIn(f"bluetooth.profile.{stale}.", props)
        set_props = re.findall(r"(?m)^([^#\s=]+)=", props)
        self.assertFalse([prop for prop in set_props
                          if "leaudio_switcher" in prop or "leaudio.allow_list" in prop])
        self.assertRegex((ROOT / "system.prop").read_text(),
                         r"(?m)^ro\.bluetooth\.leaudio_switcher\.supported=true$")

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
