"""Keep advertised secure decoders consistent with their vendor feature gate."""
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(os.environ.get("SECURE_VIDEO_TEST_DEVICE_ROOT", Path(__file__).resolve().parents[1]))


class SecureVideoContractTests(unittest.TestCase):
    def test_advertised_secure_decoders_have_driver_entries_and_enabled_video_path(self):
        public = ET.parse(ROOT / "configs/media/media_codecs_c2.xml").getroot()
        # Dolby's secure decoder wraps c2.mtk.hevc.decoder.secure (test_dolby.py).
        advertised = {codec.get("name") for codec in public.findall("./Decoders/MediaCodec")
                      if codec.get("name").startswith("c2.mtk.")
                      and any(feature.get("name") == "secure-playback"
                             and feature.get("required") == "true"
                             for feature in codec.findall("Feature"))}
        platform = ET.parse(ROOT / "configs/media/mtk_platform_codecs_config.xml").getroot()
        driver_entries = {codec.get("name") for codec in platform.findall("./Decoders/Video")}
        self.assertTrue(advertised, "Expected the device's protected video decoder declarations")
        self.assertLessEqual(advertised, driver_entries)
        properties = dict(line.split("=", 1) for raw in (ROOT / "vendor.prop").read_text().splitlines()
                          if (line := raw.strip()) and not line.startswith("#") and "=" in line)
        # The shipped MTK decoder defaults this gate to 0 and rejects secure mode.
        self.assertEqual(properties.get("ro.vendor.mtk_sec_video_path_support"), "1",
                         "Secure decoder declarations require the stock secure-video driver gate")


if __name__ == "__main__":
    unittest.main()
