"""Static checks for the userdebug diagnostics block in device.mk."""
import os
from pathlib import Path
import re
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))


def diagnostics_block() -> str:
    mk = (ROOT / "device.mk").read_text()
    match = re.search(r"^# Diagnostics.*?^endif\nendif\n", mk, re.M | re.S)
    if match is None:
        raise AssertionError("device.mk has no diagnostics block")
    return match.group(0)


class DiagnosticsTests(unittest.TestCase):
    def test_never_in_user_builds_and_can_be_switched_off(self):
        block = diagnostics_block()
        self.assertIn("ifneq ($(TARGET_BUILD_VARIANT),user)", block)
        self.assertIn("ifneq ($(MALACHITE_DIAGNOSTICS),false)", block)

    def test_persists_all_buffers_including_the_kernel(self):
        block = diagnostics_block()
        for prop in (
            "persist.logd.logpersistd=logcatd",
            "persist.logd.logpersistd.buffer=all",
            "ro.logd.kernel=true",
        ):
            self.assertIn(prop, block)

    def test_bounded_on_disk(self):
        block = diagnostics_block()
        size = int(re.search(r"persist\.logd\.logpersistd\.size=(\d+)", block).group(1))
        rotate = int(re.search(r"persist\.logd\.logpersistd\.rotate_kbytes=(\d+)", block).group(1))
        self.assertLessEqual(size * rotate, 256 * 1024)


if __name__ == "__main__":
    unittest.main()
