"""Static checks on the libperfmgr hint table, not a model of the power HAL."""
import json
import os
from pathlib import Path
import shlex
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
CEILING = "/proc/sys/kernel/sched_util_clamp_min"
MIN_FREQ_NODES = ("CPULittleClusterMinFreq", "CPUBigClusterMinFreq")


def table():
    return json.loads((ROOT / "configs/powerhint.json").read_text())


def nodes():
    return {n["Name"]: n for n in table()["Nodes"]}


def actions(hint):
    return [a for a in table()["Actions"] if a["PowerHint"] == hint and "Node" in a]


def rc_writes():
    for raw in (ROOT / "init/init.mt6878.power.rc").read_text().splitlines():
        words = shlex.split(raw, comments=True)
        if len(words) == 3 and words[0] == "write":
            yield words[1], words[2]


def ceiling():
    values = [value for path, value in rc_writes() if path == CEILING]
    if len(values) != 1:
        raise AssertionError(f"expected one {CEILING} write, found {values}")
    return int(values[0])


# Group and power-hint boosts keep the value they had under the old 128/1024
# system cap; bringup/POWER-BOOSTS.md keeps the larger profile.
GROUP_BOOST_LIMIT = 12.5

# Required AdpfConfig entries and their jsoncpp type checks, from
# HintManager::ParseAdpfConfigs (hardware/google/pixel lineage-23.2). A
# missing or mistyped entry drops every ADPF profile, silently disabling ADPF.
ADPF_REQUIRED = {
    "PID_On": bool, "PID_Po": float, "PID_Pu": float, "PID_I": float,
    "PID_I_Init": int, "PID_I_High": int, "PID_I_Low": int,
    "PID_Do": float, "PID_Du": float, "UclampMin_On": bool,
    "UclampMin_Init": int, "UclampMin_High": int, "UclampMin_Low": int,
    "SamplingWindow_P": int, "SamplingWindow_I": int, "SamplingWindow_D": int,
    "StaleTimeFactor": float, "ReportingRateLimitNs": int, "TargetTimeFactor": float,
}
ADPF_UNSIGNED = {"UclampMin_Init", "UclampMin_High", "UclampMin_Low", "SamplingWindow_P",
                 "SamplingWindow_I", "SamplingWindow_D", "ReportingRateLimitNs"}


class PowerHintTests(unittest.TestCase):
    def test_every_action_uses_a_declared_value(self):
        declared = nodes()
        for action in table()["Actions"]:
            if "Node" not in action:
                continue
            with self.subTest(hint=action["PowerHint"], node=action["Node"]):
                self.assertIn(action["Node"], declared)
                self.assertIn(action["Value"], declared[action["Node"]]["Values"])

    def test_system_ceiling_does_not_cap_adpf(self):
        # The kernel caps every uclamp.min at sched_util_clamp_min, including
        # the per-thread values ADPF sets.
        self.assertEqual(ceiling(), 1024)
        for profile in table()["AdpfConfig"]:
            with self.subTest(profile=profile["Name"]):
                self.assertLessEqual(profile["UclampMin_High"], ceiling())

    def test_group_boosts_keep_their_effective_values(self):
        limit = GROUP_BOOST_LIMIT
        requests = [(path, value) for path, value in rc_writes()
                    if path.endswith("/cpu.uclamp.min")]
        for node in nodes().values():
            if node.get("Path", "").endswith("/cpu.uclamp.min"):
                requests += [(node["Name"], value) for value in node["Values"]]
        self.assertTrue(requests)
        for where, value in requests:
            with self.subTest(where=where, value=value):
                self.assertLessEqual(float(value), limit)

    def test_game_mode_does_not_pin_cpus_at_maximum(self):
        # GameManagerService holds GAME for as long as any game is in front,
        # so a Duration 0 floor here lasts the whole session.
        declared = nodes()
        game = {a["Node"]: a for a in actions("GAME")}
        for name in MIN_FREQ_NODES:
            with self.subTest(node=name):
                self.assertIn(name, game)
                self.assertNotEqual(game[name]["Value"], declared[name]["Values"][0])

    def test_memory_is_boosted_only_while_a_game_loads(self):
        self.assertNotIn("MemFreq", {a["Node"] for a in actions("GAME")})
        self.assertIn("MemFreq", {a["Node"] for a in actions("GAME_LOADING")})

    def test_adpf_profiles_parse(self):
        profiles = table().get("AdpfConfig", [])
        self.assertTrue(profiles)
        self.assertEqual(len({p["Name"] for p in profiles}), len(profiles))
        for profile in profiles:
            for key, kind in ADPF_REQUIRED.items():
                with self.subTest(profile=profile.get("Name"), key=key):
                    self.assertIn(key, profile)
                    value = profile[key]
                    if kind is bool:
                        self.assertIsInstance(value, bool)
                    elif kind is float:
                        self.assertIsInstance(value, (int, float))
                        self.assertNotIsInstance(value, bool)
                    else:
                        self.assertIsInstance(value, int)
                        self.assertNotIsInstance(value, bool)
                        if key in ADPF_UNSIGNED:
                            self.assertGreaterEqual(value, 0)
            with self.subTest(profile=profile["Name"], check="heuristic boost"):
                # HeuristicBoost_On needs a further nine entries; leave it out.
                self.assertNotIn("HeuristicBoost_On", profile)
            with self.subTest(profile=profile["Name"], check="efficiency pair"):
                self.assertEqual("UclampMax_EfficientBase" in profile,
                                 "UclampMax_EfficientOffset" in profile)
            with self.subTest(profile=profile["Name"], check="ordering"):
                self.assertLessEqual(profile["UclampMin_Low"], profile["UclampMin_Init"])
                self.assertLessEqual(profile["UclampMin_Init"], profile["UclampMin_High"])


if __name__ == "__main__":
    unittest.main()
