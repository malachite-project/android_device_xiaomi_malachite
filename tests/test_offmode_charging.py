"""Model the off-mode charging flag writes, not the bootloader."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
NODE = "/sys/class/power_supply/battery/charger_partition_poweroffmode"
# ShutdownThread sets sys.shutdown.requested to "0" (power-off) or "1" (reboot) plus the
# reason; PowerManager's power-off reasons are userrequested, battery, thermal,
# thermal,battery and service.
POWER_OFF_TRIGGERS = {"property:sys.shutdown.requested=0" + reason for reason in
                      ("", "userrequested", "battery", "thermal", "thermal,battery", "service")}
SCRIPT = "init/offmode_charge.sh"
SERVICE = "vendor.offmode_charge"


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


def services_of(name):
    result = {}
    current = None
    for raw in (ROOT / name).read_text().splitlines():
        words = shlex.split(raw, comments=True)
        if not words:
            continue
        if not raw[0].isspace():
            current = words[1] if words[0] == "service" else None
            if current is not None:
                result[current] = {"command": words[2:], "options": []}
        elif current is not None:
            result[current]["options"].append(words)
    return result


# Stands in for the kernel: called by the fake sleep with the node and the sleep count.
KERNEL_READY_AT_SIXTH_SLEEP = """
import sys
from pathlib import Path
node, n = Path(sys.argv[1]), int(sys.argv[2])
reset = node.with_name("reset")
value = node.read_text().strip()
if n == 6 and value == "0":
    node.write_text("2")        # partition ready; the bootloader left 2
elif value == "1" and not reset.exists():
    reset.write_text("done")    # the kernel's own reset lands after the first write
    node.write_text("2")
"""


def run_script(kernel):
    """Run the script with the node and /vendor/bin/sleep replaced by fakes.

    Returns (exit status, final node value, number of sleeps).
    """
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        node = work / "node"
        node.write_text("0")      # what the driver prints before the partition is ready
        count = work / "count"
        count.write_text("0")
        hook = work / "kernel.py"
        hook.write_text(kernel)
        sleep = work / "sleep"
        sleep.write_text(
            "#!/bin/sh\n"
            f'n=$(cat "{count.as_posix()}"); n=$((n + 1)); echo "$n" > "{count.as_posix()}"\n'
            f'"{Path(sys.executable).as_posix()}" "{hook.as_posix()}" "{node.as_posix()}" "$n"\n')
        sleep.chmod(0o755)
        text = (ROOT / SCRIPT).read_text()
        text = text.replace(NODE, node.as_posix()).replace("/vendor/bin/sleep", sleep.as_posix())
        script = work / "script.sh"
        script.write_text(text)
        run = subprocess.run([shutil.which("sh"), script.as_posix()], capture_output=True,
                             text=True, timeout=300)
        return run.returncode, node.read_text().strip(), int(count.read_text())


class OffModeChargingTests(unittest.TestCase):
    def test_flag_is_set_on_every_power_off(self):
        for trigger in POWER_OFF_TRIGGERS:
            with self.subTest(trigger=trigger):
                self.assertIn(["write", NODE, "1"], actions().get(trigger, []))

    def test_flag_is_written_nowhere_else(self):
        # Not at boot: the charger partition is not ready until ~58 s after the kernel
        # starts, so vendor.all.modules.ready=1 only produced "charger partition not rdy".
        # Not on reboots, so a restart with a cable keeps booting Android. The charging
        # screen re-arms it through the script (below).
        for trigger, commands in actions().items():
            if trigger not in POWER_OFF_TRIGGERS:
                self.assertFalse([c for c in commands if NODE in c], trigger)

    def test_charging_screen_rearms_through_the_script_only(self):
        # Only the charging screen (on charger) starts it; a normal boot must not arm the
        # flag, or a crash reset while plugged in would land on the charging screen.
        starters = [trigger for trigger, commands in actions().items()
                    if ["start", SERVICE] in commands]
        self.assertEqual(starters, ["charger"])
        service = services_of("init/init.mt6878.rc")[SERVICE]
        self.assertEqual(service["command"], ["/vendor/bin/offmode_charge.sh"])
        self.assertIn(["oneshot"], service["options"])
        self.assertIn(["disabled"], service["options"])
        self.assertIn(NODE, (ROOT / SCRIPT).read_text())

    def test_script_is_packaged_and_labelled(self):
        self.assertIn('name: "offmode_charge.sh"', (ROOT / "init/Android.bp").read_text())
        packages = (ROOT / "device.mk").read_text().split()
        self.assertIn("offmode_charge.sh", packages)
        contexts = (ROOT / "sepolicy/vendor/file_contexts").read_text()
        self.assertIn(r"/bin/offmode_charge\.sh u:object_r:vendor_offmode_charge_exec:s0",
                      contexts)
        policy = (ROOT / "sepolicy/vendor/vendor_offmode_charge.te").read_text()
        self.assertIn("init_daemon_domain(vendor_offmode_charge)", policy)
        self.assertIn("allow vendor_offmode_charge vendor_toolbox_exec:file rx_file_perms;",
                      policy)
        self.assertIn("allow vendor_offmode_charge sysfs_batteryinfo:file w_file_perms;", policy)

    def test_script_runs_no_system_binaries(self):
        # init's PATH starts with /system/bin, which a vendor domain may not execute:
        # only shell builtins and the vendor toybox.
        text = (ROOT / SCRIPT).read_text()
        self.assertTrue(text.startswith("#!/vendor/bin/sh\n"))
        builtins = {"while", "if", "fi", "done", "read", "echo", "exit", "[", "then", "do"}
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            first = shlex.split(line)[0]
            if "=" in first or first in builtins:
                continue
            self.assertEqual(first, "/vendor/bin/sleep", line)

    @unittest.skipUnless(shutil.which("sh"), "needs sh")
    def test_script_waits_for_the_kernel_reset_then_arms(self):
        status, value, sleeps = run_script(KERNEL_READY_AT_SIXTH_SLEEP)
        self.assertEqual((status, value), (0, "1"))
        # 1 initial, 5 polls until ready, 2 + 5 for the write the kernel resets, 1 poll,
        # 2 + 5 for the write that stays.
        self.assertEqual(sleeps, 11)

    @unittest.skipUnless(shutil.which("sh"), "needs sh")
    def test_script_gives_up_when_the_partition_never_appears(self):
        status, value, sleeps = run_script("")
        self.assertEqual((status, value), (1, "0"))
        self.assertEqual(sleeps, 61)

    def test_no_reboot_into_kpoc(self):
        # The bootloader ignores reboot,kpoc (reverted 0646150).
        self.assertNotIn("reboot,kpoc", (ROOT / "init/init.mt6878.rc").read_text())


if __name__ == "__main__":
    unittest.main()
