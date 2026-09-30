"""Model the off-mode charging flag write, not the bootloader."""
import os
from pathlib import Path
import shlex
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
NODE = "/sys/class/power_supply/battery/charger_partition_poweroffmode"
# ShutdownThread sets sys.shutdown.requested to "0" (power-off) or "1" (reboot) plus the
# reason; PowerManager's power-off reasons are userrequested, battery, thermal,
# thermal,battery and service.
POWER_OFF_TRIGGERS = {"property:sys.shutdown.requested=0" + reason for reason in
                      ("", "userrequested", "battery", "thermal", "thermal,battery", "service")}


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
    def test_flag_is_set_on_every_power_off(self):
        for trigger in POWER_OFF_TRIGGERS:
            with self.subTest(trigger=trigger):
                self.assertIn(["write", NODE, "1"], actions().get(trigger, []))

    def test_flag_is_written_nowhere_else(self):
        # Not at boot: the charger partition is not ready until ~58 s after the kernel
        # starts, so vendor.all.modules.ready=1 only produced "charger partition not rdy".
        # Not on reboots, so a restart with a cable keeps booting Android.
        for trigger, commands in actions().items():
            if trigger not in POWER_OFF_TRIGGERS:
                self.assertFalse([c for c in commands if NODE in c], trigger)

    def test_no_reboot_into_kpoc(self):
        # The bootloader ignores reboot,kpoc (reverted 0646150).
        self.assertNotIn("reboot,kpoc", (ROOT / "init/init.mt6878.rc").read_text())


if __name__ == "__main__":
    unittest.main()
