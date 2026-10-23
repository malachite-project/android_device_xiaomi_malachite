"""Static checks that FPSGO gets libgui's frame events and controls games."""
import json
import os
from pathlib import Path
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
CONTROL = "/sys/kernel/fpsgo/composer/fpsgo_control"


def powerhint():
    return json.loads((ROOT / "configs/powerhint.json").read_text())


class FpsgoTests(unittest.TestCase):
    def test_libgui_flag_is_set(self):
        # frameworks/native sends FPSGO's BufferQueue events only under this flag.
        mk = (ROOT / "device.mk").read_text()
        self.assertIn("$(call soong_config_set_bool,libgui,support_mtk_fpsgo,true)", mk)

    def test_games_alone_are_controlled(self):
        # Without control FPSGO only tracks a queue and GED keeps the panel-rate
        # target. Control is per game on stock (fpsgo_control_pid from the
        # MediaTek power HAL); app RenderThreads stay with ADPF.
        table = powerhint()
        node = {n["Name"]: n for n in table["Nodes"]}["FpsgoControl"]
        self.assertEqual(node["Path"], CONTROL)
        self.assertEqual(node["Values"][node["DefaultIndex"]], "0")
        writers = [a for a in table["Actions"] if a.get("Node") == "FpsgoControl"]
        self.assertEqual([(a["PowerHint"], a["Value"], a["Duration"]) for a in writers],
                         [("GAME", "1", 0)])

    def test_fbt_leaves_thread_uclamp_to_adpf(self):
        # FBT's per-task uclamp writes would overwrite ADPF's on shared threads.
        rc = (ROOT / "init/init.mt6878.power.rc").read_text()
        self.assertIn("write /sys/kernel/fpsgo/common/perfserv_ta 1\n", rc)
        # Its power-HAL commands would pile up unread.
        self.assertIn("write /sys/kernel/fpsgo/fbt/enable_switch_down_throttle 0\n", rc)

    def test_power_hal_may_write_the_control(self):
        policy = (ROOT / "sepolicy/vendor/hal_power_default.te").read_text()
        self.assertIn("rw_dir_file(hal_power_default, sysfs_fpsgo)", policy)

    def test_apps_may_send_the_events(self):
        # MediaTek's common policy grants every app the ioctls libgui sends.
        policy = ROOT.parent / "device_mediatek_sepolicy_vndr" / "base" / "vendor"
        if not policy.is_dir():
            self.skipTest("device_mediatek_sepolicy_vndr is not checked out beside the tree")
        app = (policy / "app.te").read_text()
        for ioctl in ("PERFMGR_FPSGO_QUEUE", "PERFMGR_FPSGO_DEQUEUE",
                      "PERFMGR_FPSGO_QUEUE_CONNECT", "PERFMGR_FPSGO_BQID"):
            with self.subTest(ioctl=ioctl):
                self.assertIn(ioctl, app)


if __name__ == "__main__":
    unittest.main()
