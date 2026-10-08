"""Model this rc file's governor writes, not physical power or full Android init."""
import os
from pathlib import Path
import shlex
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
POLICIES = tuple(f"/sys/devices/system/cpu/cpufreq/policy{p}/scaling_governor" for p in (0, 4))


def actions():
    result = {}
    trigger = None
    for raw in (ROOT / "init/init.mt6878.power.rc").read_text().splitlines():
        words = shlex.split(raw, comments=True)
        if not words:
            continue
        if not raw[0].isspace():
            trigger = " ".join(words[1:]) if words[0] == "on" else None
            if trigger is not None:
                result.setdefault(trigger, [])
        elif trigger is not None:
            result[trigger].append(words)
    return result


UFS_CLKGATE = "/sys/devices/platform/soc/112b0000.ufshci/clkgate_enable"
CPUQOS = "/sys/devices/system/cpu/cpuqos/cpuqos_boot_complete"
PELT = "/proc/sys/kernel/sched_pelt_multiplier"
C2PS = "/sys/module/mtk_c2ps/parameters/"
# Stock odm/etc/camera/xiaomi/MiCamCPUControl.xml, DefaultCPUPolicy_30FPS,
# mapped to module parameters by stock vendor/etc/powercontable.xml.
STOCK_C2PS_VIDEO = {
    "c2ps_regulator_process_mode": "1",          # C2PS_UCLAMP_POLICY_MODE
    "c2ps_uclamp_up_margin": "10",               # ..._SIMPLE_POLICY_UP_MARGIN
    "c2ps_uclamp_down_margin": "10",             # ..._SIMPLE_POLICY_DOWN_MARGIN
    "c2ps_regulator_base_update_uclamp": "20",   # ..._SIMPLE_POLICY_BASE_UPDATE_UCLAMP
    "proc_time_window_size": "33",               # C2PS_PROC_TIME_WINDOW_SIZE
    "background_monitor_duration": "33",         # ..._BG_UCLAMP_POLICY_MONITOR_DURATION
    "background_idlerate_alert": "15",           # ..._BG_UCLAMP_POLICY_IDLERATE_ALERT
    "c2ps_uclamp_bg_up_margin_cluster0": "1000", # ..._BG_UCLAMP_POLICY_UP_MARGIN_CLUSTER_0
    "c2ps_uclamp_bg_up_margin_cluster1": "1000", # ..._BG_UCLAMP_POLICY_UP_MARGIN_CLUSTER_1
    "c2ps_regulator_bg_update_uclamp": "20",     # ..._BG_UCLAMP_POLICY_BASE_UPDATE_UCLAMP
}


def writes(events, paths):
    # Assumes successful writes on existing nodes; other rc files and drivers
    # are intentionally outside this source-level lifecycle model.
    state = {}
    for event in events:
        for words in actions().get(event, []):
            if words[0] == "write" and words[1] in paths:
                state[words[1]] = words[2]
    return state


def governors(events):
    return writes(events, POLICIES)


class PowerInitTests(unittest.TestCase):
    def test_normal_boot_boost_remains(self):
        self.assertEqual(governors(["init"]), dict.fromkeys(POLICIES, "performance"))

    def test_normal_boot_releases_boost(self):
        self.assertEqual(governors(["init", "property:sys.boot_completed=1"]),
                         dict.fromkeys(POLICIES, "sugov_ext"))

    def test_charger_mode_releases_boost_without_android_boot_completion(self):
        self.assertEqual(governors(["init", "charger"]), dict.fromkeys(POLICIES, "sugov_ext"))

    def test_schedutil_is_written_before_sugov_ext(self):
        # A failed sugov_ext write must not leave the performance boot boost.
        for event in ("property:sys.boot_completed=1", "charger"):
            for policy in POLICIES:
                with self.subTest(event=event, policy=policy):
                    values = [w[2] for w in actions()[event]
                              if w[0] == "write" and w[1] == policy]
                    self.assertEqual(values, ["schedutil", "sugov_ext"])

    def test_pelt_multiplier_is_stock(self):
        # Stock vendor/etc/init/hw/init.cgroup.rc: on post-fs-data, 4.
        self.assertEqual(writes(["early-init", "init"], {PELT}), {})
        self.assertEqual(writes(["post-fs-data"], {PELT}), {PELT: "4"})
        self.assertEqual(writes(["early-init", "init", "post-fs-data",
                                 "property:sys.boot_completed=1"], {PELT}), {PELT: "4"})

    def test_c2ps_video_policy_is_stock_after_boot(self):
        paths = {C2PS + name for name in STOCK_C2PS_VIDEO}
        self.assertEqual(writes(["early-init", "init", "post-fs-data"], paths), {})
        self.assertEqual(writes(["property:sys.boot_completed=1"], paths),
                         {C2PS + k: v for k, v in STOCK_C2PS_VIDEO.items()})
        self.assertEqual(writes(["charger"], paths), {})

    def test_c2ps_values_match_stock_xml_when_available(self):
        xml = os.environ.get("MALACHITE_STOCK_MICAMCPUCONTROL")
        if not xml:
            self.skipTest("set MALACHITE_STOCK_MICAMCPUCONTROL to stock MiCamCPUControl.xml")
        import xml.etree.ElementTree as ET
        mode = next(m for m in ET.parse(xml).getroot()
                    if m.get("ID") == "DefaultCPUPolicy_30FPS")
        stock = {c.tag: c.text for c in mode}
        names = {
            "c2ps_regulator_process_mode": "PERF_RES_C2PS_UCLAMP_POLICY_MODE",
            "c2ps_uclamp_up_margin": "PERF_RES_C2PS_UCLAMP_SIMPLE_POLICY_UP_MARGIN",
            "c2ps_uclamp_down_margin": "PERF_RES_C2PS_UCLAMP_SIMPLE_POLICY_DOWN_MARGIN",
            "c2ps_regulator_base_update_uclamp":
                "PERF_RES_C2PS_UCLAMP_SIMPLE_POLICY_BASE_UPDATE_UCLAMP",
            "proc_time_window_size": "PERF_RES_C2PS_PROC_TIME_WINDOW_SIZE",
            "background_monitor_duration": "PERF_RES_C2PS_BG_UCLAMP_POLICY_MONITOR_DURATION",
            "background_idlerate_alert": "PERF_RES_C2PS_BG_UCLAMP_POLICY_IDLERATE_ALERT",
            "c2ps_uclamp_bg_up_margin_cluster0":
                "PERF_RES_C2PS_BG_UCLAMP_POLICY_UP_MARGIN_CLUSTER_0",
            "c2ps_uclamp_bg_up_margin_cluster1":
                "PERF_RES_C2PS_BG_UCLAMP_POLICY_UP_MARGIN_CLUSTER_1",
            "c2ps_regulator_bg_update_uclamp":
                "PERF_RES_C2PS_BG_UCLAMP_POLICY_BASE_UPDATE_UCLAMP",
        }
        for param, tag in names.items():
            with self.subTest(param=param):
                self.assertEqual(STOCK_C2PS_VIDEO[param], stock[tag])

    def test_cpuqos_starts_after_boot_completes(self):
        self.assertEqual(writes(["init"], {CPUQOS}), {})
        self.assertEqual(writes(["init", "property:sys.boot_completed=1"], {CPUQOS}),
                         {CPUQOS: "1"})

    def test_ufs_clock_gating_is_disabled_only_during_boot(self):
        self.assertEqual(writes(["init"], {UFS_CLKGATE}), {UFS_CLKGATE: "0"})
        self.assertEqual(writes(["init", "property:sys.boot_completed=1"], {UFS_CLKGATE}),
                         {UFS_CLKGATE: "1"})
        self.assertEqual(writes(["init", "charger"], {UFS_CLKGATE}), {UFS_CLKGATE: "1"})

    def test_top_app_uclamp_min_targets_top_app(self):
        top_app = [w for w in actions()["init"]
                   if w[0] == "write" and w[1].startswith("/dev/cpuctl/")]
        paths = [w[1] for w in top_app]
        self.assertIn("/dev/cpuctl/top-app/cpu.uclamp.min", paths)
        self.assertEqual(paths.count("/dev/cpuctl/foreground/cpu.uclamp.min"), 1)

    def test_charger_retains_authentication_without_enabling_powerhal(self):
        commands = actions()["charger"]
        self.assertIn(["start", "batterysecret"], commands)
        self.assertNotIn(["setprop", "vendor.powerhal.init", "1"], commands)
        self.assertFalse(any(c[0] in ("stop", "restart") for c in commands))
        paths = {
            "/sys/class/Charging_Adapter/pd_adapter/usbpd_verifed",
            "/sys/class/Charging_Adapter/pd_adapter/request_vdm_cmd",
            "/sys/class/Charging_Adapter/pd_adapter/verify_process",
            "/sys/class/power_supply/usb/pd_authentication",
        }
        self.assertEqual({c[2] for c in commands if c[0] == "chmod" and c[1] == "0664"}, paths)


if __name__ == "__main__":
    unittest.main()
