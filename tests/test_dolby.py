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
        self.assertEqual(dolby.get("revision"), "lineage-23.2")
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


# Dolby Codec2 decoders from stock OS2.0.208.0.VOOMIXM, served over AIDL by
# dolby/codec2 instead of stock's HIDL services.
CODEC_BLOBS = (
    "vendor/etc/dolby_vision.cfg",
    "vendor/etc/media_codecs_dolby_audio.xml",
    "vendor/lib64/c2.dolby.client.so",
    "vendor/lib64/c2.dolby.hevc.dec.so",
    "vendor/lib64/c2.dolby.hevc.sec.dec.so",
    "vendor/lib64/c2.dolby.store.so",
    "vendor/lib64/libcodec2_soft_ac4dec.so",
    "vendor/lib64/libcodec2_soft_ddpdec.so",
    "vendor/lib64/libcodec2_store_dolby.so",
    "vendor/lib64/libdeccfg.so",
    "vendor/lib64/libdolbydecoderprocessor.so",
    "vendor/lib64/libdolbyeglcore.so",
    "vendor/lib64/libdolbyottcameracontrol.so",
)
# Imported by stock 208's c2.dolby.client.so; the platform exports it only under
# the templated BufferPoolSender name.
OLD_OBJCPY = ("_ZN7android8hardware5media2c24V1_05utils6objcpyEPNS3_10WorkBundleERKNSt3__14list"
              "INS7_10unique_ptrI6C2WorkNS7_14default_deleteISA_EEEENS7_9allocatorISD_EEEE"
              "PNS4_16BufferPoolSenderE")


class DolbyCodecTests(unittest.TestCase):
    def test_codec_blobs_are_listed(self):
        lines = (ROOT / "proprietary-files.txt").read_text().splitlines()
        for blob in CODEC_BLOBS:
            with self.subTest(blob=blob):
                self.assertIn(blob, lines)

    def test_stock_hidl_services_are_not_shipped(self):
        # The AIDL wrapper replaces them; the framework would not list them anyway.
        text = (ROOT / "proprietary-files.txt").read_text()
        for blob in ("vendor/bin/hw/dolbycodec2", "vendor/bin/hw/vendor.dolby.media.c2@1.0-service",
                     "vendor.dolby.media.c2@1.0-service.rc", "vendor.dolbyvision.media.c2@1.0-service.rc",
                     "vendor.dolby.media.c2@1.0-service.xml", "libcodec2_soft_common"):
            with self.subTest(blob=blob):
                self.assertNotIn(blob, text)

    def test_decoders_get_their_shims(self):
        fixups = (ROOT / "extract-files.py").read_text()
        self.assertRegex(fixups, r"'vendor/lib64/c2\.dolby\.client\.so': blob_fixup\(\)\s*"
                                 r"\.add_needed\('libcodec2_hidl_shim\.so'\)")
        self.assertRegex(fixups, r"\('vendor/lib64/c2\.dolby\.hevc\.dec\.so', "
                                 r"'vendor/lib64/c2\.dolby\.hevc\.sec\.dec\.so'\): blob_fixup\(\)\s*"
                                 r"\.add_needed\('libcodec2_shim\.so'\)")
        shim = (ROOT / "dolby/codec2/objcpy_shim.cpp").read_text()
        self.assertIn(OLD_OBJCPY + "(", shim)
        # Forward to the real conversion; an empty stub returns garbage to queue().
        self.assertIn("return objcpy(d, s, static_cast<BufferPoolSender*>(bpSender));", shim)
        bp = (ROOT / "dolby/codec2/Android.bp").read_text()
        self.assertIn('name: "libcodec2_hidl_shim"', bp)
        mk = (ROOT / "device.mk").read_text()
        for package in ("android.hardware.media.c2-dolby-service", "libcodec2_hidl_shim",
                        "libcodec2_shim"):
            with self.subTest(package=package):
                self.assertRegex(mk, rf"(?m)^\s+{re.escape(package)}( \\)?$")

    def test_service_serves_both_stores(self):
        rc = (ROOT / "dolby/codec2/android.hardware.media.c2-dolby-service.rc").read_text()
        self.assertIn("/vendor/lib64/libcodec2_store_dolby.so default1", rc)
        self.assertIn("/vendor/lib64/c2.dolby.store.so default2", rc)
        manifest = ET.parse(ROOT / "dolby/codec2/manifest_media_c2_dolby.xml").getroot()
        instances = {hal.findtext("fqname") for hal in manifest.iter("hal")
                     if hal.get("format") == "aidl" and hal.findtext("name") == "android.hardware.media.c2"}
        self.assertEqual(instances, {"IComponentStore/default1", "IComponentStore/default2"})

    def test_codec_list_matches_stock(self):
        codecs = ET.parse(ROOT / "configs/media/media_codecs_c2.xml").getroot()
        self.assertIn("media_codecs_dolby_audio.xml",
                      [node.get("href") for node in codecs.findall("Include")])
        decoders = {codec.get("name"): codec for codec in codecs.findall("./Decoders/MediaCodec")}
        for name, secure in (("c2.dolby.decoder.hevc", False), ("c2.dolby.decoder.hevc.secure", True)):
            with self.subTest(name=name):
                self.assertEqual(decoders[name].get("type"), "video/dolby-vision")
                features = {f.get("name"): f.get("required") for f in decoders[name].findall("Feature")}
                self.assertEqual(features.get("secure-playback"), "true" if secure else None)
        # The Dolby Vision decoders run the MediaTek HEVC decoders underneath.
        self.assertIn("c2.mtk.hevc.decoder", decoders)
        self.assertIn("c2.mtk.hevc.decoder.secure", decoders)


    def test_display_reports_dolby_vision(self):
        # MediaTek's composer does not list Dolby Vision; SurfaceFlinger adds it
        # from this property, which needs a context it can read.
        props = (ROOT / "vendor.prop").read_text()
        self.assertRegex(props, r"(?m)^ro\.surface_flinger\.has_dolby_vision=true$")
        contexts = (ROOT / "sepolicy/private/property_contexts").read_text()
        self.assertRegex(contexts, r"(?m)^ro\.surface_flinger\.has_dolby_vision\s+"
                                   r"u:object_r:surfaceflinger_prop:s0 exact bool$")


if __name__ == "__main__":
    unittest.main()
