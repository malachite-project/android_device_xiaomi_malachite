"""Model the cable-start restart trigger and its policy, not the bootloader."""
import os
from pathlib import Path
import re
import shlex
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
TRIGGER = "early-init && property:ro.boot.bootreason=usb && property:ro.bootmode=normal"


def actions():
    result = {}
    trigger = None
    for raw in (ROOT / "init/init.mt6878.rc").read_text().splitlines():
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


class OffModeChargingTests(unittest.TestCase):
    def test_cable_start_restarts_into_kpoc(self):
        self.assertEqual(actions().get(TRIGGER), [["setprop", "sys.powerctl", "reboot,kpoc"]])

    def test_only_the_cable_start_restarts(self):
        # Charger mode, power-key starts and the restart itself must boot on.
        for trigger, commands in actions().items():
            if trigger != TRIGGER:
                self.assertNotIn(["setprop", "sys.powerctl", "reboot,kpoc"], commands, trigger)

    def test_kernel_knows_the_kpoc_reboot_mode(self):
        # Workspace checkout name, then the synced tree's device/xiaomi/malachite-kernel.
        for name in ("device_xiaomi_malachite-kernel", "malachite-kernel"):
            dtb = ROOT.parent / name / "dtb/mt6878.dtb"
            if dtb.exists():
                self.assertIn(b"mode-kpoc", dtb.read_bytes())
                return
        self.skipTest("prebuilt kernel checkout not beside the device tree")

    def test_vendor_init_may_set_powerctl(self):
        policy = (ROOT / "sepolicy/vendor/vendor_init.te").read_text()
        self.assertRegex(policy, re.compile(r"^set_prop\(vendor_init, powerctl_prop\)$", re.M))


if __name__ == "__main__":
    unittest.main()
