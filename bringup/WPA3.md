# WPA3-only connection compatibility

The September 11, 2026 image ships `wlan_drv_gen4m_6878.ko` with SHA-256
`ae8796728aa8726978ee551041bb7ee6a95a754570aca04a9743d87b81224f01`.
Its `mtk_cfg80211_connect` handler only recognizes the nl80211 version bits
`0x1` and `0x2`. A request containing only `NL80211_WPA_VERSION_3` (`0x4`)
falls through to `IW_AUTH_WPA_VERSION_DISABLED`.

Android's supplicant can send `0x4` for SAE when the kernel's generic nl80211
attribute range includes `NL80211_ATTR_SAE_PASSWORD`. That check does not prove
that the separate vendor Wi-Fi module accepts the version bit. Advertised SAE
capability therefore does not exclude this incompatibility.

## Device opt-in

`device.mk` sets the Boolean Soong option
`wpa_supplicant_8.wifi_disable_wpa_version_3`. It requires the paired change in
`external/wpa_supplicant_8`, which adds `CONFIG_DISABLE_WPA_VERSION_3` to the
supplicant driver compiler flags and excludes the WPA3 version bit when set.
Both changes must be retained when syncing or reproducing this candidate.

This uses the driver's existing RSN (`0x2`) path with SAE still selected.
It does not change the Wi-Fi password, AKM, PMF, H2E, or router security mode.
Products without the opt-in retain the default version selection. The kernel,
modules, boot images, and firmware are not modified by this remedy.

The same compatibility approach is implemented in
[this supplicant change](https://github.com/nathanzerogarage/external_wpa_supplicant_8/commit/1fffebb87fb3ac0f81b47f3fbe7b7a08eb0a8941).
The alternative is to update the vendor driver to handle the new version bit,
as in [LineageOS's gen4m change](https://github.com/LineageOS/android_kernel_xiaomi_mt6768/commit/dfb07042bec5523e4773a7721bb230c514acb7ae).
That alternative needs a compatible driver build and is not this patch.

## Verification and remaining evidence

The host regression test compiles the actual WPA-version encoding block in
`driver_nl80211.c` against a capture stub. It checks SAE, FT-SAE, WPA2-PSK,
enterprise, OWE, WPA1, and open-network behavior with old and new kernel
attribute ranges, with the opt-in enabled and disabled, and with the existing
Broadcom/Synaptics exclusions. The two SAE cases fail before the patch and
pass after it; the authentication selector is preserved in all cases.

From the Android root:

```sh
python3 -m unittest discover -s external/wpa_supplicant_8/tests -v
source build/envsetup.sh
lunch lineage_malachite-bp4a-userdebug
m wpa_supplicant
```

The reported symptom is repeated disconnections on a WPA3-only access point.
It has not yet been captured locally. On the affected device, establish the
exact installed build, record a failed attempt before replacement, and repeat
on the same access point with the candidate. Confirm SAE and PMF negotiation,
successful IP configuration, reconnection, and sustained connectivity. Also
check an existing WPA2 network for regression. Capture supplicant and driver
disconnect/status codes if failures remain.

The static mismatch is confirmed; resolution of the reported device failure
remains unverified until this runtime comparison passes. A passing host build
alone is not a WPA3 interoperability result.
