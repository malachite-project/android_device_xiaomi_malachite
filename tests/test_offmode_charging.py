"""Model the off-mode charging flag write, not the bootloader."""
import os
from pathlib import Path
import shlex
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
NODE = "/sys/class/power_supply/battery/charger_partition_poweroffmode"
TRIGGER = "property:vendor.all.modules.ready=1"


def actions_of(name):
    result = {}
    trigger = None
    for raw in (ROOT / name).read_text().splitlines():
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


def actions():
    return actions_of("init/init.mt6878.rc")


class OffModeChargingTests(unittest.TestCase):
    def test_flag_is_set_after_modules_load(self):
        self.assertIn(["write", NODE, "1"], actions().get(TRIGGER, []))

    def test_flag_is_written_nowhere_else(self):
        for trigger, commands in actions().items():
            if trigger != TRIGGER:
                self.assertFalse([c for c in commands if NODE in c], trigger)

    def test_modules_ready_is_set_in_every_mode(self):
        # insmod_sh starts at early-init, which runs in charger mode too.
        self.assertEqual(actions_of("modules/init.insmod.rc").get("early-init", [])[:2],
                         [["setprop", "vendor.all.modules.ready", "0"], ["start", "insmod_sh"]])
        cfg = (ROOT / "modules/init.insmod.mt6878.cfg").read_text()
        self.assertIn("setprop|vendor.all.modules.ready", cfg)

    def test_no_reboot_into_kpoc(self):
        # The bootloader ignores reboot,kpoc (reverted 0646150).
        self.assertNotIn("reboot,kpoc", (ROOT / "init/init.mt6878.rc").read_text())


if __name__ == "__main__":
    unittest.main()
