"""Model lmkd's swap-low test against this tree's properties, not a running lmkd."""
import os
from pathlib import Path
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
PROP_FILES = ("vendor.prop", "odm.prop", "product.prop", "system.prop")
# system/memory/lmkd/lmkd.cpp DEF_LOW_SWAP and DEF_SWAP_COMP_RATIO.
DEF_LOW_SWAP = 10
DEF_SWAP_COMP_RATIO = 1


def lmk_props():
    props = {}
    for name in PROP_FILES:
        for raw in (ROOT / name).read_text().splitlines():
            line = raw.strip()
            if line.startswith("ro.lmk.") and "=" in line:
                key, value = line.split("=", 1)
                props[key[len("ro.lmk."):]] = value
    return props


def swap_is_low(props, total_swap, free_swap, easy_available):
    # __mp_event_psi(): free swap is min(free_swap, easy_available * ratio),
    # compared with total_swap * swap_free_low_percentage / 100.
    percentage = min(100, max(0, int(props.get("swap_free_low_percentage", DEF_LOW_SWAP))))
    ratio = int(props.get("swap_compression_ratio", DEF_SWAP_COMP_RATIO))
    free = min(free_swap, easy_available * ratio) if ratio else free_swap
    return percentage != 0 and free < total_swap * percentage // 100


class LmkdTests(unittest.TestCase):
    GIB = 1 << 30
    # 8 GB model: zram is 50% of RAM (fstab.zram.50p-1g).
    TOTAL_SWAP = 4 * GIB

    def test_swap_with_room_left_is_not_low(self):
        props = lmk_props()
        # Half of zram used, 1.5 GiB free + inactive file cache.
        self.assertFalse(swap_is_low(props, self.TOTAL_SWAP, 2 * self.GIB, 3 * self.GIB // 2))
        # Unused zram while page cache is moderate.
        self.assertFalse(swap_is_low(props, self.TOTAL_SWAP, self.TOTAL_SWAP, self.GIB))

    def test_nearly_full_swap_is_still_low(self):
        self.assertTrue(swap_is_low(lmk_props(), self.TOTAL_SWAP, self.GIB // 4, self.GIB))

    def test_pixel_lmk_tuning_kept(self):
        # hardware/google/pixel/mm/device_gki.mk, the origin of these values.
        props = lmk_props()
        self.assertEqual(props.get("filecache_min_kb"), "153600")
        self.assertEqual(props.get("kill_timeout_ms"), "50")
        self.assertEqual(props.get("stall_limit_critical"), "40")


if __name__ == "__main__":
    unittest.main()
