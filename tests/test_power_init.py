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
