# WPA3 (SAE) connection compatibility

## Symptom

`wlan_drv_gen4m_6878.ko` as shipped in the September 11, 2026 image has SHA-256
`ae8796728aa8726978ee551041bb7ee6a95a754570aca04a9743d87b81224f01`. Verified
2026-09-20 against `vendor_dlkm/wlan_drv_gen4m_6878.ko` at
`android_device_xiaomi_malachite-kernel` `lineage-23.2`, 7,041,312 bytes: the
module consumed by `TARGET_FORCE_PREBUILT_KERNEL` is the module described here.
Its `mtk_cfg80211_connect` handler recognizes only the nl80211 version bits
`0x1` and `0x2`. A request carrying only `NL80211_WPA_VERSION_3` (`0x4`) falls
through to `IW_AUTH_WPA_VERSION_DISABLED`, and the negotiated AKM is discarded
with it.

Captured on the September 11, 2026 image, 2026-09-20, associating with a
WPA2/WPA3 transition-mode access point:

```
wpa_supplicant: wlan0: Trying to associate with SSID 'REDACTED'
wpa_supplicant: assoc key_mgmt 0x400 network key_mgmt 0x542
mtk_cfg80211_connect: (REQ INFO) sme->auth_type=4, sme->crypto.wpa_versions=4
mtk_cfg80211_connect: (REQ INFO) n_akm_suites=3, akm_suites=fac08
mtk_cfg80211_connect: (REQ INFO) u4WpaVersion=1, u4AuthAlg=16, eAuthMode=11,
                                 u4AkmSuite=0x0, ...
wlanoidSetAuthMode: (RSN INFO) New auth mode: SAE
wpa_supplicant: wlan0: CTRL-EVENT-ASSOC-REJECT bssid=00:00:00:00:00:00
                       status_code=16
```

`wpa_versions=4` in, `u4WpaVersion=1` (`IW_AUTH_WPA_VERSION_DISABLED`) and
`u4AkmSuite=0x0` out, then IEEE 802.11 status 16 (authentication timeout)
roughly nine seconds later. PMF is not the cause: the driver logs the
negotiated group management cipher and sets `New auth mode: SAE` before
discarding the configuration. `pmf=0` in `configs/wifi/wpa_supplicant.conf` is
unrelated to this failure; Android sets `ieee80211w` per network for SAE.

The scope is wider than a WPA3-only access point. `network key_mgmt 0x542`
(`PSK | FT-PSK | PSK-SHA256 | SAE`) is a transition-mode network, and Android
still selects SAE (`assoc key_mgmt 0x400`) on it. Any access point advertising
SAE is affected, whether or not it also offers WPA2.

Android's supplicant sends `0x4` for SAE when the kernel's generic nl80211
attribute range includes `NL80211_ATTR_SAE_PASSWORD`. That range does not prove
the separate vendor Wi-Fi module accepts the version bit, so advertised SAE
capability does not exclude this incompatibility.

## Device opt-in

`device.mk` sets the Boolean Soong option
`wpa_supplicant_8.wifi_disable_wpa_version_3`. It requires the paired change in
`external/wpa_supplicant_8`, which defines `CONFIG_DISABLE_WPA_VERSION_3` in the
supplicant compiler flags and excludes the WPA3 version bit when set. Both
changes must be retained when syncing or reproducing this candidate; the
`device.mk` line alone has no effect.

The two halves must agree on the Soong variable type. `soong_config_set_bool`
declares a Boolean, so every branch key in `wpa_supplicant/Android.bp` must be
an unquoted `true`, matching the other `wpa_supplicant_8` flags in that file. A
quoted `"true"` key is a string and Soong rejects the mismatch:

```
Expected all branches of a select on condition
soong_config_variable("wpa_supplicant_8", "wifi_disable_wpa_version_3")
to have type bool, found string
```

This is a build-stopping error, not a silent no-op, and the host regression
test below does not cover it because that test never invokes Soong. Use
`soong_config_set_bool` with unquoted keys, or `soong_config_set` with quoted
keys, consistently.

The remedy uses the driver's existing RSN (`0x2`) path with SAE still selected.
It does not change the Wi-Fi password, AKM, PMF, H2E, or the access point's
security mode. Products without the opt-in retain the default version
selection. The kernel, modules, boot images and firmware are not modified.

The approach follows
[this supplicant change](https://github.com/nathanzerogarage/external_wpa_supplicant_8/commit/1fffebb87fb3ac0f81b47f3fbe7b7a08eb0a8941),
which does not apply as-is to `lineage-23.2`: that branch gates the version bit
on a runtime `drv->chip_vendor_id != OUI_BRCM` check, while Lineage uses
preprocessor exclusions. The equivalent change here adds
`CONFIG_DISABLE_WPA_VERSION_3` to the existing
`!defined(CONFIG_DRIVER_NL80211_BRCM) && !defined(CONFIG_DRIVER_NL80211_SYNA)`
guard, so control falls to the existing `ver |= NL80211_WPA_VERSION_2`.

The alternative is to teach the vendor driver the new version bit, as in
[LineageOS's gen4m change](https://github.com/LineageOS/android_kernel_xiaomi_mt6768/commit/dfb07042bec5523e4773a7721bb230c514acb7ae).
That needs a compatible driver build and is not this patch. It is also not
available while `TARGET_FORCE_PREBUILT_KERNEL := true`, because the shipped
module is a prebuilt rather than a build product of this tree.

## Verification

`external/wpa_supplicant_8/tests/wpa_version_3` extracts the live
version-selection block from `src/drivers/driver_nl80211.c` and compiles it
twice, with and without the opt-in, asserting the emitted nl80211 version bits.
Extraction rather than duplication means the test fails loudly if upstream
restructures the block instead of silently checking a stale copy.

From `external/wpa_supplicant_8`:

```sh
CC=gcc tests/wpa_version_3/run.sh
```

Result on this candidate, gcc 13.3.0, `-Wall -Wextra -Werror`:

| Case | opt-in disabled | opt-in enabled |
| --- | --- | --- |
| RSN + SAE, `SAE_PASSWORD` supported | `0x4` | `0x2` |
| RSN + FT-SAE | `0x4` | `0x2` |
| WPA + RSN + SAE | `0x5` | `0x3` |
| RSN + SAE, no `SAE_PASSWORD` attribute | `0x2` | `0x2` |
| RSN + PSK (WPA2) | `0x2` | `0x2` |
| WPA1 + PSK | `0x1` | `0x1` |

All twelve cases pass. The disabled column reproduces the captured
`wpa_versions=4`; the enabled column emits the `0x2` the driver decodes. WPA2,
WPA1 and the no-`SAE_PASSWORD` fallback are unchanged, so the opt-in narrows
only the SAE version bit. The script exits `1` against unpatched sources and
`0` with the change applied.

This is a host source-behaviour result. It is not a build of the supplicant, a
Soong evaluation, a merged VINTF result, or a Wi-Fi interoperability result.

## Remaining gates

An Android build of `wpa_supplicant` is still required, and is the only check
that exercises the Soong select typing described above.

The device test remains outstanding. On the affected phone, record the exact
installed build, capture a failed attempt before replacement, then repeat
against the same access point with the candidate. Confirm SAE and PMF
negotiation, IP configuration, reconnection after suspend and sustained
connectivity. Re-test a WPA2-only network for regression, and a WPA3-only
network separately from transition mode. Capture supplicant and driver
disconnect/status codes if failures remain.

The static mismatch and its source-level remedy are confirmed. Resolution of
the device failure is unverified until that runtime comparison passes.

## Protected management frames

With the version bit fixed, SAE authentication completes but the association
is refused with status 31, `WLAN_STATUS_ROBUST_MGMT_FRAME_POLICY_VIOLATION`:
WPA3-SAE requires PMF, and `pmf=0` left MFPC=0 in the association request.
This build's `wpas_get_ssid_pmf()` has no SAE override, and the AIDL
`setRequirePmf(false)` leaves `ieee80211w` at its default, so the global
`pmf` value decides.

`pmf=1` is set in both `wpa_supplicant.conf` and `wpa_supplicant_overlay.conf`.
The supplicant runs from `/data/vendor/wifi/wpa/wpa_supplicant.conf`, which
`ensureConfigFileExists()` copies from the vendor template only when absent,
so a template change alone never reaches an existing install. The overlay is
passed as `confanother` on every interface start and read into the same
configuration after the base file, so it overrides a stale `/data` copy on
dirty flashes too.

`pmf=0` came from a122ee35ee2a (July 2024), which reported driver crashes when
mixed-mode access points queried PMF. The identical commit exists in the
Motorola `scout` tree, so it originated in a shared template. The two MediaTek
trees carrying this same WPA3 workaround (`emerald`, `tanzanite`) and three
MT6878 `tetris` trees ship `pmf=1`.

Verified on the September 11, 2026 image, 2026-09-21: with the version-bit
patch alone, association to a WPA2/WPA3 transition-mode access point failed
with status 31; with `pmf=1` applied to the live configuration as well, it
connected, and Android reports the connection as WPA3-Personal. Not yet
verified: WPA3-only access
points, SoftAP, and absence of the 2024 mixed-mode driver crash over time.
