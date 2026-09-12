"""Execute the production loader with fake commands; never load a host module."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get("MALACHITE_DEVICE_ROOT", Path(__file__).resolve().parents[1]))
SHELL = os.environ.get("MALACHITE_TEST_SHELL", "/bin/sh")

# Only these command stubs are on PATH. The loader's absolute module-list reads
# are mapped to fixtures; enable actions only target this test's temporary tree.
STUB = r'''#!/bin/sh
root=$LOADER_FIXTURE
name=${0##*/}
{
    printf '%s' "$name"
    for arg do printf '\t%s' "$arg"; done
    printf '\n'
} >> "$root/calls.tsv"
case "$name" in
    cat) exec "$REAL_CAT" "$root$1" ;;
    modprobe)
        for arg do
            if [ -n "$FAIL_PARTITION" ] && [ "$arg" = "$FAIL_PARTITION" ]; then
                exit 1
            fi
        done ;;
    insmod) [ -z "$FAIL_INSMOD" ] || exit 1 ;;
    setprop)
        count=0
        if [ -f "$root/property_attempts" ]; then
            read -r count < "$root/property_attempts"
        fi
        count=$((count + 1))
        printf '%s\n' "$count" > "$root/property_attempts"
        [ "$count" -gt "${FAIL_PROPERTY_ATTEMPTS:-0}" ] || exit 1 ;;
    *) exit 99 ;;
esac
exit 0
'''


class ModuleLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="malachite-loader-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.bin = self.work / "bin"
        self.bin.mkdir()
        for name in ("cat", "modprobe", "insmod", "setprop"):
            stub = self.bin / name
            stub.write_text(STUB)
            stub.chmod(0o755)
        for partition, modules in (("system_dlkm", "system.ko\nshared.ko\n"),
                                   ("vendor", "kernelsu.ko\nvendor.ko\n")):
            directory = self.work / partition / "lib/modules"
            directory.mkdir(parents=True)
            (directory / "modules.load").write_text(modules)
        self.environment = {
            "PATH": str(self.bin), "LOADER_FIXTURE": str(self.work),
            "LC_ALL": "C", "HOME": str(self.work), "REAL_CAT": shutil.which("cat"),
        }

    def run_loader(self, config=None, *, extra_env=None, filename="loader.cfg", args=None):
        path = self.work / filename
        if config is not None:
            path.write_text(config)
        environment = self.environment | (extra_env or {})
        result = subprocess.run(
            [SHELL, str(ROOT / "modules/init.insmod.sh")]
            + ([str(path)] if args is None else args),
            cwd=self.work, env=environment, text=True, capture_output=True, timeout=15,
        )
        log = self.work / "calls.tsv"
        calls = [line.split("\t") for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    def test_success_preserves_partition_and_module_order(self):
        result, calls = self.run_loader((ROOT / "modules/init.insmod.mt6878.cfg").read_text())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call for call in calls if call[0] == "modprobe"], [
            ["modprobe", "-a", "-d", "/system_dlkm/lib/modules", "system.ko", "shared.ko"],
            ["modprobe", "-a", "-d", "/vendor/lib/modules", "kernelsu.ko", "vendor.ko"],
        ])
        self.assertEqual(calls[-1], ["setprop", "vendor.all.modules.ready", "1"])

    def test_failed_partition_is_not_hidden_by_successful_handoff(self):
        for partition in ("system_dlkm", "vendor"):
            with self.subTest(partition=partition):
                log = self.work / "calls.tsv"
                log.unlink(missing_ok=True)
                result, calls = self.run_loader(
                    "modprobe|*\nsetprop|vendor.all.modules.ready\n",
                    extra_env={"FAIL_PARTITION": f"/{partition}/lib/modules"},
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len([c for c in calls if c[0] == "modprobe"]), 2)
                # Retain the existing completion handoff: withholding it would
                # deadlock init's post-fs-data wait. Exit status reports failure.
                self.assertEqual(calls[-1], ["setprop", "vendor.all.modules.ready", "1"])
                self.assertIn(partition, result.stderr)

    def test_missing_list_fails_but_attempts_other_partition(self):
        (self.work / "system_dlkm/lib/modules/modules.load").unlink()
        result, calls = self.run_loader("modprobe|*\nsetprop|vendor.all.modules.ready\n")
        self.assertNotEqual(result.returncode, 0)
        loads = [c for c in calls if c[0] == "modprobe"]
        self.assertEqual(len(loads), 1)
        self.assertIn("/vendor/lib/modules", loads[0])
        self.assertEqual(calls[-1][0], "setprop")

    def test_blocklist_flag_is_preserved(self):
        for spelling in ("-b", "-b *"):
            with self.subTest(spelling=spelling):
                (self.work / "calls.tsv").unlink(missing_ok=True)
                result, calls = self.run_loader(f"modprobe|{spelling}\n")
                self.assertEqual(result.returncode, 0, result.stderr)
                loads = [c for c in calls if c[0] == "modprobe"]
                self.assertEqual(len(loads), 2)
                self.assertTrue(all(c[4] == "-b" for c in loads))
                self.assertEqual(loads[1][5:], ["kernelsu.ko", "vendor.ko"])

    def test_explicit_module_arguments_are_preserved(self):
        result, calls = self.run_loader("modprobe|wifi.ko debug=0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c[4:] for c in calls if c[0] == "modprobe"],
                         [["wifi.ko", "debug=0"], ["wifi.ko", "debug=0"]])

    def test_module_arguments_do_not_expand_host_filenames(self):
        (self.work / "unrelated.ko").touch()
        result, calls = self.run_loader("modprobe|*.ko\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c[4:] for c in calls if c[0] == "modprobe"], [["*.ko"], ["*.ko"]])

    def test_final_config_line_without_newline_is_executed(self):
        result, calls = self.run_loader("setprop|vendor.all.modules.ready")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [["setprop", "vendor.all.modules.ready", "1"]])

    def test_configuration_path_with_spaces(self):
        result, calls = self.run_loader("setprop|vendor.all.modules.ready\n", filename="with spaces.cfg")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 1)

    def test_insmod_failure_survives_later_success(self):
        result, calls = self.run_loader("insmod|driver.ko param=1\nsetprop|vendor.all.modules.ready\n",
                                        extra_env={"FAIL_INSMOD": "1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls[0], ["insmod", "driver.ko", "param=1"])
        self.assertEqual(calls[-1][0], "setprop")

    def test_enable_failure_survives_later_success(self):
        result, calls = self.run_loader(f"enable|{self.work}/missing/node\nsetprop|vendor.all.modules.ready\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls[-1][0], "setprop")

    def test_enable_supports_one_path_with_spaces(self):
        node = self.work / "fake node"
        result, _ = self.run_loader(f"enable|{node}\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(node.read_text(), "1\n")

    def test_property_retry_recovers(self):
        result, calls = self.run_loader("setprop|vendor.all.modules.ready\n",
                                        extra_env={"FAIL_PROPERTY_ATTEMPTS": "2"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 3)

    def test_property_retry_is_bounded_and_failure_is_retained(self):
        result, calls = self.run_loader("setprop|vendor.all.modules.ready\ninsmod|driver.ko\n",
                                        extra_env={"FAIL_PROPERTY_ATTEMPTS": "1000"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len([c for c in calls if c[0] == "setprop"]), 128)
        self.assertEqual(calls[-1], ["insmod", "driver.ko"])

    def test_unknown_action_is_not_silently_accepted(self):
        result, calls = self.run_loader("modporbe|*\nsetprop|vendor.all.modules.ready\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls[-1][0], "setprop")

    def test_comments_and_blank_lines_do_not_execute(self):
        result, calls = self.run_loader("# fixture comment\n\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [])

    def test_indented_comments_and_actions(self):
        result, calls = self.run_loader("  # fixture comment\n   \n  setprop |vendor.all.modules.ready\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [["setprop", "vendor.all.modules.ready", "1"]])

    def test_empty_list_is_a_noop_and_does_not_reorder_other_partition(self):
        (self.work / "system_dlkm/lib/modules/modules.load").write_text("")
        result, calls = self.run_loader("modprobe|*\nsetprop|vendor.all.modules.ready\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c for c in calls if c[0] == "modprobe"], [
            ["modprobe", "-a", "-d", "/vendor/lib/modules", "kernelsu.ko", "vendor.ko"],
        ])
        self.assertEqual(calls[-1][0], "setprop")

    def test_missing_configuration_is_an_error(self):
        result, calls = self.run_loader()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_argument_count_is_checked(self):
        for args in ([], ["one", "two"]):
            with self.subTest(args=args):
                result, calls = self.run_loader(args=args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
