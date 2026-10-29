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
inherits from. The device configuration consists of:

- `manifests/evolution.xml` - the local manifest for their manifest
  (device, kernel-prebuilt, vendor, hardware/mediatek, hardware/xiaomi,
  sepolicy_vndr, vendor/mediatek/ims, hardware/dolby, ParanoidSense added;
  external/wpa_supplicant_8 replaced with our fork; frameworks/native uses
  our Evolution X branch described below).
- `lineage_malachite.mk` - the Evolution X options (EVO_BUILD_TYPE,
  WITH_GMS := false, TARGET_ENABLE_FP_OVERRIDE := false,
  TARGET_PROVIDES_FACE_UNLOCK_HAL := true, TARGET_BOOT_ANIMATION_RES := 1080).
  It also inherits the existing local inline-signing configuration.

`android_frameworks_native`, branch `feature/evolutionx-24.0`, starts at
Evolution X cnb `cc9996b` and replaces its GED KPI implementation with the
safe implementation from our lineage-24.0 commit `a469d75` (native fix
`2bcc679`). GED stays enabled,
but its state lives outside `Surface`, so framework callers and prebuilts
agree on the class layout. The port also retains the source fix's locked
state table, one-time probe, null-buffer checks and fence handling.
All other Evolution X native changes are retained.

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
would break Evolution X's features: three-finger screenshot,
unrounded backlight, the FPSGO BufferQueue hooks, the eSIM
settings UI, the LE Audio fixes, the brightness smoothing framework parts.
Each needs its own Evolution X branch after the first build boots. The source
ID (feature/source-id-24.0) is not merged into lineage-24.0 and is not here
either; porting it needs an evo variant of tools/source-id.sh (their
LINEAGE_VERSION has a different format).

Face unlock: ParanoidSense is built and Evolution X already registers
SenseProvider when ro.face.sense_service is true, as this device requests.
It is not known broken because of a missing provider; compatibility still
needs a build and phone test.

## Before the first build

1. Push feature/evolutionx-24.0 in both the device and frameworks/native
   forks. The authoring session never pushes. Both branches are required
   by evolution.xml; the native branch keeps Evolution X's base.
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
TOP="$PWD" bash /mnt/e/LineageOS-23.2-Malachite/tools/setup_inline_keys.sh || exit 1
source build/envsetup.sh
breakfast malachite userdebug
mka -j$(nproc) --skip-soong-tests target-files-package otatools
```

- `breakfast malachite userdebug` matches tools/build_malachite.sh; the
  userdebug variant is not debuggable here (see above).
- `repo init --reference` against the existing 24.0 tree should make the
  sync cheap: evo pins LineageOS projects at exactly lineage-24.0.
- Signing: run setup_inline_keys.sh with TOP set to the new EvoX tree, as
  above, before product configuration. It uses the existing local keys and
  reference signed target-files and writes vendor/lineage-priv/keys. The
  device product explicitly inherits that keys.mk because Evolution X's
  vendor config only looks under vendor/evolution-priv. Keep this workflow
  on the lineage-priv path; do not make a second copy under evolution-priv.
  If the script reports missing keys or a missing reference, stop and
  resolve it before compiling. No keys belong in either public branch.
- Before packaging, run
  `python3 /mnt/e/LineageOS-23.2-Malachite/tools/check_inline_signing.py REFERENCE_signed-target_files.zip EVOX_target_files.zip`
  from the source root with the build environment sourced. Replace the two
  file names with the reference used by setup_inline_keys.sh and the new
  target-files zip. Stop if the command fails; do not package that output.
  No signed EvoX output has been checked yet.
- EvoX's vanilla build has no MindTheGapps dependency. Expected zip name:
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
