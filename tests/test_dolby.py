"""Dolby DAX wiring contracts. Static checks only; audio behavior needs the phone."""
import os
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

# Library names, paths and effect UUIDs from stock 208's vendor/etc/audio_effects.xml.
LIBRARIES = {"dap": "libswdap.so", "dvl": "libdlbvol.so",
             "gamedap": "libswgamedap.so", "vqe": "libswvqe.so"}
EFFECTS = {
    "dap": ("dap", "9d4921da-8225-4f29-aefa-39537a04bcaa"),
    "gamedap": ("gamedap", "3783c334-d3a0-4d13-874f-0032e5fb80e2"),
    "vqe": ("vqe", "64a0f614-7fa4-48b8-b081-d59dc954616f"),
    "dlb_music_listener": ("dvl", "40f66c8b-5aa5-4345-8919-53ec431aaa98"),
    "dlb_ring_listener": ("dvl", "21d14087-558a-4f21-94a9-5002dce64bce"),
    "dlb_alarm_listener": ("dvl", "6aff229c-30c6-4cc8-9957-dbfe5c1bd7f6"),
    "dlb_system_listener": ("dvl", "874db4d8-051d-4b7b-bd95-a3bebc837e9e"),
}
BLOBS = (
    "vendor/bin/hw/vendor.dolby.hardware.dms@2.0-service",
    "vendor/etc/dolby/dax-default.xml",
    "vendor/etc/init/vendor.dolby.hardware.dms@2.0-service.rc",
    "vendor/etc/vintf/manifest/vendor.dolby.hardware.dms.xml",
    "vendor/lib64/libdapparamstorage.so",
    "vendor/lib64/libdlbdsservice.so",
    "vendor/lib64/libdlbpreg.so",
    "vendor/lib64/soundfx/libdlbvol.so",
    "vendor/lib64/soundfx/libswdap.so",
    "vendor/lib64/soundfx/libswgamedap.so",
    "vendor/lib64/soundfx/libswvqe.so",
    "vendor/lib64/vendor.dolby.hardware.dms@2.0-impl.so",
    "vendor/lib64/vendor.dolby.hardware.dms@2.0.so",
)


NS = "{http://schemas.android.com/audio/audio_effects_conf/v2_0}"


class DolbyTests(unittest.TestCase):
    def test_blobs_are_extracted_unmodified(self):
        lines = (ROOT / "proprietary-files.txt").read_text().splitlines()
        for blob in BLOBS:
            with self.subTest(blob=blob):
                self.assertIn(blob, lines)

    def test_effects_match_stock(self):
        config = ET.parse(ROOT / "configs/audio/audio_effects.xml").getroot()
        libraries = {node.get("name"): node.get("path") for node in config.iter(NS + "library")
                     if node.get("path")}
        for name, path in LIBRARIES.items():
            self.assertEqual(libraries.get(name), path)
        effects = {node.get("name"): (node.get("library"), node.get("uuid"))
                   for node in config.iter(NS + "effect")}
        for name, expected in EFFECTS.items():
            self.assertEqual(effects.get(name), expected)
        post = {stream.get("type"): [apply.get("effect") for apply in stream.iter(NS + "apply")]
                for node in config.findall(NS + "postprocess") for stream in node.iter(NS + "stream")}
        self.assertEqual(post, {"music": ["dlb_music_listener"], "ring": ["dlb_ring_listener"],
                                "alarm": ["dlb_alarm_listener"]})

    def test_misound_props_match_stock(self):
        # Stock keeps libmisoundfx and the aurisys MiSound chain and sets the prop.
        # The prop alone does not stop libmisound: see test_dolby_app_switches_misound.
        props = (ROOT / "vendor.prop").read_text()
        for line in ("persist.vendor.audio.misound.disable=true",
                     "ro.vendor.audio.dolby.dax.support=true",
                     "ro.vendor.dolby.dax.version=DAX3_3.8.5.20_r1",
                     "ro.vendor.audio.device.db=DB_XM"):
            with self.subTest(prop=line):
                self.assertRegex(props, rf"(?m)^{re.escape(line)}$")
        effects = (ROOT / "configs/audio/audio_effects.xml").read_text()
        self.assertIn('<library name="misoundfx" path="libmisoundfx.so"/>', effects)
        aurisys = (ROOT / "configs/audio/aurisys_config.xml").read_text()
        self.assertIn('<library name="misound"/>', aurisys)

    def test_framework_matrix_accepts_the_service(self):
        matrix = ET.parse(ROOT / "framework_compatibility_matrix.xml").getroot()
        hals = [hal for hal in matrix.iter("hal") if hal.findtext("name") == "vendor.dolby.hardware.dms"]
        self.assertEqual(len(hals), 1)
        self.assertEqual(hals[0].findtext("version"), "2.0")
        self.assertEqual(hals[0].findtext("interface/name"), "IDms")
        self.assertEqual(hals[0].findtext("interface/instance"), "default")

    def test_service_has_stock_selinux_labels(self):
        policy = ROOT / "sepolicy/vendor"
        self.assertIn(r"/vendor/bin/hw/vendor\.dolby\.hardware\.dms@2\.0-service "
                      "u:object_r:hal_dms_default_exec:s0",
                      (policy / "file_contexts").read_text())
        self.assertIn("vendor.dolby.hardware.dms::IDms u:object_r:hal_dms_hwservice:s0",
                      (policy / "hwservice_contexts").read_text())
        te = (policy / "hal_dms_default.te").read_text()
        for rule in ("init_daemon_domain(hal_dms_default)",
                     "hal_server_domain(hal_dms_default, hal_dms)",
                     "hal_client_domain(hal_audio_default, hal_dms)"):
            with self.subTest(rule=rule):
                self.assertIn(rule, te)

    def test_control_app_comes_from_hardware_dolby(self):
        root = ET.parse(ROOT / "manifests/malachite.xml").getroot()
        projects = {p.get("path"): p for p in root.findall("project")}
        dolby = projects["hardware/dolby"]
        self.assertEqual(dolby.get("name"), "android_hardware_dolby")
        self.assertEqual(dolby.get("remote"), "malachite-project")
        self.assertEqual(dolby.get("revision"), "noam/lineage-23.2")
        self.assertIn("$(call inherit-product, hardware/dolby/dolby.mk)",
                      (ROOT / "device.mk").read_text())

    def dolby_repo(self):
        repo = Path(os.environ.get("MALACHITE_DOLBY_ROOT", ROOT.parent / "dolby-hwdolby"))
        if not (repo / "dolby.mk").is_file():
            self.skipTest("hardware/dolby is not checked out beside the tree")
        return repo

    def test_hardware_dolby_ships_only_the_app(self):
        # It must not bring its own Dolby blobs, policy or VINTF: the device has them.
        repo = self.dolby_repo()
        mk = (repo / "dolby.mk").read_text()
        self.assertIn("LunarisDolby", mk)
        for word in ("BOARD_VENDOR_SEPOLICY_DIRS", "DEVICE_MANIFEST_FILE",
                     "DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE", "libswdap", "dax-default"):
            with self.subTest(word=word):
                self.assertNotIn(word, mk)
        self.assertFalse((repo / "proprietary").exists())
        self.assertFalse((repo / "sepolicy").exists())
        effect = (repo / "LunarisDolby/src/org/lunaris/dolby/audio/DolbyAudioEffect.kt").read_text()
        self.assertIn(EFFECTS["dap"][1], effect)

    def test_dolby_app_switches_misound(self):
        # Stock's audio HAL starts with MisoundEnable=1 and forwards the key to
        # libmisound (its native enable, parameter 19). The app sends it on every
        # apply, so it survives HAL restarts.
        src = self.dolby_repo() / "LunarisDolby/src/org/lunaris/dolby"
        self.assertIn('MISOUND_HAL_KEY = "MisoundEnable"',
                      (src / "DolbyConstants.kt").read_text())
        repository = (src / "data/DolbyRepository.kt").read_text()
        self.assertIn("audioManager.setParameters(\"${DolbyConstants.MISOUND_HAL_KEY}=$value\")",
                      repository)
        self.assertIn("getBoolean(DolbyConstants.PREF_MISOUND, false)", repository)
        self.assertRegex(repository, r"fun applySavedState\(\) \{[^}]*\}[^}]*applyMiSound\(\)")


if __name__ == "__main__":
    unittest.main()
