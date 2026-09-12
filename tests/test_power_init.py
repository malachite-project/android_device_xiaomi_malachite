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


def governors(events):
    # Assumes successful writes on existing nodes; other rc files and drivers
    # are intentionally outside this source-level lifecycle model.
    state = {}
    for event in events:
        for words in actions().get(event, []):
            if words[0] == "write" and words[1] in POLICIES:
                state[words[1]] = words[2]
    return state


class PowerInitTests(unittest.TestCase):
    def test_normal_boot_boost_remains(self):
        self.assertEqual(governors(["init"]), dict.fromkeys(POLICIES, "performance"))

    def test_normal_boot_releases_boost(self):
        self.assertEqual(governors(["init", "property:sys.boot_completed=1"]),
                         dict.fromkeys(POLICIES, "schedutil"))

    def test_charger_mode_releases_boost_without_android_boot_completion(self):
        self.assertEqual(governors(["init", "charger"]), dict.fromkeys(POLICIES, "schedutil"))

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
