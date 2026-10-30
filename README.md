# RisingOS Revived 17 for the Redmi Note 14 Pro 5G / POCO X7 5G (malachite)

Unofficial RisingOS Revived 17 (Android 17) device tree for malachite. It is
based on the [malachite-project](https://github.com/malachite-project)
`lineage-24.0` trees; the RisingOS branch is `rising-17` in this fork.

The device tree was originally written by **Noam
([@noamtu123](https://github.com/noamtu123))** and is maintained with the
malachite-project contributors. The ROM side is RisingOS Revived, built on
LineageOS and AOSP.

**Telegram group:** [t.me/malachite_project](https://t.me/malachite_project)

## What this branch changes

- RisingOS Revived 17 product flags, with full GApps
  (`WITH_GMS := true`, not the mini or pico package set).
- `user` builds by default, with release-key APK/APEX/OTA signing and an
  optional release AVB key.
- RisingOS's own `frameworks/base`, `frameworks/native`, `Settings`,
  `Telephony` and `Bluetooth` are kept. Replacing them with the LineageOS-based
  malachite forks would remove RisingOS features.
- The malachite device, vendor, kernel, MediaTek hardware, Xiaomi hardware,
  sepolicy, IMS and wpa_supplicant trees are used unchanged from
  `malachite-project`.
- `manifests/rising.xml` is the local manifest for a RisingOS checkout.

## Requirements

- A Linux build host with the usual AOSP dependencies, `repo`, `git-lfs`,
  OpenJDK 21 and at least 16 GB RAM (more is faster).
- The phone on **HyperOS 2.0.208.0.VOOMIXM** firmware. Do not mix regional
  firmware or downgrade the bootloader/preloader to match a different build.
- An unlocked bootloader. Flashing a custom AVB key does not make a locked
  bootloader trust this ROM.

## Build

```bash
repo init -u https://github.com/RisingOS-Revived/android -b seventeen --git-lfs
mkdir -p .repo/local_manifests
curl -o .repo/local_manifests/rising.xml \
  https://raw.githubusercontent.com/ridhzlabs/android_device_xiaomi_malachite/rising-17/manifests/rising.xml
repo sync -c --no-clone-bundle --optimized-fetch --prune --force-sync -j32
```

Then create the release keys once and build a signed user build:

```bash
source build/envsetup.sh
bash device/xiaomi/malachite/tools/rising/setup-signing.sh
riseup malachite user
rise sb
```

`setup-signing.sh` runs `gk -f` for the APK and APEX keys and adds the
4096-bit AVB key at `vendor/lineage-priv/keys/avb.pem`. The keys are private:
back them up, never commit them, and reuse the same keys for every update.
Changing the AVB key changes the vbmeta signature, so keep the backup with the
ROM release.

`rise sb` builds `target-files-package` and `otatools`, signs the APKs and the
OTA, and writes `RisingOS_Revived-*-ota-signed.zip` under `out/target/product/malachite/`.
`rise b` builds the unsigned OTA if signing is not needed.

The product name stays `lineage_malachite` because RisingOS's `riseup` helper
lunches `lineage_<device>-<release>-<variant>`. This is intentional; do not
rename it to `rising_malachite` without also changing the build command.

## Source ID

The device tree keeps the malachite source-ID tooling. Before a release build:

```bash
bash device/xiaomi/malachite/tools/source-snapshot.sh
```

The build records the source ID and the full project manifest in the ROM:

```bash
adb shell getprop ro.malachite.source.id
adb shell cat /system_ext/etc/source/manifest.xml
```

Commit and push every change before taking the snapshot. A snapshot that
contains uncommitted or unpushed projects is marked `-untraceable`, and one
taken before a later device, vendor or kernel change is marked `-stale`.

## Notes

- This port has not been boot-tested yet. Build success alone is not a boot or
  hardware test.
- The vendor blobs are the HyperOS 2.0.208.0.VOOMIXM baseline. The build
  fingerprint override inherited from the device tree is kept as it is.
- MediaTek GED KPI frame timestamps are already in RisingOS's
  `frameworks/native`. The malachite fork's FPSGO BufferQueue reporting and
  `BnProducerListener` ABI shim are not part of RisingOS; they can be ported
  onto RisingOS's `frameworks/native` later without replacing the repository.
- Dolby support comes from the malachite `hardware/dolby` app and the DAX
  vendor stack in `vendor/xiaomi/malachite`.

## Credits

- **Noam ([@noamtu123](https://github.com/noamtu123))** - original malachite
  device tree author.
- [malachite-project](https://github.com/malachite-project),
  [mt6878-devs](https://github.com/mt6878-devs),
  [puhboo](https://github.com/puhboo) and
  [cmdr-chara](https://github.com/cmdr-chara) - device bringup, kernel,
  hardware and vendor trees.
- [LineageOS](https://lineageos.org) and
  [RisingOS Revived](https://github.com/RisingOS-Revived) - the ROM base.
- The upstream projects credited in [BUILDING.md](BUILDING.md) and the
  malachite manifests.

```
#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#
```
