# Evolution X on malachite (feature/evolutionx-24.0)

State of the Evolution X port, written 2026-10-29 when the branch was made.
Read this before changing or building anything on this branch. The longer
version, with references, is `notes/2026-10-29-evolutionx-port.md` in the
workspace repository (E:\LineageOS-23.2-Malachite, local only).

## What this branch is

Evolution X (their Android 17 line, manifest branch `cnb`, version 12.3)
ported from `lineage-24.0`. Evolution X cnb is LineageOS 24.0 plus their own
forks: their manifest pins every LineageOS project at lineage-24.0, replaces
frameworks/base, frameworks/native, Settings, Telephony, Bluetooth, build,
system/sepolicy and others with Evolution X's forks, and mounts their
`vendor_evolution` repo at `vendor/lineage` - the same path our tree already
inherits from. That is why the port is two files:

- `manifests/evolution.xml` - the local manifest for their manifest
  (device, kernel-prebuilt, vendor, hardware/mediatek, hardware/xiaomi,
  sepolicy_vndr, vendor/mediatek/ims, hardware/dolby, ParanoidSense added;
  external/wpa_supplicant_8 replaced with our fork; everything else is
  Evolution X's).
- `lineage_malachite.mk` - the Evolution X options (EVO_BUILD_TYPE,
  WITH_GMS := false, TARGET_ENABLE_FP_OVERRIDE := false,
  TARGET_PROVIDES_FACE_UNLOCK_HAL := true, TARGET_BOOT_ANIMATION_RES := 1080).

The product name stays `lineage_malachite`; that follows Evolution X's own
device trees (marble, rosemary), whose trees are unmodified LineageOS trees
with a few variables added.

## What was verified before the first build (all read in the sources,
never compiled)

- Every repository `device.mk` and `BoardConfig.mk` needs exists in the cnb
  manifest (main + snippets): hardware/lineage/interfaces,
  hardware/google/pixel (incl. mm/fstab.zram.50p-1g, pixelstats,
  power-libperfmgr, thermal), hardware/google/interfaces, packages/apps/Dialer,
  packages/modules/NetworkStack, lineage-sdk, device/lineage/sepolicy,
  packages/resources/devicesettings, vendor/qcom/opensource/vibrator,
  packages/apps/Aperture.
- The config chain is common_full_phone.mk -> common.mk -> evolution.mk +
  version.mk, so every option set in lineage_malachite.mk takes effect.
- evo's vendor config sets PRODUCT_NOT_DEBUGGABLE_IN_USERDEBUG := true like
  LineageOS: `breakfast malachite userdebug` produces ro.debuggable=0, the
  same release-by-default behaviour as our 24.0 builds.

## What is deliberately not in this port

Our framework-side features do not exist here, because Evolution X's
frameworks are their own forks and pointing those paths at our lineage forks
would break Evolution X's features: three-finger screenshot, FaceSense
provider, unrounded backlight, MediaTek GED KPI frame timestamps, the eSIM
settings UI, the LE Audio fixes, the brightness smoothing framework parts.
Each needs its own Evolution X branch after the first build boots. The source
ID (feature/source-id-24.0) is not merged into lineage-24.0 and is not here
either; porting it needs an evo variant of tools/source-id.sh (their
LINEAGE_VERSION has a different format).

Face unlock: ParanoidSense is built, but its SenseProvider is registered by
frameworks/base, which evo replaces. Expected broken until that part is
ported (or until the miface port covers it).

## Before the first build

1. Push this branch. The authoring session never pushes.
2. Merge `fix/wifi-supplicant-nan-24.0` (3be5c41) into hardware/mediatek
   `lineage-24.0` and push that too. Without it wpa_supplicant crashes on
   every start and Wi-Fi is dead (the 2026-10-27 24.0 bug; note
   2026-10-27-test24-build.md in the workspace). evolution.xml references
   lineage-24.0 branches, so the fix must be on the branch, not only in a
   local merge.

## Building (nothing here has run yet; treat every step as unproven)

```
mkdir -p ~/evox && cd ~/evox
repo init -u https://github.com/Evolution-X/manifest.git -b cnb --git-lfs
mkdir -p .repo/local_manifests
curl -o .repo/local_manifests/evolution.xml \
  https://raw.githubusercontent.com/malachite-project/android_device_xiaomi_malachite/feature/evolutionx-24.0/manifests/evolution.xml
repo sync -c -j4 --no-tags --no-clone-bundle
source build/envsetup.sh
breakfast malachite userdebug
mka -j$(nproc) --skip-soong-tests target-files-package otatools
```

- `breakfast malachite userdebug` matches tools/build_malachite.sh; the
  userdebug variant is not debuggable here (see above).
- `repo init --reference` against the existing 24.0 tree should make the
  sync cheap: evo pins LineageOS projects at exactly lineage-24.0.
- Signing: the usual inline-keys step applies; evo's vanilla build has no
  MindTheGapps dependency. Expected zip name:
  EvolutionX-17.0-<date>-lineage_malachite-12.3-Vanilla-Unofficial.zip.
- Google apps: baked evo gapps instead of vanilla = delete the
  `WITH_GMS := false` line (vendor/gms ships either way).

## What the first build will most likely surface

- RRO/overlay mismatches against evo's Settings, Telephony and Wifi module
  forks (SettingsResOverlayMalachite, TeleServiceResOverlayMalachite,
  WifiOverlay, NetworkStackResMalachite): fix by adjusting the overlay, not
  by pointing the manifest at our lineage forks.
- ParanoidSense may fail to compile against evo's frameworks; if so, that is
  the moment to decide between porting it and dropping it.
- Whatever evo changed in build/make that a LineageOS tree assumption
  depends on. Read the error; do not disable the check that found it.

## Decisions made (user may change)

- Vanilla, no baked Google apps (WITH_GMS := false).
- Stock Xiaomi fingerprint kept; evo's Pixel fingerprint spoof off
  (TARGET_ENABLE_FP_OVERRIDE := false).
- Branch name: feature/evolutionx-24.0 (project convention: -24.0 suffix for
  the Android 17 line).
