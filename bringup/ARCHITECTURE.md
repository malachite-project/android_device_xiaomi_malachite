# Malachite architecture and dependency map

Inspected 2026-09-05. All source references below mean the immutable revisions in [source-lock.json](source-lock.json), not a moving branch. This is a source baseline, not a known-good ROM build or boot certification.

## Twelve owned repositories

All repositories are under `cmdr-chara`; the initial branch is `lineage-23.2`. Full commit IDs are in the lock. Android and kernel are separate workspaces.

| Repository | Checkout path | Inspected HEAD | Producer / consumer relationship |
| --- | --- | --- | --- |
| android_device_xiaomi_malachite | Android: device/xiaomi/malachite | 0f54832a13d8 | Product, BoardConfig, init, fstab, overlays, SELinux, extraction/fixups; consumes the six other Android-side forks below |
| proprietary_vendor_xiaomi_malachite | Android: vendor/xiaomi/malachite | 28a87d5dda2c | Generated Android.bp, malachite-vendor.mk and BoardConfigVendor.mk; proprietary userspace and configurations |
| android_hardware_mediatek | Android: hardware/mediatek | d3d6d6178dbf | MediaTek HAL implementations, codecs, shims, libaedv/performance support and framework VINTF matrix |
| android_hardware_xiaomi | Android: hardware/xiaomi | 8d8fd4a47d88 | Xiaomi fingerprint/sensor integration, eUICC policy, device support and framework VINTF matrix |
| android_device_mediatek_sepolicy_vndr | Android: device/mediatek/sepolicy_vndr | 77533d8a4241 | Common vendor/system_ext policies; includes upstream device/lineage/sepolicy/libperfmgr/sepolicy.mk |
| android_vendor_mediatek_ims | Android: vendor/mediatek/ims | 06c462f1dfc2 | ImsService, IMS overlays, permissions and properties inherited through ims.mk |
| android_kernel_xiaomi_mt6878 | Kernel: kernel-6.1 | 9f205dab5f27 | Xiaomi/MediaTek kernel source with ACK updates; NOT the separate pure AOSP common project |
| android_kernel_device_modules | Kernel: kernel_device_modules-6.1 | 034b70b1cbe1 | Platform/device drivers, configuration overlay and malachite Kleaf target |
| android_vendor_mediatek_kernel_modules | Kernel: vendor/mediatek/kernel_modules | ce0e09550e09 | Connectivity, camera, GPU, FPSGO and other MediaTek module projects |
| kernel-build-bazel_mgk_rules | Kernel: build/bazel_mgk_rules | d8ca975a69ce | MediaTek Kleaf macros plus root BUILD/WORKSPACE templates |
| kernel_manifest-6.1 | Manifest repository, not Android source | 13c8383aa91b | Places 22 kernel projects and seven entry-point linkfiles; ownership/pinning proposal is separate from this historical baseline |
| android_device_xiaomi_malachite-kernel | Android: device/xiaomi/malachite-kernel | 9668297071a1 | Transitional Image.lz4, DTB and modules actually consumed by BoardConfig |

The device/prebuilt fork parents are `puhboo`; the IMS parent is archived `xiaomi-mt6899-dev`; the other nine parents are archived `mt6878-devs`. Archive status is an inspection-time fact, not a reason to discard their historical fixes. The new Android local manifest and kernel manifest proposal use owned remotes for mutable device-specific projects. AOSP/Lineage/Google dependencies remain upstream.

## Android inheritance and external dependencies

`AndroidProducts.mk` exports `lineage_malachite.mk`. That product inherits the core 64-bit telephony products, this device's `device.mk`, and Lineage's common phone product. `device.mk` inherits generic/virtual-A/B ramdisk products, emulated storage, `vendor/mediatek/ims/ims.mk`, and `vendor/xiaomi/malachite/malachite-vendor.mk`. `BoardConfig.mk` includes vendor BoardConfig and common MediaTek policy.

Soong namespaces include this device, `hardware/mediatek`, its `libaedv` and performance subtrees, `hardware/xiaomi`, Google Pixel/interfaces and Lineage power-libperfmgr. `extract-files.py` imports the device, MediaTek, libaedv and Xiaomi namespaces. These relationships must stay synchronized with the extraction-generated vendor files.

External build prerequisites include standard framework/native/AV media and permission modules, Lineage interfaces and policy, Pixel thermal/memory helpers, Google interfaces, Qualcomm's open-source vibrator service used by this device, extraction tools, and standard Android host toolchains. The Qualcomm package name is not evidence that the MediaTek device configuration is wrong. The seven-project [android.xml](android.xml) does not replace or fully lock these external dependencies; a full `repo manifest -r` remains required for each Android build.

## Boot, storage and recovery contracts

Evidence: [BoardConfig.mk](../BoardConfig.mk), [device.mk](../device.mk), [init/fstab.mt6878](../init/fstab.mt6878), [init/Android.bp](../init/Android.bp).

- arm64, MT6878, shipping API 34. Header version 4, 64 MiB boot, 8 MiB init_boot and 64 MiB vendor_boot are declared. Ramdisks use LZ4; recovery resources/ramdisk move into vendor_boot. These are source declarations; image headers and the actual phone's sizes are not verified.
- Eight dynamic partitions: odm, odm_dlkm, product, system, system_dlkm, system_ext, vendor, vendor_dlkm. The group is 9,121,562,624 bytes inside a 9,125,756,928-byte super declaration, leaving 4 MiB. Filesystem declarations match fstab: ext4 for system/system_ext/product, EROFS for vendor/odm and DLKM partitions.
- Virtual A/B OTA includes those eight partitions plus boot, init_boot, vendor_boot and the three vbmeta images. The source uses logical/slotselect/AVB first-stage mounts and system postinstall. This does not establish actual slot contents, snapshot health or OTA success.
- `fstab.mt6878` is both a vendor/vendor-ramdisk prebuilt and `TARGET_RECOVERY_FSTAB`. Userdata/metadata use F2FS, with file/metadata encryption configured. Changing this file affects normal and recovery paths, not just one image.
- `TARGET_FORCE_PREBUILT_KERNEL := true` overrides the nominal source-kernel variables. The actual inputs are Image.lz4, the DTB directory and system_dlkm/vendor_dlkm/vendor_ramdisk module directories from the prebuilt repository. Do not mistake `TARGET_KERNEL_SOURCE` for an active source-built-kernel migration.
- DTB placement is controlled by the Android image builder and header-4 configuration; unpack generated images to verify it. `dtbo.img` exists in the prebuilt repository but is deliberately NOT configured for packaging or OTA. Historical commit `3f0a97055157f346cb5abb9a998250e1de286e41` removed it after reported cross-firmware hard-brick risk. Its exclusion is a safety contract, not an omitted feature to restore.
- AVB is nominally enabled but `--flags 3` and public test keys are inherited. This is a release-policy FAIL, not verified boot readiness. Rollback locations 2/3/4 and timestamp inputs require an actual generated-chain review. See [SAFETY.md](SAFETY.md).

The module inventories contain 60 system, 208 vendor, 215 vendor-ramdisk and 214 recovery load-list entries. All names exist in the corresponding prebuilt tree. `mtk_dramc.ko` appears twice in both ramdisk lists; retained pending load-order/runtime evidence. File presence does not prove vermagic, symbol versions, KMI compatibility or successful insertion.

## Kernel build topology

The kernel manifest has 18 upstream projects and four owned source projects. Upstream `common` is AOSP GKI/common; `kernel-6.1` is the Xiaomi/MediaTek source tree. Neither should be silently substituted for the other.

Seven manifest linkfiles expose `tools/bazel`, build helper scripts, root BUILD/WORKSPACE, `build.config.constants` and `build.config.malachite`. The MediaTek WORKSPACE creates local repositories rooted at `vendor/mediatek` and its kernel_modules subtree. Its `BUILD.internal`, `BUILD.ko` and `bazel.WORKSPACE` files are text templates, not binary modules.

The source target is `//kernel_device_modules-6.1:mgk_64_k61_customer_dist.user`. Configuration uses `KERNEL_VERSION=kernel-6.1`, `DEFCONFIG_OVERLAYS=malachite.config`, the `kernel_version=6.1` build setting and a recorded SOURCE_DATE_EPOCH. `build.config.constants` specifies clang-r487747c. `BUILD.bazel`, `mgk.bzl` and `kleaf/key_value_repo.bzl` define the producer path. The pure ACK variant references `common-6.1`, whereas the manifest installs upstream common at `common`; do not advertise the ACK variant as validated by a user-target test.

The prebuilt repository's latest commit explicitly describes a SELECTIVE source-module migration with ACK 6.1.166. The kernel source HEAD has 6.1.167. This is a hybrid compatibility baseline, not proof that today's source reproduces every consumed artifact. Keep the prebuilt path until Image/DTB/module membership, `.config`, Module.symvers, KMI, signing and load order are compared. Never publish source-built replacements by copying an arbitrary dist directory into the Android prebuilt tree.

The owned kernel manifest proposal pins all four device-specific commits and includes a fully resolved 22-project snapshot. A real pinned `repo sync` and customer-user `cquery` succeeded; compilation/output equivalence are separate gates. The kernel repository README and build-probe evidence are authoritative for compilation status.

## Hardware integration and required consumers

| Area | Current source integration | Outstanding validation |
| --- | --- | --- |
| VINTF / radio | Device target-level 7; mixed HIDL/AIDL; hardware framework matrices; vendor service fragments; Radio AIDL and MediaTek extensions | `checkvintf` on built framework/vendor/ODM matrices and every selected SKU; target-level must not be bumped merely because the OS branch is newer |
| SKU selection / NFC | Three NFC-capable ODM SKU manifests; additional dsds/qsqs/ss/tsts manifests; init.nfc.malachite.rc, boardid data and permission directories | Verify emitted SKU/property selection. Non-SKU ODM_MANIFEST_FILES includes several override manifests; inspect the merged result rather than assuming their order is harmless |
| IMS / RIL | Source IMS service/overlays plus proprietary radio services; IMS/VoLTE/WFC feature overrides | Carrier provisioning, both SIM paths, voice/data/SMS, VoLTE/VoWiFi/handover; feature properties are not proof of registration |
| Camera | OS2 userspace blobs, provider/plugins and device Apex/Aperture policy; ABI fixups | Global-model crash logs, all lenses, recording/stabilization and exact ELF dependencies |
| UDFPS / FOD | Xiaomi fingerprint implementation V2, libudfpshandler, sensor bridge, FOD init and SELinux | Enrolment/authentication, screen-off/AOD/HBM callbacks and enforcing-policy denials |
| Display / AOD / brightness | Source panel changes, Xiaomi DisplayFeature/PQ, display config, overlays and lights service | Actual panel modes; flicker, HBM/HDR/brightness scaling and doze transitions |
| Sensors / ambient light | Xiaomi multi-HAL plus citsensor optical compensation and scheduling policy | Under-display ALS in bright/dim scenes, rotation/proximity/pocket interaction and power consumption |
| Audio / Dolby | Audio 7.1/effect 7.0, MediaTek primary HAL, USBv2, retained routing/ABI workarounds; MediaTek Bluetooth audio provider with A2DP hardware offload (SBC/AAC) by default and a software fallback policy file | USB DAC/calls/VoIP, speaker/mic/Bluetooth routes, offloaded and fallback A2DP. Dolby Vision stays dropped. Dolby DAX audio was restored from stock 208 with the SELinux domain the first attempt lacked; LunarisDolby (hardware/dolby) controls it |
| Wi-Fi / Bluetooth | Source Wi-Fi/hostapd/supplicant and MediaTek Bluetooth HAL; proprietary firmware/userspace and kernel connectivity modules | WPA2/WPA3/mixed/PMF, hotspot/P2P, reconnect/suspend and BT audio. Current supplicant still has pmf=0 |
| Charging / thermal / power | batterysecret, Lineage charging control, Pixel thermal, mi_thermald and libperfmgr/device powerhint | Charging protocol/current, offline charge, charge limits, temperature, idle drain and CPU-frequency scaling; do not infer watts from node presence |
| GNSS | gps.default, mtk_agpsd, init module loading; GPS power/SCP module history | Cold/warm fixes, suspend/resume, assistance, module ABI and SELinux |
| DRM | ClearKey from source, vendor Widevine non-updatable APEX | Secure provisioning and streaming behavior on the actual phone; no L1 claim and no calibration/key writes |

## Policy and modernization boundaries

Common MediaTek base/debug policy is inherited by build variant. There is a `userdebug_or_eng`-guarded permissive `osi` domain in `base/private/osi.te`; this is not global permissive mode, but a debug build must not be described as wholly enforcing without compiled-policy inspection. No permissive or neverallow bypass was added.

Retain narrowed batterysecret labels/rules and fingerprint/display/citsensor policy until runtime denials justify a precise change. Do not replace them with blanket sysfs access or generated allow rules. Android-version-dependent blob shims and HIDL/AIDL combinations require exact binary/consumer validation. In particular, current upstream extract-utils merges overlapping fixup groups; the PQ entries do not justify deleting its libui shim. See [HISTORY.md](HISTORY.md) for retained, superseded and intentionally removed workarounds.
