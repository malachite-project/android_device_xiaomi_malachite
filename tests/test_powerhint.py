"""Static checks on the libperfmgr hint table, not a model of the power HAL."""
import json
import os
from pathlib import Path
import shlex
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
CEILING = "/proc/sys/kernel/sched_util_clamp_min"


def table():
    return json.loads((ROOT / "configs/powerhint.json").read_text())


def nodes():
    return {n["Name"]: n for n in table()["Nodes"]}


def rc_writes():
    for raw in (ROOT / "init/init.mt6878.power.rc").read_text().splitlines():
        words = shlex.split(raw, comments=True)
        if len(words) == 3 and words[0] == "write":
            yield words[1], words[2]


def ceiling_percent():
    values = [value for path, value in rc_writes() if path == CEILING]
    if len(values) != 1:
        raise AssertionError(f"expected one {CEILING} write, found {values}")
    return int(values[0]) * 100 / 1024


class PowerHintTests(unittest.TestCase):
    def test_every_action_uses_a_declared_value(self):
        declared = nodes()
        for action in table()["Actions"]:
            if "Node" not in action:
                continue
            with self.subTest(hint=action["PowerHint"], node=action["Node"]):
                self.assertIn(action["Node"], declared)
                self.assertIn(action["Value"], declared[action["Node"]]["Values"])

    def test_uclamp_min_values_fit_under_the_system_ceiling(self):
        # The kernel caps every uclamp.min at sched_util_clamp_min, so a larger
        # value is silently cut; bringup/POWER-BOOSTS.md keeps the full profile.
        limit = ceiling_percent()
        requests = [(path, value) for path, value in rc_writes()
                    if path.endswith("/cpu.uclamp.min")]
        for node in nodes().values():
            if node.get("Path", "").endswith("/cpu.uclamp.min"):
                requests += [(node["Name"], value) for value in node["Values"]]
        self.assertTrue(requests)
        for where, value in requests:
            with self.subTest(where=where, value=value):
                self.assertLessEqual(float(value), limit)


if __name__ == "__main__":
    unittest.main()
