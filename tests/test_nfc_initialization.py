"""Boot-order contracts for NFC storage; these do not certify CIE transactions."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def actions(path):
    trigger = None
    result = {}
    for line in path.read_text().splitlines():
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        if not line[0].isspace():
            trigger = " ".join(words[1:]) if words[0] == "on" else None
        elif trigger is not None:
            result.setdefault(trigger, []).append(words)
    return result


class NfcInitializationTests(unittest.TestCase):
    def test_storage_exists_before_boot_starts_enabled_hal_services(self):
        nfc_actions = actions(ROOT / "init/init.nfc.malachite.rc")
        early_mkdirs = {
            command[1]: command[2:]
            for command in nfc_actions.get("post-fs-data", [])
            if command[0] == "mkdir"
        }
        expected = {
            "/data/vendor/nfc_socket": ["0770", "nfc", "nfc"],
            "/data/vendor/nfc": ["0777", "nfc", "nfc"],
            "/data/vendor/nfc/param": ["0777", "nfc", "nfc"],
            "/data/vendor/secure_element": ["0777", "secure_element", "secure_element"],
        }
        for directory, attributes in expected.items():
            with self.subTest(directory=directory):
                self.assertEqual(early_mkdirs.get(directory), attributes)
        self.assertFalse(any(
            command[0] == "mkdir" and command[1] in expected
            for command in nfc_actions.get("boot", [])
        ))

    def test_device_services_do_not_change_the_shared_vendor_data_root(self):
        offenders = []
        for path in sorted((ROOT / "init").glob("*.rc")):
            for commands in actions(path).values():
                for command in commands:
                    if command[0] in {"mkdir", "chmod", "chown"} and "/data/vendor" in command[1:]:
                        offenders.append((str(path.relative_to(ROOT)), command))
        self.assertEqual(offenders, [])

    def test_waiting_for_hardware_does_not_delay_post_fs_data(self):
        nfc_actions = actions(ROOT / "init/init.nfc.malachite.rc")
        self.assertFalse(any(
            command[0] == "wait"
            for command in nfc_actions.get("post-fs-data", [])
        ))
        self.assertIn(["wait", "/sys/nfc/chip_name"], nfc_actions["nfc-nodes"])
        self.assertIn(["wait", "/dev/tms_ese", "1"], nfc_actions["nfc-nodes"])

    def test_only_nfc_skus_wait_for_nfc_nodes(self):
        nfc_actions = actions(ROOT / "init/init.nfc.malachite.rc")
        waiting = sorted(
            trigger for trigger, commands in nfc_actions.items()
            if ["trigger", "nfc-nodes"] in commands
        )
        self.assertEqual(waiting, [
            "boot && property:ro.boot.hwc=CN",
            "boot && property:ro.boot.hwc=Global",
        ])
        self.assertFalse(any(command[0] == "wait" for command in nfc_actions.get("boot", [])))


if __name__ == "__main__":
    unittest.main()
